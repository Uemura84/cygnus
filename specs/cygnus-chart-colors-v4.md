# Cygnus Chart Colors — v4 Alignment

## Purpose

Align the Cygnus product UI chart data colors with the v4 visual identity spec (`visual-identity-content.md` v4 and Product Vision Section 13, both updated April 22, 2026). This is a narrow, surgical fix. It does **not** touch typography, CSS custom properties, brand accent colors, or logomark — those belong to the larger post-demo migration pass.

Scope: chart data series colors in React frontend components and the Python PDF report generator. Nothing else.

## The v4 chart data palette

| Series role | Hex | Opacity | Notes |
|---|---|---|---|
| Revenue / positive / primary | `#2E86C1` | 1.0 | Financial Blue. Replaces whatever teal/blue is currently in this position. |
| Costs / negative / declining | `#C0392B` | 0.65 | Cost Red, muted (not alarm). Preserved from v3 spec. |
| Gross profit / derived / neutral | `#0B1F3A` | 1.0 | Navy. Should already be correct — verify only. |
| Chart annotations, "watch this" markers | `#EF9F27` | 1.0 | Amber. Preserved. |
| Structural period annotation bands (behind data) | `#0E8F9A` | 0.10 | Cygnus Teal. Used for banded rectangles marking periods like "Commodity Supercycle 2021". Only chart use of teal. |
| DVA Shareholders (stakeholder chart only) | `#7EC8E3` | 1.0 | Light Blue. **Do not change.** Documented DVA-specific variant. |

## Why these specific values

- **Revenue → Financial Blue `#2E86C1`:** Conventional financial-publication blue (Bloomberg, FT, Economist tradition). Deeper and more editorial than generic bright blue; readable by CFO-level readers who parse blue-for-revenue pre-cognitively. Cygnus Teal is reserved for brand surfaces (UI chrome, section labels, logomark) — not data.
- **COGS → Cost Red at 65%:** Muted brick-red, not salmon. Preserves cool-vs-warm semantic contrast with Financial Blue. The 65% opacity prevents the red from reading as alarm and pairs well with the blue.
- **Gross Profit → Navy:** Derived metrics stay neutral. Navy reads as "this is a calculation, not a direct measurement."
- **Cygnus Teal only as period-annotation bands at 10% opacity:** Teal does appear in charts, but only as a low-opacity background band behind data to mark macro periods. Never as a data series.

## Out of scope — do NOT touch

- CSS custom properties (`--teal`, `--blue`, `--blue-dim`, etc.) — these belong to the post-demo migration
- Typography (DM Sans, DM Serif Display, JetBrains Mono) — post-demo migration
- Logomark SVG files — post-demo migration
- Brand accent colors in UI chrome (sidebar, wordmark, section label teal eyebrows) — these stay as-is in the live v1 product until the full migration
- `#7EC8E3` DVA Shareholders Light Blue — preserved exception
- Amber `#EF9F27` — preserved unchanged
- Chart structural elements: axis styles, gridlines, typography inside charts, legend placement, chart sizes
- Chart component structure: don't refactor, rename, or reorganize

## Reference documents

- `visual-identity-content.md` v4 Section 3 (Core palette — chart data colors) and Section 8 (Series coloring) — authoritative spec for content visuals
- `product-vision-architecture.md` Section 13.4 (chart palette) — authoritative spec for product UI

---

# Two-part execution

This prompt has a discovery phase and an execution phase, separated by a checkpoint. Part 1 performs read-only discovery and stops. After review, Part 2 executes the edits.

---

## Part 1 — Discovery pass (paste this first, wait for report)

