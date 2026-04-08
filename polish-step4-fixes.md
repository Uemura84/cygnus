# Polish — Step 4 Financial Metrics Fixes

> **What this is:** Build spec for Claude Code. Fixes six visual and content issues
> in Step 4 identified during review.
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 4 frontend only. No analytical changes.

---

## 1. Fix X-Axis Labels on BS and CF Charts

### 1.1 Problem

Balance sheet and cash flow charts show quarterly data with year-only labels,
creating a wall of repeated years: "2020 2020 2020 2020 2021 2021 2021 2021..."
The profitability charts show annual data only and don't have this issue.

### 1.2 Fix

**Option A (recommended): Show annual data only on BS and CF charts.**

Filter the chart data to annual periods only (DFP data), matching the profitability
charts. This gives 6 clean data points per chart (2020–2025), consistent x-axis
labels, and avoids the quarterly label clutter.

Quarterly data is still available in the Step 3 summary tables and in the
detection algorithms (Step 6). The charts are for visual trend communication,
not granular analysis.

**Option B (alternative): Format quarterly labels properly.**

If quarterly granularity is kept, format labels as "Q1'20", "Q2'20", etc. Show
year labels only at Q1 of each year with minor ticks for Q2–Q4. This preserves
the data but requires more x-axis formatting work.

Pick Option A unless there's a strong reason to show quarterly data in charts.

### 1.3 Affected charts

All 8 BS + CF charts from Sprint 2:
- Liquidity Ratios
- Net Debt Trend
- Working Capital
- Return on Assets & Equity
- Operating / Investing / Financing
- Free Cash Flow
- Cash Conversion Cycle
- Capex Metrics

---

## 2. Fix ROE Chart Scale

### 2.1 Problem

The Return on Assets & Equity chart shows ROE swinging from +400% to -300%.
This is mathematically correct (Braskem's equity is small relative to net income
swings, especially near negative equity), but it makes the chart unreadable and
compresses ROA into a flat line.

### 2.2 Fix

Separate ROA and ROE into two independent charts:

**Chart A: Return on Assets (ROA %)**
- Line chart, single series, normal y-axis scale
- Reference line at 0%

**Chart B: Return on Equity (ROE %)**
- Line chart, single series
- Cap y-axis at -100% to +100%
- If values exceed the cap, add a note: "Values clipped — actual range: -312% to +421%"
  in JetBrains Mono, slate, 11px, below the chart
- Clip markers at the cap boundary so the user sees the line hitting the edge

This gives ROA a readable scale and ROE a bounded view that still communicates
the volatility without destroying the chart.

---

## 3. Fix Financing CF Color (Amber → Blue Ramp)

### 3.1 Problem

The Operating / Investing / Financing chart uses amber (#EF9F27) for Financing CF.
Amber is a severity color in the Cygnus design system — using it for a neutral
data series creates a false "warning" association.

### 3.2 Fix

Replace the three-series colors:

```
Operating CF:   #1e90ff              (Signal Blue — full)
Investing CF:   #E24B4A              (Red — keep, investing is cash outflow)
Financing CF:   rgba(30,144,255,0.5) (Signal Blue — 50% opacity)
```

Wait — Investing CF shouldn't be red either, for the same reason. Red is a
severity color. All three should use the blue ramp:

```
Operating CF:   #1e90ff              (Signal Blue — full opacity)
Investing CF:   rgba(30,144,255,0.55)(Signal Blue — 55% opacity)
Financing CF:   rgba(30,144,255,0.3) (Signal Blue — 30% opacity)
```

The opacity differentiation plus the legend labels are sufficient to distinguish
the three series. Positive/negative values already communicate the cash flow
direction — no need for color to encode "good vs. bad."

---

## 4. Fix Cash Conversion Cycle Chart Colors

### 4.1 Problem

The Cash Conversion Cycle chart uses amber for Inventory Days and red for
Payable Days. These are neutral data series, not severity indicators.

### 4.2 Fix

Replace with the blue ramp:

```
Receivable Days:  #1e90ff              (Signal Blue — full)
Inventory Days:   rgba(30,144,255,0.55)(Signal Blue — 55%)
Payable Days:     rgba(30,144,255,0.35)(Signal Blue — 35%)
Cash Cycle:       #1e90ff dashed       (Signal Blue — full, dashed line to distinguish)
```

The dashed line for Cash Cycle (which is a derived metric from the other three)
visually distinguishes it as a composite without using a different color.

---

## 5. Update Description Text

### 5.1 Problem

The description says: "Calculates derived metrics: Gross Margin, EBIT Margin,
COGS/Revenue, and period-over-period changes."

This only mentions profitability metrics. Step 4 now computes balance sheet
metrics (liquidity, leverage, efficiency) and cash flow metrics (FCF, capex
ratios, earnings quality).

### 5.2 Fix

Update to: "Computes derived financial metrics across profitability (margins,
cost ratios), balance sheet health (liquidity, leverage, efficiency), and cash
flow quality (free cash flow, capex intensity, earnings conversion)."

