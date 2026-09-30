# Data Model

Postgres via async SQLAlchemy 2.x (`Mapped[...]` typing) with Alembic migrations; SQLite for local
development and tests. All timestamps are `TIMESTAMPTZ` stored in UTC.

Portability choices, so the same models run on both engines:

| Concern | Approach |
| --- | --- |
| Enums | `sa.Enum(..., native_enum=False)` → `VARCHAR(32)` + CHECK constraint, storing member **values** |
| UUIDs | `sa.Uuid(as_uuid=True)` → native `uuid` on Postgres, `CHAR(32)` on SQLite |
| JSON | `JSON` with `with_variant(JSONB, "postgresql")` → `JSONB` in production |
| Uniqueness with NULLs | A computed `dedupe_key` / `idempotency_key` string column instead of relying on composite keys containing NULL |

Conventions: UUID primary keys, `created_at` / `updated_at` on every table.

## Enums

```
reminder_channel : email | whatsapp
agenda_status    : draft | generating | ready | active | completed | archived | cancelled
sub_status       : planned | in_progress | done | missed
todos_source     : agent | user
ledger_reason    : task_completed | task_uncompleted | day_complete | day_missed
                 | streak_bonus | agenda_complete | perfect_run | adjustment
reminder_status  : pending | claimed | sent | failed | skipped
reminder_kind    : daily | weekly_rollup
draft_status     : queued | running | needs_input | needs_review | approved | failed
```

Sheet: `app/models/enums.py`.

## users

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| email | varchar(320) UNIQUE NOT NULL, indexed | stored lower-cased; login identifier |
| password_hash | text NOT NULL | bcrypt (SHA-256 pre-hash above 72 bytes) |
| full_name | varchar(200) | |
| timezone | varchar(64) NOT NULL | IANA name, e.g. `Africa/Lagos` |
| phone_e164 | varchar(20) | required for the WhatsApp channel |
| email_verified_at | timestamptz | optional by product decision |
| last_login_at | timestamptz | |
| is_active | bool NOT NULL | |
| points_balance | int NOT NULL DEFAULT 0 | cached sum of `points_ledger` |
| current_streak | int NOT NULL DEFAULT 0 | consecutive fully-complete days |
| longest_streak | int NOT NULL DEFAULT 0 | |
| last_complete_date | date | |

## refresh_tokens

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| user_id | uuid FK → users CASCADE, indexed | |
| token_hash | varchar(64) UNIQUE | SHA-256 of the opaque refresh token; the token itself is never stored |
| expires_at | timestamptz NOT NULL | |
| revoked_at | timestamptz | set on rotation; reuse revokes every session |
| user_agent | varchar(300) | |
| ip_address | varchar(64) | |

## agendas

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| user_id | uuid FK → users CASCADE, indexed | |
| title | varchar(300) NOT NULL | the long-term agenda |
| description | text | |
| timeframe_days | int NOT NULL | CHECK `>= 1`; capped at `MAX_TIMEFRAME_DAYS` (90) in the service |
| start_date | date NOT NULL | user-local first day |
| end_date | date NOT NULL, indexed | `start_date + timeframe_days - 1`; CHECK `end_date >= start_date` |
| reminder_channel | enum NOT NULL DEFAULT email | |
| reminder_time | time NOT NULL | local wall time, e.g. `08:00` |
| timezone | varchar(64) NOT NULL | snapshot of the user's tz for this agenda |
| status | enum NOT NULL DEFAULT draft, indexed | |
| approved_at | timestamptz | |
| completed_at | timestamptz | |
| total_points | int NOT NULL DEFAULT 0 | points earned inside this agenda |
| perfect_run | bool NOT NULL DEFAULT false | no missed days |
| last_materialized_date | date | scheduler bookkeeping |
| last_closed_date | date | days up to here have been closed |

## agenda_drafts

One row per generation run. `id` **is** the LangGraph `thread_id`.

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | `thread_id` for the graph checkpointer |
| agenda_id | uuid FK → agendas CASCADE, indexed | |
| status | enum NOT NULL DEFAULT queued | |
| revision | int NOT NULL DEFAULT 1 | increments per generation |
| clarifying_questions | JSON | questions the agent asked |
| clarifying_answers | JSON | user responses |
| validation_issues | JSON | critique output (errors and warnings) |
| raw_plan | JSON | last graph output, for debugging |
| stats | JSON | `{days, todos, expanded_days}` |
| model | varchar(200) | e.g. `nvidia/nemotron-3-ultra-550b-a55b` |
| prompt_version | varchar(50) | prompt-set version that produced it |
| error | text | |
| tokens_in / tokens_out | int NOT NULL DEFAULT 0 | cost tracking |
| repair_passes | int NOT NULL DEFAULT 0 | critique→repair iterations used |

## sub_agendas

The daily milestones — exactly one per day of the timeframe.

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| agenda_id | uuid FK → agendas CASCADE, indexed | |
| draft_id | uuid FK → agenda_drafts SET NULL | provenance |
| day_index | int NOT NULL | 1..timeframe_days |
| scheduled_date | date NOT NULL, indexed | `start_date + day_index - 1` |
| title | varchar(300) NOT NULL | shown as the reminder title |
| description | text | |
| expected_outcome | text | what "done" looks like; used by the finale check |
| expected_effort_minutes | int | difficulty-ramp signal |
| phase | varchar(40) | `foundation` / `build` / `push` / `finish` |
| status | enum NOT NULL DEFAULT planned | |
| is_user_edited | bool NOT NULL DEFAULT false | regeneration never overwrites these |
| todos_expanded | bool NOT NULL DEFAULT false | has the agent produced to-dos yet |
| completion_seq | int NOT NULL DEFAULT 0 | increments each time the day becomes complete; keeps day bonuses idempotent |
| closed_at | timestamptz | set when the day is finalised |

