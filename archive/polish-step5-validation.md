# Polish — Step 5 Metric Validation Overhaul

> **What this is:** Build spec for Claude Code. Renames Step 5, collapses the
> cash reconciliation warnings into a summary, and adds plausibility checks
> for balance sheet and cash flow metrics.
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 5 frontend + backend plausibility logic. No changes to
> detection, stacking, or AI prompts.

---

## 1. Rename Step 5

### 1.1 Change

"Data Quality Scan" → "Metric Validation"

Update in:
- Sidebar step label
- Step header text
- i18n files (EN + PT-BR)

PT-BR: "Validação de Métricas"

### 1.2 Update description text

Current: "Validates computed metrics against sector-specific plausibility bounds.
Flags out-of-range values and assigns confidence scores that gate downstream
pattern detection."

Updated: "Confirms the computed financial metrics are trustworthy before running
pattern detection. Validates plausibility bounds across profitability, balance
sheet, and cash flow metrics, and checks cross-statement consistency."

PT-BR: "Confirma que as métricas financeiras calculadas são confiáveis antes de
executar a detecção de padrões. Valida limites de plausibilidade em métricas de
rentabilidade, balanço patrimonial e fluxo de caixa, e verifica a consistência
entre demonstrações."

---

## 2. Collapse Cash Reconciliation Warnings

### 2.1 Problem

