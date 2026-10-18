---
version: 1
slug: "new-agenda"
primary_target: "new-agenda"
related_targets: []
---

# Surface brief — first-agenda wizard (`new-agenda`)

**Scope:** the entire first-run flow for one agenda, as one page that advances through
`capture → planning → clarify → review → approved` (plus a failure state). Mode: **Operate**.
**Audience & job:** one person, alone, who has just decided to do the long-deferred thing; on a
phone in a spare moment, resolved but afraid it will fade. They must turn one intention plus a
deadline into an approved, active plan and believe the final day lands on their date.
**Constraints:** frozen REST contract (`docs/api-contract.md`), JWT bearer, polling only (no SSE),
React + Vite + Tailwind in `apps/web`, mobile-first. Binding: deadline arithmetic visible before
commit; no points or streaks anywhere in this flow; reminder channel + local time chosen in-flow;
1–90 days.
**Open decisions:** public launch/pricing model (product-level, not this surface).
**Anti-goals:** photography of any kind, "you've got this" gradients, confetti, glass for its own
sake; fabricated to-dos for days it has not planned; any return of the ascents-and-camps metaphor,
the elevation chart, the stamp, or the punched-tab device language.

## Direction contract

THESIS: The plan is a normal, trustworthy web application. The surface refuses the category's
fabricated progress charts and card decks: it is one page whose body and footer change with the
plan's state, and whose deadline arithmetic is stated plainly and never dramatised.

OWN-WORLD: A conventional dark application in the incumbent palette, re-cast. Slate ground
`#0E1A24` is the canvas; panels sit on it as `#16232E` surfaces with `#24343F` hairlines. Sheet
`#F2F4F0` is the primary text, steel-ghost `#9FB2BD` the muted tier. Hi-vis `#FF5A1F` is rationed
to the primary action, the focus ring, and the active step; ink `#16222C` is the text on it. Archivo
at normal width, one scale, sentence case — no condensed cut, no tracked uppercase. Controls are
standard fields and three button weights; depth is hairlines and tonal surfaces, not shadow theatre.

STORY: The visitor states a goal and a timeframe, watches the plan generate, answers the agent's
questions if any, reads and edits real days and to-dos, then approves. They understand: this is
finite, it starts today, it ends on the date they chose.

FIRST VIEWPORT: A slim top bar (`AgentDa`, the signed-in address, Sign out) over a `720px` column.
A labelled step path (`Details · Plan · Review · Done`) with a thin progress bar sits above a single
panel: the goal as a large inked heading, then the timeline — one tick per day, the start on the
left and the deadline pinned on the right in hi-vis. Below, the capture form in titled sections
(duration, start date, reminder), and the one primary action **Generate plan** at the panel's foot.

FORM: The conventional dark app — "Clean Slate". The direction was pinned by the user over the
roll: keep the incumbent palette, drop the metaphor, build the ordinary app. Build key `a7d20b91`.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
verdict, DESIGN.md, and every shipping raster carrying its provenance.
