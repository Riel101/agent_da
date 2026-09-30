# API Contract

Base path `/api/v1`. JSON in, JSON out. Auth via `Authorization: Bearer <access_token>` unless the
row is marked *public*.

Error shape (all failures):

```json
{
  "error": { "code": "AGENDA_NOT_FOUND", "message": "Agenda does not exist", "details": {} }
}
```

Status codes: `400` validation, `401` unauthenticated, `403` forbidden, `404` missing,
`409` conflict (e.g. reminders already approved), `422` schema, `429` rate limited, `500` internal.

## Auth

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/signup` | *public* → user + token pair; `409 EMAIL_TAKEN` on duplicates |
| POST | `/auth/login` | *public* → token pair; `401 BAD_CREDENTIALS` |
| POST | `/auth/refresh` | *public*, rotates the refresh token; reuse revokes every session (`TOKEN_REUSED`) |
| POST | `/auth/logout` | revokes the presented refresh token |
| POST | `/auth/logout-all` | auth required; revokes every session |
| GET | `/auth/sessions` | auth required; recent sessions with device/IP/expiry |
| POST | `/auth/verify-email` | consumes a signed token (optional flow) |
| POST | `/auth/verify-email/request` | emails a verification link |
| POST | `/auth/forgot-password` | *public*, always `200` so it cannot enumerate accounts |
| POST | `/auth/reset-password` | consumes a signed token, revokes all sessions |

`signup`:

```json
{ "email": "ada@example.com", "password": "••••••••", "full_name": "Ada", "timezone": "Africa/Lagos" }
→ 201 {
  "user": { "id": "…", "email": "ada@example.com", "full_name": "Ada",
            "timezone": "Africa/Lagos", "points_balance": 0, "current_streak": 0,
            "longest_streak": 0, "phone_e164": null, "email_verified_at": null },
  "access_token": "…", "refresh_token": "…", "token_type": "bearer", "expires_in": 3600
}
```

Implemented: `apps/api/app/api/routers/auth.py` · verified by `tests/test_auth.py`.

## Users

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/users/me` | profile + totals |
| PATCH | `/users/me` | `full_name`, `timezone`, `phone_e164` |
| GET | `/users/me/points` | paginated ledger, `?from=&to=&agenda_id=&page=&limit=` |
| GET | `/users/me/points/summary` | balance, earned, lost, and a per-reason breakdown |
| GET | `/users/me/streak` | `current`, `longest`, `last_complete_date`, 30-day day map |


## Agendas

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/agendas` | `?status=&page=&limit=` |
| POST | `/agendas` | create draft |
| GET | `/agendas/{id}` | agenda + summary counts |
| PATCH | `/agendas/{id}` | editable while `draft`/`ready` (title, description, timeframe, reminder settings) |
| DELETE | `/agendas/{id}` | soft delete → `cancelled` |
| POST | `/agendas/{id}/generate` | create a draft and start the graph → `202 { draft_id }`; reuses an in-flight draft |
| GET | `/agendas/{id}/draft` | poll run/review state, clarifying questions and the full plan |
| POST | `/agendas/{id}/draft/answers` | resume a clarifying interrupt → `202` |
| POST | `/agendas/{id}/approve` | activate + schedule reminders |
| POST | `/agendas/{id}/regenerate` | `{ "scope": "all" \| "day", "day_index": 4, "instructions": "…" }` |
| GET | `/agendas/{id}/days` | sub-agendas with per-day completion |
| GET | `/agendas/{id}/days/{day_index}` | one day: sub-agenda + to-dos |
| PATCH | `/agendas/{id}/days/{day_index}` | edit title/description/outcome/effort (flags the day `is_user_edited`) |
| GET | `/agendas/{id}/progress` | completion %, points, streak, missed days, per-day breakdown |
| POST | `/agendas/{id}/archive` | archive a running or finished agenda |
| DELETE | `/agendas/{id}` | soft delete → `cancelled` |

Notes that matter for the client:

- Changing `timeframe_days` or `start_date` on a `PATCH` discards the existing plan (the days no
  longer line up) and returns the agenda to `draft`; everything else is edited in place.
- `approve` returns `400 PLAN_INCOMPLETE` unless the stored plan has exactly `timeframe_days` days,
  and `409 ALREADY_ACTIVE` if it is already running.
- `generate` never burns a second generation while a draft is `queued`, `running`, `needs_input` or
  `needs_review` — it returns that draft instead.


Create:

```json
{
  "title": "Launch my SaaS to 100 paying users",
  "description": "Ship the product, get first 100 customers on the Pro plan.",
  "timeframe_days": 30,
  "start_date": "2026-10-01",
  "reminder_channel": "email",
  "reminder_time": "08:00",
  "timezone": "Africa/Lagos",
  "phone_e164": null
}
→ 201 {
  "id": "…", "status": "draft",
  "start_date": "2026-10-01", "end_date": "2026-10-30",
  "reminder_channel": "email", "reminder_time": "08:00", "timezone": "Africa/Lagos",
  "timeframe_days": 30, "total_points": 0, "perfect_run": false, "approved_at": null
}
```

Draft poll:

```json
{
  "draft_id": "…", "agenda_id": "…", "status": "needs_review", "revision": 1,
  "clarifying_questions": [],
  "validation_issues": [{ "severity": "warning", "code": "NO_SLACK", "day_index": 27,
                          "message": "No buffer day before the finale." }],
  "model": "nvidia/nemotron-3-ultra-550b-a55b", "prompt_version": "…", "repair_passes": 1,
  "error": null,
  "sub_agendas": [
    { "day_index": 1, "scheduled_date": "2026-10-01", "title": "Define the wedge",
      "description": "Pick one painful problem and write the one-liner.",
      "expected_outcome": "A validated one-liner sentence.",
      "expected_effort_minutes": 45, "phase": "foundation",
      "todos": [ { "title": "Shortlist 10 problems", "notes": null, "points": 10 } ] }
  ],
  "stats": { "days": 30, "todos": 12, "expanded_days": 3 }
}
```

`status` is one of `queued`, `running`, `needs_input`, `needs_review`, `approved`, `failed`. When it
is `needs_input`, read `clarifying_questions` and answer them. Poll this endpoint until the status
settles.

## To-dos

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/sub-agendas/{id}/todos` | add a user to-do → `source: user`, appended at the end |
| PATCH | `/todos/{id}` | edit title/notes/position (position re-orders the day) |
| DELETE | `/todos/{id}` | hard delete; points already earned are kept in the ledger |
| POST | `/todos/{id}/complete` | awards points, returns new balance + bonus flags |
| POST | `/todos/{id}/uncomplete` | compensating ledger rows |
| POST | `/sub-agendas/{id}/todos/reorder` | `{ "order": ["todo_id", …] }` — must list every to-do on the day |

