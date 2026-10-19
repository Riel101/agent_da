---
version: 1
slug: "plans"
primary_target: "plans"
related_targets: []
---

# Surface brief — plan index (`plans`)

**Scope:** the index of every plan the account has created, newest first, filterable by status and
paged with *Load more*. Mode: **Operate**.
**Audience & job:** one person who is already running one plan, or who finished one and wants the
next. They arrive to check where they are, to reopen a half-finished draft, or to prove to
themselves that something is still going. They must see each plan's status and progress at a glance
and be one click from the wizard that owns it.
**Constraints:** frozen REST contract (`docs/api-contract.md`) — this surface only consumes
`GET /agendas?status=&page=&limit=` and `DELETE /agendas/{id}`; the list envelope is
`{items, page, limit, total}`. JWT bearer, React + Vite + Tailwind in `apps/web`, mobile-first. The
wizard at `/new?agenda=<id>` stays the only place a plan is read or edited. Binding: no points or
streaks shown as a scoreboard — progress is to-do counts only; the index must not become a
dashboard.
**Open decisions:** the today dashboard and the progress views remain unbuilt and out of scope; the
index does not pre-empt them.
**Anti-goals:** stat tiles, heatmaps, streak counters, sparklines, or any fabricated chart; a card
grid; per-plan colour coding; a second accent; an archive action invented ahead of the contract's UI.

## Direction contract

THESIS: The plans you have made are a list, not a trophy case. The surface refuses the
productivity-app scoreboard and does what an index does — newest first, one row per plan, the status
and the arithmetic stated plainly.

OWN-WORLD: The same dark application as the wizard. Slate ground `#0E1A24` is the canvas; the list
rests on one `#16232E` panel with `#24343F` hairlines between rows. Sheet `#F2F4F0` is the title and
the value; steel-ghost `#9FB2BD` is everything descriptive. Hi-vis `#FF5A1F` is rationed to the
primary *New plan*, the focus ring, and the progress fill; danger `#FF6B52` appears only for missed
days. Archivo at normal width, sentence case, tabular figures for every date and count.

STORY: The visitor scans the list, recognises the plan they meant, reads its status and how far
along it is, and opens it — or starts a new one. They understand: this is everything I have committed
to, and nothing is hiding from me.

FIRST VIEWPORT: A slim top bar (`AgentDa`, *Plans*, *New plan*, the signed-in address, Sign out) over
a `720px` column. The title **Your plans** and a tabular count, with one primary **New plan** on the
right; a row of small status filters (All, Drafts, Active, Completed, Archived) with `aria-pressed`;
then one panel of plan rows divided by hairlines — title and status badge, the description clamped to
two lines, `1 Oct 2026 → 30 Oct 2026 · 30 days`, a thin hi-vis progress bar with `6 of 30 to-dos done`
and the percentage, and an *Open* action.

FORM: The conventional dark app — "Clean Slate", extended. No new world: the index borrows the
wizard's panel, hairlines, badges and button weights, and adds exactly one component, the plan row.
Build key `a7d20b91`.

FINISH: unreviewed and undocumented is unfinished; this surface ships with the `plans` e2e phase
(`plans`, `plans-filtered`, `plans-mobile`, `plans-empty`), the DESIGN.md plan-row entry, and this
brief.
