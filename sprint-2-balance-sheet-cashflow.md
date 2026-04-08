# Sprint 2 — CVM Balance Sheet + Cash Flow Parsing

> **What this is:** Build spec for Claude Code. Phase 3b (data layer) of the Cygnus product vision.
> This sprint extends the CVM adapter to parse BPA/BPP (balance sheet) and full DFC
> (cash flow statement) into the Common Financial Data Model. It also extends Step 4
> to compute and display balance sheet and cash flow metrics alongside existing
> profitability charts.
>
> **Branch:** Continue on `phase3-common-model` (from Sprint 1).
>
> **Depends on:** Sprint 1 complete — `backend/models/` dataclasses exist, CVM adapter
> outputs `CompanyFinancials`, Steps 4–6 read from common model.
>
> **Success criteria:**
> 1. `CompanyFinancials.balance_sheets` is populated with parsed BPA/BPP data
> 2. `CompanyFinancials.cash_flows` is populated with parsed DFC data
> 3. `determine_active_modules()` returns all three modules when data exists
> 4. Step 4 displays balance sheet and cash flow metrics (charts/tables) in the UI
> 5. Steps 5–6 continue to work exactly as before (profitability only — no new detection)
> 6. All Sprint 1 regression tests still pass
>
> **Reference:** `product-vision-architecture.md` (Sections 3, 6, 7, 8)

---

## 0. Pre-Work: Understand CVM ZIP File Structure

### 0.1 Explore the data

Before writing any code, inspect the CVM ZIP files that the adapter already downloads.
Identify the files available inside each ZIP. The expected structure is:

```
DFP (annual filings):
  dfp_cia_aberta_DRE_con_YYYY.csv       — Income statement (consolidated)
  dfp_cia_aberta_BPA_con_YYYY.csv       — Balance sheet — assets (consolidated)
  dfp_cia_aberta_BPP_con_YYYY.csv       — Balance sheet — liabilities + equity (consolidated)
  dfp_cia_aberta_DFC_MI_con_YYYY.csv    — Cash flow statement, indirect method (consolidated)
  dfp_cia_aberta_DVA_con_YYYY.csv       — Value added statement (ignore for now)
  ... individual (ind) versions of each ...

ITR (quarterly filings):
  itr_cia_aberta_DRE_con_YYYY.csv       — Income statement (consolidated)
  itr_cia_aberta_BPA_con_YYYY.csv       — Balance sheet — assets (consolidated)
  itr_cia_aberta_BPP_con_YYYY.csv       — Balance sheet — liabilities + equity (consolidated)
  itr_cia_aberta_DFC_MI_con_YYYY.csv    — Cash flow statement, indirect method (consolidated)
  ... etc ...
```

**Verify this by listing the actual files in the downloaded ZIPs.** The naming convention
may vary slightly. Document what you find before proceeding.

### 0.2 Understand the current adapter flow

Trace how the existing adapter processes DRE and DFC_MI_con files:
- Which functions handle download, filtering, deduplication?
- Where does ORDEM_EXERC filtering happen?
- Where does DFP/ITR overlap resolution happen?
- Where does YTD-to-standalone quarterly conversion happen?
- Where does D&A extraction from DFC happen?

The BPA, BPP, and full DFC parsing will need the same data quality treatments
(ORDEM_EXERC filtering, holding company dedup, DFP/ITR overlap, potentially
YTD-to-standalone conversion for quarterly cash flows).

---

## 1. Extend CVM Adapter: Balance Sheet Parsing

### 1.1 Files to parse

- `BPA_con` (Balanço Patrimonial Ativo — Assets)
- `BPP_con` (Balanço Patrimonial Passivo — Liabilities + Equity)

These are two separate CSV files that together form the complete balance sheet.

### 1.2 CVM account mapping — BPA (Assets)

Map CVM CD_CONTA codes to common model fields:

```
CD_CONTA  CVM Account Name (expected)                    → Common Model Field
--------  -----------------------------------------------  --------------------------
1         Ativo Total                                      → total_assets
1.01      Ativo Circulante                                 → current_assets
1.01.01   Caixa e Equivalentes de Caixa                    → cash_and_equivalents
1.01.03   Contas a Receber                                 → accounts_receivable
1.01.04   Estoques                                         → inventories
1.02      Ativo Não Circulante                             → non_current_assets
1.02.03   Imobilizado                                      → property_plant_equipment
1.02.04   Intangível                                       → intangible_assets
```

