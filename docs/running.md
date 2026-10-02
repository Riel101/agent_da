# Running the backend

Everything below works with **no external accounts**. With no `NVIDIA_API_KEY`, the agent uses a
deterministic offline planner; with no SMTP or Twilio credentials, reminders are logged to the
console instead of sent. That means the whole product is exercisable locally and in CI.

## Requirements

- Python 3.11+ (3.12 tested)
- No database server needed locally — SQLite is the default

## Install

```bash
cd apps/api
python3 -m venv .venv            # or reuse a repo-root venv
.venv/bin/pip install -r requirements.txt
```

## Configure

```bash
cp ../../.env.example ../../.env
```

Every value has a default, so an empty file is fine. To use the real model, set:

```
NVIDIA_API_KEY=nvapi-...
```

To send real email, set the `SMTP_*` values. To send WhatsApp, set the `TWILIO_*` values and
`WHATSAPP_PROVIDER=twilio` (or leave it `auto` to prefer Twilio, fall back to Meta, then console).

## Database

Local development creates tables automatically on startup. For a normal migration flow:

```bash
cd apps/api
alembic upgrade head
```

A Render-style URL (`postgres://…`) is normalised to the async driver automatically. Migrations run
synchronously (psycopg) while the app runs on asyncpg.

## Run the API

```bash
cd apps/api
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/docs
```

Useful endpoints:

| Endpoint | What it shows |
| --- | --- |
| `GET /healthz` | Liveness, no dependencies touched |
| `GET /readyz` | Database, scheduler jobs and next run times, channel configuration, pending reminders |
| `GET /docs` | Interactive OpenAPI docs for all 38 routes |

## Run the web app

```bash
cd apps/web
npm install
npm run dev:all
```

`dev:all` starts the API (`:8000`) and Vite (`:5173`) together — Ctrl-C stops both. It runs the API
from `apps/api/.pylibs` unless a virtualenv with the dependencies is present. Override with
`API_PORT`, `WEB_PORT`, `DATABASE_URL`, `AGENT_AUTOSTART`, `SCHEDULER_ENABLED`, or `DEV_PYTHON`.
Then open http://localhost:5173 and sign in.

To run the two servers by hand instead:

```bash
# terminal 1 — API
cd apps/api
PYTHONPATH=.pylibs SCHEDULER_ENABLED=false \
  DATABASE_URL="sqlite+aiosqlite:///$(pwd)/agent_da.db" \
  python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2 — web
cd apps/web && npm run dev
```

## Smoke-testing the web app

```bash
cd apps/web
npm run e2e:all
```

Headless Chrome drives the first-agenda flow through every state, writes the screenshots to
`.impeccable/review/`, and exits non-zero if a state does not render. It boots a throwaway API on its
own SQLite file and starts Vite when one is not already running. See `apps/web/e2e/README.md` for the
phases, environment variables, and the URL-detector step.

## See the whole product work

```bash
cd apps/api
python -m app.cli demo
```

The demo creates a user and a 30-day agenda, runs the agent, prints the plan and its final day,
approves it, dispatches the first reminder (to the console here), completes today's to-dos, shows
the points breakdown, then simulates three elapsed days so you can watch the missed-day penalty and
the streak reset happen.

## Operational commands

The same jobs the in-process scheduler runs, available for cron or manual use:

```bash
python -m app.cli dispatch      # send reminders that are due
python -m app.cli materialize   # expand upcoming to-dos
python -m app.cli day-close     # close elapsed days, apply penalties, refresh streaks
```

## Tests

```bash
cd apps/api
python -m pytest -q
```

36 tests covering auth and token rotation, graph invariants (dating, day count, the finale, chunked
long plans, clarifying questions, per-day regeneration, approval), the full HTTP lifecycle from
signup to agenda completion and the perfect-run bonus, reminder idempotency, and missed-day
penalties.

The suite configures its environment before importing the app (see `tests/conftest.py`) and uses a
file-backed SQLite database under `/tmp/opencode/`.

The frontend has no unit suite; it is covered by the browser smoke harness above (`npm run e2e:all`).

## Environment notes

- **Scheduler.** `SCHEDULER_ENABLED=true` starts three APScheduler jobs in the web process. Run the
  web service as a single instance, or set it to `false` on all but one.
- **Agent autostart.** `AGENT_AUTOSTART=false` makes `/generate` create the draft without running
  the graph, so generation can be driven by a separate worker (or a test).
- **Checkpointer.** `CHECKPOINTER_BACKEND=postgres` persists paused graph runs across deploys.
  Anything else uses the in-memory saver, which loses paused runs on restart.
- **Timezones.** Each agenda stores an IANA timezone plus a local `reminder_time`; the UTC fire time
  is recomputed per day, so daylight-saving changes do not shift reminders.
- **Timeframe cap.** `MAX_TIMEFRAME_DAYS=90`.

## Deploying to Render

`render.yaml` at the repo root defines the database, the web service, and two cron jobs. After
`git push`, use **Dashboard → Blueprints → New Blueprint Instance**. Variables marked `sync: false`
(`NVIDIA_API_KEY`, `SMTP_*`, `TWILIO_*`, `PUBLIC_BASE_URL`, `CORS_ORIGINS`) are filled in from the
dashboard; `JWT_SECRET` and `INTERNAL_TOKEN` are generated.
