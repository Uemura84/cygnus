# Sprint 3 — Detection Algorithms + Signal Stacking + AI Agent Update

> **What this is:** Build spec for Claude Code. This sprint adds Module 2 (Balance Sheet
> Health) and Module 3 (Cash Flow Quality) detection algorithms to Step 6, builds the
> cross-module signal stacking engine, and updates the AI agent prompts (Steps 7–9) to
> reason about the full range of findings.
>
> **Branch:** Continue on `phase3-common-model`.
>
> **Depends on:** Sprint 2 complete — CVM adapter parses all three financial statements,
> Step 4 computes derived metrics, `IMPLEMENTED_MODULES` guard exists in Step 6.
>
> **Success criteria:**
> 1. Step 6 runs balance sheet and cash flow detection alongside profitability detection
> 2. Cross-module signal stacking produces diagnoses when signals from 2+ modules combine
> 3. Steps 7–9 receive and reason about all findings (profitability + BS + CF + stacked)
> 4. Sprint 1 regression tests still pass for profitability findings
> 5. New findings are visible in the Step 6 UI for Braskem, Vale, and Votorantim
>
> **Reference:** `product-vision-architecture.md` (Sections 4, 5, 7)

---

## 0. Pre-Work: Sprint 2 Regression Baseline

Sprint 1 established regression baselines for profitability output (Step 4 metrics,
Step 6 findings, risk scores). Sprint 2 added balance sheet and cash flow data but
didn't create baselines for the new data.

### 0.1 Capture Sprint 2 baselines

Before writing any Sprint 3 code, capture the current Step 4 output for all three
companies including the new balance sheet and cash flow series:

```
tests/regression/
  braskem_baseline_s2.json       # NEW
  vale_baseline_s2.json          # NEW
  votorantim_baseline_s2.json    # NEW
```

Each file should contain:

```json
{
  "company_name": "BRASKEM S.A.",
  "snapshot_sprint": "sprint2",
  "step4_balance_sheet_series": [...],
  "step4_cash_flow_series": [...],
  "step5_cross_statement_warnings": [...]
}
```

This validates that Sprint 3's detection changes don't accidentally alter the
underlying metric computation from Sprint 2.

### 0.2 Sprint 2 structural fix: update determine_active_modules()

The Sprint 2 report shows `determine_active_modules()` still only checks for
profitability columns. It should now also check for balance sheet and cash flow
data availability. Update it:

```python
def determine_active_modules(df=None, company_financials=None) -> list[str]:
    active = []

    # Module 1: Profitability — check DataFrame columns (existing logic)
    if df is not None:
        if any(col in df.columns for col in ["Gross_Margin_pct", "EBIT_Margin_pct", "revenue"]):
            active.append("profitability")

    # Module 2: Balance Sheet Health — check CompanyFinancials
    if (company_financials is not None
            and company_financials.balance_sheets
            and len(company_financials.balance_sheets) >= 4):
        active.append("balance_sheet_health")

    # Module 3: Cash Flow Quality — check CompanyFinancials
    if (company_financials is not None
            and company_financials.cash_flows
            and len(company_financials.cash_flows) >= 4):
        active.append("cash_flow_quality")

    return active
```

The function needs to accept `CompanyFinancials` in addition to (or instead of)
the DataFrame. Adjust the call sites in Step 6 accordingly. The
`IMPLEMENTED_MODULES` intersection already exists from Sprint 2 — once this
function returns all three modules, the guard lets Sprint 3's new algorithms run.

---

## 1. Module 2: Balance Sheet Health Detection

### 1.1 Input

Balance sheet derived metrics from Step 4's `balance_sheet_series` (already computed
in Sprint 2). The detector receives the time series and looks for patterns across
periods.

### 1.2 Detection algorithms (7 patterns)

Each algorithm produces findings with the same structure as Module 1: a finding code,
severity, category, description, metric values, and materiality estimate where
applicable.

**All finding codes for Module 2 are prefixed with `BS_` to distinguish from
Module 1's profitability findings.**

---

#### 1.2.1 LEVERAGE_ESCALATION

**What it detects:** Debt/EBITDA ratio trending upward or exceeding danger thresholds.

