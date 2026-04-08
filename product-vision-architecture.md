# Decision Intelligence for CFOs — Product Vision & Core Architecture

> **What this is:** The foundational architecture document for evolving the CVM Demo App
> into a source-agnostic financial signal detection and decision intelligence platform.
> Defines the common financial data model, the adapter pattern, the analysis module
> system, and the signal stacking engine.
>
> **This is a DESIGN document, not a build spec.** It establishes the architecture that
> all future development should follow. Individual build specs (Phase 3, 4, 5) reference
> this document for the data contracts.
>
> **Last updated:** April 2, 2026

---

## 1. Product Vision

**What we're building:** A financial signal detection and decision intelligence
platform for CFOs and senior finance leaders. It ingests financial data from any
source, detects value leakage signals, stacks and combines them into a diagnosis,
quantifies the economic impact, and maps the path from findings to decisions.

**What this is NOT:** This is not another BI dashboard, FP&A tool, or financial
reporting platform. CFOs already have more metrics than they know what to do with.
The gap isn't between data and analysis — it's between analysis and action.

**The four questions this product answers:**
1. **How much money is at stake?** → Materiality layer (economic impact estimation)
2. **Where is it leaking?** → Signal detection (which accounts, which periods, which patterns)
3. **What might be causing it?** → AI hypothesis generation (root cause theories)
4. **What data would prove it?** → Data readiness gap mapping (internal data sources needed)

**Core insight:** The value chain has four layers:
- Layer 1: Data → Metrics (what ERP and BI tools do)
- Layer 2: Metrics → Signals (what detection algorithms do)
- Layer 3: Signals → Diagnosis (what signal stacking + AI agent + domain expertise do)
- Layer 4: Diagnosis → Decisions (what the consulting engagement delivers)

Most tools stop at Layer 1 or 2. This product operates at Layers 2-3 and bridges
to Layer 4. Individual signals are evidence. Stacked signals are a diagnosis.
The product presents the diagnosis, not just the evidence.

**Value proposition:** "We found R$9 billion of margin pressure in your financial
data, generated 7 hypotheses for what's driving it, and mapped exactly which internal
data you need to confirm each one. Here's the decision framework."

**Competitive positioning:**
- vs. Power BI / Tableau: They show you numbers. We tell you what the numbers mean.
- vs. FP&A tools (Anaplan, Planful): They help you plan. We help you understand
  why your plans aren't working.
- vs. Big 4 consulting: They take 3 months and charge $500K. We surface the same
  patterns in 30 minutes and focus the engagement on confirmation and action.
- vs. AI-native analytics (Maxa, etc.): They solve data coherence. We solve data
  interpretation. Most defensible position: upstream diagnostic before platform selection.

**The moat:** The combination of financial domain expertise (knowing what questions
CFOs actually ask), data engineering capability (knowing how messy enterprise data
really is), and AI orchestration (knowing how to make LLMs produce genuinely useful
financial analysis, not generic summaries). No pure-play AI company has the F&A
domain depth. No Big 4 firm has the technical agility. No BI vendor operates at
the hypothesis layer.

---

## 2. Architecture: Three Layers

### Layer 1: Source Adapters (Steps 1-3)

Each data source has its own adapter that handles:
- **Step 1 — Ingest:** Download, connect, or receive data from the source
- **Step 2 — Clean:** Apply source-specific filters, handle encoding, resolve duplicates
- **Step 3 — Map:** Transform source-specific schemas into the Common Financial Data Model

Adapters are independent modules. Adding a new data source means writing a new adapter —
it does NOT require changes to the analysis engine.

**Current adapter:** CVM (Brazilian Securities Commission)
**Planned adapters:** SEC EDGAR (US), ERP Extract (SAP FI/CO, Oracle), Manual Upload (CSV/Excel)

### Layer 2: Common Financial Data Model

The contract between adapters and the analysis engine. Defined in detail in Section 3.

This model standardizes:
- Account taxonomy (what is revenue, COGS, SG&A, etc.)
- Period representation (annual, quarterly, monthly)
- Currency and unit handling
- Company and segment identification

### Layer 3: Analysis Engine (Steps 4-9)

Source-agnostic modules that operate on the common model:
- **Step 4 — Metrics:** Compute derived metrics (margins, ratios, period changes)
- **Step 5 — Quality:** Validate data ranges, flag anomalies, assign confidence
- **Step 6 — Detection:** Run pattern detection algorithms + risk scoring
- **Step 7 — AI Agent:** Generate hypotheses and context
- **Step 8 — Summary:** Executive narrative synthesis
- **Step 9 — Q&A:** Open conversation with AI agent

### AI Agent Capabilities (Steps 7, 8, 9)

The AI agent is not limited to generating text. It should be able to produce
**mixed-media output** — text, charts, diagrams, and structured data — as part
of its reasoning. It should also be able to use **any available LLM tool or skill**
when necessary to enhance its analysis.

**Visual output (charts and diagrams):**