Unique: `(agenda_id, day_index)` and `(agenda_id, scheduled_date)` — the second is what makes
"one to-do list per day" a database guarantee rather than a convention.

## todos

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| sub_agenda_id | uuid FK → sub_agendas CASCADE, indexed | |
| user_id | uuid FK → users CASCADE, indexed | denormalised for dashboard queries |
| agenda_id | uuid FK → agendas CASCADE, indexed | |
| position | int NOT NULL | user-visible order |
| title | varchar(300) NOT NULL | |
| notes | text | |
| points | int NOT NULL DEFAULT 10 | snapshot of the award at creation |
| is_done | bool NOT NULL DEFAULT false, indexed | |
| completed_at | timestamptz | |
| source | enum NOT NULL DEFAULT agent | agent-generated vs user-added |
| completion_seq | int NOT NULL DEFAULT 0 | increments per completion; builds ledger idempotency keys |

Unique: `(sub_agenda_id, position)`. Deletion is a hard delete; points already earned remain in the
ledger with `todo_id` set to NULL.

## points_ledger

Append-only and idempotent. Balance is `SUM(delta)`.

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| user_id | uuid FK → users CASCADE, indexed | |
| agenda_id | uuid FK → agendas SET NULL | |
| sub_agenda_id | uuid FK → sub_agendas SET NULL | |
| todo_id | uuid FK → todos SET NULL | |
| reason | enum NOT NULL, indexed | |
| delta | int NOT NULL | signed |
| meta | JSON | e.g. `{"streak": 14}` |
| occurred_on | date NOT NULL, indexed | user-local date, used for streaks and rollups |
| idempotency_key | varchar(200) UNIQUE NOT NULL | see below |

Key formats — the reason a retry can never double-award:

```
todo:{todo_id}:completed:{completion_seq}      task_completed    +points
todo:{todo_id}:uncompleted:{completion_seq}    task_uncompleted  -points
day:{sub_agenda_id}:complete:{completion_seq}  day_complete      +25
day:{sub_agenda_id}:uncompleted:{seq}          task_uncompleted  -25
day:{sub_agenda_id}:missed                     day_missed        -5   (once per day, ever)
streak:{user_id}:{milestone}                   streak_bonus      +100
agenda:{agenda_id}:complete                    agenda_complete   +250
agenda:{agenda_id}:perfect                     perfect_run       +500
agenda:{agenda_id}:uncompleted                 adjustment        -250
```

## reminders

Outbox and delivery log in one table.

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK | |
| user_id | uuid FK → users CASCADE, indexed | |
| agenda_id | uuid FK → agendas CASCADE, indexed | |
| sub_agenda_id | uuid FK → sub_agendas CASCADE | NULL for weekly rollups |
| kind | enum NOT NULL DEFAULT daily | |
| channel | enum NOT NULL | |
| status | enum NOT NULL DEFAULT pending, indexed | |
| scheduled_for | timestamptz NOT NULL | computed UTC fire time |
| local_date | date NOT NULL | the day the reminder is about |
| dedupe_key | varchar(200) UNIQUE NOT NULL | `{agenda}:{sub or 'none'}:{kind}:{date}` — the exactly-once guarantee |
| claimed_at | timestamptz | |
| attempted | int NOT NULL DEFAULT 0 | |
| sent_at | timestamptz | |
| provider | varchar(40) | `smtp`, `console`, `twilio-whatsapp`, `meta-whatsapp` |
| provider_message_id | varchar(200) | SMTP Message-ID / Twilio SID / Meta message id |
| error | text | |
| body_subject | varchar(300) | rendered subject, reused on retry |
| body_preview | text | rendered body, reused on retry so motivation is not re-generated |

The `dedupe_key` exists because a composite unique constraint containing `NULL`
(`sub_agenda_id` for rollups) is not unique on either Postgres or SQLite.

## agent_checkpoints

Created by `saver.setup()` for LangGraph's `AsyncPostgresSaver` (`checkpoints`,
`checkpoint_blobs`, `checkpoint_writes`). Keyed by `thread_id = agenda_drafts.id`, which is what
lets a paused human-in-the-loop run resume after a deploy.

## Derived queries

- **Today's view**: `sub_agendas` where `scheduled_date = local_today(agenda.timezone)` joined to
  its to-dos (the `todos` relationship is `lazy="selectin"`, so it is one extra query).
- **Agenda progress**: grouped counts plus `SUM(is_done)` per day in a single query.
- **Streak**: walk dates backwards from today, counting days that had work and finished it,
  skipping days with nothing scheduled.
- **Dispatch scan**: `status = 'pending' AND scheduled_for <= now() AND attempted < max`, claimed
  with `FOR UPDATE SKIP LOCKED`.

## Retention

`reminders.body_preview` and `body_subject` are the only place verbatim agenda text sits outside the
plan; `REMINDER_RETENTION_DAYS` (90) governs how long they are kept. Completed and archived agendas
keep their plan and ledger indefinitely; unapproved drafts are cancellable after
`CANCEL_UNAPPROVED_DRAFTS_AFTER_DAYS`.