**Logic:**
- Compute debt_to_ebitda for each period (already in BS series)
- **Threshold trigger:** Latest debt_to_ebitda > 3.5× → flag HIGH
- **Trend trigger:** debt_to_ebitda increased by more than 1.0× over the last 3 periods → flag MEDIUM
- **Critical trigger:** Latest debt_to_ebitda > 5.0× → flag CRITICAL

**Finding code:** `BS_LEVERAGE_ESCALATION`
**Category:** Core
**Materiality:** Net debt value (absolute BRL amount at stake)

---

#### 1.2.2 WORKING_CAPITAL_DETERIORATION

**What it detects:** Receivable days, inventory days, or cash conversion cycle growing.

**Logic:**
- Compute trend (linear regression or simple start-to-end comparison) for:
  - receivable_days
  - inventory_days
  - cash_conversion_cycle
- **Threshold triggers:**
  - Receivable days > 90 → MEDIUM, > 120 → HIGH
  - Inventory days increased > 20% over analysis period → MEDIUM
  - Cash conversion cycle increased > 15 days over analysis period → MEDIUM
- **Compound trigger:** If 2+ of the three sub-metrics are deteriorating simultaneously → HIGH

**Finding code:** `BS_WORKING_CAPITAL_DETERIORATION`
**Category:** Core
**Materiality:** Estimate working capital increase in BRL (change in working_capital between first and last period)

---

#### 1.2.3 LIQUIDITY_STRESS

**What it detects:** Current ratio declining toward or below 1.0.

**Logic:**
- Track current_ratio over time
- **Threshold triggers:**
  - Current ratio < 1.0 → HIGH (liabilities exceed current assets)
  - Current ratio < 1.2 → MEDIUM (approaching stress zone)
  - Current ratio declining > 0.3 over the analysis period → MEDIUM (trajectory)
- **Quick ratio cross-check:** If quick_ratio < 0.8 while current_ratio > 1.0, flag MEDIUM
  (inventories are masking liquidity weakness)

**Finding code:** `BS_LIQUIDITY_STRESS`
**Category:** Core
**Materiality:** Working capital value (negative = direct measure of shortfall)

---

#### 1.2.4 ASSET_EFFICIENCY_DECLINE

**What it detects:** ROA or asset turnover declining over time.

**Logic:**
- Compute trend for return_on_assets and asset_turnover
- **Threshold triggers:**
  - ROA declining > 2pp/year over 3+ periods → MEDIUM
  - Asset turnover declining > 15% over analysis period → MEDIUM
  - Both declining simultaneously → HIGH

**Finding code:** `BS_ASSET_EFFICIENCY_DECLINE`
**Category:** Supporting
**Materiality:** Estimate revenue gap if asset turnover had remained constant
(delta_turnover × current_total_assets)

---

#### 1.2.5 CASH_CONVERSION_CYCLE_EXPANSION

**What it detects:** Cash conversion cycle expanding, indicating the company takes
longer to convert operations to cash.

**Logic:**
- Track cash_conversion_cycle over time
- **Threshold triggers:**
  - CCC expanded > 20 days over analysis period → MEDIUM
  - CCC expanded > 40 days → HIGH
  - CCC negative (common in retail/services) turning positive → MEDIUM (structural shift)
- **Decomposition:** Report which component drove the change (receivables, inventory,
  or payables) by comparing the deltas

**Finding code:** `BS_CCC_EXPANSION`
**Category:** Supporting
**Materiality:** Estimate cash tied up = (CCC change in days / 365) × annual revenue

**Note:** This overlaps with WORKING_CAPITAL_DETERIORATION. If both fire, the stacking
engine should recognize the overlap. Keep both as separate findings — the stacking
rules handle deduplication at the diagnosis level.

---

#### 1.2.6 DEBT_MATURITY_CONCENTRATION

**What it detects:** High proportion of debt maturing in the short term.

**Logic:**
- Compute short_term_debt / (short_term_debt + long_term_debt) ratio
- **Threshold triggers:**
  - Ratio > 0.4 → MEDIUM (40%+ of debt is short-term)
  - Ratio > 0.6 → HIGH (majority of debt is short-term)
  - Ratio increased > 15pp over analysis period → MEDIUM (shifting toward short-term)

