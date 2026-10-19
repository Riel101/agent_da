# agent_da

An agent that helps you achieve long-term goals by setting daily tasks to complete.

You describe an agenda and a timeframe. The agent writes a progressive day-by-day plan that lands on
your deadline, turns each day into a concrete to-do list, reminds you on your chosen channel at your
chosen time, and rewards completion with points and streaks.

## Status

**Core product complete** — 43 tests passing. The React app covers the first-agenda wizard
(sign in → capture → plan → review → approve), the plan index, and the Today surface where each
day's to-dos are checked off; wider progress views are still to come.

| Milestone | State |
| --- | --- |
| M1 Skeleton: FastAPI + Postgres + Alembic + auth + Render blueprint | ✅ |
| M2 Plan generation: LangGraph intake → clarify → plan → critique → repair → review | ✅ |
| M3 Daily execution: materialisation, to-do CRUD, completion, points, dashboard | ✅ |
| M4 Delivery: SMTP / Twilio / Meta / console channels, dispatcher, scheduler + cron | ✅ |
| M5 Gamification: streaks, missed-day penalties, bonuses, weekly rollup | ✅ |
| M6 Hardening: tests, rate limits, logging, health checks, migrations | ✅ |
| M7 Frontend: React + Vite + Tailwind | ✅ wizard, plan index, today dashboard |

## Quickstart (no credentials needed)

With no `NVIDIA_API_KEY`, the agent uses a deterministic offline planner; with no SMTP or Twilio
credentials, reminders are logged to the console and recorded as `skipped` — never as `sent` — so
the reminder log never claims a delivery that did not happen. The whole product is exercisable
locally; `python -m app.cli send-test` proves real delivery in one command.

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# watch the entire product work, goal to points
.venv/bin/python -m app.cli demo

# or run the API
.venv/bin/uvicorn app.main:app --reload   # -> http://127.0.0.1:8000/docs
```

Full instructions, tests and deployment: [`docs/running.md`](docs/running.md).

## Design documents

| Document | Contents |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | Decisions, system diagram, runtime flows, points and streak rules, Render deployment, risks |
| [`docs/data-model.md`](docs/data-model.md) | Postgres schema, including the ledger idempotency keys that make rewards retry-safe |
| [`docs/langgraph-agent.md`](docs/langgraph-agent.md) | Agent state, graph, node-by-node behaviour, prompt constraints, failure handling |
| [`docs/api-contract.md`](docs/api-contract.md) | All 38 routes with request/response examples |
| [`docs/running.md`](docs/running.md) | Install, configure, run, test, deploy |

## Stack

- **Agent & backend:** LangGraph + FastAPI (Python)
- **LLM:** `nvidia/nemotron-3-ultra-550b-a55b` via NVIDIA NIM, structured output
- **Database:** Render Postgres (async SQLAlchemy + Alembic); SQLite locally
- **Frontend:** React + Vite + Tailwind CSS (wizard, plan index, today dashboard)
- **Reminders:** APScheduler dispatcher in-process, Render Cron as a safety net
- **Channels:** SMTP email, Twilio WhatsApp, Meta WhatsApp Cloud API, console fallback
- **Hosting:** Render (`render.yaml`)

## How the hard parts are handled

- **The plan always lands on the deadline.** The agent works against a deterministically built,
  dated skeleton. Model output is re-normalised onto it, so the number of days and their dates can
  never drift — a truncated response degrades into a valid plan plus warnings, not a broken one.
- **Reminders go out exactly once.** A unique `dedupe_key` per (agenda, day, kind, date) plus
  `SELECT … FOR UPDATE SKIP LOCKED` claiming, shared by the in-process scheduler and the Render cron.
- **Points can't be double-awarded.** The ledger is append-only and every row has a deterministic
  idempotency key; un-completing writes compensating negative rows instead of deleting.
- **Long agendas stay affordable.** To-dos are expanded for the first 3 days at approval, then lazily
  the day before, with the previous day's actual completion fed back into the prompt.
- **It runs with zero credentials.** Every integration degrades: offline planner, console channel.

## The app

Run the whole product locally with `npm run dev:all` from `apps/web`: sign in, capture an intention
and a deadline, watch the agent plan, answer its questions, review the drafted days, approve, and then
work each day from the **Today** surface — check to-dos off and watch the progress bar, points and
streak move. `npm run e2e:all` drives every surface headless — see
[`docs/running.md`](docs/running.md).

What remains is the wider progress views (calendar, streaks over time). The API contract they need is
already frozen in [`docs/api-contract.md`](docs/api-contract.md).
