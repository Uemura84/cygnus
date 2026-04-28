# Cygnus — Product Vision & Core Architecture

> **What this is:** The foundational architecture document for the Cygnus financial
> signal detection and decision intelligence platform. Defines the product vision,
> the 9-step pipeline, the analysis module system, the distress scoring engine,
> the reasoning engine, and the source adapter architecture.
>
> **This is a DESIGN document.** It reflects the current implemented state plus
> the planned evolution. Individual build specs reference this document for
> data contracts and architectural decisions.
>
> **Last updated:** April 27, 2026

---

## 1. Product Vision

**What we're building:** A financial signal detection and decision intelligence
platform for CFOs and senior finance leaders. It ingests financial data from any
source, detects value leakage signals, stacks and combines them into a diagnosis,
scores financial distress, quantifies the economic impact, and maps the path from
findings to decisions.

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
- Layer 3: Signals → Diagnosis (what signal stacking + distress scoring + AI agent + domain expertise do)
- Layer 4: Diagnosis → Decisions (what the consulting engagement delivers)

Most tools stop at Layer 1 or 2. Cygnus operates at Layers 2-3 and bridges to Layer 4.
Individual signals are evidence. Stacked signals are a diagnosis.
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

## 2. Architecture: The 9-Step Pipeline

### Layer 1: Source Adapters (Steps 1-3)

Each data source has its own adapter that handles ingestion, cleaning, and
transformation into the Common Financial Data Model.

- **Step 1 — Download:** Fetch data from source (CVM portal ZIP files, SEC EDGAR, ERP export)
- **Step 2 — Quality Filters:** Source-specific cleaning, deduplication, encoding normalization
- **Step 3 — Statement Mapping:** Transform source schemas into common model; parse IS, BS, CF, DVA, DMPL, DRA statements

Adapters are independent modules. Adding a new data source means writing a new adapter —
it does NOT require changes to the analysis engine.

**Current adapter:** CVM (Brazilian Securities Commission) — fully implemented
**Planned adapters:** SEC EDGAR (US), ERP Extract (SAP FI/CO, Oracle), Manual Upload (CSV/Excel)

### Layer 2: Analysis Engine (Steps 4-6)

Source-agnostic modules that operate on the common financial data model:

- **Step 4 — Financial Metrics:** Compute derived metrics (margins, ratios, bridges, period changes). LLM-generated chart interpretations and section headlines (language-keyed sidecar cache).
- **Step 5 — Quality Scan:** Validate data ranges, flag anomalies, auditor assessment, assign confidence scores
- **Step 6 — Core Analysis:** Pattern detection across 5 modules (profitability, balance sheet, cash flow, auditor, equity), signal stacking, reasoning engine, distress scoring engine

### Layer 3: AI Intelligence (Steps 7-9)

- **Step 7 — AI Industry Specialist:** 5 parallel Claude API calls (macro_context, profitability, balance_sheet, cash_flow, cross_module). Prompt engineering with severity authority, anti-hedging rules, dominant-stance enforcement, CFO lens. Reasoning engine output injected into cross_module call.
- **Step 8 — Executive Summary:** Claude-generated narrative synthesis (what_happened, how_serious, when_things_turned, what_comes_next, what_we_cant_answer)
- **Step 9 — Ask the Specialist:** Open-ended Q&A conversation via WebSocket streaming

### AI Agent Capabilities (Steps 7, 8, 9)

The AI agent produces **mixed-media output** — text, charts, diagrams, and structured data.
It can embed structured chart data within its text responses, which the frontend parses
and renders as interactive Recharts visualizations inline.

The AI agent has access to tools that enhance analysis:
- **Web search** — current commodity prices, exchange rates, company news
- **Document retrieval** — CVM filings, explanatory notes
- **Calculation tools** — scenario modeling, sensitivity analysis
- **Data lookup** — external benchmarks, industry averages

---

## 3. Common Financial Data Model

### 3.1 Design Principles

1. **Minimal but sufficient.** Include only accounts that the analysis engine actually uses.
2. **Source-agnostic naming.** English-language standard names, not source-specific codes.
3. **Absolute values + derived ratios.** Store both raw BRL/USD amounts AND computed percentages.
4. **Period-flexible.** Support annual, quarterly, and monthly granularity.
5. **Nullable fields.** Missing data is None, not zero. The analysis engine handles gaps gracefully.

### 3.2 Core Tables

#### Company