**Finding code:** `BS_DEBT_MATURITY_CONCENTRATION`
**Category:** Supporting
**Materiality:** Short-term debt value (BRL amount that needs refinancing soon)

**Note:** Requires both short_term_debt and long_term_debt to be non-None. Skip
this check if either is missing (some companies in CVM don't break out debt maturity
in the standard accounts).

---

#### 1.2.7 EQUITY_EROSION

**What it detects:** Retained earnings declining or total equity shrinking.

**Logic:**
- Track total_equity and retained_earnings over time
- **Threshold triggers:**
  - Total equity declined > 20% over analysis period → MEDIUM
  - Total equity declined > 40% → HIGH
  - Retained earnings negative (accumulated losses) → HIGH
  - Total equity negative → CRITICAL (technically insolvent)

**Finding code:** `BS_EQUITY_EROSION`
**Category:** Core
**Materiality:** Equity change in BRL (absolute decline)

---

### 1.3 Module registration

Add `"balance_sheet_health"` to `IMPLEMENTED_MODULES` in Step 6:

```python
IMPLEMENTED_MODULES = ["profitability", "balance_sheet_health"]
```

---

## 2. Module 3: Cash Flow Quality Detection

### 2.1 Input

Cash flow derived metrics from Step 4's `cash_flow_series`. Same pattern as Module 2.

**All finding codes for Module 3 are prefixed with `CF_`.**

---

#### 2.1.1 EARNINGS_QUALITY_GAP

**What it detects:** Operating cash flow diverging from net income, indicating
reported earnings aren't converting to cash.

**Logic:**
- Track ocf_to_net_income ratio over time
- **Threshold triggers:**
  - Latest OCF/NI < 0.5 → HIGH (less than half of earnings converting to cash)
  - Latest OCF/NI < 0.8 → MEDIUM
  - OCF/NI declining > 0.3 over analysis period → MEDIUM (trend)
  - OCF positive but net income negative (or vice versa) → HIGH (sign divergence)

**Finding code:** `CF_EARNINGS_QUALITY_GAP`
**Category:** Core
**Materiality:** Absolute gap = |OCF - net_income| for the latest period

---

#### 2.1.2 CAPEX_STARVATION

**What it detects:** Company underinvesting relative to depreciation or revenue.

**Logic:**
- Track capex_to_depreciation and capex_to_revenue over time
- **Threshold triggers:**
  - capex_to_depreciation < 0.5 → HIGH (spending less than half of depreciation)
  - capex_to_depreciation < 0.8 → MEDIUM
  - capex_to_revenue declining > 30% over analysis period → MEDIUM
  - capex_to_depreciation < 1.0 for 3+ consecutive periods → MEDIUM (sustained harvest mode)

**Finding code:** `CF_CAPEX_STARVATION`
**Category:** Core
**Materiality:** Estimate investment gap = D&A - |capex| for latest period (how much
the company is underinvesting relative to asset consumption)

---

#### 2.1.3 FREE_CASH_FLOW_EROSION

**What it detects:** Free cash flow declining or persistently negative.

**Logic:**
- Track free_cash_flow over time
- **Threshold triggers:**
  - FCF negative for 3+ consecutive periods → HIGH
  - FCF negative for 2 consecutive periods → MEDIUM
  - FCF positive but declining > 50% over analysis period → MEDIUM
  - FCF turned from positive to negative → MEDIUM

**Finding code:** `CF_FCF_EROSION`
**Category:** Core
**Materiality:** Latest FCF value (negative = cash burn rate)

---

#### 2.1.4 DEBT_DEPENDENCY

**What it detects:** Company consistently relying on financing (borrowing) to fund
operations.

**Logic:**
- Track financing_cash_flow over time
- **Threshold triggers:**
  - Financing CF positive for 3+ consecutive periods while OCF is negative or
    insufficient to cover investing → HIGH (borrowing to survive)
  - Financing CF positive for 3+ consecutive periods while OCF is positive → MEDIUM
    (borrowing to grow — less concerning but worth flagging)
  - debt_issuance consistently > debt_repayment → MEDIUM

