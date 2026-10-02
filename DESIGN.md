---
name: AgentDa — The Route Card
description: A lit waxed route card on a deep slate ground; each deadline is a turn-around time and every day a camp.
colors:
  # primary — the rationed signal
  hivis: "#ff5a1f"
  hivis-deep: "#c63c08"
  # secondary — the profile chart's steel
  steel: "#2f4a5a"
  steel-ghost: "#9fb2bd"
  # tertiary — a flagged problem
  fault: "#b23a2a"
  # neutral — the slate ground and the waxed sheet
  ground: "#0e1a24"
  ground-line: "#24343f"
  sheet: "#f2f4f0"
  sheet-recess: "#e5eae4"
  sheet-rule: "#c6cfc6"
  sheet-rule-soft: "#d8ded6"
  ink: "#16222c"
  ink-soft: "#46545e"
  ink-faint: "#5c6a74"
typography:
  display:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem (1.875rem at ≥640px)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "normal"
    fontVariation: "'wdth' 88"
  headline:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.3125rem (1.625rem at ≥640px)"
    fontWeight: 600
    lineHeight: 1.25
    fontVariation: "'wdth' 88"
  title:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.375
  body:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.625
  caption:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.78125rem"
    fontWeight: 400
    lineHeight: 1.375
    fontFeature: "'tnum' 1"
  label:
    fontFamily: "Archivo Variable, Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.16em"
    fontVariation: "'wdth' 88"
rounded:
  sheet: "0px"
  tab: "2px"
  punch: "999px"
spacing:
  hairline: "1px"
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  "2xl": "16px"
  "3xl": "20px"
  "4xl": "24px"
components:
  label:
    textColor: "{colors.ink-faint}"
    typography: "{typography.label}"
  punch-tab:
    backgroundColor: "{colors.hivis}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tab}"
    padding: "0.6rem 1.5rem"
    height: "2.75rem"
  punch-tab-hover:
    backgroundColor: "{colors.hivis-deep}"
    textColor: "#ffffff"
    rounded: "{rounded.tab}"
  punch-tab-disabled:
    backgroundColor: "{colors.sheet-rule}"
    textColor: "{colors.ink-faint}"
    rounded: "{rounded.tab}"
  edge-tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.tab}"
    padding: "0.55rem 1.4rem"
    height: "2.5rem"
  edge-tab-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.tab}"
  line-input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "0.35rem 0 0.45rem"
  route-card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    width: "760px"
  route-card-band:
    backgroundColor: "{colors.steel}"
    textColor: "{colors.sheet}"
    padding: "10px 16px"
  route-card-footer:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    padding: "16px"
  date-strip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink-soft}"
    padding: "10px 0"
  notice:
    backgroundColor: "{colors.sheet-recess}"
    textColor: "{colors.ink-soft}"
    padding: "10px 12px"
  field-row:
    textColor: "{colors.ink}"
    padding: "8px 0"
  punch:
    backgroundColor: "{colors.sheet-recess}"
    rounded: "{rounded.punch}"
    size: "0.6rem"
  stamp:
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "4px 8px"
---

# Design System: AgentDa — The Route Card

## Overview

**Creative North Star: "The Route Card"**

A lit waxed route card lying on a deep slate table. The whole surface is one printed sheet that grows through five states — capture, planning, clarify, review, approved — rather than five screens or a progress-dot stepper. The card is the interface: its steel header band states what the sheet is and where it stands, its objective is a large inked line, its deadline is a dashed hi-vis turn-around rule at the profile's summit, and its single primary action is a punched tab at the foot.

The character is industrial signage and outfitter's paperwork: printed rules, punched camps, folded tags, tabular figures. Color is two materials and one signal — a dark slate ground, a waxed sheet, and a rationed hi-vis orange that belongs only to the turn-around rule and the one action, because its rarity is what carries the deadline. Type is a single grotesque on a width axis; the condensed cut reads as stencilled camp markers and printed labels, never as a second voice.

Depth is material, not decorative. The sheet is the only lifted object; the ground is flat. Confirmed visual rejections: no points or streaks drawn as ornaments, no progress dots, no confetti, no "you've got this" gradients or glass, and nothing of the cream-and-serif calming-coach aesthetic.