**IMPORTANT:** These CD_CONTA codes are the standard CVM structure, but companies
may use slightly different sub-account numbering. Verify against actual data for
Braskem, Vale, and Votorantim. The top-level codes (1, 1.01, 1.02) should be
consistent; sub-accounts (1.01.01, 1.01.03, etc.) may vary.

**Fallback strategy:** If a specific sub-account code doesn't exist for a company,
set the corresponding field to None. The common model is designed for nullable fields.
Only `total_assets`, `current_assets`, and `non_current_assets` should be reliably
present for all companies.

### 1.3 CVM account mapping — BPP (Liabilities + Equity)

```
CD_CONTA  CVM Account Name (expected)                    → Common Model Field
--------  -----------------------------------------------  --------------------------
2         Passivo Total                                    → total_liabilities
2.01      Passivo Circulante                               → current_liabilities
2.01.04   Empréstimos e Financiamentos (Circulante)        → short_term_debt
2.01.02   Fornecedores                                     → accounts_payable
2.02      Passivo Não Circulante                           → non_current_liabilities
2.02.01   Empréstimos e Financiamentos (Não Circulante)    → long_term_debt
2.03      Patrimônio Líquido Consolidado                   → total_equity
2.03.04   Reservas de Lucros (or Lucros/Prejuízos Acum.)   → retained_earnings
```

**Same fallback strategy:** Nullable fields. The reliable codes are 2, 2.01, 2.02, 2.03.
Sub-accounts for debt, payables, and retained earnings may vary by company.

**Approach for ambiguous sub-accounts:** When a sub-account doesn't map cleanly
(e.g., a company uses 2.01.02 for something other than Fornecedores), skip it
rather than mapping incorrectly. It's better to have `accounts_payable: None` than
a wrong number. Log a warning when a mapping is skipped.

### 1.4 Data quality treatments

Apply the same data quality pipeline as the DRE adapter:

1. **ORDEM_EXERC filtering** — keep only ÚLTIMO (most recent exercise) to avoid
   prior-year restated figures double-counting
2. **Holding company deduplication** — exclude Suzano Holding, Metalúrgica Gerdau, etc.
3. **DFP/ITR overlap resolution** — when both DFP and ITR cover the same period,
   DFP takes precedence
4. **Company filtering** — same company filter as the income statement

**Balance sheet is a point-in-time snapshot, NOT a flow statement.** This means:
- No YTD-to-standalone conversion needed (unlike income statement quarters)
- Each quarterly balance sheet is already a standalone snapshot
- But DFP/ITR overlap still applies (same period reported in both)

### 1.5 Implementation approach

The cleanest approach is to **reuse the existing adapter's data quality functions**
for BPA/BPP. The processing pattern is:

1. Read BPA_con CSV (same encoding, delimiter handling as DRE)
2. Apply ORDEM_EXERC filter
3. Apply company filter
4. Apply holding company dedup
5. Apply DFP/ITR overlap resolution
6. Pivot to one row per period with accounts as columns
7. Map CVM accounts to common model fields
8. Create `BalanceSheet` dataclass instances (one per period)

Repeat for BPP_con, then merge assets (BPA) + liabilities/equity (BPP) into
a single `BalanceSheet` object per period (they share the same period dates).

### 1.6 Merging BPA + BPP

Each `BalanceSheet` dataclass instance contains both asset fields (from BPA)
and liability/equity fields (from BPP). The merge is by period date:

```python
# Pseudocode
for period_date in all_period_dates:
    bs = BalanceSheet(
        company_id=company_id,
        period=period,
        # From BPA
        total_assets=bpa_row.get("total_assets"),
        current_assets=bpa_row.get("current_assets"),
        # ...
        # From BPP
        total_liabilities=bpp_row.get("total_liabilities"),
        current_liabilities=bpp_row.get("current_liabilities"),
        # ...
    )
```

If a period exists in BPA but not BPP (or vice versa), still create the
BalanceSheet with None for the missing side. This shouldn't happen in practice
but handle it gracefully.

---

## 2. Extend CVM Adapter: Full Cash Flow Parsing

### 2.1 Files to parse

- `DFC_MI_con` (Demonstração do Fluxo de Caixa — Método Indireto, Consolidado)

This file is already partially parsed — the current adapter extracts D&A for
EBITDA calculation. This sprint extends it to extract the full cash flow statement.