```
company:
  id: str                    # unique identifier (CVM code, SEC CIK, internal ID)
  name: str                  # display name ("BRASKEM S.A.")
  source: str                # data source identifier ("cvm", "sec", "erp", "manual")
  country: str               # ISO country code ("BR", "US")
  currency: str              # reporting currency ("BRL", "USD")
  sector: str | None         # sector classification (27 sectors + In Bankruptcy/Unclassified)
  sector_source: str         # "mapped" | "inferred" | "unknown"
```

#### Income Statement

```
income_statement:
  company_id: str
  period: Period

  # Revenue
  revenue: float | None
  cost_of_goods_sold: float | None
  gross_profit: float | None

  # Operating expenses
  sga_expenses: float | None
  selling_expenses: float | None
  general_admin: float | None
  other_operating: float | None

  # Operating profit
  ebit: float | None
  depreciation_amortization: float | None
  ebitda: float | None

  # Below the line
  financial_result: float | None
  income_before_tax: float | None
  income_tax: float | None
  net_income: float | None

  # Derived ratios (computed by Step 4)
  gross_margin_pct, ebit_margin_pct, ebitda_margin_pct,
  cogs_pct_revenue, sga_pct_revenue
```

#### Balance Sheet

```
balance_sheet:
  # Assets
  total_assets, current_assets, cash_and_equivalents,
  accounts_receivable, inventories, non_current_assets,
  property_plant_equipment, intangible_assets

  # Liabilities
  total_liabilities, current_liabilities, accounts_payable,
  short_term_debt, non_current_liabilities, long_term_debt

  # Equity
  total_equity, retained_earnings

  # Derived metrics (Step 4)
  net_debt, working_capital, current_ratio, quick_ratio,
  debt_to_ebitda, receivable_days, inventory_days, payable_days,
  cash_conversion_cycle, return_on_assets, return_on_equity, asset_turnover
```

#### Cash Flow Statement

```
cash_flow:
  # Operating
  operating_cash_flow, depreciation_amortization,
  working_capital_change, other_operating

  # Investing
  investing_cash_flow, capex, acquisitions, other_investing

  # Financing
  financing_cash_flow, debt_issuance, debt_repayment,
  dividends_paid, equity_issuance, other_financing

  # Derived (Step 4)
  free_cash_flow, ocf_to_net_income, capex_to_revenue, capex_to_depreciation
```

#### Value Added Statement (DVA — CVM-specific)

```
dva:
  revenues, inputs_acquired, gross_value_added, net_value_added,
  distribution_employees, distribution_government,
  distribution_lenders, distribution_shareholders
```

#### Changes in Equity (DMPL) & Comprehensive Income (DRA)

```
dmpl: net_income, dividends, oci, equity_movements
dra: net_income, oci_components (FX, hedge, actuarial), comprehensive_income_ratio
```

### 3.3 The Adapter Contract

Every source adapter produces a `CompanyFinancials` object containing company
metadata, income statements, balance sheets, cash flows, and supplementary
statements (DVA, DMPL, DRA where available). The analysis engine receives this
object and doesn't care how it was produced.

### 3.4 Account Mapping

Each adapter maps source-specific accounts to the common model:

| Source | Revenue | COGS | Total Assets | Total Equity |
|--------|---------|------|--------------|--------------|
| CVM | CD_CONTA 3.01 | CD_CONTA 3.02 | CD_CONTA 1 | CD_CONTA 2.03 |
| SEC EDGAR | us-gaap:Revenue | us-gaap:CostOfGoodsSold | us-gaap:Assets | us-gaap:StockholdersEquity |
| SAP FI/CO | GL 4000-4999 | GL 5000-5999 | Configurable | Configurable |

---

## 4. Analysis Modules (Step 6)

### Module 1: Profitability Analysis — IMPLEMENTED

**Data required:** Income Statement
**Algorithms (6):** Margin compression/expansion, cost composition drift, revenue-cost
decoupling, YoY same-period comparison, statistical anomalies, materiality estimation

### Module 2: Balance Sheet Health — IMPLEMENTED

**Data required:** Balance Sheet + Income Statement (for cross-statement ratios)
**Algorithms (7):** Leverage escalation, working capital deterioration, liquidity stress,
asset efficiency decline, cash conversion cycle expansion, debt maturity risk, equity erosion

### Module 3: Cash Flow Quality — IMPLEMENTED

**Data required:** Cash Flow Statement + Income Statement
**Algorithms (6):** Earnings quality gap (OCF/NI ratio), CAPEX starvation,
free cash flow erosion, debt dependency, dividend sustainability, working capital cash drain