**Key Characteristics:**
- One printed sheet, ~760px, centred on a deep slate ground.
- Two materials (slate ground / waxed sheet) plus one rationed hi-vis signal.
- A single family, Archivo, used on a `wdth` axis; condensed for labels and camp markers.
- Depth from one deep sheet shadow and tonal layering, plus a punched-hole inset.
- Controls are ruled card fields and punched tabs; never pills, boxes, or switches.
- Tabular figures everywhere a date, time, or count appears.

## Colors

Two printed materials and one rationed signal: a dark slate ground, a waxed sheet, and an orange reserved for the deadline.

### Primary
- **Turnaround Hi-Vis** (`#ff5a1f`): the turn-around rule and the single primary action (`.punch-tab`). It also owns the text-selection fill and a marked punch. It appears nowhere else.
- **Hi-Vis Deep** (`#c63c08`): the darker cut of the signal, used whenever the orange must sit as *type* or as a hairline on the sheet — the end-date figure, the `TURNAROUND` label, the "Summit lands on…" line, the approved stamp, and focus rings — and as the primary action's hover.

### Secondary
- **Route Steel** (`#2f4a5a`): the card's header band and the elevation profile's path and camps; the profile's material.
- **Steel Ghost** (`#9fb2bd`): the profile's perforated rail, the tick marks, and the `⋯` elision in the date strip.

### Tertiary
- **Flagged Rust** (`#b23a2a`): a flagged problem — error prose, error borders, and the armed state of a destructive confirm.

### Neutral
- **Deep Slate Ground** (`#0e1a24`): the page background; the table the card is lit on.
- **Ground Line** (`#24343f`): the top bar's hairline divider on the ground.
- **Waxed Sheet** (`#f2f4f0`): the card stock, and the body color when type sits on the ground.
- **Sheet Recess** (`#e5eae4`): the shaded fill — notices, the selected camp row, the selected channel, and the punched hole's interior.
- **Sheet Rule** (`#c6cfc6`): input underlines, punch outlines, disabled plates, and the preset-chip borders.
- **Sheet Rule Soft** (`#d8ded6`): the faint rules that separate rows and bound the date strip.
- **Carbon Ink** (`#16222c`): the sheet's text, its outlines, and its filled controls.
- **Ink Soft** (`#46545e`): secondary prose.
- **Ink Faint** (`#5c6a74`): printed labels, hints, and meta.

### Named Rules
**The Rationed Hi-Vis Rule.** Hi-vis orange (`#ff5a1f`) appears only on the turn-around rule and the single primary action. When orange must be read as type on the sheet, use Hi-Vis Deep (`#c63c08`). The orange is never a second accent, chrome, or decoration.

**The Two-Material Rule.** Every surface is either the slate ground or the waxed sheet. There is no third surface tone; recess and rule tints of the sheet carry every subordinate zone.

## Typography

**Display Font:** Archivo Variable (with Archivo, ui-sans-serif, system-ui, sans-serif)
**Body Font:** Archivo Variable (same family)
**Label Font:** the condensed cut of the same family (`font-stretch: 88%`)

**Character:** One grotesque, self-hosted, with a real `wdth` axis. Its condensed cut is the whole labeling voice — short, stencilled, slightly industrial. Dates, counts, and times are set in tabular figures so the deadline arithmetic never jitters as it recomputes.

### Hierarchy
- **Display** (600, 1.5rem → 1.875rem at ≥640px, line-height 1.15, `wdth` 88): the objective as a printed headline. Wraps with `text-balance`; never clips.
- **Headline** (600, 1.3125rem → 1.625rem at ≥640px, line-height 1.25, `wdth` 88): the objective while it is being typed, as an auto-growing ruled line.
- **Title** (600, 0.9375rem, line-height 1.375): a camp's own name in the editable list.
- **Body** (400, 0.9375rem, line-height 1.625): panel prose and the finish line; measure capped at 54–68ch.
- **Caption** (400, 0.78125rem, tabular figures): hints, counts, metadata, and the date strip.
- **Label** (600, 0.6875rem, letter-spacing 0.16em, uppercase, `wdth` 88): printed field and band labels, stamps, and camp `D<n>` markers.