### 2.2 CVM account mapping — DFC (Cash Flow)

```
CD_CONTA  CVM Account Name (expected)                           → Common Model Field
--------  -------------------------------------------------------  ----------------------------
6.01      Caixa Líquido Atividades Operacionais                    → operating_cash_flow
6.01.01   Depreciação e Amortização (within operating section)     → depreciation_amortization
6.02      Caixa Líquido Atividades de Investimento                 → investing_cash_flow
6.03      Caixa Líquido Atividades de Financiamento                → financing_cash_flow
```

**Sub-account mapping (best effort):**

```
6.01.xx   Various working capital adjustments                      → working_capital_change (sum)
6.02.xx   Aquisição de Imobilizado / Intangível                   → capex
6.02.xx   Aquisição de Controladas/Coligadas                       → acquisitions
6.03.xx   Captação de Empréstimos                                  → debt_issuance
6.03.xx   Pagamento de Empréstimos                                 → debt_repayment
6.03.xx   Dividendos Pagos                                         → dividends_paid
```

**Cash flow sub-accounts are highly variable across companies.** The top-level codes
(6.01, 6.02, 6.03) are standardized. Sub-accounts within each section differ
significantly. Strategy:

- **Always map:** 6.01 → operating_cash_flow, 6.02 → investing_cash_flow,
  6.03 → financing_cash_flow (these are reliable)
- **Best-effort map:** sub-accounts for capex, debt, dividends — use keyword
  matching on the account description (DS_CONTA) rather than relying on fixed
  CD_CONTA codes
- **Set to None when ambiguous.** Better to have `capex: None` than a wrong number.

### 2.3 Keyword matching for sub-accounts

For sub-accounts that vary by company, match on the description field:

```python
CAPEX_KEYWORDS = ["imobilizado", "intangível", "investimento em imobilizado",
                  "aquisição de imobilizado"]
DEBT_ISSUANCE_KEYWORDS = ["captação", "empréstimos obtidos", "ingressos de empréstimos"]
DEBT_REPAYMENT_KEYWORDS = ["pagamento de empréstimos", "amortização de empréstimos"]
DIVIDENDS_KEYWORDS = ["dividendos", "juros sobre capital próprio pagos"]
ACQUISITIONS_KEYWORDS = ["aquisição de controladas", "aquisição de coligadas",
                         "investimentos em controladas"]
DA_KEYWORDS = ["depreciação", "amortização"]
```

Use case-insensitive partial matching. When multiple sub-accounts match a keyword
category, sum them (e.g., multiple capex line items sum to total capex).

### 2.4 Data quality treatments

Same pipeline as income statement:

1. **ORDEM_EXERC filtering**
2. **Holding company dedup**
3. **DFP/ITR overlap resolution**
4. **Company filtering**

**Cash flow IS a flow statement** (like income statement), so:
- **YTD-to-standalone conversion IS needed for quarterly data.** ITR reports
  cumulative year-to-date cash flows. Convert to standalone quarters by subtracting
  the prior quarter's YTD from the current quarter's YTD.
- Apply the same logic the current adapter uses for income statement quarters.

### 2.5 D&A consolidation

The current adapter already extracts D&A from DFC for EBITDA calculation and places
it on `IncomeStatement.depreciation_amortization`. With full DFC parsing:

- `CashFlow.depreciation_amortization` gets the D&A value from the cash flow statement
- `IncomeStatement.depreciation_amortization` continues to get its D&A value as before
- These values should be identical (same source). But keep both populated — Sprint 3
  may use the cash flow version for OCF quality analysis.

Do NOT change how D&A flows to the income statement. That path is tested and
working from Sprint 1. Just additionally populate the cash flow D&A field.

---

## 3. Update `dataframe_to_company_financials()`

### 3.1 Current state

The conversion function (added in Sprint 1) creates `CompanyFinancials` with
populated `income_statements` and `balance_sheets=None, cash_flows=None`.

### 3.2 Target state

The conversion function receives the parsed BPA/BPP and DFC data and creates
fully populated `CompanyFinancials`:

```python
CompanyFinancials(
    company=company,
    income_statements=[...],      # existing — unchanged
    balance_sheets=[...],          # NEW — from BPA + BPP
    cash_flows=[...],              # NEW — from DFC
    source="cvm",
    # ... metadata updated to reflect new data
)
```

### 3.3 data_completeness metadata