```
Cygnus UI chart color alignment — discovery pass only, do not edit any files.

I need to align the product UI chart data colors with the v4 visual identity spec. Before any edits, I need a complete picture of where chart colors are currently defined.

## Run these searches across the repo

1. Find every file containing any of these hex values (case-insensitive):
   - #0E8F9A (Cygnus Teal — may currently be used as Revenue color, should move to period-annotation only)
   - #1E90FF (Signal Blue — legacy v1 Revenue color, may or may not still be present)
   - #2E86C1 (Financial Blue — target Revenue color, probably not present yet)
   - #C0392B (Cost Red — target COGS color, may be present)
   - #7EC8E3 (DVA Shareholders Light Blue — preserved, do not change)
   - #0B1F3A (Navy — likely Gross Profit color)
   - #EF9F27 (Amber — annotations)

2. Find every file containing rgba() expressions with any of these RGB triplets (catches all opacity variants):
   - rgba(14, 143, 154 (or 14,143,154) — Cygnus Teal
   - rgba(30, 144, 255 (or 30,144,255) — Signal Blue
   - rgba(46, 134, 193 (or 46,134,193) — Financial Blue
   - rgba(192, 57, 43 (or 192,57,43) — Cost Red

3. Identify the chart library being used. Look for imports in frontend/src/:
   - `from 'recharts'`
   - `from 'chart.js'` or `from 'react-chartjs-2'`
   - `import * as d3`
   - `from 'victory'` or similar

4. Find candidate chart-theme or chart-config files by searching for typical filenames:
   - frontend/src/chartTheme.*
   - frontend/src/chartColors.*
   - frontend/src/theme/*
   - frontend/src/constants/colors.*
   - frontend/src/config/chart*.*

5. Find chart component files. Search for:
   - Files in frontend/src/components/ with names containing "Chart", "Graph", "Bar", "Line", "Bridge", "Waterfall"
   - Files importing the chart library identified in step 3
   - Specifically locate the Revenue-vs-COGS chart (likely in Step 4) and the Margin Bridge chart (also Step 4)

6. Check backend/report_pdf.py for chart color constants. Look for any hex color literals, especially near:
   - matplotlib color arguments (color=, facecolor=, edgecolor=)
   - Any module-level color dictionaries or constants
   - Plot configuration setup

## Report back with

A structured summary organized as:

### Chart library in use
[recharts / chart.js / d3 / other] imported from [paths]

### Centralized chart theme file
Path, or "none found" if chart colors are scattered across components

### Files with hard-coded chart colors (frontend)
For each file: path, list of hex values found, guess at what series each value represents (Revenue bar / COGS bar / Gross Profit line / annotation / unknown)

### Files with hard-coded chart colors (backend — PDF generator)
For each file: path, list of hex values found, guess at what series each represents

### Current state of the four key positions
- Revenue series currently uses: [hex]
- COGS series currently uses: [hex]
- Gross Profit series currently uses: [hex]
- DVA Shareholders currently uses: [hex] (expected #7EC8E3, confirm)

### Proposed edits
A preview of which files need changes and roughly how many hex-value replacements per file.

### Flags and uncertainties
Anything ambiguous — e.g., "file X has #0E8F9A but I can't tell if it's a chart data color or a UI chrome color, please clarify before I edit."

STOP here. Do not proceed to edits. I will review the discovery report and then send you Part 2 to execute the changes.
```

---

## Part 2 — Execution (paste after reviewing discovery output)

