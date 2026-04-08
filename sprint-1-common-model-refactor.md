# Sprint 1 — Common Data Model + CVM Adapter Refactor

> **What this is:** Build spec for Claude Code. Phase 3a of the Cygnus product vision.
> This sprint introduces the Common Financial Data Model as Python dataclasses,
> refactors the CVM adapter to output `CompanyFinancials`, and rewires Steps 4–6
> to read from the common model instead of CVM-specific column names.
>
> **Branch:** Create `phase3-common-model` from `master`.
>
> **Success criteria:** The application produces **identical output** to the current
> master branch for all test companies. This is a pure refactor — no new features,
> no new data sources, no UI changes.
>
> **Reference:** `product-vision-architecture.md` (Sections 2, 3, 7, 8, 9)

---

## 0. Pre-Work: Regression Baseline Snapshot

**Before writing any new code**, capture the current output for three companies.
This snapshot becomes the regression test that validates the refactor.

### 0.1 Companies to snapshot

| Company | Notes |
|---|---|
| BRASKEM S.A. | Primary demo company, petrochemical, rich data |
| VALE S.A. | Mining, large company, different sector profile |
| VOTORANTIM CIMENTOS S.A. | Building materials, different data characteristics |

### 0.2 What to capture

For each company, run the current pipeline and dump to JSON:

```
tests/regression/
  braskem_baseline.json
  vale_baseline.json
  votorantim_baseline.json
```

Each JSON file should contain:

```json
{
  "company_name": "BRASKEM S.A.",
  "snapshot_date": "2026-04-XX",
  "snapshot_branch": "master",
  "step4_metrics": {
    "periods": [...],
    "revenue": [...],
    "cogs": [...],
    "gross_profit": [...],
    "gross_margin_pct": [...],
    "ebitda": [...],
    "ebitda_margin_pct": [...],
    "cogs_pct_revenue": [...],
    "sga_pct_revenue": [...]
  },
  "step5_quality": {
    "data_quality_flags": [...],
    "confidence_scores": {...}
  },
  "step6_findings": {
    "findings": [
      {
        "code": "COGS_DRIFT",
        "severity": "HIGH",
        "category": "Core",
        "metric_values": {...},
        "materiality_brl": ...
      }
    ],
    "risk_score": 71.2,
    "finding_count": 8
  }
}
```

The exact field names should match whatever the current endpoints return.
The point is: capture everything Steps 4, 5, and 6 produce so we can
diff after the refactor.

### 0.3 Regression test script

Create `tests/test_regression.py` that:
1. Loads each baseline JSON
2. Runs the refactored pipeline for the same company
3. Compares output field by field
4. Asserts numerical values match within floating-point tolerance (1e-6)
5. Asserts finding codes, severities, and categories match exactly
6. Asserts risk scores match within 0.1

This test must pass before the sprint is considered complete.

---

## 1. Define the Common Financial Data Model

### 1.1 Location

Create `backend/models/` directory with:

```
backend/models/
  __init__.py
  company.py
  period.py
  financial_statements.py
  company_financials.py
```

### 1.2 Company model (`company.py`)

```python
from dataclasses import dataclass

@dataclass
class Company:
    id: str                     # unique identifier (CVM code, SEC CIK, internal ID)
    name: str                   # display name ("BRASKEM S.A.")
    source: str                 # data source identifier ("cvm", "sec", "erp", "manual")
    country: str                # ISO country code ("BR", "US")
    currency: str               # reporting currency ("BRL", "USD")
    sector: str | None = None   # sector classification if known
    sector_source: str = "unknown"  # "mapped" | "inferred" | "unknown"
```

### 1.3 Period model (`period.py`)

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class Period:
    date: date                      # period end date (2025-12-31)
    granularity: str                # "annual" | "quarterly" | "monthly"
    fiscal_year: int                # 2025
    fiscal_quarter: int | None = None   # 1-4 for quarterly, None for annual
    fiscal_month: int | None = None     # 1-12 for monthly, None otherwise
    is_standalone: bool = True      # True = standalone period, False = YTD cumulative
    filing_type: str | None = None  # Source-specific: "DFP", "ITR", "10-K", "10-Q", etc.
```

### 1.4 Financial statement models (`financial_statements.py`)

```python
from dataclasses import dataclass, field
from .period import Period