Update the `data_completeness` dict to reflect which statements are available:

```python
data_completeness = {
    "income_statement": True,
    "balance_sheet": len(balance_sheets) > 0,
    "cash_flow": len(cash_flows) > 0,
    "statements_available": ["income_statement", "balance_sheet", "cash_flow"],
    "income_statement_periods": len(income_statements),
    "balance_sheet_periods": len(balance_sheets),
    "cash_flow_periods": len(cash_flows),
}
```

---

## 4. Extend Step 4 — Balance Sheet and Cash Flow Metrics

### 4.1 New derived metrics to compute

**Balance Sheet metrics** (compute in Step 4, store on BalanceSheet objects):

```python
net_debt = (short_term_debt or 0) + (long_term_debt or 0) - (cash_and_equivalents or 0)
working_capital = (current_assets or 0) - (current_liabilities or 0)
current_ratio = current_assets / current_liabilities  # None if denominator is None or 0
quick_ratio = (current_assets - (inventories or 0)) / current_liabilities
debt_to_ebitda = net_debt / ebitda  # requires income statement cross-reference
receivable_days = (accounts_receivable / revenue) * 365  # requires income statement
inventory_days = (inventories / cogs) * 365  # requires income statement
payable_days = (accounts_payable / cogs) * 365  # requires income statement
cash_conversion_cycle = receivable_days + inventory_days - payable_days
return_on_assets = net_income / total_assets  # requires income statement
return_on_equity = net_income / total_equity  # requires income statement
asset_turnover = revenue / total_assets  # requires income statement
```

**Cash Flow metrics** (compute in Step 4, store on CashFlow objects):

```python
free_cash_flow = (operating_cash_flow or 0) + (capex or 0)  # capex is negative
ocf_to_net_income = operating_cash_flow / net_income  # requires income statement
capex_to_revenue = abs(capex) / revenue  # requires income statement
capex_to_depreciation = abs(capex) / depreciation_amortization  # capex negative, D&A positive
```

**Cross-statement metrics require matching periods.** Match by fiscal_year (for annual)
or fiscal_year + fiscal_quarter (for quarterly). If a period exists in one statement
but not the other, the cross-statement metric is None for that period.

### 4.2 Handle None values defensively

Many sub-account fields will be None for some companies. Every metric computation
must handle this:

```python
# Pattern: compute only when all required inputs exist
if current_assets is not None and current_liabilities is not None and current_liabilities != 0:
    current_ratio = current_assets / current_liabilities
else:
    current_ratio = None
```

### 4.3 New API response data

Step 4's API endpoint currently returns profitability metrics (revenue, margins, etc.).
Extend it to also return:

**Balance Sheet time series:**
- `total_assets`, `total_liabilities`, `total_equity` over time
- `current_ratio`, `quick_ratio` over time
- `net_debt`, `debt_to_ebitda` over time
- `working_capital`, `cash_conversion_cycle` over time
- `receivable_days`, `inventory_days`, `payable_days` over time
- `return_on_assets`, `return_on_equity`, `asset_turnover` over time

**Cash Flow time series:**
- `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow` over time
- `free_cash_flow` over time
- `capex`, `capex_to_revenue`, `capex_to_depreciation` over time
- `ocf_to_net_income` over time

Structure these as additional keys in the Step 4 response, parallel to the existing
profitability metrics. The frontend will render them as new chart sections.

---

## 5. Extend Step 4 Frontend — New Chart Sections

### 5.1 Design approach

Add two new collapsible sections to Step 4, below the existing profitability charts:

1. **Balance Sheet Health** — charts showing leverage, liquidity, and efficiency metrics
2. **Cash Flow Analysis** — charts showing cash generation, investment, and quality metrics

Use the same chart component library and design patterns as the existing profitability
charts (Recharts, Cygnus color palette, JetBrains Mono for values).

### 5.2 Balance Sheet charts

**Chart 1: Capital Structure**
- Stacked bar chart: total_assets broken into current_assets + non_current_assets
- Overlay line: total_equity
- Shows how the balance sheet composition changes over time

**Chart 2: Leverage Metrics**
- Dual axis: net_debt (bars, left axis) + debt_to_ebitda (line, right axis)
- Highlights leverage escalation or reduction over time

**Chart 3: Liquidity**
- Line chart: current_ratio and quick_ratio over time
- Reference line at 1.0 (below this = liquidity stress)