PT-BR: "Calcula métricas financeiras derivadas em rentabilidade (margens, índices
de custo), saúde do balanço patrimonial (liquidez, alavancagem, eficiência) e
qualidade do fluxo de caixa (fluxo de caixa livre, intensidade de capex, conversão
de resultados)."

---

## 6. Update "Metrics Computed" Count

### 6.1 Problem

The summary card shows "Metrics Computed: 6" — this only counts profitability
metrics. With balance sheet and cash flow metrics, the total is much higher.

### 6.2 Fix

Either:

**Option A: Show total count across all sections.**
"Metrics Computed: 25" (or whatever the actual total is — count all derived
metrics from profitability + BS + CF).

**Option B (recommended): Break down by section.**
Replace the single "Metrics Computed: 6" card with three cards:

```
PROFITABILITY METRICS    BALANCE SHEET METRICS    CASH FLOW METRICS
7                        12                       4
```

This immediately tells the user what kind of analysis was performed across
all three financial statement dimensions.

The "Periods: 6" card stays as-is (or could show "6 annual + 24 quarterly"
if the data includes both).

---

## 7. i18n

Update both EN and PT-BR for:
- Step 4 description text (Section 5)
- "Profitability Metrics" / "Métricas de Rentabilidade"
- "Balance Sheet Metrics" / "Métricas do Balanço"
- "Cash Flow Metrics" / "Métricas de Fluxo de Caixa"
- "Return on Assets" / "Retorno sobre Ativos"
- "Return on Equity" / "Retorno sobre Patrimônio"
- "Values clipped" / "Valores limitados"
- "actual range" / "faixa real"

---

## 8. Testing

- [ ] BS and CF charts show annual data only (no repeated year labels)
- [ ] X-axis shows clean year labels (2020, 2021, 2022, 2023, 2024, 2025)
- [ ] ROA and ROE are separate charts
- [ ] ROE chart y-axis capped at -100% to +100%
- [ ] ROE clipping note appears when values exceed range
- [ ] Operating/Investing/Financing chart uses blue ramp only (no amber, no red)
- [ ] Cash Conversion Cycle chart uses blue ramp only
- [ ] Cash Cycle line is dashed to distinguish from components
- [ ] Description text mentions all three metric categories
- [ ] Metrics count shows per-section breakdown
- [ ] Profitability charts unchanged (still annual, same colors)
- [ ] All charts render correctly for Braskem
- [ ] All charts render correctly for Vale
- [ ] All charts render correctly for Votorantim
- [ ] Bilingual labels work
- [ ] All regression tests pass

---

## 9. Definition of Done

- [ ] BS and CF charts show annual data only
- [ ] ROA and ROE split into separate charts with ROE capping
- [ ] All chart series use Cygnus blue ramp (no amber/red for data series)
- [ ] Description text updated
- [ ] Metrics count shows per-section breakdown
- [ ] All labels bilingual
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