@dataclass
class IncomeStatement:
    company_id: str
    period: Period

    # Revenue
    revenue: float | None = None
    cost_of_goods_sold: float | None = None     # positive = cost, stored as absolute value
    gross_profit: float | None = None

    # Operating expenses
    sga_expenses: float | None = None
    selling_expenses: float | None = None
    general_admin: float | None = None
    other_operating: float | None = None

    # Operating profit
    ebit: float | None = None
    depreciation_amortization: float | None = None  # D&A — sourced from DFC in CVM
    ebitda: float | None = None

    # Below the line
    financial_result: float | None = None
    income_before_tax: float | None = None
    income_tax: float | None = None
    net_income: float | None = None

    # Derived ratios (computed by Step 4, not stored by adapter)
    gross_margin_pct: float | None = None
    ebit_margin_pct: float | None = None
    ebitda_margin_pct: float | None = None
    cogs_pct_revenue: float | None = None
    sga_pct_revenue: float | None = None


@dataclass
class BalanceSheet:
    company_id: str
    period: Period

    # Assets
    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventories: float | None = None
    non_current_assets: float | None = None
    property_plant_equipment: float | None = None
    intangible_assets: float | None = None

    # Liabilities
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    accounts_payable: float | None = None
    short_term_debt: float | None = None
    non_current_liabilities: float | None = None
    long_term_debt: float | None = None

    # Equity
    total_equity: float | None = None
    retained_earnings: float | None = None

    # Derived metrics (computed by Step 4) — all None until Sprint 3
    net_debt: float | None = None
    working_capital: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_ebitda: float | None = None
    receivable_days: float | None = None
    inventory_days: float | None = None
    payable_days: float | None = None
    cash_conversion_cycle: float | None = None
    return_on_assets: float | None = None
    return_on_equity: float | None = None
    asset_turnover: float | None = None


@dataclass
class CashFlow:
    company_id: str
    period: Period

    # Operating
    operating_cash_flow: float | None = None
    depreciation_amortization: float | None = None
    working_capital_change: float | None = None
    other_operating: float | None = None

    # Investing
    investing_cash_flow: float | None = None
    capex: float | None = None
    acquisitions: float | None = None
    other_investing: float | None = None

    # Financing
    financing_cash_flow: float | None = None
    debt_issuance: float | None = None
    debt_repayment: float | None = None
    dividends_paid: float | None = None
    equity_issuance: float | None = None
    other_financing: float | None = None

    # Derived metrics (computed by Step 4) — all None until Sprint 3
    free_cash_flow: float | None = None
    ocf_to_net_income: float | None = None
    capex_to_revenue: float | None = None
    capex_to_depreciation: float | None = None
```

### 1.5 CompanyFinancials container (`company_financials.py`)

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from .company import Company
from .financial_statements import IncomeStatement, BalanceSheet, CashFlow

@dataclass
class CompanyFinancials:
    """The output of any source adapter. This is the input to the analysis engine."""

    company: Company
    income_statements: list[IncomeStatement]         # sorted by period date
    balance_sheets: list[BalanceSheet] | None = None  # None if source doesn't provide
    cash_flows: list[CashFlow] | None = None          # None if source doesn't provide

    # Metadata
    source: str = ""
    source_version: str = ""
    extraction_date: datetime = field(default_factory=datetime.now)
    period_range: tuple[date, date] | None = None
    granularity: list[str] = field(default_factory=list)
    data_completeness: dict = field(default_factory=dict)
```

### 1.6 `__init__.py`

Export all models:

```python
from .company import Company
from .period import Period
from .financial_statements import IncomeStatement, BalanceSheet, CashFlow
from .company_financials import CompanyFinancials
```

---

## 2. Refactor CVM Adapter

### 2.1 Current state

The CVM adapter currently:
- Downloads DFP + ITR ZIP files from CVM
- Filters by company, handles ORDEM_EXERC, deduplicates holdings
- Resolves DFP/ITR overlap, converts YTD to standalone quarters
- Extracts D&A from DFC_MI_con for EBITDA calculation
- Outputs a **pandas DataFrame** with CVM-specific columns:
  - `DENOM_CIA`, `CD_CONTA`, `DT_REFER`, `VL_CONTA`
  - Pivoted columns like `Receita de Venda de Bens e/ou Serviços`

### 2.2 Target state

The CVM adapter outputs a `CompanyFinancials` object. Internally it can still
use DataFrames for the heavy data manipulation — the conversion to dataclasses
happens at the boundary (end of Step 3).

### 2.3 Implementation approach

**Do NOT rewrite the data processing logic.** The current pipeline is tested and
produces correct results. The refactor adds a conversion layer at the end:

1. Keep the existing DataFrame processing (download, filter, dedup, pivot)
2. Add a new function `dataframe_to_company_financials(df, company_name, ...)` that:
   - Creates a `Company` object from the company metadata
   - Iterates over the pivoted DataFrame rows (one per period)
   - For each row, creates an `IncomeStatement` with the mapped fields
   - Creates a `Period` object from `DT_REFER` and `_doc_type`
   - Maps CVM account names to common model fields:
     - `Receita de Venda de Bens e/ou Serviços` → `revenue`
     - `Custo dos Bens e/ou Serviços Vendidos` → `cost_of_goods_sold` (absolute value)
     - `Resultado Bruto` → `gross_profit`
     - `Despesas/Receitas Operacionais` or SGA equivalent → `sga_expenses`
     - `Resultado Antes do Resultado Financeiro e dos Tributos` → `ebit`
     - D&A value (from DFC extraction) → `depreciation_amortization`
     - Computed EBITDA → `ebitda`
   - Sorts income statements by period date
   - Sets `balance_sheets = None` (Sprint 2)
   - Sets `cash_flows = None` (Sprint 2)
   - Populates metadata (source="cvm", period_range, granularity, data_completeness)
3. The adapter's public interface returns `CompanyFinancials`

### 2.4 Account mapping reference

Create a mapping constant in the adapter:

```python
CVM_ACCOUNT_MAP = {
    # CVM Portuguese account name → common model field name
    "Receita de Venda de Bens e/ou Serviços": "revenue",
    "Custo dos Bens e/ou Serviços Vendidos": "cost_of_goods_sold",
    "Resultado Bruto": "gross_profit",
    "Despesas/Receitas Operacionais": "sga_expenses",
    "Resultado Antes do Resultado Financeiro e dos Tributos": "ebit",
    "Resultado Financeiro": "financial_result",
    "Resultado Antes dos Tributos sobre o Lucro": "income_before_tax",
    "Imposto de Renda e Contribuição Social sobre o Lucro": "income_tax",
    "Lucro/Prejuízo Consolidado do Período": "net_income",
}
```

**Important:** Check the actual column names in the current pivoted DataFrame.
The names above are from CVM's standard DRE structure but the current code may
use slightly different names or CD_CONTA codes. Match what the code actually uses.

### 2.5 COGS sign convention

CVM reports COGS as a negative number (it's an expense). The common model stores
it as a **positive absolute value** (cost_of_goods_sold = abs(cvm_value)).
Make sure the sign flip happens in the adapter, not in the analysis engine.

Check the current code for where sign handling happens — it may already flip the
sign. Don't double-flip.

### 2.6 D&A handling

D&A is currently extracted from DFC_MI_con (cash flow statement) solely for EBITDA
calculation. In Sprint 1, this value goes into `IncomeStatement.depreciation_amortization`.
The full cash flow statement parsing is deferred to Sprint 2.

The D&A extraction logic stays in the adapter. The value is placed on the income
statement because that's where it's used (EBITDA = EBIT + D&A).

---

## 3. Refactor Steps 4–6

### 3.1 General approach

Steps 4, 5, and 6 currently read from CVM-specific DataFrame columns. They need
to read from the `CompanyFinancials` object instead.

**Strategy:** Each step receives `CompanyFinancials` as input. Internally, if it's
easier to convert back to a DataFrame for the heavy computation (pandas is good at
this), that's fine — but the interface boundary uses the common model.

The most practical approach may be:

1. `CompanyFinancials` → internal DataFrame (with common model column names like
   `revenue`, `cogs`, `gross_margin_pct`) → run existing algorithms → return results

This means the internal DataFrame uses **English common model names** instead of
CVM Portuguese names. The algorithms themselves don't change — only the column
names they reference.

### 3.2 Step 4 — Metrics Computation

Current: Reads CVM DataFrame, computes margins, ratios, period-over-period changes.

Refactored:
- Input: `CompanyFinancials`
- Convert income statements to a DataFrame with common model column names
- Run existing metric computation logic (unchanged except column name references)
- Output: Same metrics structure as before (for the API response)

Derived ratios that the adapter doesn't compute (gross_margin_pct, ebitda_margin_pct,
cogs_pct_revenue, sga_pct_revenue) are computed here in Step 4, just as they are now.

### 3.3 Step 5 — Data Quality

Current: Validates data ranges, flags anomalies, assigns confidence scores.

Refactored:
- Input: `CompanyFinancials` + Step 4 metrics
- Same logic, different column name references
- Output: Same quality structure as before

### 3.4 Step 6 — Pattern Detection

Current: Runs 6 detection algorithms + materiality + composite signals.

Refactored:
- Input: `CompanyFinancials` + Step 4 metrics + Step 5 quality flags
- Same algorithms, different column name references
- Output: Same findings structure as before (codes, severities, categories,
  materiality values, risk score)

### 3.5 Module availability gating (foundation only)

Add a function that checks which analysis modules can run based on data availability:

