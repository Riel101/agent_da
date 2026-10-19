---
name: AgentDa — Clean Slate
description: A conventional dark application on a slate canvas; one panel whose body and footer change with the plan's state, a plain deadline timeline, and an index of every plan as hairline rows.
colors:
  # primary — the one rationed accent
  hivis: "#ff5a1f"
  hivis-deep: "#c63c08"
  # secondary — the quiet chrome
  steel: "#2f4a5a"
  steel-soft: "#55707f"
  steel-ghost: "#9fb2bd"
  # tertiary — a flagged problem
  fault: "#b23a2a"
  danger: "#ff6b52"
  # neutral — the canvas, the panels, the text
  ground: "#0e1a24"
  ground-raised: "#16232e"
  elevated: "#1b2836"
  ground-line: "#24343f"
  sheet: "#f2f4f0"
  ink: "#16222c"
  ink-soft: "#46545e"
  ink-faint: "#5c6a74"
  sheet-recess: "#e5eae4"
  sheet-rule: "#c6cfc6"
  sheet-rule-soft: "#d8ded6"
typography:
  display:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.375rem (1.625rem at ≥640px)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "normal"
    fontVariation: "normal"
    textWrap: "balance"
  headline:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.0625rem (1.1875rem at ≥640px)"
    fontWeight: 600
    lineHeight: 1.3
  title:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.375
  body:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  caption:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.78125rem"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "'tnum' 1"
  label:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "normal"
    fontVariation: "normal"
rounded:
  field: "6px"
  button: "6px"
  alert: "8px"
  card: "12px"
  pill: "999px"
spacing:
  hairline: "1px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  "2xl": "24px"
  column: "720px"
components:
  field:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.sheet}"
    borderColor: "{colors.ground-line}"
    rounded: "{rounded.field}"
    padding: "0.5rem 0.7rem"
  field-focus:
    borderColor: "{colors.hivis}"
    ring: "0 0 0 3px rgb(255 90 31 / 0.16)"
  inline-field:
    backgroundColor: "transparent"
    textColor: "{colors.sheet}"
    rounded: "{rounded.field}"
    padding: "0.25rem 0.5rem"
  button:
    rounded: "{rounded.button}"
    padding: "0.5rem 1rem"
    height: "2.5rem"
  button-primary:
    backgroundColor: "{colors.hivis}"
    textColor: "{colors.ink}"
  button-primary-hover:
    backgroundColor: "{colors.hivis-deep}"
    textColor: "#ffffff"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.sheet}"
    borderColor: "{colors.ground-line}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.steel-ghost}"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.danger}"
    borderColor: "rgb(255 107 82 / 0.45)"
  card:
    backgroundColor: "{colors.ground-raised}"
    borderColor: "{colors.ground-line}"
    rounded: "{rounded.card}"
  badge:
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.625rem"
  alert:
    backgroundColor: "{colors.elevated}"
    borderColor: "{colors.ground-line}"
    rounded: "{rounded.alert}"
    padding: "0.75rem 0.875rem"
  field-row:
    textColor: "{colors.sheet}"
    borderColor: "{colors.ground-line}"
    padding: "0.625rem 0"
  plan-row:
    backgroundColor: "transparent"
    textColor: "{colors.sheet}"
    borderColor: "{colors.ground-line}"
    padding: "1rem 0"
---

# Design System: AgentDa — Clean Slate

## Overview

**Creative North Star: "Clean Slate"**

A conventional dark application. Every surface is one centred panel on a slate canvas. The wizard swaps its body and footer with the plan's state — capture, planning, clarify, review, approved, and a failure case — while the frame around it stays put: a slim top bar, a labelled step path, a thin progress bar, the goal, and a plain timeline of days. The plan index is one row per plan on the same kind of panel, divided by hairlines, each row carrying the plan's status, its dates, and how far along it is. The daily surface is one panel too: a completion summary over the day's checkable to-dos, with a plan tab when more than one plan is running. There is no card deck, no metaphor, and nothing that needs a diagram to explain.

