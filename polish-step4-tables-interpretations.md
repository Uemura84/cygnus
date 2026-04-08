# Polish — Step 4 Per-Section Metric Tables + LLM Chart Interpretations

> **What this is:** Build spec for Claude Code. Two enhancements to Step 4:
> (1) add compact metric tables above each chart section (Balance Sheet, Cash Flow),
> (2) add a one-sentence LLM interpretation below each chart.
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 4 frontend + one new backend LLM call. No changes to metric
> computation, detection, or stacking.

---

## 1. Per-Section Metric Tables

### 1.1 Current state

Step 4 has one "Annual Metrics" table at the top showing profitability metrics
(7 rows × 6 years). Balance sheet and cash flow metrics only appear as charts
further down the page — no tabular view of the actual values.

### 1.2 Target state

Each chart section gets its own compact metrics table placed above the charts
in that section. Three tables total:

**Profitability Metrics table (existing — keep as-is):**
Already shows: Revenue YoY, COGS YoY, Gross Margin, EBIT Margin, EBITDA Margin,
COGS/Revenue, SGA/Revenue.

**Balance Sheet Metrics table (new — 6 rows):**
Place above the Balance Sheet Health charts.

```
BALANCE SHEET METRICS (ANNUAL)

METRIC                    2020        2021        2022        2023        2024        2025
─────────────────────────────────────────────────────────────────────────────────────────
Current Ratio             1.18×       1.54×       1.37×       1.42×       1.10×       0.59×
Quick Ratio               0.88×       0.98×       0.83×       0.96×       0.80×       0.52×
Net Debt (BRL M)          28,450      25,890      22,340      27,120      38,450      42,130
Debt / EBITDA             4.2×        1.1×        2.8×        9.3×        8.9×        12.1×
Working Capital (BRL M)   4,890       13,450      10,230      12,010      8,340       -5,670
ROA %                     -8.2%       14.3%       -0.8%       -5.2%       -11.8%      -12.4%
```

**Cash Flow Metrics table (new — 4 rows):**
Place above the Cash Flow Analysis charts.

```
CASH FLOW METRICS (ANNUAL)

METRIC                    2020        2021        2022        2023        2024        2025
─────────────────────────────────────────────────────────────────────────────────────────
Free Cash Flow (BRL M)    1,234       10,560      3,450       -4,890      890         -3,210
OCF / Net Income          -0.8×       0.6×        -3.2×       0.9×        -0.5×       0.4×
Capex / Revenue %         4.8%        3.2%        5.1%        6.3%        5.0%        4.5%
Capex / D&A               0.72×       0.56×       0.92×       1.05×       0.78×       0.68×
```

### 1.3 Design

- Same visual pattern as the existing profitability table
- Section label: JetBrains Mono uppercase, Signal Blue (e.g., "BALANCE SHEET METRICS (ANNUAL)")
- Metric names: DM Sans 400
- Values: JetBrains Mono, right-aligned
- Ratios show × suffix (1.18×), percentages show % suffix, monetary values show BRL M
- None values show "—"

### 1.4 Data source

The values are already computed in Step 4's `balance_sheet_series` and
`cash_flow_series`. The frontend just needs to render them as a table
(same approach as the existing profitability table).

---

## 2. LLM Chart Interpretations

### 2.1 Concept

Below each chart in Step 4, display a one-sentence interpretation generated
by the LLM. This is the "Layer 3" moment — the chart shows the data (Layer 2),
the sentence tells you what it means (Layer 3).

Example:

```
LIQUIDITY RATIOS
[chart]
───
Current ratio declined from 1.5× in 2021 to 0.6× in 2025, falling below the
1.0× threshold — current liabilities now exceed current assets.
```

### 2.2 Implementation: single batch LLM call

**Do NOT make a separate LLM call per chart.** Make one call that receives all
the metric data and generates interpretations for all charts at once.

**When it runs:** After Step 4 metric computation completes, before rendering.
The LLM call happens server-side and the interpretations are returned as part
of the Step 4 API response.

**Caching:** Cache the interpretations alongside the metric data. Same cache
key as the Step 4 results. Don't re-run the LLM call on every page view.

### 2.3 Backend: new endpoint or extended Step 4 response

Add a new field to the Step 4 API response:

```json
{
  "time_series": [...],
  "balance_sheet_series": [...],
  "cash_flow_series": [...],
  "chart_interpretations": {
    "margin_trajectory": "Gross margin collapsed from 30.4% in 2021 to 2.2% in 2025...",
    "revenue_cogs_growth": "COGS growth consistently outpaced revenue growth...",
    "liquidity_ratios": "Current ratio declined from 1.5× to 0.6×...",
    "net_debt_trend": "Net debt increased 48% from 2022 to 2025...",
    "working_capital": "Working capital turned negative in 2025...",
    "return_on_assets": "ROA has been negative since 2022...",
    "return_on_equity": "ROE swings reflect near-zero equity base...",
    "ocf_icf_fcf": "Operating cash flow declined 70% from 2021 peak...",
    "free_cash_flow": "FCF turned negative in 2023 and remains volatile...",
    "cash_conversion_cycle": "Cash cycle is stable around 25-30 days...",
    "capex_metrics": "Capex/D&A ratio below 1.0× since 2024..."
  }
}
```

### 2.4 LLM prompt

