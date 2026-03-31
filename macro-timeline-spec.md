# Macro Timeline Visual Redesign — Claude Code Spec

> **What this is:** Instructions for replacing the text-list "Findings vs. Macro Events"
> section at the bottom of Step 6 with a visual horizontal timeline that plots findings
> against macro events.
>
> **Scope:** Only the MacroTimeline component in Step 6. Do NOT change backend logic,
> API responses, or other components.

---

## Problem

The current "Findings vs. Macro Events" section is a flat text list:

```
2020    COVID-19 demand collapse — industrial output down globally
2020    COVID recovery — fiscal stimulus, demand rebound in China
2021    Post-COVID demand surge — commodity supercycle begins
...
```

This is functional but doesn't show the relationship between findings and macro events.
The audience can't see *when* findings occurred relative to macro shifts. For a live demo,
a visual timeline is significantly more impactful — it tells the story of what happened
and when, in one glance.

---

## Design: Horizontal Timeline with Two Lanes

```
MACRO EVENTS (top lane)
──────────────────────────────────────────────────────────────────────
  COVID         Supercycle    Ukraine    China         Cycle
  collapse      peak          war        oversupply    trough
  │             │             │          │             │
──┼──────┼──────┼──────┼──────┼──────┼───┼──────┼──────┼──────┼─────
  2020         2021         2022         2023         2024      2025
──┼──────┼──────┼──────┼──────┼──────┼───┼──────┼──────┼──────┼─────
  │                    │           │                        │
  F006,F007            F004        F005,F008                F001-F003
  EBIT anomaly         Supercycle  Cost stickiness          Structural
  (29-34%)             decoupling  Rev -8.6%/COGS +15.8%   deterioration
──────────────────────────────────────────────────────────────────────
FINDINGS (bottom lane)
```

### Layout Details

**Container:** Full-width card within Step 6, below the findings cards. Title: "Findings
vs. Macro Context" (i18n).

**Structure:** Two horizontal lanes separated by a central time axis.

**Top lane (Macro Events):**
- Each macro event is a labeled marker above the timeline
- Events are positioned by their half-year period (2020-H1, 2020-H2, etc.)
- Use color coding by category:
  - Red/orange: crisis events (COVID collapse, Ukraine war)
  - Green: recovery events (COVID recovery, supercycle)
  - Blue: normalization/tightening events (Fed tightening, China oversupply)
  - Gray: neutral/current (cycle trough, potential recovery)
- Labels should be SHORT (2-4 words max). Full description shows on hover tooltip.
- If two events share the same year, offset them vertically slightly to avoid overlap

**Central axis:**
- Horizontal line with year markers (2020, 2021, 2022, 2023, 2024, 2025)
- Half-year tick marks between years
- Current period (2025) optionally highlighted

**Bottom lane (Findings):**
- Each finding is a dot/marker below the timeline, positioned at its period
- Findings without a specific period (e.g., trend findings F001-F003) are shown as
  a horizontal bar spanning their full analysis range
- Color code by finding category:
  - Blue border: Core findings
  - Gray border: Supporting evidence
  - Light/muted: Contextual findings
  - Yellow border: Anomalies
- Label: finding ID + short name (e.g., "F005: Cost stickiness")
- Hover/click shows full finding description

**Connections:**
- Subtle vertical dashed lines connecting findings to their macro context period
- For findings with a `macro_context` field, draw a faint line from the finding
  dot to the corresponding macro event marker above

### Responsive Behavior

- On wide screens (>1000px): full horizontal timeline as described
- On narrow screens (<1000px): switch to a vertical timeline (events and findings
  interleaved chronologically, scrollable)

---

## Data Mapping

The component receives two data sources from the Step 6 API response:

**1. `macro_timeline` array** (already in API response):
```json
[
  { "period": "2020-H1", "event": "COVID-19 demand collapse — industrial output down globally" },
  { "period": "2020-H2", "event": "COVID recovery — fiscal stimulus, demand rebound in China" },
  ...
]
```

Map `period` to x-position on the timeline. Parse "YYYY-HN" to get year + half.

Short labels for the top lane (derive from the event text or hardcode a mapping):

```javascript
const SHORT_LABELS = {
  "2020-H1": "COVID collapse",
  "2020-H2": "COVID recovery",
  "2021-H1": "Demand surge",
  "2021-H2": "Supercycle peak",
  "2022-H1": "Ukraine war",
  "2022-H2": "Fed tightening",
  "2023-H1": "Post-war normalization",
  "2023-H2": "China oversupply",
  "2024-H1": "BRL weakness",
  "2024-H2": "Cycle trough",
  "2025-H1": "Recovery signals",
};
```

These should be in the i18n files (both EN and PT-BR).

**2. `findings` array** (already in API response):

