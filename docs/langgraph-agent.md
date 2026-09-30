# LangGraph Agent Design

The agent converts a long-term agenda into a date-anchored sequence of daily sub-agendas, then into
concrete to-dos, with two human-in-the-loop pauses: one for clarifying questions, one for review.

- Graph: `StateGraph(AgendaState)` — `app/agents/graph.py`
- Nodes: `app/agents/nodes.py`
- Checkpointer: `AsyncPostgresSaver` in production, `InMemorySaver` locally — `app/agents/checkpointer.py`
- Runner: `app/agents/runner.py`, keyed by `thread_id = agenda_drafts.id`
- LLM: `ChatNVIDIA(model="nvidia/nemotron-3-ultra-550b-a55b")` via NVIDIA NIM, always with
  `with_structured_output(schema, include_raw=True)`
- Prompts: versioned modules in `app/agents/prompts/`, recorded on the draft as `prompt_version`

## 1. The central design rule

**The model proposes, deterministic code disposes.**

Everything that must be true — exactly one day per date, dates in order, every day populated — is
enforced by code, not by prompt compliance:

1. `build_skeleton` produces the exact list of `(day_index, scheduled_date, phase)` slots, with no
   LLM involved.
2. `plan` is asked to fill *those* slots.
3. `_normalise_plan` then forces the result onto the skeleton: it re-keys by `day_index`, keeps the
   skeleton's dates verbatim, substitutes a fallback day for anything missing or empty, and clamps
   effort into a sane range.
4. `critique` re-checks the invariants deterministically and only *adds* to the issue list with the
   LLM reviewer.

So a truncated, reordered or partially-hallucinated response degrades into a valid plan plus
warnings — it can never produce 27 days when the user asked for 30.

## 2. State

`app/agents/state.py` — all JSON-serialisable so a paused run survives in the checkpointer.

```python
class AgendaState(TypedDict, total=False):
    user_id, agenda_id, draft_id : str
    title, description           : str
    timeframe_days               : int
    start_date, end_date         : str          # ISO dates
    timezone, full_name          : str
    streak                       : int
    agenda_type                  : str          # learning|fitness|shipping|writing|business|other

    clarifying_questions : list[str]
    clarifying_answers   : dict[str, str]

    skeleton    : list[DaySlot]      # deterministic, dated
    sub_agendas : list[dict]         # the plan, one entry per skeleton slot
    todos       : list[dict]         # flat: {day_index, position, title, notes}

    issues                    : list[dict]
    repair_passes             : int
    reaches_goal_on_final_day : bool

    phase, user_decision, target_day, instructions : ...
    regenerated_days : list[int]
    error           : str | None
    approved        : bool

    tokens_in, tokens_out : int
    model, prompt_version : str
```

`todos` is a **flat list** rather than a per-day map. That keeps merges trivial and makes
`expand_todos` idempotent: it rebuilds only the days that need expansion and carries the rest
through untouched.

## 3. Graph

```
START ─▶ intake_validate ─┬─▶ ask_clarifications ─▶ build_skeleton ─▶ plan ─▶ critique
                          │                                                  │
                          │                                    ┌─────────────┴─────────────┐
                          │                                    ▼                           ▼
                          │                                  repair ──▶ critique        expand_todos
                          │                                                                │
                          │                                                                ▼
                          │                                                          persist_draft
                          │                                                                │
                          │                                                                ▼
                          │                                                           await_review
                          │                                                                 │
                          │                        ┌────────────────────────────────────────┤
                          │                        ▼                     ▼                  ▼
                          │                       plan              apply_edits        finalize ─▶ END
                          │                    (regen all)              │
                          │                                           ▼
                          └────────────(failed)──▶ END            critique ◀──┘
```

Conditional routing (`app/agents/graph.py`):

| After | Route |
| --- | --- |
| `intake_validate` | `clarify` if questions were raised and unanswered · `failed` if the timeframe is out of range · else `plan` (which runs `build_skeleton`) |
| `critique` | `repair` if any `severity == "error"` issue remains and `repair_passes < MAX_REPAIR_PASSES` · else `expand_todos` |
| `await_review` | `plan` for `regenerate_all` · `apply_edits` for `regenerate_day` / `edit` · `finalize` for `approve` |

## 4. Nodes

### `intake_validate`

- Hard check: `MIN_TIMEFRAME_DAYS <= timeframe_days <= MAX_TIMEFRAME_DAYS` (1..90). Outside that,
  the run ends with `phase = "failed"` and a user-facing message.
- If the user has already answered clarifications, it short-circuits and never asks twice.
- Otherwise one cheap LLM call classifies specificity and agenda type. A vague goal yields at most
  three questions; if the model returns none for a vague goal, two generic defaults are used so the
  branch can never silently no-op.

### `ask_clarifications`

`interrupt({"kind": "clarifications", "questions": [...]})`. The API surfaces the questions on the
draft; `POST /agendas/{id}/draft/answers` resumes with `{"answers": {...}}` and control returns to
`build_skeleton`.

### `build_skeleton`

No LLM. Produces exactly `timeframe_days` slots, each with the correct date and a phase
(`foundation` ≤15%, `build` ≤50%, `push` ≤85%, `finish` after that).

### `plan`

The main generation node. Prompt constraints (`prompts/plan_v1.py`):