```
Discovery reviewed and approved. Proceed with the chart color alignment to v4 spec.

## The mapping

For the Revenue / positive / primary chart series:
- Replace the current value (identified in discovery, probably #0E8F9A or a washed-out teal variant) with #2E86C1

For the COGS / costs / negative chart series:
- If the current value is not #C0392B, replace it with #C0392B
- Ensure the fill opacity is 0.65 (either via rgba(192, 57, 43, 0.65), or via an 8-digit hex #C0392BA6, or via a separate fillOpacity={0.65} prop — use whichever pattern matches the existing code style in each file)

For the Gross Profit / derived / neutral chart series:
- Verify it is #0B1F3A Navy. If it is, leave unchanged. If it is something else, replace with #0B1F3A.

Do not change:
- #7EC8E3 DVA Shareholders Light Blue — preserved exception
- #EF9F27 Amber annotations — unchanged
- Cygnus Teal #0E8F9A when used as a period-annotation band at 10% opacity (rgba(14, 143, 154, 0.10) or similar). If discovery found no such band, skip this — don't add one.
- Any UI chrome color (sidebar, wordmark, section label eyebrow teal) — these remain in v1 state until the full post-demo migration

## Order of edits

### Step 1 — Centralized chart theme file (if found)

If discovery found a single file that centralizes chart colors (chartTheme.js, chartColors.js, or similar), edit it first. All downstream chart components that import from it will inherit the change without needing individual edits.

Apply the three mappings above. Keep variable names as-is (don't rename `REVENUE_COLOR` to `FINANCIAL_BLUE`, for example) — changing only values, not names, minimizes blast radius.

### Step 2 — Individual chart components (if no central theme, or if any component hard-codes colors bypassing the theme)

For each component that hard-codes a chart color, apply the same three mappings. Watch for:

- JSX props: `<Bar fill="#0E8F9A" />` → `<Bar fill="#2E86C1" />`
- Object literals: `{ color: '#0E8F9A' }` → `{ color: '#2E86C1' }`
- Array entries: `['#0E8F9A', '#C0392B', ...]` → `['#2E86C1', '#C0392B', ...]`
- Tailwind arbitrary values: `bg-[#0E8F9A]` → `bg-[#2E86C1]` (if any)

Preserve the exact quote style and whitespace of the surrounding code.

### Step 3 — Backend PDF generator (backend/report_pdf.py)

Apply the same three mappings. For matplotlib:

- Bar chart Revenue: color='#2E86C1'
- Bar chart COGS: color='#C0392B', alpha=0.65 (matplotlib convention for opacity)
- Line chart Gross Profit: color='#0B1F3A'

If the PDF generator uses a local color dictionary at the top of the file, update entries there. If colors are hard-coded inline in plot calls, update each inline reference.

### Step 4 — Do NOT create new files or add new dependencies

If you're tempted to create a new centralized color constants file because you feel one is missing, STOP and report instead. Consolidation is out of scope for this change — it's a refactor that belongs with the full post-demo migration.

### Step 5 — Verification after edits

Run the existing test suite:
- `npm test` or `yarn test` or `pnpm test` in frontend (check package.json for the correct script)
- `pytest backend/tests/` or the project's Python test command

For snapshot tests where the only difference is a color hex value, regenerate the snapshot and include it in the commit. For anything else that fails, STOP and report.

### Step 6 — Visual QA

I will verify the live UI and PDF export manually. Do not add screenshots or launch a dev server. Just confirm:

- Edits applied cleanly with no merge conflicts or syntax errors
- Linter passes (`npm run lint` or equivalent)
- TypeScript compiles if TS is in use
- Git status shows only the expected files modified

## Commit message

When edits are complete and tests pass, create one commit:

```
Align Cygnus chart data colors with v4 visual identity spec

- Revenue / primary series: previous value → #2E86C1 Financial Blue
- COGS / negative series: previous value → #C0392B at 65% opacity
- Gross Profit / derived series: verified #0B1F3A Navy (unchanged)
- DVA Shareholders #7EC8E3 preserved as documented DVA-specific variant
- Typography, CSS custom properties, and brand accent unchanged — those belong to the post-demo full migration

Spec references:
- visual-identity-content.md v4 Section 3 and Section 8
- product-vision-architecture.md Section 13.4
```

Replace "previous value" in the commit message with the actual hex values identified in discovery, so the git log captures the before/after cleanly.

## If you get stuck, STOP and report. Specifically:

- If a chart component uses a color that discovery didn't anticipate (e.g., a gradient, a function-generated color, or a theme-derived color), STOP and ask
- If the same hex value appears in both chart data and UI chrome contexts (e.g., `#0E8F9A` used as both Revenue bar fill and as section-label text color), STOP and ask — the replacement strategy differs per context
- If a test fails in a way that isn't just a color-snapshot mismatch, STOP and report
- If the PDF generator uses a chart color palette library (Seaborn palettes, ColorBrewer, etc.) instead of hard-coded hex, STOP and describe what you found
- If you find charts that use MORE than three data colors (e.g., a chart with five series), STOP and report — that may be the DVA stakeholder chart or a multi-category comparison that needs case-by-case guidance
```

---

## Expected scope

Based on the design system as documented:

- **If centralized chart theme exists:** 1 file edited, 3 hex replacements, 10-minute change
- **If colors are scattered across components:** 5-15 component files, 15-40 replacements, 20-30 minute change
- **PDF generator:** ~1 file (`backend/report_pdf.py`), 3-5 replacements
- **Snapshot tests:** 0-5 regenerations

If Part 1 discovery shows 50+ files with chart-related hex values, that's a signal the chart color system has drifted badly and consolidation is warranted — but that consolidation belongs with the full post-demo migration, not this surgical change. In that case, report and we'll decide whether to proceed with scattered edits or defer.

## Why this is a separate prompt from the full v4 migration

Three reasons, worth naming explicitly:

1. **External-facing urgency.** If the demos land in the next two weeks, the chart colors in the live product directly contradict the freshly-published v4 spec. The full migration can wait for post-demo; the chart contradiction should not.

2. **Risk isolation.** The full migration touches typography (character metrics shift), CSS custom properties (every component that references the old variable name breaks), and brand colors simultaneously. Debugging a chart issue mixed into that change is much harder than debugging it in isolation.

3. **Builder's Trap discipline.** The full migration is a multi-hour commitment with no external-facing payoff. This chart fix is 15-30 minutes with an immediate payoff: the live product stops contradicting the content spec. That's a different cost-benefit profile and deserves a different scheduling decision.
