# FindingChart Annotation Spec — Claude Code

> **What this is:** Instructions for improving the FindingChart component used in Step 6
> to add contextual annotations that explain what the data means, not just what it shows.
>
> **Scope:** Only the chart rendering inside finding cards (the expandable mini-charts).
> Do NOT change any backend logic, API responses, or other frontend components.

---

## Problem

The current FindingChart for "Cost composition drift" (F003) shows a line chart of
COGS_pct_Revenue over time with two dashed horizontal lines (first-half avg and
second-half avg). The chart is technically correct but visually confusing because:

1. The 2021 dip (COGS dropping to ~70%) looks like an improvement, but it's actually
   the commodity supercycle anomaly — a temporary margin expansion that reversed.
   Without annotation, the audience sees a dip and wonders what happened.

2. The overall shape is a V (start at 81%, dip to 70%, climb to 97%), which reads as
   "recovery that overshot" rather than "structural deterioration." The finding says
   "+15.7pp deterioration" but the chart tells a more ambiguous story.

3. The dashed average lines do mathematical work (averaging across the V) but aren't
   labeled clearly enough to explain why they matter.

## Solution: Add Annotations to the Chart

### For "Cost composition drift" pattern charts:

Add the following annotations using Recharts' `ReferenceLine`, `ReferenceArea`,
`Label`, or custom SVG overlays:

**1. Label the dashed average lines explicitly:**
- Blue dashed line: add a label "1st half avg: {value}%" positioned at the left end
- Red dashed line: add a label "2nd half avg: {value}%" positioned at the right end
- Use a readable font size (11-12px) and match the line color

**2. Annotate the 2021 trough:**
- Add a small annotation near the 2021 data point:
  - Text: "Commodity supercycle" (or in PT-BR: "Superciclo de commodities")
  - Style: small italic text (10-11px), gray color, positioned below or beside the data point
  - This should be i18n-aware (use the language context)

**3. Annotate the 2022+ climb:**
- Add a subtle shaded region or annotation arrow covering 2022-2025:
  - Text: "Structural deterioration" (or "Deterioração estrutural")
  - Style: light red/orange background shading (very subtle, ~5% opacity) over the
    2022-2025 region, with the label at the top
  - Alternative: just a text label positioned above the 2023 data point area

**4. Improve the y-axis:**
- Consider starting the y-axis at 60% instead of auto-scaling, to give stable framing
- Add a subtle horizontal reference line at 100% with a faint label "Revenue = COGS"
  to show how close Braskem is to the breakeven threshold

### For "Margin compression" pattern charts (F001, F002):

These show Gross_Margin_pct or EBIT_Margin_pct trending downward. Add:

**1. A horizontal reference line at 0%:**
- For EBIT_Margin_pct (F002, currently at -2.6%), show a clear 0% line
- Label: "Breakeven" — this shows the audience that Braskem crossed into negative EBIT
- Style: dashed gray line, 1px

**2. Trend direction indicator:**
- Add a small annotation showing the compression rate: "-4.6pp/year" or "-2.8pp/year"
- Position: near the last data point, angled to follow the trendline
- Style: small text (10px), red color

### For "Revenue-cost decoupling" pattern charts (F004, F005):

These show revenue change % vs. COGS change % for a specific period. Add:

**1. Divergence arrow or gap indicator:**
- Draw a vertical double-arrow between the revenue bar and COGS bar
- Label the gap: "24.4pp divergence" or "25.0pp divergence"
- This makes the divergence visually obvious rather than requiring mental math

### General annotation rules:

- All text annotations must use the i18n system (add keys to en.json and pt-br.json)
- Annotations should be subtle — they augment the chart, not overwhelm it
- Use muted colors (grays, light reds) for annotation text
- For mobile/small screens, annotations can be hidden (they're for presentation mode)
- Annotations should not overlap data points or make the chart harder to read

---

## i18n Keys to Add

```json
{
  "charts": {
    "first_half_avg": "1st half avg",
    "second_half_avg": "2nd half avg",
    "commodity_supercycle": "Commodity supercycle",
    "structural_deterioration": "Structural deterioration",
    "revenue_equals_cogs": "Revenue = COGS",
    "breakeven": "Breakeven",
    "per_year": "/year",
    "divergence": "divergence"
  }
}
```

Portuguese:
```json
{
  "charts": {
    "first_half_avg": "Média 1ª metade",
    "second_half_avg": "Média 2ª metade",
    "commodity_supercycle": "Superciclo de commodities",
    "structural_deterioration": "Deterioração estrutural",
    "revenue_equals_cogs": "Receita = CPV",
    "breakeven": "Ponto de equilíbrio",
    "per_year": "/ano",
    "divergence": "divergência"
  }
}
```

---

## Files to Modify

- `frontend/src/components/charts/FindingChart.jsx` — add annotation logic per pattern type
- `frontend/src/i18n/en.json` — add chart annotation keys
- `frontend/src/i18n/pt-br.json` — add chart annotation keys (Portuguese)

## Files NOT to Modify

- Nothing in `backend/`
- No other frontend components
- No step components (Step1-Step9)