```python
def determine_active_modules(financials: CompanyFinancials) -> list[str]:
    """Check which analysis modules can fire based on available data."""
    active = []

    # Module 1: Profitability — requires income statements
    if (financials.income_statements
            and len(financials.income_statements) >= 4):
        active.append("profitability")

    # Module 2: Balance Sheet Health — requires balance sheets (Sprint 3)
    if (financials.balance_sheets is not None
            and len(financials.balance_sheets) >= 4):
        active.append("balance_sheet_health")

    # Module 3: Cash Flow Quality — requires cash flows (Sprint 3)
    if (financials.cash_flows is not None
            and len(financials.cash_flows) >= 4):
        active.append("cash_flow_quality")

    return active
```

In Sprint 1, this function will always return `["profitability"]` only, since
balance_sheets and cash_flows are None. But the gating mechanism is in place
for Sprints 3 and 4 to use.

### 3.6 What does NOT change

- **Steps 7, 8, 9 (AI agent, summary, Q&A):** These receive the output of Steps 4-6
  as structured data (findings, metrics, risk scores). They don't read from the
  DataFrame or CompanyFinancials directly. No changes needed.
- **Frontend:** No changes. The API response shapes remain identical.
- **API endpoints:** The endpoint signatures and response schemas stay the same.
  The refactor is entirely behind the API boundary.
- **Cache layer:** No changes. Cached responses remain valid.

---

## 4. Files to Modify (Expected)

This is a guide, not an exhaustive list. The actual files depend on the current
codebase structure. Claude Code should inspect the codebase to identify all files
that reference CVM-specific column names.

### New files
- `backend/models/__init__.py`
- `backend/models/company.py`
- `backend/models/period.py`
- `backend/models/financial_statements.py`
- `backend/models/company_financials.py`
- `tests/regression/braskem_baseline.json`
- `tests/regression/vale_baseline.json`
- `tests/regression/votorantim_baseline.json`
- `tests/test_regression.py`

### Modified files (CVM adapter)
- Whatever file(s) implement Steps 1-3 (download, clean, pivot) — add the
  `dataframe_to_company_financials()` conversion at the end

### Modified files (Analysis engine)
- Whatever file(s) implement Step 4 (metrics) — change column name references
- Whatever file(s) implement Step 5 (quality) — change column name references
- Whatever file(s) implement Step 6 (detection) — change column name references
- Add `determine_active_modules()` function

### Files NOT modified
- Step 7, 8, 9 files
- Frontend files
- API endpoint files (response shapes unchanged)
- Cache files
- i18n files
- CSS/design files

---

## 5. Testing Checklist

### 5.1 Regression tests (automated)
- [ ] `test_regression.py` passes for Braskem
- [ ] `test_regression.py` passes for Vale
- [ ] `test_regression.py` passes for Votorantim Cimentos
- [ ] All numerical values match within tolerance (1e-6)
- [ ] All finding codes, severities, categories match exactly
- [ ] Risk scores match within 0.1

### 5.2 Structural tests
- [ ] `CompanyFinancials` dataclass instantiates correctly
- [ ] CVM adapter returns `CompanyFinancials` (not DataFrame)
- [ ] `determine_active_modules()` returns `["profitability"]` for current data
- [ ] `determine_active_modules()` returns `[]` for empty data
- [ ] `balance_sheets` is None in adapter output
- [ ] `cash_flows` is None in adapter output

### 5.3 Manual smoke test
- [ ] Start the app, select Braskem, run full 9-step pipeline
- [ ] Verify Step 4 charts render correctly
- [ ] Verify Step 5 quality flags appear
- [ ] Verify Step 6 findings match expected count and codes
- [ ] Verify Step 7 AI agent streams correctly
- [ ] Verify Step 8 executive summary renders
- [ ] Verify Step 9 Q&A works
- [ ] Repeat for Vale
- [ ] Repeat for Votorantim Cimentos
- [ ] Test bilingual toggle (PT-BR / EN) still works

### 5.4 Edge cases
- [ ] Company with sparse data (fewer periods) — does it degrade gracefully?
- [ ] Company not found — does the error handling still work?
- [ ] Cached responses — do they still load correctly?

---

## 6. Definition of Done

- [ ] `phase3-common-model` branch created from master
- [ ] Regression baselines captured before any code changes
- [ ] Common data model dataclasses defined in `backend/models/`
- [ ] CVM adapter outputs `CompanyFinancials`
- [ ] Steps 4-6 read from common model (no CVM-specific column names)
- [ ] `determine_active_modules()` implemented
- [ ] All regression tests pass
- [ ] Manual smoke test passes for all 3 companies
- [ ] No frontend changes required (API response shapes unchanged)
- [ ] Code committed and pushed to `phase3-common-model` branch