**Finding code:** `CF_DEBT_DEPENDENCY`
**Category:** Supporting
**Materiality:** Cumulative net borrowing over the analysis period
(sum of financing_cash_flow)

---

#### 2.1.5 DIVIDEND_SUSTAINABILITY

**What it detects:** Dividends exceeding free cash flow.

**Logic:**
- Compare dividends_paid (absolute value) to free_cash_flow
- **Threshold triggers:**
  - |dividends| > FCF for 2+ periods → MEDIUM
  - |dividends| > FCF for 3+ periods → HIGH
  - Dividends paid while FCF is negative → HIGH
- **Skip if** dividends_paid is None for all periods (company doesn't pay dividends
  or data not available)

**Finding code:** `CF_DIVIDEND_SUSTAINABILITY`
**Category:** Supporting
**Materiality:** Dividend overshoot = |dividends| - FCF for latest period

---

#### 2.1.6 WORKING_CAPITAL_CASH_DRAIN

**What it detects:** Working capital changes consistently reducing operating cash flow.

**Logic:**
- Track working_capital_change from the cash flow statement over time
- **Threshold triggers:**
  - Working capital change negative (cash drain) for 3+ consecutive periods → MEDIUM
  - Working capital change represents > 30% of OCF (absorbing a large share of
    operating cash) → MEDIUM
  - Both conditions met → HIGH

**Finding code:** `CF_WORKING_CAPITAL_DRAIN`
**Category:** Supporting
**Materiality:** Latest working_capital_change value (negative = cash absorbed)

**Note:** This requires `working_capital_change` on the CashFlow object. If Sprint 2
didn't populate this field (it may be None for companies where keyword matching
didn't find it), skip this check when the field is None.

---

### 2.2 Module registration

Add `"cash_flow_quality"` to `IMPLEMENTED_MODULES`:

```python
IMPLEMENTED_MODULES = ["profitability", "balance_sheet_health", "cash_flow_quality"]
```

---

## 3. Detection Architecture

### 3.1 Where the new algorithms live

Create two new files (or add to existing pattern_detector.py — whichever matches
the codebase structure better):

```
backend/pipeline/
  pattern_detector.py          # existing — Module 1 profitability
  bs_detector.py               # NEW — Module 2 balance sheet health
  cf_detector.py               # NEW — Module 3 cash flow quality
  signal_stacker.py            # NEW — cross-module stacking engine
```

If the codebase is structured differently, follow its conventions. The key is that
each module's detection logic is separable.

### 3.2 Finding structure

All new findings must use the same structure as Module 1 findings so they integrate
seamlessly with Steps 7–9. Each finding should have:

```python
{
    "code": "BS_LEVERAGE_ESCALATION",     # prefixed by module
    "module": "balance_sheet_health",      # NEW field — identifies source module
    "severity": "HIGH",                    # CRITICAL / HIGH / MEDIUM / LOW
    "category": "Core",                    # Core / Supporting / Contextual
    "description": "...",                  # human-readable description
    "metric_name": "debt_to_ebitda",       # primary metric involved
    "metric_values": {...},                # relevant values (current, prior, change)
    "materiality_brl": 15_000_000_000,     # BRL impact estimate
    "periods_affected": ["2023", "2024", "2025"],
    "trend_direction": "deteriorating",    # "deteriorating" / "improving" / "stable"
}
```

The `module` field is new — it identifies which module produced the finding. This is
used by the stacking engine and by the AI agent prompt to organize findings by source.

### 3.3 Integration with existing Step 6 flow

Step 6 currently:
1. Calls `detect_patterns()` for profitability (Module 1)
2. Calls `enrich_findings()` for composite signals
3. Calls `compute_risk_score()`
4. Returns findings + risk score

The new flow:
1. Calls Module 1 profitability detection (existing — unchanged)
2. Calls Module 2 balance sheet detection (NEW)
3. Calls Module 3 cash flow detection (NEW)
4. Calls stacking engine with findings from all modules (NEW)
5. Calls `enrich_findings()` for Module 1 composite signals (existing — unchanged)
6. Calls `compute_risk_score()` on ALL findings (updated)
7. Returns all findings (M1 + M2 + M3 + stacked) + updated risk score

