# CVM Financial Analysis — Technical Specification

> Covers: (0) Purpose and architecture, (1) EBITDA driver calculations, (2) the 6 pattern detection algorithms, (3) LLM prompts in Steps 7 and 8.

---

## Part 0 — Purpose and Architecture

### Purpose

The CVM Financial Analysis Demo is a live pipeline that downloads public financial filings from Brazil's securities regulator (CVM/B3), transforms them into structured metrics, detects financial patterns using statistical algorithms, and streams AI-generated hypotheses via the Claude API.

The primary use case is **pre-engagement financial due diligence**: given a Brazilian publicly-listed company, the system surfaces structural cost deterioration, margin compression, peer anomalies, and other quantitative signals — entirely from public data — and then asks: *"What would internal data reveal?"* This frames the value of deeper access for a prospective client or analyst.

### Data Source

All financial data comes from CVM (Comissão de Valores Mobiliários) — the Brazilian equivalent of the SEC. Two filing types are used:

| Filing | Frequency | Coverage |
|---|---|---|
| **DFP** (Demonstrações Financeiras Padronizadas) | Annual | Full-year audited statements |
| **ITR** (Informações Trimestrais) | Quarterly | Unaudited interim statements |

Files are downloaded as ZIP archives from the CVM data portal. Each ZIP contains multiple CSVs: `DRE_con` (income statement), `DFC_MI_con` (indirect-method cash flow), `BPA_con` (balance sheet assets), `BPP_con` (balance sheet liabilities), and others. The pipeline uses only `DRE_con` and `DFC_MI_con`.

### 9-Step Pipeline

The pipeline runs sequentially. Each step is implemented as a Python module in `backend/steps/` exposing a single `run(config, pipeline_state) -> dict` function. Results are cached as JSON in `backend/cache/{company}/stepN.json`.