The first surface's palette is kept and re-cast. The slate ground `#0e1a24` stops being a tabletop and becomes the canvas itself; panels rest on it as `#16232e` surfaces with `#24343f` hairlines; sheet `#f2f4f0` becomes the primary text and steel-ghost `#9fb2bd` the muted tier. Hi-vis orange `#ff5a1f` survives as the single rationed accent — the one primary action, the focus ring, the active step, and the deadline — and ink `#16222c` is the text that sits on it. Archivo is kept at its normal width on one scale, in sentence case; the condensed cut is gone.

Depth is hairlines and tonal surfaces. There is no sheet shadow and no ornament: panels are separated from the canvas by a 1px line and a slightly lighter fill. Every rejection from the first world is honoured — no camps, no summit or turnaround, no route card, no elevation chart, no stamp, no punched tabs, no tracked uppercase labels — and the progress-dot stepper ban is deliberately lifted: this build states where the visitor is with a labelled step path and a progress bar, the ordinary way.

## Colors

The palette is the incumbent one, so it carries the product's history; its **roles** are new. Three families: the slate canvas and its panels, the light text scale, and the rationed orange. Steel is the quiet chrome in between.

### Primary

- **Hi-Vis Orange** (`#ff5a1f`): the single accent. Primary button fills, the focus ring, the active step, the progress bar, the deadline tick and label, and links that are truly actions. Ink `#16222c` is its foreground — 5.2:1, so the primary action is legible.
- **Hi-Vis Deep** (`#c63c08`): the primary button's hover fill only. It is never used as type on the dark ground (2.0:1) and never as a second accent.

### Secondary

- **Steel** (`#2f4a5a`): a completed step's chip in the step path.
- **Steel Soft** (`#55707f`): hairline-weight tick marks and the field's hover border. Never body text on the ground (3.2:1).
- **Steel Ghost** (`#9fb2bd`): the muted text tier — field labels, hints, captions, prose body on the canvas (7.6:1). This is the default secondary text colour; it is a light tint of the canvas's own hue, never neutral gray.

### Tertiary

- **Fault** (`#b23a2a`): retained for fault surfaces and 1px danger borders.
- **Danger** (`#ff6b52`): the fault hue's *text* tint for the dark ground (6.3:1) — error prose, danger badges, the armed confirm button.

### Neutral

- **Deep Slate Ground** (`#0e1a24`): the page canvas.
- **Ground Raised** (`#16232e`): the panel, and the inline field's hover/focus fill.
- **Elevated** (`#1b2836`): standard text fields, badges, and alert fills — one step above the panel.
- **Ground Line** (`#24343f`): every hairline — panel border, dividers, the timeline track, the progress track.
- **Waxed Sheet** (`#f2f4f0`): primary text on the canvas (15.4:1), and the focus ring on the primary button.
- **Carbon Ink** (`#16222c`): text on hi-vis fills, the caret, and the text selection background's foreground.

`ink-soft`, `ink-faint`, `sheet-recess`, `sheet-rule`, and `sheet-rule-soft` remain in the theme so the palette is not fragmented, but the dark system draws on `ground-raised` and `elevated` for surfaces and `steel-ghost` for muted text; they are not part of the current surface vocabulary.

### Named Rules

**The One Accent Rule.** Hi-vis orange is the only accent and it is rationed: the primary action, the focus ring, the active step, the deadline, and the progress bar. Nothing else may be orange — not headings, not borders, not a second button. Its scarcity is what makes it read as signal.

**The Tinted-Muted Rule.** Muted text on the canvas is always steel-ghost — a light tint of the canvas's own hue. Neutral gray is never introduced, and `steel-soft` never carries body text.

**The Tonal-Surface Rule.** Surfaces are three values of one slate: canvas, panel, elevated. There is no fourth, and no surface is coloured except a hi-vis or danger tint at ≤10%.

## Typography

One family, **Archivo Variable**, at its normal width, on a single tight scale. There is no condensed cut and no uppercase tracking; hierarchy comes from size and weight. Full sentences, sentence case, everywhere.

### Hierarchy