**Chart 4: Working Capital Efficiency**
- Line chart: receivable_days, inventory_days, payable_days over time
- Secondary line: cash_conversion_cycle
- Shows whether the company is getting faster or slower at converting operations to cash

### 5.3 Cash Flow charts

**Chart 5: Cash Flow Composition**
- Grouped bar chart: operating_cash_flow, investing_cash_flow, financing_cash_flow per period
- Shows the balance between the three cash flow categories

**Chart 6: Free Cash Flow**
- Bar chart: free_cash_flow over time
- Color: blue for positive, red/amber for negative
- Horizontal reference line at zero

**Chart 7: Investment Intensity**
- Dual axis: capex (bars, left axis) + capex_to_depreciation ratio (line, right axis)
- Reference line at 1.0 for capex/depreciation (below = underinvesting)

**Chart 8: Earnings Quality**
- Line chart: ocf_to_net_income ratio over time
- Reference line at 1.0 (below = earnings not converting to cash)
- This is a key quality signal — it shows whether reported profits are real

### 5.4 UI layout

- Each section (Balance Sheet, Cash Flow) has a section header in JetBrains Mono
  uppercase style (matching existing section labels)
- Sections are collapsible (default expanded)
- Charts use the same responsive grid as existing profitability charts
- If balance_sheets is None (no BPA/BPP data), show a message:
  "Balance Sheet analysis not available — BPA/BPP data not found in CVM filings"
- If cash_flows is None (no DFC data), show a similar message
- These messages use the standard Cygnus info card style

### 5.5 Bilingual labels

All new chart labels, section headers, axis labels, and unavailability messages
must have both EN and PT-BR translations in the i18n files. Follow the existing
i18n pattern in the codebase.

---

## 6. Module Availability Gating — Keep It Simple

### 6.1 Current state

`determine_active_modules()` from Sprint 1 checks data availability and returns
a list of active modules. With Sprint 2 data, it will start returning
`["profitability", "balance_sheet_health", "cash_flow_quality"]`.

### 6.2 The problem

Modules 2 and 3 don't have detection algorithms yet (Sprint 3). If Step 6 tries
to run them, it will fail.

### 6.3 Solution: separate data gating from detection gating

The simplest approach: Step 6 currently only runs profitability detection. Don't
change Step 6 at all in this sprint. The module gating function can report what
data is available, but Step 6 only runs the algorithms that exist.

```python
# In Step 6 — keep this hardcoded until Sprint 3 adds the algorithms
IMPLEMENTED_MODULES = ["profitability"]

active_modules = determine_active_modules(company_financials)
runnable_modules = [m for m in active_modules if m in IMPLEMENTED_MODULES]
# Run detection only for runnable_modules
```

This way:
- `determine_active_modules()` correctly reports data availability (used by the UI
  to show which sections are possible)
- Step 6 only runs detection for modules that have implementations
- Sprint 3 simply adds to IMPLEMENTED_MODULES when new algorithms are built

### 6.4 UI indication

Step 4 already shows the new data (charts). The module gating affects Step 6 only.
In Step 6, if balance sheet or cash flow data exists but detection isn't implemented:

- Show an info message: "Balance Sheet and Cash Flow data loaded — detection
  algorithms coming in the next update"
- Or simply don't mention it — Step 4 shows the data, Step 6 shows profitability
  findings as before

Either approach is fine. Pick whichever is simpler to implement.

---

## 7. Extend Step 5 — Balance Sheet Validation

### 7.1 Accounting identity check

Add a fundamental data quality validation to Step 5:

**Total Assets ≈ Total Liabilities + Total Equity**

For each period where balance sheet data exists, check:

```python
if total_assets is not None and total_liabilities is not None and total_equity is not None:
    expected = total_liabilities + total_equity
    diff = abs(total_assets - expected)
    tolerance = abs(total_assets) * 0.001  # 0.1% tolerance for rounding
    if diff > tolerance:
        flag_data_quality_warning(
            period=period,
            check="BALANCE_SHEET_IDENTITY",
            message=f"Assets ({total_assets:,.0f}) ≠ Liabilities + Equity ({expected:,.0f}), diff={diff:,.0f}",
            severity="HIGH"  # this means the parsing mapped something wrong
        )
```

This is a **parsing validation**, not a financial health signal. If this check
fails, it means either:
- The CVM account mapping is wrong (we mapped the wrong CD_CONTA)
- The CVM data itself has an inconsistency
- BPA and BPP period dates didn't align correctly during the merge