The AI agent can embed structured chart data within its text responses, which
the frontend parses and renders as interactive visualizations inline. This is
critical because financial analysis is inherently visual — a CFO understands
a chart faster than a paragraph.

Use cases for AI-generated visuals:
- Overlay hypothetical scenarios on actual data (e.g., "what if naphtha cost
  had tracked gas-based feedstock instead?")
- Show the relative magnitude of different factors as a waterfall chart
- Illustrate causal chains as flow diagrams (Mermaid syntax)
- Compare what-if scenarios side by side
- Visualize the timeline of events and their cascading impact
- Show sensitivity analysis (how much does each hypothesis explain?)

Implementation approach: The AI agent outputs structured JSON blocks
(```json:chart) within its markdown response. The frontend MarkdownView
component detects these blocks and renders them as Recharts or Mermaid
components. Chart types: line, bar, waterfall, comparison, and flow diagrams.

**LLM tool and skill use:**

The AI agent should have access to any available tools or skills that enhance
its analysis. This includes but is not limited to:
- **Web search** — to retrieve current commodity prices, exchange rates, recent
  news about the company, industry reports, or regulatory changes
- **Document retrieval** — to reference specific CVM filings, explanatory notes,
  or earnings call transcripts when available
- **Calculation tools** — to perform complex financial computations, scenario
  modeling, or sensitivity analysis on the fly
- **Data lookup** — to cross-reference findings with external benchmarks,
  industry averages, or historical comparisons

The principle: the AI agent should be empowered to use whatever resources it
needs to produce the most insightful analysis possible. The specific tools
available will depend on the deployment context and integrations configured.

---

## 3. Common Financial Data Model

### 3.1 Design Principles

1. **Minimal but sufficient.** Include only accounts that the analysis engine actually
   uses. Don't model the entire chart of accounts.
2. **Source-agnostic naming.** Use English-language standard names, not source-specific
   codes (not CVM's CD_CONTA, not SAP's GL account numbers).
3. **Absolute values + derived ratios.** Store both the raw BRL/USD amounts AND the
   computed percentages. The materiality layer needs absolutes; the pattern detection
   needs ratios.
4. **Period-flexible.** Support annual, quarterly, and monthly granularity. Not all
   sources provide all granularities.
5. **Nullable fields.** Not every source provides every account. Missing data is None,
   not zero. The analysis engine handles gaps gracefully.

### 3.2 Core Tables

#### Company

```
company:
  id: str                    # unique identifier (CVM code, SEC CIK, internal ID)
  name: str                  # display name ("BRASKEM S.A.")
  source: str                # data source identifier ("cvm", "sec", "erp", "manual")
  country: str               # ISO country code ("BR", "US")
  currency: str              # reporting currency ("BRL", "USD")
  sector: str | None         # sector classification if known
  sector_source: str         # "mapped" | "inferred" | "unknown"
```

#### Period

```
period:
  date: date                 # period end date (2025-12-31)
  granularity: str           # "annual" | "quarterly" | "monthly"
  fiscal_year: int           # 2025
  fiscal_quarter: int | None # 1-4 for quarterly, None for annual
  fiscal_month: int | None   # 1-12 for monthly, None otherwise
  is_standalone: bool        # True = standalone period, False = YTD cumulative
  filing_type: str | None    # Source-specific: "DFP", "ITR", "10-K", "10-Q", etc.
```

#### Income Statement

```
income_statement:
  company_id: str
  period: Period

  # Revenue
  revenue: float | None              # Net revenue (BRL/USD)
  cost_of_goods_sold: float | None   # COGS (positive = cost, stored as absolute value)
  gross_profit: float | None         # Revenue - COGS

  # Operating expenses
  sga_expenses: float | None         # Selling, General & Administrative
  selling_expenses: float | None     # Selling only (subset of SGA if available)
  general_admin: float | None        # G&A only (subset of SGA if available)
  other_operating: float | None      # Other operating income/expenses

  # Operating profit
  ebit: float | None                 # Earnings Before Interest and Taxes
  depreciation_amortization: float | None  # D&A (from income statement or cash flow)
  ebitda: float | None               # EBIT + D&A

  # Below the line
  financial_result: float | None     # Net financial income/expense
  income_before_tax: float | None
  income_tax: float | None
  net_income: float | None

  # Derived ratios (computed by Step 4, not stored by adapter)
  gross_margin_pct: float | None
  ebit_margin_pct: float | None
  ebitda_margin_pct: float | None
  cogs_pct_revenue: float | None
  sga_pct_revenue: float | None
```

#### Balance Sheet

```
balance_sheet:
  company_id: str
  period: Period

  # Assets
  total_assets: float | None
  current_assets: float | None
  cash_and_equivalents: float | None
  accounts_receivable: float | None
  inventories: float | None
  non_current_assets: float | None
  property_plant_equipment: float | None  # PP&E (net)
  intangible_assets: float | None

  # Liabilities
  total_liabilities: float | None
  current_liabilities: float | None
  accounts_payable: float | None
  short_term_debt: float | None
  non_current_liabilities: float | None
  long_term_debt: float | None

  # Equity
  total_equity: float | None
  retained_earnings: float | None

  # Derived metrics (computed by Step 4)
  net_debt: float | None              # short_term_debt + long_term_debt - cash
  working_capital: float | None       # current_assets - current_liabilities
  current_ratio: float | None         # current_assets / current_liabilities
  quick_ratio: float | None           # (current_assets - inventories) / current_liabilities
  debt_to_ebitda: float | None        # net_debt / ebitda (requires income statement)
  receivable_days: float | None       # (accounts_receivable / revenue) × 365
  inventory_days: float | None        # (inventories / cogs) × 365
  payable_days: float | None          # (accounts_payable / cogs) × 365
  cash_conversion_cycle: float | None # receivable_days + inventory_days - payable_days
  return_on_assets: float | None      # net_income / total_assets
  return_on_equity: float | None      # net_income / total_equity
  asset_turnover: float | None        # revenue / total_assets
```

#### Cash Flow Statement

```
cash_flow:
  company_id: str
  period: Period

  # Operating
  operating_cash_flow: float | None
  depreciation_amortization: float | None  # D&A (may differ from income statement)
  working_capital_change: float | None
  other_operating: float | None

  # Investing
  investing_cash_flow: float | None
  capex: float | None                 # Capital expenditures (negative = spending)
  acquisitions: float | None
  other_investing: float | None

  # Financing
  financing_cash_flow: float | None
  debt_issuance: float | None
  debt_repayment: float | None
  dividends_paid: float | None
  equity_issuance: float | None
  other_financing: float | None

  # Derived metrics (computed by Step 4)
  free_cash_flow: float | None        # operating_cash_flow + capex
  ocf_to_net_income: float | None     # operating_cash_flow / net_income
  capex_to_revenue: float | None      # |capex| / revenue
  capex_to_depreciation: float | None # |capex| / D&A
```

### 3.3 The Adapter Contract

Every source adapter must produce a `CompanyFinancials` object:

```python
@dataclass
class CompanyFinancials:
    """The output of any source adapter. This is the input to the analysis engine."""

    company: Company
    income_statements: list[IncomeStatement]       # sorted by period date
    balance_sheets: list[BalanceSheet] | None       # None if source doesn't provide
    cash_flows: list[CashFlow] | None              # None if source doesn't provide

    # Metadata
    source: str                                     # "cvm", "sec", "erp", "manual"
    source_version: str                             # adapter version
    extraction_date: datetime
    period_range: tuple[date, date]                 # earliest to latest period
    granularity: list[str]                          # ["annual", "quarterly"]
    data_completeness: dict                         # which statements/fields are populated
```

The analysis engine receives `CompanyFinancials` and doesn't care how it was produced.

### 3.4 Account Mapping Rules

Each adapter maps source-specific accounts to the common model. Examples:

**CVM Adapter mapping:**
```
CD_CONTA "3.01"  → revenue
CD_CONTA "3.02"  → cost_of_goods_sold
CD_CONTA "3.04"  → sga_expenses (or split into sub-accounts)
CD_CONTA "3.05"  → ebit
CD_CONTA "1"     → total_assets
CD_CONTA "1.01"  → current_assets
CD_CONTA "2"     → total_liabilities
CD_CONTA "2.01"  → current_liabilities
CD_CONTA "2.03"  → total_equity
```

**SEC EDGAR mapping (XBRL tags):**
```
us-gaap:Revenue                    → revenue
us-gaap:CostOfGoodsSold            → cost_of_goods_sold
us-gaap:SellingGeneralAndAdmin      → sga_expenses
us-gaap:OperatingIncomeLoss         → ebit
us-gaap:Assets                      → total_assets
us-gaap:Liabilities                 → total_liabilities
us-gaap:StockholdersEquity          → total_equity
```

**SAP FI/CO mapping (configurable per client):**
```
GL accounts 4000-4999              → revenue
GL accounts 5000-5999              → cost_of_goods_sold
GL accounts 6000-6999              → sga_expenses
Cost elements by category          → more granular COGS decomposition
```

The SAP adapter is inherently configurable because every company's chart of accounts
is different. The adapter includes a **field mapping UI** where the consultant (you)
configures which GL accounts map to which common model fields.

---

## 4. Signal Stacking Engine

The most important analytical capability in the product is not individual signal
detection — it's the ability to **stack and combine signals into a diagnosis.**

### Why Signal Stacking Matters

A single signal (e.g., "COGS ratio increased 15pp") is an observation.
Multiple correlated signals ("COGS increased 15pp + revenue fell while costs
didn't + EBIT went negative + margins compressing 4.6pp/year") is a diagnosis.

CFOs don't act on individual observations. They act on diagnoses. The product's
value comes from combining signals across modules and across time periods to
answer the four CFO questions with a unified narrative.

### Current State (Partially Implemented)

Step 6 already has composite signals (STRUCTURAL_COMPETITIVENESS_ISSUE,
NEGATIVE_OPERATING_LEVERAGE) that combine findings. But these are:
- Limited to income statement patterns (Module 1 only)
- Rule-based (hardcoded IF/THEN combinations)
- Not cross-module (can't combine profitability + balance sheet + cash flow signals)

### Target State

**Cross-module signal stacking:**

When multiple modules are active, the stacking engine should detect combinations
that no single module would catch:

- **Margin compression + leverage escalation + negative FCF** = "Company is
  deteriorating operationally AND has no financial cushion. Distress risk is HIGH."

- **COGS drift + inventory build + receivable days growing** = "The company is
  not just facing cost pressure — it's also accumulating unsold inventory and
  having trouble collecting from customers. Working capital is absorbing cash."

- **Revenue growth + margin compression + CAPEX decline** = "Revenue is growing
  but profitability is declining and the company has stopped investing. This
  suggests the growth is low-quality — possibly buying revenue at the expense
  of margin."

- **Margin recovery + debt repayment + positive FCF** = "Recovery signal across
  all three dimensions. The turnaround may be real."

**Signal stacking rules:**

Each stacked signal is a combination rule:

```python
STACKING_RULES = [
    {
        "diagnosis": "FINANCIAL_DISTRESS_RISK",
        "requires": {
            "profitability": ["margin_compression", "cost_drift"],
            "balance_sheet": ["leverage_escalation"],
            "cash_flow": ["negative_fcf"],
        },
        "min_modules": 2,  # must have signals from at least 2 modules
        "severity": "CRITICAL",
        "narrative": "The company is deteriorating operationally and has no financial cushion.",
    },
    {
        "diagnosis": "WORKING_CAPITAL_TRAP",
        "requires": {
            "profitability": ["cost_drift"],
            "balance_sheet": ["inventory_build", "receivable_days_growing"],
        },
        "min_modules": 2,
        "severity": "HIGH",
        "narrative": "Cost pressure is compounded by working capital accumulation.",
    },
    {
        "diagnosis": "LOW_QUALITY_GROWTH",
        "requires": {
            "profitability": ["revenue_growth", "margin_compression"],
            "cash_flow": ["capex_decline"],
        },
        "min_modules": 2,
        "severity": "HIGH",
        "narrative": "Revenue growth is coming at the expense of profitability and investment.",
    },
    {
        "diagnosis": "CONFIRMED_RECOVERY",
        "requires": {
            "profitability": ["margin_expansion"],
            "balance_sheet": ["leverage_reduction"],
            "cash_flow": ["positive_fcf"],
        },
        "min_modules": 2,
        "severity": "LOW",  # positive signal
        "narrative": "Recovery is confirmed across profitability, leverage, and cash generation.",
    },
]
```

**The AI agent leverages stacked signals:** When the AI Industry Specialist (Step 7)
receives stacked signals, it produces dramatically better analysis because it can
reason about the interactions between profitability, leverage, and cash flow —
not just each in isolation.

### Implementation Approach

Signal stacking sits between the individual module detection (Step 6) and the AI
agent (Step 7). The flow is:

1. Module 1 produces profitability signals
2. Module 2 produces balance sheet signals
3. Module 3 produces cash flow signals
4. Stacking engine combines cross-module signals into diagnoses
5. AI agent receives individual signals AND stacked diagnoses

This is a Phase 3 deliverable (alongside Modules 2 and 3), since stacking requires
signals from multiple modules to be meaningful.

---

## 5. Analysis Modules

The analysis engine is organized into modules that can be enabled/disabled independently.

### Module 1: Profitability Analysis (CURRENT — implemented)

**Data required:** Income Statement
**Patterns detected:**
- Margin compression / expansion (Gross, EBIT, EBITDA)
- Cost composition drift (COGS, SGA as % of revenue)
- Revenue-cost decoupling (revenue and cost growing at different rates)
- YoY same-period comparison
- Statistical anomalies in margin metrics
- Peer comparison (when multiple companies)
- Materiality estimation (BRL impact of findings)

### Module 2: Balance Sheet Health (PLANNED — Phase 3)

**Data required:** Balance Sheet + Income Statement (for cross-statement ratios)
**Patterns to detect:**
- Leverage escalation (debt/EBITDA trending up)
- Working capital deterioration (receivable/inventory days growing)
- Liquidity stress (current ratio declining, approaching 1.0)
- Asset efficiency decline (ROA, asset turnover declining)
- Cash conversion cycle expansion
- Debt maturity concentration risk
- Equity erosion (retained earnings declining)

**Detection thresholds (examples):**
- Debt/EBITDA > 3.5× → flag HIGH
- Current ratio < 1.2 → flag MEDIUM, < 1.0 → flag HIGH
- Receivable days > 90 → flag MEDIUM, > 120 → flag HIGH
- Working capital negative → flag HIGH
- ROA declining > 2pp/year → flag MEDIUM

### Module 3: Cash Flow Quality (PLANNED — Phase 3)

**Data required:** Cash Flow Statement + Income Statement
**Patterns to detect:**
- Earnings quality gap (OCF/Net Income ratio declining or < 0.8)
- CAPEX starvation (CAPEX/Revenue or CAPEX/D&A declining)
- Free cash flow erosion
- Debt dependency (financing cash flow consistently positive = borrowing to fund operations)
- Dividend sustainability (dividends > free cash flow)
- Working capital cash drain (operating cash flow reduced by working capital changes)

**Detection thresholds (examples):**
- OCF/Net Income < 0.5 → flag HIGH (earnings not converting to cash)
- CAPEX/D&A < 0.5 → flag HIGH (underinvesting relative to depreciation)
- FCF negative for 3+ periods → flag HIGH
- Dividends > FCF for 2+ periods → flag MEDIUM

### Module 4: Value Distribution (FUTURE — lower priority)

**Data required:** DVA (Value Added Statement) — CVM-specific
**Patterns to detect:**
- Labor cost escalation as % of value added
- Government burden shift (tax as % of value added)
- Capital return compression (return to shareholders declining)

---

## 6. Source Adapter Roadmap

**Build principle: adapters are built when data exists, not speculatively.**
The CVM adapter exists because CVM data is public and available now. The SEC adapter
will be built when there's a reason to analyze US companies. The ERP adapter will be
built when a client hands over data. No adapter should be built ahead of demand.

### Adapter 1: CVM (CURRENT — implemented)

**Status:** Complete (Phase 1 + Phase 2)
**Data available:** Income Statement (DRE), Cash Flow (DFC for D&A), Balance Sheet (BPA/BPP)
**Currently mapped:** Income Statement + D&A only
**Phase 3 will add:** Full Balance Sheet + Full Cash Flow mapping

### Adapter 2: SEC EDGAR (FUTURE — build when targeting US market)

**Status:** Not started — build only when English-language publishing creates demand
**Data available:** Income Statement, Balance Sheet, Cash Flow (all via XBRL)
**Format:** XBRL (structured XML) — well-defined taxonomy (US GAAP)
**Challenges:**
- XBRL tag inconsistency across companies (extended taxonomy elements)
- Fiscal year end varies by company (not always Dec 31)
- Need to handle both 10-K (annual) and 10-Q (quarterly)
- Currency always USD
**Estimated effort:** 1-2 weeks for a working adapter
**Strategic value:** Opens US market, makes English-language content more relevant
**Build trigger:** When LinkedIn content generates inbound interest from US/UK markets

### Adapter 3: ERP Extract (FUTURE — build when first client provides data)

**Status:** Not started — build only when a client engagement requires it
**Data available:** Everything — trial balance, sub-ledger, cost centers, profit centers
**Format:** CSV/Excel exports from SAP, Oracle, NetSuite, etc.
**Challenges:**
- Every company's chart of accounts is different
- Requires a field mapping configuration step
- Data may be monthly (more granular than public filings)
- May include segment-level or product-level breakdowns
- Currency may vary by entity
**Estimated effort:** 2-3 weeks for configurable adapter + mapping UI
**Strategic value:** This is where consulting revenue lives — the adapter configuration
IS the Data Readiness Assessment engagement
**Build trigger:** When a client says "here's our SAP export, can you analyze this?"

### Adapter 4: Manual Upload (FUTURE — build for self-service prospects)

**Status:** Not started
**Data available:** Whatever the user uploads
**Format:** CSV or Excel with user-defined column mapping
**Challenges:**
- Completely unstructured — need a column mapping UI
- Data quality unpredictable
- May have mixed currencies, mixed periods, missing fields
**Estimated effort:** 1-2 weeks for upload + mapping UI
**Strategic value:** Low-friction entry point for prospects who want to try the tool
**Build trigger:** When there's a self-service product motion (post-consulting validation)

---

## 7. How Analysis Modules Use the Common Model

Each analysis module declares what it needs:

```python
MODULE_REQUIREMENTS = {
    "profitability": {
        "required": ["income_statement"],
        "optional": [],
        "min_periods": 4,
    },
    "balance_sheet_health": {
        "required": ["balance_sheet"],
        "optional": ["income_statement"],  # for cross-statement ratios
        "min_periods": 4,
    },
    "cash_flow_quality": {
        "required": ["cash_flow"],
        "optional": ["income_statement"],  # for OCF/NI ratio
        "min_periods": 4,
    },
}
```

When the analysis engine runs (Step 6), it checks which modules can fire based on
data availability:

```python
def determine_active_modules(company_financials: CompanyFinancials) -> list[str]:
    active = []
    for module, reqs in MODULE_REQUIREMENTS.items():
        has_required = all(
            getattr(company_financials, stmt) is not None
            and len(getattr(company_financials, stmt)) >= reqs["min_periods"]
            for stmt in reqs["required"]
        )
        if has_required:
            active.append(module)
    return active
```

The UI shows which modules are active and which are disabled (with a message like
"Balance Sheet analysis requires BPA data — not available from current source").

---

## 8. Impact on Current Codebase

### What changes now (foundation)
- Define the common model as Python dataclasses in a new `backend/models/` directory
- Refactor the CVM adapter to output `CompanyFinancials` instead of raw DataFrames
- Refactor Steps 4-6 to read from `CompanyFinancials` instead of CVM-specific column names

### What changes for Phase 3 (CVM Balance Sheet + Cash Flow)
- Extend CVM adapter to map BPA/BPP accounts to Balance Sheet model
- Extend CVM adapter to map full DFC accounts to Cash Flow model
- Build Module 2 (Balance Sheet Health) detection algorithms
- Build Module 3 (Cash Flow Quality) detection algorithms
- Update Step 6 to run active modules based on data availability
- Update AI agent prompts to reason about balance sheet and cash flow findings

### What changes for Phase 4 (ERP adapter)
- Build the ERP adapter with configurable field mapping
- Build the field mapping UI (a configuration step before the 9-step pipeline)
- The analysis engine (Steps 4-9) requires NO changes — it already works on the common model

### What changes for Phase 5 (SEC adapter)
- Build the SEC EDGAR adapter with XBRL parsing
- Map US GAAP tags to the common model
- Handle USD currency and non-December fiscal year ends
- The analysis engine requires NO changes

---

## 9. Migration Path

The current codebase uses CVM-specific DataFrames with column names like
`DENOM_CIA`, `CD_CONTA`, `DT_REFER`, `Receita de Venda de Bens e/ou Serviços`.

The migration to the common model should be gradual:

**Phase 3a (refactor):** Introduce the common model dataclasses. Update the CVM adapter
(Steps 1-3) to output `CompanyFinancials`. Update Steps 4-6 to read from the common
model fields instead of CVM column names. This is a refactor, not a feature — the
output should be identical.

**Phase 3b (balance sheet + cash flow):** With the common model in place, add BPA/BPP
and full DFC mapping to the CVM adapter. Build Modules 2 and 3.

**Phase 4+:** New adapters plug into the same common model. No analysis engine changes.

---

## 10. The Decision Support Layer (Future — Layer 4)

The current product reaches Layer 3 (Patterns → Hypotheses). The ultimate product
vision extends to Layer 4 (Hypotheses → Decisions). This section outlines what
Layer 4 would look like — not for immediate development, but as the north star.

### What Layer 4 Delivers

For each hypothesis generated by the AI agent, Layer 4 would provide:

**Decision framework:**
- If hypothesis H1 is confirmed → recommended actions A, B, C
- If hypothesis H2 is confirmed → recommended actions D, E, F
- Expected economic impact of each action
- Implementation complexity and timeline estimate

**Investigation plan:**
- Specific data requests to confirm/refute each hypothesis
- Who in the organization owns that data
- What format the data should be in
- Expected timeline to obtain and analyze

**Risk assessment:**
- What happens if no action is taken (status quo trajectory)
- What are the risks of each recommended action
- What are the second-order effects

**Monitoring framework:**
- After action is taken, what metrics should be tracked
- What thresholds trigger escalation
- How frequently should the analysis be re-run

### Why This Is the Consulting Engagement

Layer 4 cannot be fully automated. It requires:
- Understanding of the company's strategic context
- Knowledge of organizational politics and constraints
- Judgment about implementation feasibility
- Accountability for recommendations

This is where the human expert (the consultant) adds irreplaceable value. The product
delivers Layers 1-3 efficiently. The consultant delivers Layer 4. The product makes
the consultant 10x more effective by doing the pattern detection and hypothesis
generation in minutes rather than weeks.

**The business model:** The product is the lead generation engine and the efficiency
multiplier. The consulting engagement is the revenue engine. They reinforce each other.

---

## 11. Non-Goals (For Now)

- **Multi-company comparison across sources** (e.g., Braskem CVM vs. Dow SEC) — interesting
  but complex due to currency, accounting standards, fiscal year differences
- **Real-time data** — all sources are periodic (quarterly/annual). Real-time market data
  is a different product
- **Automated remediation** — the tool identifies problems and generates hypotheses.
  The remediation is the consulting engagement (Layer 4)
- **Replacing FP&A tools** — the product complements, not competes with, budgeting and
  forecasting tools. It answers "why did actual deviate from plan?" not "what should the plan be?"
- **Selling to data teams** — the buyer is the CFO or VP Finance, not the BI team.
  The product must speak financial language, not data language
- **Building adapters ahead of demand** — the ERP adapter, SEC adapter, and manual upload
  adapter are architecturally designed but will only be built when a concrete need exists
  (a client provides data, or a market demands it). No speculative adapter development.

---

## 12. Product Name

**Name:** Cygnus

**Tagline:** Revealing Hidden Value in Financial Data

**Why Cygnus:**
- A constellation — pattern recognition in the sky, parallel to pattern recognition
  in financial data
- Works identically in Portuguese and English
- Short, distinctive, professional — doesn't sound like another BI tool or consulting firm
- Cygnus X-1 is one of the strongest X-ray sources in the sky and the first widely
  accepted black hole — a hidden, powerful force revealed by the right instruments.
  The product reveals hidden value leakage with the right analytical instruments.
- Does not need explanation in a business context — it's a name, not an acronym

**Usage:**
- Product: "Cygnus" or "Cygnus Financial"
- Full formal: "Cygnus — Decision Intelligence for CFOs"
- In conversation: "I ran a Cygnus analysis on your CVM data"
- Tagline for marketing: "Revealing Hidden Value in Financial Data"

---

## 13. Design System

The visual identity serves the product's core message: hidden patterns revealed by the
right instruments. Every design decision reinforces this — the dark canvas suggests depth
and what's hidden beneath the surface, the blue accent marks where signals emerge, and
the typography separates three distinct voices: authority, operations, and data.

### 13.1 Logomark: The Accretion Disk

The Cygnus mark is an accretion disk — concentric elliptical rings converging on a bright
core, representing Cygnus X-1's matter spiraling inward until the hidden force at the
center becomes undeniable.

**Construction:**
- Three concentric ellipses with decreasing size and increasing opacity (0.12 → 0.22 → 0.38)
- A solid blue core circle with a navy-colored inner void (the "black hole")
- The opacity gradient communicates intensity: data converges, signal strengthens toward center

**Metaphor:** Financial data is scattered and faint at the edges. As the analysis converges,
the pattern intensifies until the finding — the core — becomes the brightest element. The
void at the center represents what was hidden; the bright ring around it is the moment of
detection.

**Variants:**
- **On dark (primary):** Blue (#1e90ff) rings and core on navy (#0b1f3a) — used in the
  product UI, demo app navigation, dark headers
- **On light:** Navy (#0b1f3a) rings and core on white/off-white — used in documents,
  slides, light contexts
- **Mark only (no wordmark):** Standalone accretion disk for favicons, app icons, loading
  states, inline references. Designed to be recognizable at 16px
- **Favicon:** Optimized version with thicker strokes and fewer rings for small rendering,
  on navy rounded-square background

**Scaling rules:** At smaller sizes, stroke widths increase and the outermost ring is
dropped. The core circle grows proportionally to maintain the "bright center" effect.
At 16px the mark is two rings and a dot — still recognizable as converging-to-center.

**Files:** `cygnus-logo-dark.svg`, `cygnus-logo-light.svg`, `cygnus-mark.svg`,
`cygnus-favicon.svg`

### 13.2 Color System

Five colors, each with a defined role. The same palette is shared across the consultant
brand, the product, and the content layer — what shifts is which color leads.

```
Navy       #0b1f3a  — Product canvas, deep backgrounds, consultant primary
Signal Blue  #1e90ff  — Accent, interactive elements, findings, the logomark core
Slate      #4a5568  — Body text, secondary information, muted labels
Off-white  #f5f7fa  — Content backgrounds, cards, light surfaces
Charcoal   #2b2b2b  — High-contrast text, headlines on light backgrounds
```

**CSS custom properties (use in all frontend code):**
```css
:root {
  --navy: #0b1f3a;
  --gray: #4a5568;
  --blue: #1e90ff;
  --offwhite: #f5f7fa;
  --charcoal: #2b2b2b;
  --blue-dim: rgba(30, 144, 255, 0.08);
  --blue-line: rgba(30, 144, 255, 0.25);
}
```

**Color emphasis by surface:**

| Token | Cygnus product | Consultant site | Content (Substack/LinkedIn) |
|---|---|---|---|
| Primary background | Navy (dark canvas) | Off-white (light, editorial) | White (clean reading) |
| Accent | Blue (dominant, active) | Blue (sparse, highlights) | Blue (dividers, tags) |
| Headlines | DM Sans 500, white | DM Serif Display, navy | DM Serif Display, navy |
| Data/labels | JetBrains Mono (heavy use) | JetBrains Mono (rare) | JetBrains Mono (inline) |

### 13.3 Typography

Three font families, each serving a distinct voice in the product:

**DM Serif Display — The authority voice**
- Used for: Executive summary narrative (Step 8), article titles, consultant-facing
  headlines, marketing materials
- NOT used in: Product UI navigation, step titles, buttons, metric displays
- The human speaking. Signals domain expertise and editorial credibility
- When Cygnus generates an executive summary, the serif font distinguishes "here is the
  interpretation" from "here are the metrics" — a visual cue that this is Layer 3-4 content

**DM Sans (400/500/600) — The product voice**
- Used for: All product UI headings, step titles, navigation, buttons, body text,
  dialog labels, form elements
- The machine speaking. Clean, operational, no personality. When you see DM Sans in
  Cygnus, the system is talking
- Weight 500 for headings and emphasis, 400 for body text, 600 for buttons and CTAs

**JetBrains Mono — The data voice**
- Used for: Finding codes (COGS_DRIFT), metric values (75%→92%), risk scores
  (SEVERITY:HIGH), section labels, step numbers, account codes, period references,
  confidence scores, data availability tags
- Signals technical precision. A user seeing monospace in Cygnus knows they're looking
  at a data point, not an interpretation
- In articles and content: used inline for specific data references, creating a visual
  link between the content and the product

**Font loading (Google Fonts):**
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1
  &family=DM+Sans:wght@300;400;500;600
  &family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### 13.4 UI Component Patterns

These patterns apply to the Cygnus product UI (the React frontend):

**App shell:** Navy (#0b1f3a) background for navigation bar and sidebar. The analysis
content area stays light (off-white or white) for readability. This creates a clear
visual hierarchy: the chrome is dark (structure), the content is light (data).

**Cards and panels:** Off-white (#f5f7fa) background, 1px border at rgba(11,31,58,0.07),
6px border-radius. On hover: border shifts to rgba(30,144,255,0.25) with subtle
box-shadow at rgba(30,144,255,0.06). Cards are the primary container for findings,
metrics, and analysis results.

**Finding cards (Step 6):** Each finding card uses the standard card pattern plus:
- A monospace tag in the top-left showing the finding code (e.g., `COGS_DRIFT`)
  in blue on blue-dim background
- Severity indicated by left border color: blue for informational, amber for medium,
  red for high/critical (extend the palette with #EF9F27 and #E24B4A for these states)

**Section labels:** JetBrains Mono, 10-11px, uppercase, letter-spacing 0.12-0.15em,
Signal Blue color. Used above every major section to orient the user within the
9-step pipeline. These are the "you are here" markers.

**Metric displays:** Large numbers in DM Sans 500, supporting context in DM Sans 400
at smaller size, labels in JetBrains Mono. Blue left-border accent on stat blocks
(2px solid at 30% opacity).

**Interactive elements:** Buttons use DM Sans 500/600. Primary actions get blue
background with white text. Secondary actions get blue text with blue-line border.
Hover states use blue-dim background.

**Charts and visualizations:** Chart lines and fills use the blue ramp at varying
opacities. Grid lines at rgba(11,31,58,0.06). Axis labels in JetBrains Mono 11px.
Annotations (breakeven lines, trend labels) in JetBrains Mono with blue or gray color.

### 13.5 Step-Specific Design Notes

**Steps 1-3 (Source Adapters):** Minimal UI. Progress indicators, data preview tables.
Monospace for account codes and field names. The visual message: "the data is loading
and being prepared." No editorial voice here.

**Steps 4-5 (Metrics + Quality):** Charts and tables dominate. Dual y-axis charts for
margin trajectory. DM Sans for labels, JetBrains Mono for values. Blue for primary
metrics, gray for secondary. The visual message: "here are the numbers."

**Step 6 (Detection):** Finding cards with severity-colored left borders. Risk gauge
(SVG arc). Show/hide chart toggles per finding. The visual message: "here's what the
system found — in data language."

**Step 7 (AI Agent):** WebSocket streaming text in DM Sans. Hypothesis cards. This is
where the product's AI voice speaks. Charts generated by the AI render inline via the
JSON:chart protocol. The visual message: "here's what the analysis means — transitioning
from data language to financial language."

**Step 8 (Executive Summary):** The ONLY place DM Serif Display appears in the product UI.
The summary uses the story arc structure (What Happened → How Serious → When Things
Turned → What Comes Next → What We Can't Answer). Key findings table with monospace
codes. The visual message: "here is the human-readable narrative — this is what you
present to the CFO."

**Step 9 (Q&A):** Chat interface. User messages right-aligned, AI responses left-aligned.
Suggested question chips in blue-dim with blue text. Conversation history preserved.
Mixed-media AI responses (text + charts). The visual message: "ask anything — the
analysis continues."

### 13.6 Brand Relationship

Cygnus exists within a three-brand architecture:

```
Ricardo Uemura Advisory     →  The consultant (who)
  ↓ publishes
Articles / Substack         →  The authority engine (why trust me)
  ↓ demonstrates
Cygnus                      →  The product (what I built)
```

**When they appear together:** The consultant brand uses "powered by Cygnus" or
"built with Cygnus" — never "Cygnus by Ricardo Uemura" (the product has its own
identity). In demo presentations, the Cygnus logo appears in the app; Ricardo's
name appears in the talk track and the follow-up conversation. The product earns
credibility through the consultant, and the consultant earns leverage through the
product.

**In content:** Articles are authored by Ricardo Uemura, not by Cygnus. The product
is referenced as a tool used in the analysis: "I ran a Cygnus analysis on Braskem's
CVM filings." This keeps the human at the center and the product as the instrument —
consistent with the augmentation-over-automation principle.

**Brand kit reference file:** `cygnus-brand-kit.html` — full visual reference with
all logo variants, color swatches, type specimens, scaling examples, and usage
do/don't guidelines.