| Step | Name | What it does |
|---|---|---|
| 1 | **Download** | Fetches DFP/ITR ZIPs from CVM portal for configured years |
| 2 | **Filter** | Extracts and filters DRE rows for the target company |
| 3 | **Transformation** | Deduplicates rows, pivots accounts, builds income statement table |
| 4 | **EBITDA Drivers** | Computes margin ratios, D&A from DFC, YoY growth rates |
| 5 | **Quality Scan** | Validates metric plausibility; flags out-of-range values |
| 6 | **Pattern Detection** | Runs 6 statistical algorithms; scores risk; categorizes findings |
| 7 | **AI Industry Specialist** | Streams macro context + hypotheses via Claude API |
| 8 | **Executive Summary** | Streams a structured C-suite summary integrating Steps 6 + 7 |
| 9 | **Q&A** | Interactive multi-turn chat with full pipeline context |

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (React + Vite)               │
│  StepWizard → StepSidebar + StepContent                  │
│  CompanySelector · LanguageToggle · CacheMode toggle     │
│  Charts: DataFunnel, MarginTrajectory, RevenueCOGSGrowth │
│          FindingChart, MacroTimeline, RiskGauge          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP /api/*  |  WebSocket /ws/llm
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI (uvicorn, port 8000)             │
│  GET  /api/step/{n}        → run step, return JSON       │
│  POST /api/config          → set company / cache mode    │
│  GET  /api/companies       → list available companies    │
│  GET  /api/companies/search?q= → fuzzy search            │
│  WS   /ws/llm              → stream tokens (steps 7–9)   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   Pipeline Modules                        │
│  cvm_downloader   → fetch + cache ZIPs from CVM portal   │
│  data_cleaner     → extract, filter, detect fin. inst.   │
│  metrics_calculator → pivot, margin ratios, D&A, EBITDA  │
│  pattern_detector → 6 algorithms, risk scoring           │
│  enrichment       → SECTOR_MAP, composite signal labels  │
│  narrative_generator → Step 8 prompt assembly            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│               Storage (local filesystem)                  │
│  data/       → raw CVM ZIPs and extracted CSVs           │
│  cache/{co}/ → stepN.json per company                    │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts, CSS Modules |
| Backend | Python 3.11+, FastAPI, uvicorn, pandas, numpy |
| LLM | Anthropic Claude API (`claude-sonnet-4-6`) via `anthropic` SDK |
| Data | CVM public portal (no auth required) |
| Streaming | WebSocket (`ws/wss`); token-by-token streaming from Claude |
| i18n | JSON locale files (`en.json`, `pt-br.json`); runtime toggle |

### Key Design Decisions

**Cache-first with live fallback.** Every step tries the cache first (when cache mode is on), falls back to live computation, and on live failure falls back to cache. This makes the demo resilient to network issues during a presentation.

**Company name as the only config axis.** Switching companies resets all pipeline state and cache lookups. There is no per-step company override — the company is global and set once per session.

**Financial institution detection early.** If COGS (account 3.02) is absent or zero for a company, the pipeline returns a human-readable error at Step 2 rather than propagating null metrics through all downstream steps.

**WebSocket step routing.** A single `/ws/llm` endpoint handles Steps 7, 8, and 9. The payload field `"step"` (7, 8, or 9) determines which handler runs. This keeps the frontend connection logic uniform across all three streaming steps.

**Mock fallback for LLM.** If `ANTHROPIC_API_KEY` is not set, all three streaming steps yield a pre-written mock response word-by-word with 20 ms delays, making the demo fully runnable offline.

---

## Part 1 — EBITDA Driver Calculations

All metrics are computed from CVM DRE (income statement) account codes. Monetary values are normalised to thousands (BRL '000) before any calculation.

### CVM Account Mapping

| CD_CONTA | Description used internally |
|---|---|
| 3.01 | Revenue |
| 3.02 | COGS (reported as negative; always taken as absolute value) |
| 3.03 | Gross Profit |
| 3.04.01 | Selling Expenses |
| 3.04.02 | SG&A |
| 3.05 | EBIT |

### Margin Ratios — computed in `build_pivot()` (`metrics_calculator.py`)

```
COGS_pct_Revenue    = abs(3.02) / 3.01 × 100
Gross_Margin_pct    = 3.03 / 3.01 × 100
EBIT_Margin_pct     = 3.05 / 3.01 × 100
SGA_pct_Revenue     = abs(3.04.02) / 3.01 × 100
Selling_pct_Revenue = abs(3.04.01) / 3.01 × 100
```

### D&A and EBITDA — computed in `compute_metrics()` (`metrics_calculator.py`)

D&A is **not** in the DRE. It is extracted from DFC_MI_con (indirect-method cash flow) files inside the same DFP/ITR ZIPs:

1. Filter DFC rows where `DS_CONTA` matches regex `deprecia|amortiza` (case-insensitive).
2. Sum `VL_CONTA` grouped by `(DENOM_CIA, DT_REFER)`, take the absolute value → `DA_from_DFC`.
3. If no DFC data is found for a period, `DA_from_DFC = 0` (EBITDA falls back to EBIT).

```
EBITDA            = EBIT (3.05) + DA_from_DFC
EBITDA_Margin_pct = EBITDA / 3.01 × 100
```

### YoY Growth Rates — computed in `_build_time_series()` (`step4_ebitda_drivers.py`)

Calculated on annual (DFP) rows only, sorted by date:

```
Revenue_YoY_pct = (Revenue_t − Revenue_t−1) / |Revenue_t−1| × 100
COGS_YoY_pct    = (|COGS_t| − |COGS_t−1|) / |COGS_t−1| × 100
```

The first period always has `null` for both YoY metrics. Displayed as "—" in the UI.

---

## Part 2 — The 6 Pattern Detection Algorithms

All algorithms live in `pipeline/pattern_detector.py`. They receive the enriched annual DataFrame (`df_annual`) or quarterly DataFrame (`df_quarterly`). Each returns a list of finding dicts merged in `detect_patterns()`.

### Data Quality Layer (runs before all 6 algorithms)

`validate_metric_ranges()` checks each row against absolute plausibility bounds:

| Metric | Min | Max |
|---|---|---|
| Gross_Margin_pct | −50% | 80% |
| EBIT_Margin_pct | −50% | 60% |
| COGS_pct_Revenue | 20% | 130% |
| SGA_pct_Revenue | 0% | 40% |

Out-of-range values populate `_plausibility_flags`. Row confidence: `HIGH` (clean), `MEDIUM` (standalone row with flag), `LOW` (non-standalone row with flag).

---

### Algorithm 1 — Margin Trend Analysis

**Input:** Annual DFP rows. Metrics: `Gross_Margin_pct`, `EBIT_Margin_pct`.

**Method:**
1. Requires ≥ 4 annual periods per company.
2. Fits a **linear regression** (`numpy.polyfit`, degree 1) on the margin series indexed 0, 1, 2, …
3. Slope = per-period change. Since input is annual, `annual_change_pp = slope`.
4. Also computes: volatility (std dev), historical average, 4-period trailing average.

**Thresholds:**
- `|annual_change_pp| > 2 pp/year` → **"Margin compression/expansion"**
  - HIGH if `> 5 pp/year`, MEDIUM otherwise
- `volatility > 5 pp` → **"High margin volatility"** (MEDIUM)

**Output fields:** `annual_change_pp`, `current_level`, `volatility`, `periods_analyzed`

---

### Algorithm 2 — Cost Composition Drift

**Input:** Annual DFP rows. Metrics: `COGS_pct_Revenue`, `SGA_pct_Revenue`, `Selling_pct_Revenue`.

**Method:**
1. Requires ≥ 4 periods per company.
2. Splits series into two equal halves: `first_half = series[:n//2]`, `second_half = series[n//2:]`.
3. `shift_pp = mean(second_half) − mean(first_half)`.
4. Also checks for **negative correlation** (`r < −0.5`) between any two cost categories, which signals a potential accounting reclassification.

**Thresholds:**
- `|shift_pp| > 3 pp` → **"Cost composition drift"**
  - HIGH if `> 5 pp`, MEDIUM otherwise
- `correlation < −0.5` between two categories → **"Potential cost reclassification"** (HIGH)

**Output fields:** `first_half_avg`, `second_half_avg`, `shift_pp`

---

### Algorithm 3 — Revenue-Cost Decoupling

**Input:** Annual DFP rows. Uses raw BRL amounts from 3.01 (Revenue) and 3.02 (COGS).

**Method:**
1. Requires ≥ 4 periods per company.
2. Computes period-over-period % change for Revenue and COGS via `pct_change()`.
3. `divergence_pp = (COGS_%_change − Revenue_%_change) × 100` for each period.
4. Flags every period where `|divergence_pp| > 10 pp`.

**Thresholds:**
- `|divergence_pp| > 10 pp` → **"Revenue-cost decoupling"**
  - HIGH if `> 20 pp`, MEDIUM otherwise
- Positive = costs grew faster than revenue (margin pressure). Negative = revenue outpaced costs (expansion).

**Output fields:** `period`, `revenue_change_pct`, `cogs_change_pct`, `divergence_pp`

---

### Algorithm 4 — Peer Comparison

**Input:** All rows; uses most recent period per company (`groupby.tail(1)`). Metrics: `Gross_Margin_pct`, `EBIT_Margin_pct`, `COGS_pct_Revenue`, `SGA_pct_Revenue`.

**Method:**
1. Assigns sector via `SECTOR_MAP` (fragment match on `DENOM_CIA`). Unmapped → "All".
2. Groups by sector. Requires ≥ 2 companies per sector.
3. **n = 2 case:** uses absolute gap (z-score is meaningless at n=2, always ±0.71).
   - Threshold: `gap > 10 pp` for margin metrics, `gap > 15 pp` for cost ratios.
4. **n ≥ 3 case:** computes sector mean and std dev. Flags `|z-score| > 1`.

**Severity:**
- n=2: HIGH if `gap > 20 pp` (margins) or `> 25 pp` (cost ratios).
- n≥3: HIGH if `|z-score| > 2`, MEDIUM if `> 1`.

**Output fields:** `company_value`, `peer_average` (or `peer_value`), `gap_pp` (or `z_score`), `sector`

---

### Algorithm 5 — Statistical Anomaly Detection

**Input:** Quarterly ITR rows (standalone only — YTD rows excluded). Metrics: `Gross_Margin_pct`, `EBIT_Margin_pct`, `COGS_pct_Revenue`.

**Method:** Uses the **IQR (Interquartile Range)** method:
1. Requires ≥ 6 data points per metric per company.
2. Q1, Q3, IQR = Q3 − Q1. Normal range: `[Q1 − 1.5×IQR, Q3 + 1.5×IQR]`.
3. Flags any period outside this range → always HIGH severity.
4. Pre-classifies anomaly type:
   - Value > 100% for a margin/COGS metric → `DATA_ISSUE`
   - Adjacent period also an outlier → `VALID_SIGNAL` (persistent structural shift)
   - Isolated → `LOW_CONFIDENCE_SIGNAL`

**Output fields:** `period`, `value`, `normal_range`, `anomaly_type`

---

### Algorithm 6 — YoY Same-Quarter Comparison

**Input:** Quarterly ITR rows. Metrics: `Gross_Margin_pct`, `EBIT_Margin_pct`.

**Method:**
1. Extracts year and quarter from `DT_REFER`.
2. For each company/metric/quarter combination, computes `yoy_change = value_t − value_{t−1}` (same quarter, prior year). This controls for seasonality.
3. Requires ≥ 2 years of data for a given quarter.
4. Capped at 3 findings per company/metric pair (sorted by worst YoY change).

**Thresholds:**
- `|yoy_change_pp| > 15 pp` → **"YoY quarter comparison"**
  - Threshold is deliberately set at 15 pp because commodity-sector companies routinely see 10–20 pp swings; lower thresholds generate noise.
  - HIGH if `> 25 pp`, MEDIUM otherwise.

**Output fields:** `period` (e.g. "Q3 2022"), `yoy_change_pp`, `current_value`

---

## Part 3 — LLM Prompts

### Step 7 — AI Industry Specialist

**Model:** `claude-sonnet-4-6` | **max_tokens:** 4,000 | **temperature:** 0.7

#### System prompt

```
You are a senior industry specialist and financial analyst with deep expertise in
Brazilian capital markets, commodity-driven industries, and corporate financial
analysis. You have access to CVM (Securities Commission of Brazil) public filings.

You have been given the results of an automated financial pattern detection analysis
on a Brazilian company. The analysis used only public CVM data (DFP annual and ITR
quarterly filings) and detected patterns using statistical methods — no external
context was applied.

Your task is to provide expert context and interpretation:

1. MACRO CONTEXT: What economic, industry, and market events during the analysis
period (2020-2025) might explain the patterns detected? Be specific about timing
and mechanisms — don't just list events, explain how they connect to the specific
findings.

2. HYPOTHESES: For each structural finding (cost deterioration, margin compression),
generate 5-7 possible root causes. For each hypothesis:
   - State the theory clearly
   - Explain the specific mechanism (how would this cause show up in the numbers?)
   - Identify what internal data source would confirm or refute it
   - Rate your confidence (HIGH/MEDIUM/LOW)

3. DATA READINESS ASSESSMENT: What questions does this analysis raise that public
data cannot answer? For each question, identify the specific internal data source
needed and why it matters.

Be specific to the company and sector. Reference actual industry dynamics, not
generic financial theory. Write in {language}.
```

#### User prompt (assembled dynamically)

```
## Company
{company_name} — {sector}

## Analysis Period
{date_range}

## Risk Assessment
Risk Score: {risk_score}/100 ({risk_level})
Composite Signals: {cs_types}

## Findings (ordered by narrative importance)

### Core Findings
- F001: Cost composition drift — {description}
  Data: {up to 4 key data points}
- ...

### Supporting Evidence
- ...

### Contextual Patterns
- ...

### Anomalies
- ...

Provide your expert analysis.
```

Findings are split into four categories (Core, Supporting, Contextual, Anomalies) by `categorize_findings()` in `step6_core_analysis.py`. Sector is looked up from `SECTOR_MAP`; unmapped companies receive `"Unknown (infer from company name and findings)"`.

---

### Step 8 — Executive Summary

**Model:** `claude-sonnet-4-6` | **max_tokens:** 2,000 | **temperature:** 0.5

#### System prompt

```
You are a senior financial analyst preparing a concise executive summary for a
C-suite audience. You will be given quantitative findings from automated pattern
detection on CVM public filings, and expert analysis from an AI industry specialist
providing macro context and hypotheses.

Write a well-structured executive summary that integrates both inputs.
Use this exact structure (markdown headers):

## Executive Summary
One tight sentence capturing the central finding with specific numbers.

## What Happened
2-3 sentences. Data-driven. Specific percentages and periods.

## How Serious It Is
2-3 sentences on magnitude, trajectory, and industry context from the specialist.

## When Things Turned
The critical inflection point — specific period, mechanism, why it is structural not cyclical.

## What Comes Next
Forward implications integrating the specialist's hypotheses and the data trajectory.

## What We Can't Answer
Key open questions that require internal data. Be specific about which data sources,
drawing from the specialist's data readiness assessment.

## Key Findings
A markdown table with columns: # | Finding | Severity | Evidence
Include the top 4-5 findings.

## Next Step
One sentence framing the value of internal data access.

Keep the whole summary under 500 words. Be specific and quantitative.
Write in {language}.
```

#### User prompt (assembled dynamically)

```
## Quantitative Analysis (automated pattern detection)

Company: {company_name}
Risk Score: {risk_score}/100 ({risk_level})
Composite Signals: {cs_types}

Findings:
  - F001: Cost composition drift (HIGH) — {description, truncated to 120 chars} [dp_1: v, dp_2: v, dp_3: v]
  - F002: Margin compression (HIGH) — ...
  ...

## Expert Analysis (AI industry specialist)

{full Step 7 streaming response, or "(Step 7 not yet run)"}

Generate the executive summary.
```

Each finding is truncated to 120 characters of description and up to 3 key data points to stay within token budget while preserving signal. Step 7 response is passed in full.