A failure here is a red flag that should be investigated before trusting any
balance sheet metrics downstream.

### 7.3 Cash movement reconciliation

Cross-statement validation between the balance sheet and cash flow statement:

**Opening Cash + Net Cash Flow ≈ Closing Cash**

For each period where both balance sheet and cash flow data exist, and the
prior period balance sheet also exists:

```python
if (prior_cash is not None
        and current_cash is not None
        and operating_cf is not None
        and investing_cf is not None
        and financing_cf is not None):
    net_cash_flow = operating_cf + investing_cf + financing_cf
    expected_closing = prior_cash + net_cash_flow
    diff = abs(current_cash - expected_closing)
    tolerance = max(abs(current_cash) * 0.02, 1_000_000)  # 2% or BRL 1M, whichever is larger
    if diff > tolerance:
        flag_data_quality_warning(
            period=period,
            check="CASH_MOVEMENT_RECONCILIATION",
            message=f"Opening cash ({prior_cash:,.0f}) + net cash flow ({net_cash_flow:,.0f}) "
                    f"= {expected_closing:,.0f}, but closing cash is {current_cash:,.0f}, "
                    f"diff={diff:,.0f}",
            severity="MEDIUM"
        )
```

**Why 2% tolerance (not 0.1% like the balance sheet identity):** Cash movement
reconciliation can have legitimate differences due to:
- Foreign exchange effects on cash balances (common for multinationals like Braskem and Vale)
- Reclassifications between cash and cash equivalents
- CVM reporting of "restricted cash" outside the main cash line

A MEDIUM severity flag (not HIGH) because a mismatch here often reflects FX effects
or reporting nuances rather than a parsing error. But a large mismatch still warrants
investigation.

**Period matching:** Use balance sheet period dates. For annual data, compare Dec 31
of year N-1 (opening) to Dec 31 of year N (closing) with the annual cash flow.
For quarterly data, compare quarter-end dates sequentially. Skip the first period
in the series (no prior balance sheet to compare against).

### 7.4 D&A consistency check

Validate that D&A extracted for the income statement matches the cash flow statement:

```python
if (income_da is not None and cashflow_da is not None):
    diff = abs(income_da - cashflow_da)
    tolerance = max(abs(income_da) * 0.001, 1_000)  # 0.1% or BRL 1K
    if diff > tolerance:
        flag_data_quality_warning(
            period=period,
            check="DA_CONSISTENCY",
            message=f"D&A on income statement ({income_da:,.0f}) ≠ "
                    f"D&A on cash flow ({cashflow_da:,.0f}), diff={diff:,.0f}",
            severity="MEDIUM"
        )
```

Both values come from the DFC file, so they should match. A mismatch likely means
the keyword matching picked up the wrong line item in one of the two extraction paths.

### 7.5 What these checks are NOT

