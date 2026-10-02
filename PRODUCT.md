# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Responsive web only. A native mobile app is a deliberate v1 non-goal; the existing service is a
React SPA against a REST API.

## Users

The primary user is an individual pursuing a personal long-term goal on their own: learning a skill,
training for fitness, shipping a product or side project, writing, or building a business. They
commit to a deadline and want a concrete, date-anchored plan instead of a vague intention. They
usually check in on a phone or laptop at a moment when they can act on a task, and they may run more
than one agenda at a time.

Collaboration is out of scope for v1: no teams, no shared agendas, no multi-user workspaces.

## Product Purpose

AgentDa turns a vague long-term intention into a sequenced, date-anchored plan that is guaranteed to
finish on the user's chosen deadline. It breaks the agenda into one sub-agenda per day, expands each
day into a concrete to-do list, reminds the user on their chosen channel at their chosen local time,
and rewards completion with points and streaks.

Success means the user keeps the daily rhythm through to the deadline. The product makes that
measurable through per-task points, day-completion bonuses, streaks, and agenda-completion bonuses.

## Positioning

The mechanism a neighboring habit or planning app could not truthfully copy:

- **The plan always lands on the deadline.** The agent plans against a deterministically built,
  dated skeleton and re-normalises all model output onto it, so the number of days and their dates
  can never drift; a truncated response degrades into a valid plan plus warnings.
- **Reminders go out exactly once.** A unique `dedupe_key` per (agenda, day, kind, date) plus
  `SELECT … FOR UPDATE SKIP LOCKED` claiming is shared by the in-process scheduler and the Render
  cron safety net.
- **Points can't be double-awarded.** The points ledger is append-only and every row carries a
  deterministic idempotency key; un-completing writes compensating negative rows instead of deleting.
- **It runs with zero credentials.** With no LLM key the agent uses a deterministic offline planner;
  with no SMTP or WhatsApp credentials reminders are logged to the console. The whole product is
  exercisable locally.
- **Long agendas stay affordable.** To-dos are expanded for the first 3 days at approval, then
  lazily the day before, with the previous day's actual completion fed back into the prompt.

## Operating Context

- Each agenda stores an IANA timezone plus a local `reminder_time` (wall time); the UTC fire time is
  recomputed per day, so daylight-saving changes do not shift reminders.
- The daily reminder is titled `Day N of M — "<sub-agenda>"`, carries a short motivational line and
  that day's to-dos, and is delivered over email (SMTP) or WhatsApp (Twilio preferred, Meta Cloud
  API fallback, console when neither is configured).
- A weekly rollup is sent each Sunday in the user's local time, summarising points earned,
  completion rate and the current streak.
- The flow is human-in-the-loop: create the agenda → generate → optionally answer clarifying
  questions → review the generated plan → edit days and to-dos → approve → the agenda goes active
  and reminders are scheduled.
- Day close (runs every 30 min, plus an hourly cron) marks each fully elapsed day `done` or
  `missed`, applies the missed-day penalty once, and recomputes streaks.
- Deployment is a Render blueprint: a FastAPI web service, managed Postgres, a `*/5 * * * *` dispatch
  cron, an hourly day-close cron, and (once built) a static site for the React app.

## Capabilities and Constraints

Confirmed functionality and rules:

- An agenda carries a title, optional description, `timeframe_days`, `start_date`, `reminder_channel`
  (`email` | `whatsapp`), `reminder_time`, and a timezone.
- Timeframe is bounded to **1–90 days** (`MAX_TIMEFRAME_DAYS`).
- Multiple concurrent active agendas per user are allowed (no cap).
- Email verification is **optional** and never gates reminders.
- A missed day costs **5 points** and resets the streak; already-earned task points are never removed.
- Overdue to-dos stay on their original day and are marked missed — they are **not** carried forward.
- Editing a day flags it `is_user_edited`; user-edited days are never overwritten by regeneration.
- Points, streak and bonus rules live in env-overridable config (task +10, day complete +25, streak
  milestone +100, agenda complete +250, perfect run +500, missed day −5 by default).
- Explicit v1 non-goals: native mobile app, multi-user collaboration, push notifications, calendar
  sync, voice, and payment tiers.

Frontend (milestone M7) is **not built yet**. Its stack is already fixed by the project: React + Vite
+ Tailwind CSS in `apps/web`, a static Render site, talking to the frozen REST contract in
`docs/api-contract.md`. No SSE endpoint exists, so plan generation is polled via
`GET /agendas/{id}/draft`. The planned surface is auth screens, the agenda wizard (create → review
the generated plan → edit → approve), the today dashboard, and progress views.

Frontend product behaviour decided during this init:

- **First run:** a guided first-agenda wizard, not a bare create form.
- **Dashboard:** tabs showing one agenda at a time, not a stacked list of all agendas.
- **Editing a day:** changing a day's title or description leaves that day's to-dos as they are; the
  app does not regenerate them automatically.

Undecided product facts (do not invent): the public launch/pricing model, and any specific habit or
vertical the product may later target beyond general personal goals.

## Brand Commitments

- The public product name is **AgentDa**. The internal working name "Agent DA" appears throughout the
  repository, paths, and sender defaults; the public name is AgentDa.
- The reminder copy currently uses a warm, encouraging, plain-spoken voice (see
  `docs/architecture.md` §7, e.g. "Good morning Ada — you're 12% through this agenda and on a 4-day
  streak."). No formal voice guide, logo, palette, or typography commitment exists yet.

## Evidence on Hand

- A working backend in `apps/api` with 36 passing tests; the full product runs with zero credentials
  via `python -m app.cli demo`.
- Design and specification documents: `docs/architecture.md`, `docs/data-model.md`,
  `docs/langgraph-agent.md`, `docs/api-contract.md`, `docs/running.md`.
- A frozen OpenAPI surface of 38 routes, served at `/docs`.
- Absences future work must not fabricate: there are **no** real users, testimonials, customer
  logos, press, case studies, benchmarks, screenshots, marketing copy, or brand asset files
  (no logo, no icons, no imagery). The sender default is `Agent DA <no-reply@example.com>`.

## Product Principles

1. **The deadline is a promise.** The plan must reach the goal on the final day of the timeframe,
   not near it.
2. **The model proposes, deterministic code disposes.** Correctness is enforced in code, never left
   to prompt compliance.
3. **One reminder, once, on time, on the user's channel.** Delivery is idempotent and retry-safe.
4. **The user is in the loop and their edits are sacred.** Plans are shown, edited and approved
   before they run, and user edits are never silently overwritten.
5. **It runs with zero credentials.** Every integration degrades to something that works.
6. **Progress must be visible and rewardable.** Points, day completion and streaks make effort
   legible.