- **Display** (600, `1.375rem` → `1.625rem` at ≥640px, lh 1.15, `text-wrap: balance`): the goal as a heading, and the sign-in title. The only large type in the flow.
- **Headline** (600, `1.0625rem` → `1.1875rem`): the goal while it is being typed, as a bordered field rather than a ruled line.
- **Title** (600, `0.9375rem`): section headings, day titles, question prompts.
- **Body** (400, `0.9375rem` / `0.875rem`, lh 1.6): panel prose, capped at 62–68ch.
- **Caption** (400, `0.78125rem`, tabular figures): hints, counts, day dates, the step path.
- **Label** (500, `0.8125rem`): field labels and metadata. Normal width, normal tracking, sentence case.

### Named Rules

**The One Family Rule.** Archivo is the only family. Emphasis is weight, never a second face.

**The Sentence-Case Rule.** Nothing is set in uppercase with tracking — not labels, not buttons, not badges. The stencilled voice of the first world is retired.

**The Tabular Rule.** Every date, time, count, and duration uses tabular figures, so the deadline arithmetic reads cleanly down a column.

## Layout

A `720px` column centred with `16px` gutters (`24px` at ≥640px), beginning `32px` below the top bar (`48px` at ≥640px) and ending with `96px` of breathing room. The top bar is full-bleed, one hairline tall, with the wordmark and the three places you can be — *Today*, *Plans* and *New plan*, the current one on an `elevated` chip — left, and the signed-in address plus *Sign out* right.

Inside the column, top to bottom: the step path and progress bar, then one panel. The panel's first zone holds the goal and the timeline; a hairline divides it from the body; the body is the phase's content; a second hairline divides it from the footer, which always holds the phase's action. Sections inside the body are separated by `24px`. The sign-in surface is a single `420px` column with one panel.

The plan index reuses the column and the top bar without the step path: the title and the plan count with one primary *New plan*, a row of status filters, then one panel of plan rows divided by hairlines, and a *Load more* button under the panel while the account has more plans than the page holds.

### Named Rules

**The One Panel Rule.** Each surface is one panel. The flow's panel changes its body and footer; the index's panel is a list of hairline rows. Neither becomes multiple cards, a deck, or a wizard of separate pages.

**The Step-Path Rule.** Where the visitor is is stated by a labelled path (`Details · Plan · Review · Done`) plus a thin bar — ordinary and readable — not by an unlabelled dot row.

## Elevation & Depth

Depth is flat and material. One hairline plus one tonal step is the entire vocabulary: a panel is `ground-raised` behind a `ground-line` border on the `ground` canvas, and a field or badge is `elevated`. There is a single recessed treatment — the focus ring on a field (`0 0 0 3px rgb(255 90 31 / 0.16)`) — and no drop shadow anywhere in the flow. The sign-in panel does not float.

### Named Rules

**The No-Shadow Rule.** Nothing in the flow casts a shadow. Separation is a hairline and a tonal step, nothing more.

**The Hairline Rule.** Every separator is exactly `1px` of `ground-line`. Bolder lines do not exist; a heavier emphasis is a fill, not a thicker border.

## Shapes

Corners are small and consistent: `6px` for fields and buttons, `8px` for alerts, `12px` for the panel. Pills (`999px`) are reserved for the status badge and the timeline's selection marker. There are no cut corners, folds, or tabs.

### Named Rules

**The Small-Radius Rule.** Fields and buttons are `6px`, panels `12px`. Nothing is square, and nothing is a capsule — pills are for badges and markers only.

**The No-Device Rule.** No clipped corners, folds, perforations, or punched ends. Shape never carries metaphor.

## Components

### Buttons

- **Primary** (`.btn-primary`): hi-vis fill, ink text, `2.5rem` tall. One per zone — *Generate plan*, *Approve & schedule*, *Try again*, *Submit answers*. Its focus ring is sheet, not hi-vis, so it stays visible on the orange.
- **Secondary** (`.btn-secondary`): transparent with a `ground-line` border and sheet text — *New plan*, *Regenerate plan*, *Add*.
- **Ghost** (`.btn-ghost`): steel-ghost text, no border — *Sign out*, *Remove*.
- **Danger** (`.btn-danger`): the armed state of the confirm button — danger text on a lighter danger tint.
- **Small** (`.btn-sm`): `2rem` tall, for row-level and footer-adjacent controls.

### Inputs / Fields