### Named Rules
**The One Family Rule.** Archivo is the only family. Emphasis comes from weight and the width axis, never from a second face or a display replacement.

**The Condensed Print Rule.** Anything printed as a label, stamp, or camp marker is set in the condensed cut (`font-stretch: 88%`) at 11px with wide tracking. The label voice is never rendered in the normal width.

## Layout

A single centred sheet on an open slate ground. The card is one column capped at `760px`; the sign-in sheet is the same pattern capped at `440px`; the top bar shares the `760px` container. Page gutters are `12px`, rising to `24px` at ≥640px; the card's own padding is `16px`, rising to `24px` at ≥640px, with a `20px` top pad before the objective.

Within the card the order is fixed: steel header band → objective heading → full-bleed elevation profile → printed date strip → the phase panel → a hairline rule → the footer. Two-up field groups split `1.35fr / 1fr` at ≥640px (Length beside Start; channel beside At + zone) and stack below it. Preset-length chips wrap.

The profile is the responsive pivot: at ≥640px it runs horizontally across the card, and below `640px` it rotates to a vertical ascent (the same `max-width: 640px` media query drives both this and the narrow flag). Body measures are capped so prose never spans the sheet: `54ch` under the objective, `56ch` in panels, `68ch` for notes and guidance, `42ch` on the sign-in card.

The rhythm is a 4px base: hairline `1px` rules, `4–6px` micro-gaps, `8–10px` inside a group, `16–24px` between groups. The bottom padding is generous (`96px`) so the card sits on the table rather than the viewport edge.

## Elevation & Depth

Depth is material and hybrid rather than decorative. The ground is flat and shadowless; the sheet is the only lifted object, casting a single deep, offset, soft shadow that reads as a card resting on a table. Subordination inside the sheet is tonal (Sheet Recess), and the punched hole is rendered as a shallow inset so it reads as removed material. Focus and selection are stated as flat rules — a Hi-Vis Deep line on focus, a hi-vis fill on selection — never as glows.

### Shadow Vocabulary
- **Sheet lift** (`box-shadow: 0 28px 70px -28px rgba(0, 0, 0, 0.75)`): the route card and the sign-in sheet — the only shadow in the system.
- **Punch inset** (`box-shadow: inset 0 1px 0 rgb(22 34 44 / 0.18)`): a camp's punched hole, so the recess reads as depth.
- **Focus rule** (`box-shadow: 0 1px 0 0 #c63c08`): a ruled input on focus doubles its underline in Hi-Vis Deep instead of glowing.

### Named Rules
**The One Shadow Rule.** The sheet casts one deep shadow; nothing else in the flow casts one. Depth on the ground is achieved by tonal separation, not by adding shadows to more elements.

## Shapes

The form language is square and punched. Corners are square (radius `0`) or at most a `2px` tab; the only true curves are circles — the punched hole (`0.6rem`, radius `999px`) and the small ringed end-holes on an edge tab. There are no pills and no switches. A printed tag is cut at its top-right corner (a `10px` `clip-path` notch) and carries a shaded fold flap rendered as a 45° `currentColor` gradient. The card's silhouette is a plain rectangle, and its steel header band is a full-bleed rectangle.

### Named Rules
**The Square-Or-Tab Rule.** Every control corner is square or a `2px` tab. Pills and rounded buttons do not exist in this world; the only round geometry is a punched hole.

**The Cut-Corner Rule.** Tags and stamps are distinguished by a cut top-right corner with a shaded flap, not by radius or color fill.

## Components

Controls are card fields and one punch. Focus is always the global 2px Hi-Vis Deep outline at a 2px offset.

### Buttons
- **Shape:** square corners with a `2px` radius (2px).
- **Primary (punched tab):** ink (`#16222c`) on hi-vis (`#ff5a1f`) at 5.2:1, `0.6rem 1.5rem` padding, `2.75rem` min-height, weight 700. Two sheet-coloured punched end-holes (4×13px) mark it as a tear-off tab.
- **Primary hover:** deepens to Hi-Vis Deep (`#c63c08`) with white text. Disabled becomes a blank plate (Sheet Rule fill, Ink Faint text) with the punched holes withdrawn.
- **Secondary (edge tab):** transparent ink outline on the sheet, `0.55rem 1.4rem`, `2.5rem` min-height, weight 600, with small ringed circular ends. Hover inverts to ink fill / sheet text. A `-quiet` modifier drops the rings for repeated row actions so the device does not dilute down a list.
- **Confirm (two-press):** a destructive action arms on first press (turning Rust) and only fires on a second press within 4 seconds; the label itself changes to state the consequence.