Complete response:

```json
{
  "todo": { "id": "…", "is_done": true, "completed_at": "2026-10-04T07:12:00Z",
            "sub_agenda_id": "…", "position": 0, "title": "Draft headline copy",
            "notes": null, "points": 10, "source": "agent" },
  "points": { "awarded": 10, "reason": "task_completed", "balance": 340,
              "bonuses": ["task_completed", "day_complete"] },
  "day": { "complete": true, "done": 4, "total": 4, "bonus_awarded": 25 },
  "streak": { "current": 4, "longest": 9 },
  "agenda_completed": false
}
```

Both endpoints are idempotent: a second `complete` returns `"awarded": 0` with
`bonuses: ["already_complete"]` and an unchanged balance, and `uncomplete` on an open to-do returns
`["already_open"]`. `bonuses` may also contain `streak_milestone`, `agenda_complete`, `perfect_run`,
`day_reopened` and `agenda_reopened`.

## Dashboard

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard` | today's sub-agenda + to-dos, points, streak, active agendas |
| GET | `/dashboard/calendar` | `?month=2026-10` day-by-day completion map |

`/dashboard` (single round-trip for the home screen):

```json
{
  "local_date": "2026-10-04",
  "totals": { "points_balance": 340, "current_streak": 4, "longest_streak": 9 },
  "today": [
    { "agenda_id": "…", "agenda_title": "Launch my SaaS",
      "day_index": 4, "title": "Build the waitlist page",
      "todos": [ { "id": "…", "title": "Draft headline copy", "is_done": true } ],
      "progress": { "done": 1, "total": 4 } }
  ],
  "agendas": [ { "id": "…", "title": "Launch my SaaS", "progress_pct": 11, "status": "active" } ]
}
```

## Internal (require `X-Internal-Token`)

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/internal/dispatch` | send reminders that are due; `?limit=` caps the batch |
| POST | `/internal/materialize` | expand upcoming to-dos for running agendas |
| POST | `/internal/day-close` | close elapsed days, apply penalties, refresh streaks |
| POST | `/internal/weekly-rollups` | schedule Sunday rollups for active agendas |

A wrong or missing token returns `403 BAD_INTERNAL_TOKEN`. The same jobs are available as CLI
commands (`python -m app.cli dispatch|materialize|day-close`), which is what `render.yaml` schedules
so the cron path shares one code path with the scheduler.

## Health

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/healthz` | *public*, dependency-free liveness for Render |
| GET | `/readyz` | *public*, database check, scheduler jobs and next run times, channel configuration, pending reminder count |

`/readyz` is the fastest way to confirm a deployment is wired correctly:

```json
{
  "status": "ok", "database": "ok",
  "scheduler": { "running": true, "enabled": true, "started_at": "…",
                 "jobs": [ { "id": "dispatch_reminders", "next_run": "…" } ] },
  "pending_reminders": 3,
  "channels": {
    "email": { "sender": "smtp", "configured": false },
    "whatsapp": { "sender": "console", "provider_setting": "auto",
                  "twilio_configured": false, "meta_configured": false }
  }
}
```

## Not built yet

`GET /agendas/{id}/generate/stream` (Server-Sent Events for per-node progress) was in the design but
is not implemented. Clients should poll `GET /agendas/{id}/draft`; the wizard can show a generic
"planning…" state meanwhile.

## Rate limits

| Path | Limit |
| --- | --- |
| `/auth/signup`, `/auth/login` | 10 / min / IP |
| `/auth/refresh` | 60 / min / IP |
| `/auth/forgot-password` | 10 / hour / IP |
| `/agendas/*/generate`, `/agendas/*/regenerate` | 5 / hour / user |

Limits are per-process (Render runs one web instance). Swap `app/core/ratelimit.py` for a
Redis-backed limiter if the service is scaled out; the call sites do not change.

## Pagination

`?page=1&limit=20`, response includes `{"items": [...], "page": 1, "limit": 20, "total": 137}`.