The cash reconciliation check produces 21 individual MEDIUM warnings — one per
quarterly period — all showing the same pattern (opening cash + net flow ≠ closing
cash). Every period has a gap, which means this is a systematic characteristic
(likely FX effects on Braskem's USD-denominated cash), not 21 separate problems.

Displaying 21 identical amber rows makes the step look alarming when the actual
situation is benign.

### 2.2 Fix

When all warnings for a check type have the same severity, collapse them into
a single summary card:

```
Cash Reconciliation    21 of 21 periods    All MEDIUM

Average gap: BRL 1.8M (range: BRL 305K – BRL 6.7M)
Gaps are consistent across all periods, suggesting a systematic cause
(e.g., FX translation effects, restricted cash, or items outside the
three-line cash flow summary).

▶ Show individual periods
```

The "Show individual periods" toggle expands to the full table (current behavior)
for anyone who wants the detail.

### 2.3 Logic

```python
# Pseudocode for summary collapse
if all warnings in a check group have the same severity:
    show summary card with:
        - check name
        - "{N} of {M} periods" count
        - severity badge
        - average gap value
        - min/max gap range
        - a one-line contextual note about likely cause
        - collapsible detail table (default collapsed)
else:
    show the current grouped table (some HIGH, some MEDIUM = keep expanded)
```

The contextual note can be a simple template based on the check type:
- Cash Reconciliation: "Consistent gaps suggest FX translation effects or
  items outside the three-line cash flow summary."
- D&A Consistency: "Minor differences between income statement and cash flow
  D&A values are common due to rounding or classification."
- Balance Sheet Equation: "Any imbalance indicates a potential account mapping
  error requiring investigation."

### 2.4 Frontend

The `CheckGroup` component from Sprint 4 already handles collapsible groups.
Extend it to detect the "all same severity" case and render the summary card
instead of the expanded table.

---

## 3. Add Balance Sheet Plausibility Checks

### 3.1 Current state

Plausibility checks only cover profitability metrics (Gross Margin, EBIT Margin,
COGS/Revenue, SGA/Revenue). No checks for balance sheet metrics.

### 3.2 New checks

Add a "Balance Sheet Plausibility" section below the existing profitability checks:

```
BALANCE SHEET PLAUSIBILITY

METRIC                  MIN       MAX       RATIONALE
──────────────────────────────────────────────────────────────────────────────────
Current Ratio           0.1×      10×       Below 0.1 suggests data error;
                                            above 10× is implausible for
                                            capital-intensive companies.

Debt / EBITDA           -5×       30×       Negative values occur with negative
                                            EBITDA; above 30× suggests data
                                            error or near-zero EBITDA.

Net Debt (sign)         —         —         Not a range check — flags if net
                                            debt is negative (net cash position)
                                            as informational, not an error.

Working Capital         —         —         Flags if working capital swings
Change %                                   more than 200% year-over-year,
                                            suggesting a data anomaly.

Asset Turnover          0         5×        Above 5× is implausible for
                                            asset-heavy industrials.

ROA %                   -100%     100%      Values outside this range suggest
                                            data scaling errors.

ROE %                   -500%     500%      Extreme values are mathematically
                                            valid with small equity but flag
                                            for review.
```

### 3.3 Implementation

Follow the same pattern as profitability plausibility checks:
- Define bounds as a constant dict in the backend
- Check each metric value against bounds for each period
- Flag violations with MEDIUM severity (out of plausible range)
- Return results in the same format as existing profitability checks

### 3.4 Sector sensitivity

The existing profitability bounds are labeled "(PETROCHEMICAL SECTOR)." The
balance sheet bounds above are general (applicable across industries). Label
them "(INDUSTRIAL / CAPITAL-INTENSIVE)" or similar. For future sector-specific
adapters, these bounds can be overridden.

---

## 4. Add Cash Flow Plausibility Checks

### 4.1 New checks

Add a "Cash Flow Plausibility" section:

```
CASH FLOW PLAUSIBILITY

METRIC                  MIN       MAX       RATIONALE
──────────────────────────────────────────────────────────────────────────────────
OCF / Net Income        -10×      10×       Values outside this range suggest
                                            extreme non-cash adjustments or
                                            data inconsistency.

Capex / Revenue %       0%        50%       Capex above 50% of revenue is
                                            implausible even for capital-
                                            intensive industries.

Capex / D&A             0         5×        Above 5× suggests a major
                                            expansion or data error.

FCF / Revenue %         -100%     100%      Free cash flow exceeding revenue
                                            (positive or negative) flags a
                                            data anomaly.
```

### 4.2 Implementation

Same pattern as profitability and balance sheet checks. Same backend structure.

---

## 5. Update Summary Cards

### 5.1 Current state

Summary cards show: Total Data Points: 24, Clean: 24, Flagged: 0, Quality Score: 100%

These only count profitability data points.

### 5.2 Fix

Update counts to include all three metric types:

```
TOTAL DATA POINTS    CLEAN    FLAGGED    QUALITY SCORE
72                   71       1          98.6%
```

Or break down by section:

```
PROFITABILITY        BALANCE SHEET        CASH FLOW            QUALITY SCORE
24 points · 0 flags  30 points · 1 flag   18 points · 0 flags  98.6%
```

The per-section breakdown is more informative — the user sees which area has
the flag.

---

## 6. i18n

### Step name
- "Metric Validation" / "Validação de Métricas"

### Description
- See Section 1.2

### New section labels
- "Balance Sheet Plausibility" / "Plausibilidade do Balanço Patrimonial"
- "Cash Flow Plausibility" / "Plausibilidade do Fluxo de Caixa"
- "(Industrial / Capital-Intensive)" / "(Industrial / Intensivo em Capital)"

### New metric names (BS)
- "Current Ratio" / "Índice de Liquidez Corrente"
- "Debt / EBITDA" / "Dívida / EBITDA"
- "Net Debt (sign)" / "Dívida Líquida (sinal)"
- "Working Capital Change %" / "Variação do Capital de Giro %"
- "Asset Turnover" / "Giro do Ativo"
- "ROA %" / "ROA %"
- "ROE %" / "ROE %"

### New metric names (CF)
- "OCF / Net Income" / "FCO / Lucro Líquido"
- "Capex / Revenue %" / "Capex / Receita %"
- "Capex / D&A" / "Capex / D&A"
- "FCF / Revenue %" / "FCL / Receita %"

### Cash reconciliation summary
- "Average gap" / "Gap médio"
- "range" / "faixa"
- "Show individual periods" / "Mostrar períodos individuais"
- "Consistent gaps suggest FX translation effects..." / "Gaps consistentes sugerem efeitos de conversão cambial..."

### Summary card labels
- "points" / "pontos"
- "flags" / "alertas"

---

## 7. Testing

### 7.1 Rename
- [ ] Step 5 shows "Metric Validation" in sidebar and header
- [ ] Description text updated
- [ ] PT-BR translation works

### 7.2 Cash reconciliation summary
- [ ] When all warnings have same severity, collapsed into summary card
- [ ] Summary shows average gap, range, and contextual note
- [ ] "Show individual periods" toggle expands to full table
- [ ] When warnings have mixed severity, still shows expanded table

### 7.3 Balance Sheet plausibility
- [ ] 7 BS plausibility checks defined and running
- [ ] Checks display in a new section below profitability checks
- [ ] Section labeled with sector context
- [ ] Out-of-range values flagged with MEDIUM severity
- [ ] Rationale column populated for each check

### 7.4 Cash Flow plausibility
- [ ] 4 CF plausibility checks defined and running
- [ ] Checks display in a new section
- [ ] Section labeled with sector context
- [ ] Out-of-range values flagged

### 7.5 Summary cards
- [ ] Counts include all three metric types
- [ ] Per-section breakdown visible
- [ ] Quality score reflects all checks

### 7.6 Regression
- [ ] All regression tests pass
- [ ] Full pipeline works for Braskem, Vale, Votorantim
- [ ] Steps 6–9 unaffected

---

## 8. Definition of Done

- [ ] Step 5 renamed to "Metric Validation"
- [ ] Description updated (EN + PT-BR)
- [ ] Cash reconciliation warnings collapsed to summary when uniform severity
- [ ] 7 balance sheet plausibility checks implemented
- [ ] 4 cash flow plausibility checks implemented
- [ ] Summary cards updated to include all metric types
- [ ] All labels bilingual
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