### Module 4: Auditor Assessment — IMPLEMENTED

**Data required:** Parecer (auditor opinion), FRE (reference form)
**Algorithms (3):** AUD001 (qualified opinion), AUD002 (emphasis of matter / going concern),
AUD003 (auditor changes — flagged as weak signal)

### Module 5: Equity & Value Distribution — IMPLEMENTED

**Data required:** DVA, DMPL, DRA statements
**Patterns detected:** Equity erosion, dividend sustainability vs FCF, OCI volatility,
labor cost escalation, government burden shift, capital return compression

### Signal Stacking Engine

Combines findings across modules into composite diagnoses:
- `STRUCTURAL_COMPETITIVENESS_ISSUE`: margin + cost + revenue signals
- `NEGATIVE_OPERATING_LEVERAGE`: cost growing faster than revenue
- `FINANCIAL_DISTRESS_RISK`: margin + leverage + negative FCF
- `WORKING_CAPITAL_TRAP`: cost drift + inventory/receivable accumulation
- `CONFIRMED_RECOVERY`: margin expansion + leverage reduction + positive FCF

Each stacked diagnosis requires signals from at least 2 modules (`min_modules: 2`).

---

## 5. Distress Scoring Engine (v1.5)

Replaces the legacy additive signal-intensity score with a layered distress score.

### Three-Layer Architecture (max 100 points)

**Layer 1 — Gating Facts (up to 60 pts):**
Binary structural checks that indicate fundamental trouble.

| Code | Factor | Points |
|------|--------|--------|
| G01 | Negative equity | 20 |
| G02 | Going concern opinion from auditor | 15 |
| G03 | Persistent liquidity stress (CR < 1.0 for 3+ periods) | 10 |
| G04 | Distributing dividends while insolvent | 8 |
| G05 | Financing dependence for payouts | 5 |
| G06 | Technical insolvency trajectory | 2 |

**Layer 2 — Fundamentals (up to 30 pts):**
Continuous metrics measuring financial health.

| Component | Max Points |
|-----------|-----------|
| Profitability (margin levels/trends) | 10 |
| Cash generation (FCF, operating CF) | 8 |
| Leverage (debt/EBITDA, debt/equity) | 6 |
| Liquidity (current ratio, quick ratio) | 6 |

**Layer 3 — Signals (capped at 10 pts):**
Pattern detection findings from Step 6, weighted by cycle classifier.

### Cycle Classifier

Determines whether findings are structural deterioration or cyclical noise.
Uses a 10pp gross margin range guardrail and 5-test classification:

| Classification | Multiplier | When applied |
|---------------|-----------|--------------|
| Gating | 1.0 | Always full weight |
| Structural | 1.0 | Persistence > sector cycle length |
| Ambiguous | 0.5 | Guardrail active + short persistence, or single-period anomalies |
| Cyclical | 0.3 | Finding near cycle peak, YoY base effects |

### Six Distress Bands

| Band | Score Range |
|------|-----------|
| Healthy | 0–19 |
| Stable | 20–39 |
| Watchlist | 40–59 |
| High Risk | 60–79 |
| Distress | 80–89 |
| Severe Distress | 90–100 |

### Band Overrides

- **O1:** G01 (negative equity) + G02 (going concern) → floor at Distress minimum
- **O2:** G01 + negative FCF + CR < 1.0 → floor at High Risk minimum

### Calibration Examples

| Company | Score | Band | Key Factors |
|---------|-------|------|-------------|
| Braskem | 100 | Severe Distress | G01+G02+G03 (60), fundamentals maxed (30), signals capped (10) |
| Vale | 13 | Healthy | No gating facts, fundamentals 3/30, signals 10 (cyclical ×0.3) |
| Suzano | 23 | Stable | No gating facts, moderate fundamentals |

### Implementation

Located in `backend/pipeline/distress/`:
- `distress_scorer.py` — main orchestrator
- `gating_facts.py` — 6 gating fact detectors (G01-G06)
- `fundamentals_scorer.py` — 4 metric components (max 30)
- `cycle_classifier.py` — 10pp guardrail + classification heuristics
- `band_overrides.py` — O1/O2 override logic + band mapping
- `sector_config.py` — 30 sector configurations with signal weights
- `step6_adapter.py` — extracts inputs from pipeline data

---

## 6. Reasoning Engine

Provides structured, deterministic reasoning over detection findings before
they reach the LLM layer. Located in `backend/pipeline/reasoning_engine.py`,
`evidence_chains.py`, `explanation_ranker.py`.