- **Field** (`.field`): an `elevated` fill, `ground-line` border, `6px` radius. On focus, the border turns hi-vis and a soft hi-vis ring appears. Native `color-scheme: dark` dresses the date and time pickers, the select chevron, and the scrollbars.
- **Inline field** (`.inline-field`): a borderless line inside the day list that reads as text and gains an `elevated` fill on hover and a hi-vis border on focus. Editing and reading are the same object.
- Labels sit above their field in `Label` type at steel-ghost.

### Chips (presets)

Duration presets are real `<button>`s in the small button weights: the active preset is `.btn-primary` with `aria-pressed`, the rest `.btn-secondary`. Reminder channels are native radios inside bordered cards; the chosen card takes the hi-vis border.

### Cards / Containers

One `.card` per surface: `ground-raised`, `1px` `ground-line`, `12px` radius, padding `20px` (`24px` at ≥640px). Its zones are divided by `Divider` hairlines. Alerts are tinted blocks inside the panel.

### Signature Components

- **Step path + progress bar** (`StepHeader`): labelled steps with numbered chips — hi-vis for the active step, steel for done — a status badge (`Draft`, `Planning`, `Needs answers`, `Ready to review`, `Approved`, `Failed`) on the right, and a `4px` progress track filling in hi-vis.
- **Timeline** (`Timeline`): the deadline arithmetic, drawn. One `1px` tick per day on a `ground-line` track, the final tick and its label in hi-vis, the count in the middle, the start and end dates in tabular figures. In review it is clickable to select a day and shows a ringed marker on the selection.
- **Day list** (`DayList`): one row per day — a `Day n` marker, the date, an *Edited* badge, the phase, and the effort in minutes; then the editable title and description, the expected outcome, any validation alerts, the to-dos, an add-to-do row, and an armed *Rewrite this day*. The selected day takes an `elevated/50` fill.
- **Field row** (`FieldRow`): label left, tabular value right, on a hairline — how the approved panel and the planning panel state facts.
- **Today** (`Today`): one panel for the local day — `done of total to-dos done`, a thin hi-vis progress track, the points balance and current streak in tabular figures, then the selected plan's day: title, description, outcome, and a hairline list of checkable to-dos. A checked row strikes through and reads *Done*; unchecked rows show their point value. A plan tab row appears only when more than one plan is running today. The day's footer states what is left or that the day is complete, in an `aria-live` line.
- **Plan row** (`Plans`): one plan per hairline row — the title and a status badge, the description clamped to two lines, `start → end · N days` in tabular figures, then a thin hi-vis progress bar with `done of total to-dos` and the percentage, plus a danger line when days were missed. A live plan offers *Open*; a draft, *Continue*. Every row also carries an armed *Delete* — the first press arms it, the second reads *Delete for good* — which removes the plan and its days, to-dos and reminders while keeping points already earned. The status filter above is a row of small buttons carrying `aria-pressed`, and the chosen filter lives in the URL.

## Do's and Don'ts

### Do:

- **Do** keep hi-vis orange to the primary action, the focus ring, the active step, the deadline, and the progress bar.
- **Do** render the flow as one panel whose body and footer swap with the phase.
- **Do** keep the plan index on one panel of hairline rows — status, description, dates, progress, one action — with the status filter in the URL.
- **Do** set all copy in sentence case, in Archivo at normal width, on one scale.
- **Do** state the deadline arithmetic plainly — timeline ticks, tabular dates, the count.
- **Do** use tabular figures for every date, time, count, and duration.
- **Do** express depth with hairlines and the two tonal steps; add no shadow.
- **Do** make destructive actions arm before they fire, with the label naming the consequence.

### Don't:

- **Don't** reintroduce the metaphor or its devices — camps, summit, turnaround, route card, elevation profile, stamp, punched tabs.
- **Don't** use a second accent, orange chrome, gradients, glass, or glow.
- **Don't** set labels or buttons in uppercase with tracking, or use the condensed cut.
- **Don't** gray muted text — tint it from the canvas (steel-ghost) instead.
- **Don't** fabricate progress charts, points, or streaks for effect; the only chart is the real timeline.
- **Don't** add shadows to more elements; the system has none.