### 3.4 Risk score update

The existing risk score is computed from Module 1 findings only. With three modules
plus stacked signals, the risk score calculation needs to account for all findings.

**Approach:** Keep the existing risk score formula but extend it to include all findings.
The `module` field on each finding allows grouping by source if needed. Stacked diagnoses
(FINANCIAL_DISTRESS_RISK, etc.) should carry the highest weight since they represent
cross-module confirmation.

Suggested weighting:
- Individual findings: current weighting (unchanged)
- Stacked diagnoses with severity CRITICAL: weight × 1.5
- Stacked diagnoses with severity HIGH: weight × 1.3

The exact weighting is less important than ensuring stacked signals visibly elevate the
risk score. Adjust if the results feel wrong during testing.

### 3.5 Handling None/missing data

Many balance sheet and cash flow fields may be None for some companies (Sprint 2's
keyword matching is best-effort). Every detection algorithm must:
- Check that required fields are not None before computing
- Skip the check entirely if required data is missing (don't flag absence as a finding)
- Log a debug message when skipping due to missing data

---

## 4. Cross-Module Signal Stacking Engine

### 4.1 Purpose

Individual signals from Modules 1, 2, and 3 are evidence. Stacked signals are a
diagnosis. The stacking engine looks for combinations of findings across modules
that together tell a bigger story than any individual finding.

### 4.2 Signal mapping

Each stacking rule references finding codes from the individual modules. The stacking
engine needs to map from the abstract signal names in the rules to actual finding codes:

```python
SIGNAL_MAP = {
    # Profitability signals (Module 1)
    "margin_compression": ["MARGIN_COMPRESSION", "GROSS_MARGIN_DECLINE",
                           "EBITDA_MARGIN_DECLINE"],
    "cost_drift": ["COGS_DRIFT", "COGS_RATIO_INCREASE"],
    "revenue_growth": ["REVENUE_GROWTH"],
    "margin_expansion": ["MARGIN_EXPANSION", "GROSS_MARGIN_IMPROVEMENT"],

    # Balance sheet signals (Module 2)
    "leverage_escalation": ["BS_LEVERAGE_ESCALATION"],
    "inventory_build": ["BS_WORKING_CAPITAL_DETERIORATION"],
    "receivable_days_growing": ["BS_WORKING_CAPITAL_DETERIORATION",
                                 "BS_CCC_EXPANSION"],
    "leverage_reduction": ["BS_LEVERAGE_ESCALATION"],  # inverse — check trend_direction

    # Cash flow signals (Module 3)
    "negative_fcf": ["CF_FCF_EROSION"],
    "positive_fcf": ["CF_FCF_EROSION"],  # inverse — check trend_direction
    "capex_decline": ["CF_CAPEX_STARVATION"],
}
```

**Important:** Some mappings reference the same finding code but check the
`trend_direction` field to determine polarity (e.g., "leverage_reduction" maps to
BS_LEVERAGE_ESCALATION but only matches when trend_direction is "improving").

Inspect the actual Module 1 finding codes in the current `pattern_detector.py` to
confirm the profitability signal names. The mapping above is approximate — use the
real codes from the codebase.

### 4.3 Stacking rules

```python
STACKING_RULES = [
    {
        "diagnosis": "FINANCIAL_DISTRESS_RISK",
        "requires": {
            "profitability": ["margin_compression", "cost_drift"],
            "balance_sheet": ["leverage_escalation"],
            "cash_flow": ["negative_fcf"],
        },
        "min_modules": 2,
        "severity": "CRITICAL",
        "narrative_en": "The company is deteriorating operationally and has no financial cushion. Multiple signals confirm distress risk.",
        "narrative_pt": "A empresa está se deteriorando operacionalmente e não possui colchão financeiro. Múltiplos sinais confirmam risco de estresse financeiro.",
    },
    {
        "diagnosis": "WORKING_CAPITAL_TRAP",
        "requires": {
            "profitability": ["cost_drift"],
            "balance_sheet": ["inventory_build", "receivable_days_growing"],
        },
        "min_modules": 2,
        "severity": "HIGH",
        "narrative_en": "Cost pressure is compounded by working capital accumulation. The company is not just facing margin squeeze — it is also tying up cash in receivables and inventory.",
        "narrative_pt": "A pressão de custos é agravada pelo acúmulo de capital de giro. A empresa não enfrenta apenas compressão de margens — também está imobilizando caixa em recebíveis e estoques.",
    },
    {
        "diagnosis": "LOW_QUALITY_GROWTH",
        "requires": {
            "profitability": ["revenue_growth", "margin_compression"],
            "cash_flow": ["capex_decline"],
        },
        "min_modules": 2,
        "severity": "HIGH",
        "narrative_en": "Revenue is growing but profitability is declining and the company has stopped investing. Growth may be low-quality — buying revenue at the expense of margin and future capacity.",
        "narrative_pt": "A receita está crescendo mas a rentabilidade está caindo e a empresa parou de investir. O crescimento pode ser de baixa qualidade — comprando receita às custas de margem e capacidade futura.",
    },
    {
        "diagnosis": "CONFIRMED_RECOVERY",
        "requires": {
            "profitability": ["margin_expansion"],
            "balance_sheet": ["leverage_reduction"],
            "cash_flow": ["positive_fcf"],
        },
        "min_modules": 2,
        "severity": "LOW",
        "narrative_en": "Recovery is confirmed across profitability, leverage, and cash generation. The turnaround appears real.",
        "narrative_pt": "A recuperação é confirmada em rentabilidade, alavancagem e geração de caixa. A reversão parece ser real.",
    },
]
```

### 4.4 Stacking algorithm

```python
def stack_signals(all_findings: list[dict]) -> list[dict]:
    """
    Check each stacking rule against the combined findings from all modules.
    Returns a list of stacked diagnosis findings.
    """
    stacked = []

    for rule in STACKING_RULES:
        modules_matched = 0
        signals_matched = {}

        for module_name, required_signals in rule["requires"].items():
            module_signals_found = []
            for signal_name in required_signals:
                # Look up which finding codes map to this signal
                finding_codes = SIGNAL_MAP.get(signal_name, [])
                # Check if any matching finding exists in all_findings
                match = _find_matching_finding(all_findings, finding_codes, signal_name)
                if match:
                    module_signals_found.append(match)

            if module_signals_found:
                modules_matched += 1
                signals_matched[module_name] = module_signals_found

        if modules_matched >= rule["min_modules"]:
            stacked.append({
                "code": rule["diagnosis"],
                "module": "stacked",
                "severity": rule["severity"],
                "category": "Diagnosis",      # NEW category for stacked signals
                "description": rule["narrative_en"],
                "description_pt": rule["narrative_pt"],
                "contributing_signals": signals_matched,
                "modules_involved": list(signals_matched.keys()),
                "trend_direction": "deteriorating" if rule["severity"] in ["CRITICAL", "HIGH"] else "improving",
            })

    return stacked
```

### 4.5 Where stacking runs

In Step 6, after all module detections complete:

```python
# After Module 1, 2, 3 detection
all_findings = profitability_findings + bs_findings + cf_findings
stacked_diagnoses = stack_signals(all_findings)
all_findings_with_stacked = all_findings + stacked_diagnoses
```

Stacked diagnoses are appended to the findings list and appear in the API response
alongside individual findings. They are distinguished by `module: "stacked"` and
`category: "Diagnosis"`.

---

## 5. Step 6 Frontend Updates

### 5.1 Finding cards for new modules

The existing Step 6 UI shows finding cards with severity-colored left borders and
monospace finding code tags. The same pattern applies to BS_ and CF_ findings.

**Organize findings by module:**

Instead of one flat list, group findings into sections:
- **Profitability Findings** (existing)
- **Balance Sheet Findings** (new)
- **Cash Flow Findings** (new)
- **Cross-Module Diagnoses** (new — stacked signals)

Each section has a JetBrains Mono section label. If a module produced no findings,
show "No issues detected" in that section.

### 5.2 Stacked diagnosis cards

Stacked diagnosis cards should be visually distinct from individual findings:
- Use the same card pattern but with a subtle background tint (e.g., blue-dim)
  to distinguish diagnoses from individual findings
- Show the contributing signals as a compact list within the card
- Show which modules contributed (e.g., "Profitability + Balance Sheet + Cash Flow")

### 5.3 Risk gauge update

The risk gauge already exists. It should now reflect the updated risk score that
includes all modules and stacked signals. No UI change needed — just ensure the
score passed to the gauge includes the new findings.

### 5.4 Bilingual

All new finding descriptions, section labels, and diagnosis narratives need EN + PT-BR
translations. Stacking rules already include both `narrative_en` and `narrative_pt`.

---

## 6. Update AI Agent Prompts (Steps 7, 8, 9)

### 6.1 Prompt restructuring

The AI agent prompts currently receive profitability findings only. With three modules
plus stacked diagnoses, the prompt needs restructuring.

**Each module gets its own prompt section:**

```
## Financial Analysis Findings

### Profitability Analysis (Module 1)
[existing profitability findings]

### Balance Sheet Health (Module 2)
[BS findings — or "No balance sheet issues detected"]

### Cash Flow Quality (Module 3)
[CF findings — or "No cash flow issues detected"]

### Cross-Module Diagnoses
[Stacked diagnoses — or "No cross-module patterns detected"]
```

### 6.2 Step 7 — AI Industry Specialist

The Step 7 prompt generates hypotheses about what's causing the detected patterns.
Update it to:

- Reason about balance sheet and cash flow findings alongside profitability
- Generate hypotheses that span multiple modules (e.g., "margin compression may be
  driven by commodity price increases, which is also evident in the inventory build
  and the leverage escalation as the company borrows to fund higher working capital")
- Reference stacked diagnoses by name and explain what the cross-module confirmation means
- Map hypotheses to internal data sources that include balance sheet and cash flow
  detail (e.g., "aged receivables report", "debt maturity schedule", "capital expenditure plan")

### 6.3 Step 8 — Executive Summary

The Step 8 narrative arc (What Happened → How Serious → When Things Turned → What
Comes Next → What We Can't Answer) should now incorporate all modules:

- **What Happened:** Cover profitability, leverage, and cash flow trends
- **How Serious:** Reference the stacked diagnoses if any fired (e.g., "Cross-module
  analysis confirms FINANCIAL_DISTRESS_RISK — profitability decline is compounded by
  leverage escalation and negative free cash flow")
- **What Comes Next:** Recommendations should span all three financial statement areas
- **What We Can't Answer:** Include balance sheet and cash flow data gaps

The Key Findings table at the bottom should include findings from all modules,
grouped by module.

### 6.4 Step 9 — Q&A

The Step 9 chat prompt provides context for open Q&A. Update it to include all
findings (profitability + BS + CF + stacked) in the context.

**Suggested questions** should be updated to include balance sheet and cash flow
topics:
- "What is driving the leverage escalation?"
- "How sustainable is the current dividend policy?"
- "Is the working capital deterioration temporary or structural?"
- "What would the company's cash position look like without the recent debt issuance?"

---

## 7. What Does NOT Change

- **Steps 1–3 (CVM adapter):** No changes. Data parsing is complete from Sprint 2.
- **Step 4 (Metrics):** No changes. All derived metrics are already computed.
- **Step 5 (Data Quality):** No changes. Cross-statement validations are in place.
- **Frontend for Steps 1–5:** No changes except Step 6 UI updates.
- **Cache layer:** Existing cached data remains valid for Steps 1–5. Step 6 cache
  may need invalidation since findings structure changes (new modules, new fields).

---

## 8. Testing Checklist

### 8.1 Sprint 1 regression (profitability baseline)
- [ ] Braskem profitability findings match Sprint 1 baseline (codes, severities)
- [ ] Vale profitability findings match Sprint 1 baseline
- [ ] Votorantim profitability findings match Sprint 1 baseline
- [ ] Profitability risk score components unchanged

**Note:** The total risk score WILL change because it now includes BS and CF findings.
The test should verify that the profitability findings themselves (codes, severities,
categories, metric values) are unchanged — not the aggregate risk score.

### 8.2 Sprint 2 regression (metrics baseline)
- [ ] Step 4 balance sheet series matches Sprint 2 baseline
- [ ] Step 4 cash flow series matches Sprint 2 baseline
- [ ] Step 5 cross-statement warnings unchanged

### 8.3 Module 2: Balance Sheet Health
- [ ] BS detection runs for Braskem — produces findings
- [ ] BS detection runs for Vale — produces findings
- [ ] BS detection runs for Votorantim — produces findings (or "no issues" if clean)
- [ ] All BS findings have correct code prefix (BS_)
- [ ] All BS findings have module = "balance_sheet_health"
- [ ] Severity levels are reasonable (not everything is CRITICAL)
- [ ] Materiality values are populated and reasonable (not negative, not astronomical)
- [ ] None fields handled gracefully (no crashes, no NaN)

### 8.4 Module 3: Cash Flow Quality
- [ ] CF detection runs for Braskem — produces findings
- [ ] CF detection runs for Vale — produces findings
- [ ] CF detection runs for Votorantim — produces findings
- [ ] All CF findings have correct code prefix (CF_)
- [ ] All CF findings have module = "cash_flow_quality"
- [ ] Severity levels are reasonable
- [ ] Materiality values populated and reasonable
- [ ] None fields handled gracefully

### 8.5 Signal stacking
- [ ] Stacking engine runs after module detection
- [ ] At least one stacked diagnosis fires for Braskem (expected given its distress profile)
- [ ] Stacked diagnoses have module = "stacked" and category = "Diagnosis"
- [ ] Contributing signals list is populated correctly
- [ ] min_modules constraint is respected (no stacked diagnosis from only 1 module)

### 8.6 Risk score
- [ ] Risk score includes findings from all modules
- [ ] Stacked diagnoses influence risk score with elevated weight
- [ ] Risk score is a reasonable number (not > 100, not negative)

### 8.7 Step 6 frontend
- [ ] Findings grouped by module in the UI
- [ ] BS and CF sections appear with correct findings
- [ ] Stacked diagnosis cards are visually distinct
- [ ] "No issues detected" message appears when a module has no findings
- [ ] Risk gauge reflects updated score
- [ ] Bilingual labels work

### 8.8 Steps 7–9 (AI agent)
- [ ] Step 7 prompt includes findings from all modules
- [ ] Step 7 AI response references balance sheet and cash flow findings
- [ ] Step 7 hypotheses span multiple modules when stacked diagnoses exist
- [ ] Step 8 executive summary covers all modules
- [ ] Step 8 Key Findings table includes BS and CF findings
- [ ] Step 9 suggested questions include BS and CF topics
- [ ] Step 9 chat context includes all findings

### 8.9 Manual smoke test
- [ ] Full 9-step pipeline works end-to-end for Braskem
- [ ] Full 9-step pipeline works end-to-end for Vale
- [ ] Full 9-step pipeline works end-to-end for Votorantim
- [ ] No console errors in frontend
- [ ] No uncaught exceptions in backend logs

---

## 9. Definition of Done

- [ ] Sprint 2 regression baselines captured
- [ ] `determine_active_modules()` checks BS and CF data availability
- [ ] Module 2 (Balance Sheet Health): 7 detection algorithms implemented
- [ ] Module 3 (Cash Flow Quality): 6 detection algorithms implemented
- [ ] `IMPLEMENTED_MODULES` includes all three modules
- [ ] Signal stacking engine implemented with 4 cross-module rules
- [ ] Step 6 returns findings from all modules + stacked diagnoses
- [ ] Risk score updated to include all findings
- [ ] Step 6 frontend groups findings by module
- [ ] Stacked diagnosis cards visually distinct
- [ ] Steps 7–9 prompts updated with per-module sections
- [ ] Step 7 generates cross-module hypotheses
- [ ] Step 8 executive summary covers all modules
- [ ] Step 9 suggested questions include BS and CF topics
- [ ] Sprint 1 profitability findings unchanged (regression passes)
- [ ] Sprint 2 metrics unchanged (regression passes)
- [ ] All new UI text has EN + PT-BR translations
- [ ] All 3 test companies work end-to-end
- [ ] Code committed and pushed to `phase3-common-model` branch