### Inputs / Fields
- **Style:** a ruled line, never a box — transparent background, no border except a `1px` Sheet Rule underline, square corners, `0.35rem 0 0.45rem` padding, tabular figures. Labels sit above in the printed label voice, with an optional right-aligned hint.
- **Focus:** the underline and a `1px` doubling shift to Hi-Vis Deep; the global outline is suppressed on the field itself.
- **Error:** error prose below the field in Rust; a channel/field error arrives as a Notice.

### Chips (presets)
- **Style:** bordered rectangles (`1px`) that are Ink fill / Sheet text when active and transparent with a Sheet Rule border when not; `12px` uppercase tracked text. They are printed selectors, not pills.

### Cards / Containers
- **Corner Style:** square (0).
- **Background:** Waxed Sheet, with a full-bleed Steel header band.
- **Shadow Strategy:** the single Sheet lift shadow (see Elevation & Depth).
- **Internal Padding:** `16px` → `24px` at ≥640px; band `10px 16px`.
- **Structure:** band → objective → profile → date strip → panel → rule → footer.

### Signature Components
- **Elevation Profile:** the card's signature SVG. Every plotted point is a real day; camps are outlined circles from real effort when a plan exists, and a labelled schematic when provisional. A perforated rail (Steel Ghost dashes) runs the axis, a Steel level rule marks the base, and the summit is pinned by a dashed hi-vis `TURNAROUND` rule with the end date. Selected camps get a dashed hi-vis ring. It rotates vertical below 640px.
- **Date Strip:** the deadline arithmetic stated flatly — `Day 1 — <start> ⋯ Day N — <end>` in tabular figures, bounded by soft rules, with the end date in Hi-Vis Deep and a right-aligned camp count.
- **Punch:** a `0.6rem` recessed hole; `data-marked="true"` fills it hi-vis. It marks a camp, a selection, and a chosen channel.
- **Stamp:** a rotated, folded-corner tag (`-2deg`, 2px Ink border, 11px bold tracked caps); the approved stamp is larger (15px, 3px border, `-4deg`, Hi-Vis Deep).
- **Notice:** a bordered recess block — Steel by default, Rust for a fault, Hi-Vis Deep for a limit — with an uppercase label over `13.5px` Ink Soft prose.
- **Field Row:** a printed key/value line, uppercase Ink Faint label left, `13.5px` semibold tabular value right, separated by a soft rule.
- **Camp list:** bordered top rules per row, a Punch + condensed `D<n>` marker in a fixed left gutter, an always-editable ruled title and description, inline to-dos with their own punches, and a quiet two-press "Rewrite this day" at the row's right.

## Do's and Don'ts

### Do:
- **Do** keep hi-vis orange (`#ff5a1f`) to the turn-around rule and the one primary action, and use Hi-Vis Deep (`#c63c08`) when orange must be type on the sheet.
- **Do** render every input as a ruled line on the sheet; no boxed fields.
- **Do** hold the card at `760px` centred, and the sign-in sheet at `440px`.
- **Do** set labels, stamps, camp markers, and the objective in the condensed cut (`font-stretch: 88%`).
- **Do** use tabular figures for every date, time, and count.
- **Do** keep the sheet's single deep shadow, and express everything else through tonal recess and hairline rules.
- **Do** make destructive actions arm before they fire, with the label stating the consequence.

### Don't:
- **Don't** introduce pills, switches, or rounded buttons; corners are square or a `2px` tab.
- **Don't** add a second type family or substitute a system display face for Archivo.
- **Don't** spend the orange anywhere else — no second accent, no orange chrome or decoration.
- **Don't** add gradients, glass, confetti, or glow effects; depth is one shadow and flat tonal layering.
- **Don't** gray secondary text on a colored surface; tint it from the palette (Ink Soft, Steel) instead.
- **Don't** revive the cream-and-serif calming-coach aesthetic, or draw the flow's commitment as progress dots.