### Knowledge Base (`backend/knowledge/`)

- **15 canonical concepts** (`canonical_concepts.yaml`): Financial principles that
  explain patterns (e.g., operating leverage, cost stickiness, margin compression)
- **14 financial relationships** (`financial_relationships.yaml`): Cause-effect
  links between metrics (e.g., COGS↑ → Gross Margin↓)
- **5 explanation templates** (`explanation_templates.yaml`): Narrative patterns
  that combine concepts and relationships into coherent explanations
- **568 companies** (`company_sectors.yaml`): Classified into 27 sectors for
  sector-specific analysis thresholds

### Pipeline

1. **Finding annotation:** Each Step 6 finding is tagged with matching canonical concepts
2. **Evidence chains:** Relationship matching walks the knowledge graph to build
   multi-step causal chains (e.g., revenue decline → margin compression → FCF erosion)
3. **Explanation ranking:** Templates are scored by concept coherence, evidence
   chain coverage, and finding count. Top-ranked explanations are injected into
   the Step 7 cross_module LLM call as structured context.

---

## 7. AI Prompt Architecture (Step 7)

### 5 Parallel LLM Calls

Each call receives the full financial context but focuses on one domain:

| Call | Focus | Key Data |
|------|-------|----------|
| macro_context | Macro environment, sector dynamics | Time series, sector info |
| profitability | Margin trends, cost structure | IS metrics, bridges |
| balance_sheet | Leverage, liquidity, working capital | BS series, ratios |
| cash_flow | Cash generation, investment, financing | CF series, FCF |
| cross_module | Integrated diagnosis, interactions | All findings + reasoning engine output |

### Prompt Rules

- **Severity authority:** Deterministic distress score sets the severity ceiling.
  LLM cannot upgrade severity beyond what the data supports.
- **Anti-hedging:** Banned phrases ("could potentially", "may or may not", "it remains
  to be seen"). Every sentence must commit to a direction.
- **Dominant stance enforcement:** Each section must declare POSITIVE, NEGATIVE, or
  NEUTRAL in the first line. All subsequent analysis must be consistent with that stance.
- **Evidence over sector priors:** The LLM must cite specific data points, not
  general sector knowledge. "Petrochemical margins are cyclical" is not an acceptable
  explanation without supporting the company's specific data.
- **CFO lens:** Output is framed for a CFO audience. Action-oriented, materiality-aware,
  no academic hedging.

---

## 8. Visual Identity (v4)

### Color System

| Token | Hex | Usage |
|-------|-----|-------|
| Navy | #0b1f3a | Product canvas, deep backgrounds, derived metrics in charts |
| Financial Blue | #2E86C1 | Chart data series (revenue, primary metrics) |
| Cost Red | rgba(192,57,43,0.65) | Chart cost/liability series (COGS, payables) |
| Cygnus Teal | #0e8f9a | UI chrome (sidebar, active states, healthy gauge band) |
| Amber | #EF9F27 | Watchlist gauge band, warning states |
| Off-white | #f5f7fa | Content backgrounds |
| Charcoal | #2b2b2b | High-contrast text |

### Typography

| Font | Weights | Usage |
|------|---------|-------|
| IBM Plex Sans | 400/500/600/700 | All UI text: headings, labels, buttons, body |
| IBM Plex Mono | 400/600/700 | Data values, chart axes, finding codes, monospace |

### Chart Components (Frontend — Recharts)

- `RevenueCOGSGrowth` — Revenue vs COGS bars with Gross Profit line
- `MarginTrajectory` — Dual Y-axis: margins (left) + COGS/Revenue (right)
- `WaterfallChart` — Reusable bridge/waterfall (margin, equity, cashflow, DVA)
- `WorkingCapitalChart` — Two-panel: net WC line (top) + component decomposition (bottom)
- `CashConversionCycleChart` — Two-panel: CCC line (top) + component lines (bottom)
- `RiskGauge` — Semi-circle gauge with 6-band gradient + needle
- `DataFunnel` — Step 2 data quality visualization
- `MacroTimeline` — Macro context timeline
- `FindingChart` — Individual finding visualization

### Chart Export Pipeline

High-res PNG export via Playwright screenshots of the actual Recharts components
at 3× device scale. The frontend includes a hidden `?export=charts` route
(`ExportCharts.jsx`) that renders charts with cached data. `capture.mjs` uses
headless Chromium to screenshot each chart by DOM id. Output is pixel-identical
to the browser rendering.

---

## 9. CVM Adapter (Current Implementation)

### Data Sources Downloaded

| File Type | Content | Parsed By |
|-----------|---------|-----------|
| DFP (Annual) | Income Statement, Balance Sheet | `metrics_calculator.py` |
| ITR (Quarterly) | Income Statement, Balance Sheet | `metrics_calculator.py` |
| FRE (Reference Form) | Auditor profiles, debt maturity/currency, foreign bonds | `fre_parser.py` |
| Parecer | Auditor opinions | `parecer_classifier.py` |
| DFC | Cash Flow Statement | `metrics_calculator.py` |
| DVA | Value Added Statement | `dva_parser.py` |
| DMPL | Changes in Equity | `dmpl_parser.py` |
| DRA | Comprehensive Income | `dra_parser.py` |

### Company Name Matching

Uses exact-match-first pattern across all parsers to prevent sibling companies
from contaminating each other's data (e.g., "PETROLEO" matching both
PETROLEO BRASILEIRO and REFINARIA DE PETROLEOS MANGUINHOS, or "SUZANO"
matching both SUZANO S.A. and SUZANO HOLDING S.A.).