Each finding has:
- `id` (e.g., "F001")
- `pattern` (e.g., "Cost composition drift")
- `period` (e.g., "2022-12-31" or "Q2 2022") — some findings don't have a period
- `macro_context` (optional, e.g., "Ukraine war — energy spike...")

For findings WITH a period: parse the period and position on the timeline.
For findings WITHOUT a period (trend findings like F001, F002, F003): show as
a horizontal bar spanning the full analysis range (2020-2025).

**3. `finding_categories`** (already in API response):
```json
{
  "core": ["F001", "F002", "F003"],
  "supporting": ["F005", "F008"],
  "contextual": ["F004"],
  "anomalies": ["F006", "F007"]
}
```

Use this to color-code finding markers.

---

## Implementation Notes

**Use Recharts or plain SVG.** Recharts might be overkill for this — a custom SVG
component would give more control over the two-lane layout. But if using Recharts,
a ScatterChart with two Y-axis categories (macro / findings) and ReferenceLine for
the axis could work.

**Recommended approach:** Custom SVG component (`MacroTimeline.jsx`), since the layout
is non-standard for charting libraries. Use the existing CSS variables for colors.

**Sizing:**
- Full width of the content area
- Height: ~250-300px for the horizontal version
- Margins: 40px left (for labels), 20px right

**Interactivity:**
- Hover on macro event: show full event description in a tooltip
- Hover on finding dot: show finding ID, pattern, description
- Click on finding dot: scroll to that finding card above (optional, nice-to-have)

---

## Event Category Colors

Add to the macro event data (either in the component or as a lookup):

```javascript
const EVENT_CATEGORIES = {
  "2020-H1": "crisis",      // red/orange
  "2020-H2": "recovery",    // green
  "2021-H1": "recovery",    // green
  "2021-H2": "peak",        // green (darker)
  "2022-H1": "crisis",      // red/orange
  "2022-H2": "tightening",  // blue
  "2023-H1": "pressure",    // blue
  "2023-H2": "pressure",    // blue
  "2024-H1": "pressure",    // blue
  "2024-H2": "trough",      // gray
  "2025-H1": "neutral",     // gray
};

const CATEGORY_COLORS = {
  crisis:     "#dc3545",  // red
  recovery:   "#28a745",  // green
  peak:       "#1a7a34",  // dark green
  tightening: "#007bff",  // blue
  pressure:   "#6c8ebf",  // muted blue
  trough:     "#6c757d",  // gray
  neutral:    "#adb5bd",  // light gray
};
```

---

## i18n Keys to Add

### English (`frontend/src/i18n/en.json`)

```json
{
  "charts": {
    "macro_timeline_title": "Findings vs. Macro Context",
    "macro_events_lane": "Macro Events",
    "findings_lane": "Findings",
    "trend_finding": "Trend (full period)",
    "macro_short_2020_H1": "COVID collapse",
    "macro_short_2020_H2": "COVID recovery",
    "macro_short_2021_H1": "Demand surge",
    "macro_short_2021_H2": "Supercycle peak",
    "macro_short_2022_H1": "Ukraine war",
    "macro_short_2022_H2": "Fed tightening",
    "macro_short_2023_H1": "Post-war normalization",
    "macro_short_2023_H2": "China oversupply",
    "macro_short_2024_H1": "BRL weakness",
    "macro_short_2024_H2": "Cycle trough",
    "macro_short_2025_H1": "Recovery signals"
  }
}
```

### Portuguese (`frontend/src/i18n/pt-br.json`)

```json
{
  "charts": {
    "macro_timeline_title": "Achados vs. Contexto Macroeconômico",
    "macro_events_lane": "Eventos Macro",
    "findings_lane": "Achados",
    "trend_finding": "Tendência (período completo)",
    "macro_short_2020_H1": "Colapso COVID",
    "macro_short_2020_H2": "Recuperação COVID",
    "macro_short_2021_H1": "Surto de demanda",
    "macro_short_2021_H2": "Pico do superciclo",
    "macro_short_2022_H1": "Guerra na Ucrânia",
    "macro_short_2022_H2": "Aperto do Fed",
    "macro_short_2023_H1": "Normalização pós-guerra",
    "macro_short_2023_H2": "Excesso China",
    "macro_short_2024_H1": "Fraqueza do BRL",
    "macro_short_2024_H2": "Vale do ciclo",
    "macro_short_2025_H1": "Sinais de recuperação"
  }
}
```

---

## Files to Modify

- `frontend/src/components/charts/MacroTimeline.jsx` — replace text list with visual timeline
- `frontend/src/i18n/en.json` — add timeline i18n keys
- `frontend/src/i18n/pt-br.json` — add timeline i18n keys (Portuguese)

## Files NOT to Modify

- Nothing in `backend/`
- No step components (the MacroTimeline is already imported in Step6)
- No other chart components