1. Return exactly one sub-agenda per supplied date; use the supplied `day_index` values.
2. Day 1 must be small, immediately actionable, and produce something visible.
3. Difficulty and scope build progressively; each day builds on the previous day's outcome.
4. **The last supplied date is the last day of the timeframe and must be the day the agenda is
   achieved** — its outcome restates the success condition. Not another preparation step.
5. Front-load the work; leave slack before the deadline.
6. Outcomes must be verifiable (an artefact, a number, a decision).
7. Realistic effort: 30–180 minutes.

Long timeframes are chunked: above `PLAN_CHUNK_THRESHOLD_DAYS` (21) the plan is generated in
`PLAN_CHUNK_DAYS` (7) windows, each receiving the previous window's outcomes so it continues rather
than restarts, and intermediate windows are told not to finish the goal yet.

### `critique`

Deterministic checks (always errors or structural warnings):

- the count equals `timeframe_days`
- `day_index` is 1..N in order with no duplicates
- `scheduled_date[i] == start_date + i - 1`
- repeated titles (`DUPLICATE_TITLE`, warning)
- any day over 300 minutes (`OVERLOADED_DAY`, warning)
- the finale does not restate the agenda's success condition (`WEAK_FINALE`, warning)

Then one LLM reviewer call against a rubric — goal reached, dependency ordering, pacing, slack,
first-day feasibility, vagueness — returning at most six issues with a concrete `fix`. If it reports
the goal is unreachable, a `GOAL_NOT_REACHED` error is appended so `repair` runs.

### `repair`

Runs only when an error remains and `repair_passes < 2`. It re-plans in windows, passing the exact
issue list and instructing the model to fix those and keep what already works. Crucially it clears
`issues` on exit so the following `critique` is a fresh judgement rather than a loop on stale
findings. If errors survive two passes, warnings are stored on `validation_issues` and the plan
proceeds — the user can always edit by hand.

### `expand_todos`

Expands only days `<= PREEXPAND_DAYS` (3) or explicitly regenerated. Each expanded day becomes 3–6
to-dos, normalised by `_normalise_todos`: trimmed, deduplicated case-insensitively, and topped up
from a fallback list if the model under-delivers. Later days are expanded lazily by the
materialiser the day before, with the previous day's actual completion passed in as context.

### `persist_draft`

Normalises ordering only. The database writes happen in `plan_service.persist_review`, which upserts
days by `day_index`, keeps user-edited days intact, and swaps agent to-dos while preserving any
user-added ones.

### `await_review`

`interrupt({...})` with the draft summary. The client polls `GET /agendas/{id}/draft` and sends a
decision back through `POST /approve` or `/regenerate`.

### `apply_edits`

- `regenerate_day`: one focused LLM call for that day, reusing its date and phase, emitted as
  `DayRegenerationOutput` (day + to-dos in one shot). Every other day is passed through byte-for-byte
  and asserted untouched in the tests.
- Then it routes back through `critique` so a regenerated day is still validated.

### `finalize`

Sets `phase = "done"` and `approved = True`. Everything that touches the database — status change,
reminder rows, preview expansion — happens in `plan_service.approve_agenda`, so the graph stays free
of I/O beyond the model calls.

## 5. Running without an LLM

`llm.py` exposes a `FakeLLM` used whenever `NVIDIA_API_KEY` is empty. `agents/fake.py` produces a
deterministic but structurally correct response for every schema: a real dated plan that builds
progress and delivers on the final day, sensible to-dos, and a motivation line.

This is why CI and local development can exercise the entire product — dashboard, reminders, points,
streaks — with no credentials and no network.

## 6. Failure handling

| Failure | Behaviour |
| --- | --- |
| Provider 5xx or timeout | Retried `LLM_MAX_RETRIES` times with exponential backoff inside `structured_call` |
| Unparsable structured output | Re-prompted once with the parse error and an instruction to return bare JSON, then retried |
| Repeated failure | `AgentError` → the draft is marked `failed` with the reason, the agenda returns to `draft`, and the user can retry |
| Timeframe out of range | `phase = "failed"` with a clear message; no model call is made |
| Graph crash mid-run | The checkpointer resumes from the last completed node on the next invoke |
| Motivation line fails | Swallowed and logged — the reminder is sent without it |
| One day failing to expand | Logged and the materialiser moves on rather than aborting the batch |

## 7. Prompt versioning

Prompts live in `app/agents/prompts/<name>_v1.py`, each exporting `VERSION`. `prompts/__init__.py`
joins them into `PROMPT_SET_VERSION`, which is written to `agenda_drafts.prompt_version` on every
run — so a stored plan can always be traced back to the prompts that produced it.

## 8. Verified invariants (`tests/test_agent_graph.py`)

1. A plan of 1, 3, 30 and 45 days has exactly that many days, dated consecutively from `start_date`,
   with the final day's outcome restating the agenda.
2. A 60-day plan is chunked and still yields all 60 ordered days.
3. Only the first 3 days are pre-expanded, each with 3–6 to-dos; a 2-day agenda expands all of it.
4. A vague goal interrupts with 1–3 questions and produces no plan until answered.
5. Answering resumes the run into a full plan.
6. A 400-day timeframe fails cleanly with no plan.
7. Regenerating one day preserves every other day exactly and keeps all dates.
8. Approval ends the graph with `approved = True`.