### Data Coverage

- **Years:** 2020–2025 (configurable in `config.py`)
- **Companies:** 568 classified into 27 sectors
- **Historical data available:** CVM portal has filings back to at least 2010

---

## 10. Source Adapter Roadmap

**Build principle: adapters are built when data exists, not speculatively.**

### Adapter 1: CVM — IMPLEMENTED

**Status:** Complete. Full IS, BS, CF, DVA, DMPL, DRA, FRE, Parecer parsing.
Multi-company support with exact-match company name resolution.

### Adapter 2: SEC EDGAR — FUTURE

**Status:** Not started — build when targeting US market
**Format:** XBRL (US GAAP taxonomy)
**Build trigger:** When English-language publishing creates inbound US/UK interest

### Adapter 3: ERP Extract — FUTURE

**Status:** Not started — build when first client provides data
**Format:** CSV/Excel from SAP, Oracle, NetSuite
**Strategic value:** The adapter configuration IS the Data Readiness Assessment engagement

### Adapter 4: Manual Upload — FUTURE

**Status:** Not started
**Build trigger:** When self-service prospect needs arise

---

## 11. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14, FastAPI, uvicorn |
| Frontend | React 18, Vite, Recharts |
| AI | Claude API (streaming over WebSocket) |
| Charts (PDF) | matplotlib + reportlab (SVG→Drawing pipeline) |
| Charts (Export) | Playwright headless Chromium screenshots |
| Fonts | IBM Plex Sans + IBM Plex Mono (Google Fonts) |
| Styling | CSS Modules, CSS custom properties |
| i18n | EN + PT-BR (frontend JSON + backend status strings) |
| Cache | JSON file cache per company per step, language-keyed for LLM steps |

---

## 12. Pipeline Data Flow

```
Step 1 (Download)
  └─ CVM ZIP files → data/raw/

Step 2 (Quality Filters)
  └─ Dedup, encoding, company matching → clean data

Step 3 (Transformation)
  └─ Parse IS, BS, CF, DVA, DMPL, DRA, FRE, Parecer
  └─ Map to Common Financial Data Model

Step 4 (Financial Metrics)
  └─ Compute margins, ratios, bridges, period changes
  └─ LLM chart interpretations (language-keyed cache)
  └─ Output: time_series, balance_sheet_series, cash_flow_series,
             dva_series, dmpl_series, dra_series, bridges

Step 5 (Quality Scan)
  └─ Data range validation, anomaly detection
  └─ Auditor assessment
  └─ Confidence scoring

Step 6 (Core Analysis)
  └─ 5 detection modules → raw findings
  └─ Signal stacker → composite diagnoses
  └─ Reasoning engine → evidence chains, ranked explanations
  └─ Distress scorer → 0-100 score, 6-band classification
  └─ Output: findings, stacked_diagnoses, risk_score, risk_level, distress{}

Step 7 (AI Industry Specialist)
  └─ 5 parallel Claude calls (streaming via WebSocket)
  └─ Reasoning engine output injected into cross_module
  └─ Language-keyed cache (step7_en.json / step7_pt-br.json)

Step 8 (Executive Summary)
  └─ Claude narrative synthesis (streaming)
  └─ Language-keyed cache (step8_en.json / step8_pt-br.json)

Step 9 (Q&A)
  └─ Open conversation via WebSocket
  └─ Full pipeline context available to Claude
```
