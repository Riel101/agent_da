---
version: 1
slug: "new-agenda"
primary_target: "new-agenda"
related_targets: []
---

# Surface brief — first-agenda wizard (`new-agenda`)

**Scope:** the entire first-run flow for one agenda, as one growing sheet:
`capture → planning → clarify → review → approved`. Mode: **Operate**.
**Audience & job:** one person, alone, who has just decided to do the long-deferred thing; on a
phone in a spare moment, resolved but afraid it will fade. They must turn one intention plus a
deadline into an approved, active agenda and believe the finale lands on their date.
**Constraints:** frozen REST contract (`docs/api-contract.md`), JWT bearer, polling only (no SSE),
React + Vite + Tailwind in `apps/web`, mobile-first. Binding: deadline math visible before commit;
no points or streaks anywhere in this flow; reminder channel + local time chosen in-flow; 1–90 days.
**Open decisions:** public launch/pricing model (product-level, not this surface).
**Anti-goals:** summit photography, "you've got this" gradients, confetti; the cream-and-serif
calming-coach aesthetic; a progress-dot stepper; fabricated to-dos for days it has not planned.

## Direction contract

THESIS: The deadline is a turn-around time you never negotiate, and every day is a camp on the
ascent. The surface refuses the category's progress-dot stepper and its dashboard-of-cards: one
sheet grows through five states instead of five screens.

OWN-WORLD: A lit waxed route card on a deep slate ground. Sheet `#F2F4F0`, ink `#16222C`, steel
`#2F4A5A` owns the elevation profile, hi-vis orange `#FF5A1F` owns only the turn-around rule and
the single primary action. Punched camps, printed rules, tabular figures. One family, Archivo;
condensed cut for camp labels. Controls are card fields and one punch, never pills or switches.

STORY: The visitor states an intention and a timeframe, watches the route compute to a fixed summit
date, answers the agent's marginal questions if any, reads and edits real camps, then stamps the
card. They understand: this is finite, it starts today, it ends on the date they chose.

FIRST VIEWPORT: Ground-owning slate. One card at ~720px, centred. Its header reads `ROUTE CARD /
NEW` over the intention as a large inked line. The elevation profile runs the card's full width
beneath it, camps marked, the summit pinned at the end date under a dashed orange TURNAROUND rule.
A printed date strip computes `Day 1 — <start> … Day N — <end>` live. Two fields (days, start
date), a signal row (channel + local time), and the single orange action **Draft the route** at the
card's foot.

FORM: The Route Card — candidate 1 of my ordered grounded list, chosen by the user over the roll's
assigned candidate 4. Seed key `8904f6de`.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
verdict, DESIGN.md, and every shipping raster carrying its provenance.