These are not detection algorithms (that's Sprint 3). They do not generate
"findings" in Step 6. They generate data quality flags in Step 5 — the same
kind of flag that the existing profitability validation produces.

### 7.6 Display

If the check passes for all periods: no display needed (silent pass).
If it fails for any period: show a warning in Step 5's data quality section,
using the existing warning card pattern. Include the period and the magnitude
of the imbalance.

Bilingual: add EN + PT-BR translations for the warning message.

---

## 8. What Does NOT Change
- **Step 6 (Detection):** Continues to run Module 1 (profitability) only. No new
  detection algorithms. Findings, risk scores, and categories remain unchanged.
- **Steps 7, 8, 9 (AI Agent, Summary, Q&A):** No changes. They still receive
  profitability findings only.
- **Sprint 1 regression baselines:** All three companies must still pass the
  existing regression tests (Braskem, Vale, Votorantim). The new data doesn't
  affect profitability outputs.
- **Cache layer:** Existing cached profitability data remains valid. New balance
  sheet and cash flow data may need fresh cache entries.

---

## 9. Testing Checklist

### 9.1 Sprint 1 regression (must still pass)
- [ ] Braskem profitability metrics match baseline
- [ ] Vale profitability metrics match baseline
- [ ] Votorantim profitability metrics match baseline
- [ ] All finding codes, severities, risk scores unchanged

### 9.2 Balance Sheet parsing
- [ ] BPA_con files successfully parsed for Braskem
- [ ] BPP_con files successfully parsed for Braskem
- [ ] BPA + BPP merged into BalanceSheet objects (one per period)
- [ ] At minimum: total_assets, current_assets, non_current_assets populated
- [ ] At minimum: total_liabilities, current_liabilities, total_equity populated
- [ ] Sub-accounts (cash, receivables, inventories, debt) populated where available
- [ ] Repeat for Vale
- [ ] Repeat for Votorantim
- [ ] ORDEM_EXERC filtering applied
- [ ] DFP/ITR overlap resolved
- [ ] No YTD conversion applied (balance sheet is point-in-time)

### 9.3 Cash Flow parsing
- [ ] DFC_MI_con files fully parsed for Braskem
- [ ] Top-level: operating_cash_flow, investing_cash_flow, financing_cash_flow populated
- [ ] Sub-accounts: capex, D&A, dividends populated where keyword match succeeds
- [ ] YTD-to-standalone conversion applied for quarterly data
- [ ] Repeat for Vale
- [ ] Repeat for Votorantim
- [ ] D&A on CashFlow matches D&A on IncomeStatement for same periods

### 9.4 CompanyFinancials population
- [ ] `company_financials.balance_sheets` is a list (not None)
- [ ] `company_financials.cash_flows` is a list (not None)
- [ ] `determine_active_modules()` returns all three modules
- [ ] `data_completeness` metadata reflects all three statements
- [ ] Income statements unchanged from Sprint 1

### 9.5 Cross-statement validation (Step 5)
- [ ] Assets = Liabilities + Equity check runs for all periods with balance sheet data
- [ ] Check passes for Braskem (no warnings or only expected tolerance)
- [ ] Check passes for Vale
- [ ] Check passes for Votorantim
- [ ] Cash movement reconciliation runs (opening cash + net CF ≈ closing cash)
- [ ] Cash reconciliation passes or flags with MEDIUM severity (FX effects expected for multinationals)
- [ ] D&A consistency check runs (income statement D&A ≈ cash flow D&A)
- [ ] D&A consistency passes for all three companies
- [ ] If any check fails, warning displays correctly in Step 5 with period and diff amount
- [ ] Warning messages have EN + PT-BR translations

### 9.6 Step 4 metrics computation
- [ ] Balance sheet derived metrics compute correctly (current_ratio, net_debt, etc.)
- [ ] Cash flow derived metrics compute correctly (FCF, OCF/NI ratio, etc.)
- [ ] Cross-statement metrics handle period matching correctly
- [ ] None values handled gracefully (no division by zero, no NaN in output)

### 9.7 Step 4 frontend
- [ ] Balance Sheet section renders with 4 charts
- [ ] Cash Flow section renders with 4 charts
- [ ] Charts display data for Braskem
- [ ] Charts display data for Vale
- [ ] Charts display data for Votorantim
- [ ] Bilingual labels work (EN and PT-BR toggle)
- [ ] Sections show graceful message if data is missing
- [ ] Existing profitability charts unchanged

### 9.8 Manual smoke test
- [ ] Full 9-step pipeline works end-to-end for Braskem
- [ ] Full 9-step pipeline works end-to-end for Vale
- [ ] Full 9-step pipeline works end-to-end for Votorantim
- [ ] Step 6 findings identical to Sprint 1 (no new detection yet)
- [ ] Steps 7-9 unaffected

---

## 10. Definition of Done

- [ ] CVM adapter parses BPA_con + BPP_con into BalanceSheet objects
- [ ] CVM adapter parses full DFC_MI_con into CashFlow objects
- [ ] `CompanyFinancials` has all three statements populated
- [ ] `determine_active_modules()` returns three modules when data exists
- [ ] Step 5 validates Assets = Liabilities + Equity for all balance sheet periods
- [ ] Step 5 validates cash movement reconciliation (opening cash + net CF ≈ closing cash)
- [ ] Step 5 validates D&A consistency between income statement and cash flow
- [ ] Step 4 computes balance sheet and cash flow derived metrics
- [ ] Step 4 frontend shows new chart sections (Balance Sheet + Cash Flow)
- [ ] All new UI text has EN + PT-BR translations
- [ ] Sprint 1 regression tests still pass
- [ ] Module gating prevents Step 6 from running non-existent detection algorithms
- [ ] All 3 test companies work end-to-end
- [ ] Code committed and pushed to `phase3-common-model` branch