```
You are a financial analyst interpreting chart data for a CFO.

For each chart below, write exactly ONE sentence (maximum 30 words) describing
what the data shows. Be specific — include the actual numbers, direction of
change, and financial significance. Do not be generic.

Charts and their data:

1. MARGIN TRAJECTORY
   Gross Margin: 19.1% (2020) → 30.4% (2021) → 11.8% (2022) → 4.3% (2023) → 7.8% (2024) → 2.2% (2025)
   EBIT Margin: -0.1% (2020) → 24.7% (2021) → 4.4% (2022) → -4.0% (2023) → -1.4% (2024) → -2.6% (2025)
   COGS/Revenue: 80.8% (2020) → 69.7% (2021) → 88.2% (2022) → 95.7% (2023) → 92.3% (2024) → 97.8% (2025)

2. REVENUE VS. COGS GROWTH
   Revenue YoY: +80.4% (2021) → -8.6% (2022) → -26.9% (2023) → +9.7% (2024) → -8.6% (2025)
   COGS YoY: +55.4% (2021) → +15.8% (2022) → -20.7% (2023) → +5.7% (2024) → -3.2% (2025)

3. LIQUIDITY RATIOS
   Current Ratio: [values per year]
   Quick Ratio: [values per year]

... [continue for all charts]

Respond as a JSON object with chart keys and one-sentence string values.
Do not include any other text.
```

The prompt sends the actual computed metric values (not raw data) so the LLM
interprets the same numbers the user sees in the tables and charts.

### 2.5 Model

Use Claude Sonnet (not Opus) for this call — it's a straightforward interpretation
task that doesn't need the most powerful model. Fast and cheap.

### 2.6 Frontend display

Below each chart, render the interpretation as:

```
─── (thin horizontal rule, rgba(11,31,58,0.07))
[interpretation text]
```

Style:
- Font: DM Sans 400, 13px
- Color: var(--gray) (slate)
- Italic
- Max width matches the chart width
- Subtle presentation — it should feel like a caption, not a headline

### 2.7 Loading state

While the LLM call is in progress, show a subtle loading indicator below each
chart (e.g., a pulsing "..." in slate). The charts themselves render immediately
from the computed metrics — only the interpretations wait for the LLM.

If the LLM call fails, don't show an error — just don't show interpretations.
The charts are self-explanatory without them; the interpretations are a bonus.

### 2.8 Bilingual

The LLM prompt should generate interpretations in the currently selected language.
Check the user's language preference and adjust the prompt:

- EN: "Write in English."
- PT-BR: "Escreva em português brasileiro."

Cache interpretations per language. If the user switches language, a new LLM call
may be needed for the interpretations (or cache both).

---

## 3. Chart List (for reference)

All charts that should have interpretations:

**Profitability section:**
1. Margin Trajectory (Gross Margin, EBIT Margin, COGS/Revenue)
2. Revenue vs. COGS Growth (YoY %)

**Balance Sheet section:**
3. Liquidity Ratios (Current Ratio, Quick Ratio)
4. Net Debt Trend
5. Working Capital
6. Return on Assets (ROA %)
7. Return on Equity (ROE %)

**Cash Flow section:**
8. Operating / Investing / Financing CF
9. Free Cash Flow
10. Cash Conversion Cycle (Days)
11. Capex Metrics (Capex/Revenue, Capex/D&A)

Total: 11 interpretations per LLM call.

---

## 4. What Does NOT Change

- Metric computation logic (Step 4 backend) — unchanged
- Chart rendering (Recharts components) — unchanged except adding the
  interpretation text below each chart
- Steps 5–9 — unchanged
- Detection algorithms — unchanged
- Existing profitability metrics table — unchanged (keep as-is, don't move it)

---

## 5. Testing

### 5.1 Metric tables
- [ ] Balance Sheet Metrics table renders above BS charts (6 rows × 6 years)
- [ ] Cash Flow Metrics table renders above CF charts (4 rows × 6 years)
- [ ] Values match the chart data (no discrepancy between table and chart)
- [ ] None values show "—"
- [ ] Correct units (×, %, BRL M)
- [ ] Tables render correctly for Braskem, Vale, Votorantim

### 5.2 LLM interpretations
- [ ] Single LLM call generates interpretations for all 11 charts
- [ ] Interpretations appear below each chart as italic captions
- [ ] Interpretations reference specific numbers from the data
- [ ] Interpretations are cached (don't re-call on page refresh)
- [ ] Loading state shows while LLM call is in progress
- [ ] Charts render immediately (don't wait for LLM)
- [ ] Graceful failure (no interpretation shown if LLM fails)
- [ ] Bilingual (EN interpretations when EN selected, PT-BR when PT-BR selected)
- [ ] Interpretations display for Braskem, Vale, Votorantim

### 5.3 Regression
- [ ] All regression tests pass
- [ ] Full pipeline works end-to-end for all 3 companies
- [ ] Steps 5–9 unaffected

---

## 6. Definition of Done

- [ ] Balance Sheet Metrics table added above BS chart section
- [ ] Cash Flow Metrics table added above CF chart section
- [ ] Single batch LLM call generates 11 chart interpretations
- [ ] Interpretations displayed as italic captions below each chart
- [ ] Interpretations cached with Step 4 results
- [ ] Bilingual (EN + PT-BR based on user language)
- [ ] Graceful failure if LLM call fails
- [ ] All 3 test companies work correctly
- [ ] All regressions pass
