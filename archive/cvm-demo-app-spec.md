# CVM Financial Analysis Demo — Technical Spec

> **Purpose:** Live demo application that downloads public Brazilian financial data (CVM/B3), transforms it, detects patterns, and generates AI-powered interpretations — all executed end-to-end in front of an audience.
>
> **Phase 1 scope:** Braskem S.A. hardcoded as default company. Architecture supports adding a company selector in Phase 2.
>
> **Stack:** React frontend + FastAPI backend + Claude API (streaming)
>
> **Language:** Bilingual (PT-BR / EN toggle). All UI labels, step descriptions, chart axes, and status messages in both languages.
>
> **Visual style:** Light theme, clean, professional. Optimized for laptop/projector presentation.

---

## 1. Architecture

```
┌─────────────────────────────────────┐
│           React Frontend            │
│  (Wizard UI, Charts, LLM Display)   │
├─────────────────────────────────────┤
│         REST + WebSocket            │
├─────────────────────────────────────┤
│          FastAPI Backend             │
│  (Pipeline Steps as Endpoints)       │
├─────────────────────────────────────┤
│  CVM Open Data    │   Claude API    │
│  (live + cache)   │   (streaming)   │
└─────────────────────────────────────┘
```

### Backend (FastAPI)

- Each of the 9 pipeline steps is a separate endpoint (`POST /api/step/{n}`)
- Steps are sequential — each step receives the output of the previous step (or reads from server-side state)
- Server holds pipeline state in memory (single-user application, no database needed)
- A `GET /api/config` endpoint returns current settings (company, language, cache mode)
- A `POST /api/config` endpoint sets company, language, and cache toggle
- WebSocket endpoint (`/ws/llm`) for streaming Claude API responses in Step 9
- All endpoints return structured JSON: `{ status, data, metadata, timing }`

### Frontend (React)

- Wizard-style navigation: 9 steps, sequential, with progress indicator
- Each step has three states: **pending** (greyed out), **running** (animated), **complete** (shows results)
- User clicks "Run Step" to execute each step (not auto-advancing — the presenter controls pace)
- Charts rendered with Recharts (lightweight, React-native, good enough for financial charts)
- Language toggle in header (PT-BR / EN) — switches all labels and descriptions instantly (client-side i18n, no reload)
- Cache toggle in header — switches backend between live CVM download and cached data

### Cache / Fallback System

- On first successful live run, backend saves each step's output as JSON to `cache/` directory
- When cache mode is ON, endpoints read from saved files instead of executing pipeline logic
- If a live step fails (timeout, CVM unavailable), backend automatically falls back to cached data for that step and flags it in the response metadata: `{ source: "cache", reason: "CVM timeout" }`
- Frontend shows a subtle indicator when cached data is being used

---

## 2. The Nine Steps — Endpoint Specs

### Step 1: Download CVM Data
**Endpoint:** `POST /api/step/1`
**What it does:** Downloads DFP (annual) and ITR (quarterly) financial statements from CVM open data portal for the configured company.
**Input:** Company CVM registration or name (from config)
**Output:**
```json
{
  "status": "complete",
  "data": {
    "dfp_rows": 1155,
    "itr_rows": 3372,
    "total_rows": 4527,
    "company": "BRASKEM S.A.",
    "date_range": { "start": "2020-03-31", "end": "2025-12-31" },
    "files_downloaded": ["dfp_2020.csv", "dfp_2021.csv", "..."]
  },
  "timing": { "elapsed_seconds": 12.3 }
}
```
**Frontend display:** Progress bar during download. Summary card showing row counts, date range, files retrieved.

### Step 2: Data Preparation
**Endpoint:** `POST /api/step/2`
**What it does:** Filters raw data — selects DRE (Income Statement) accounts, applies ORDEM_EXERC filter (keeps only current-year figures, excludes prior-year restated comparatives), excludes holding company entities.
**Output:**
```json
{
  "data": {
    "raw_rows": 4527,
    "after_dre_filter": 3200,
    "after_ordem_exerc": 2800,
    "after_holding_exclusion": 2600,
    "filters_applied": [
      { "name": "DRE accounts only", "removed": 1327, "reason": "Non-income statement accounts excluded" },
      { "name": "ORDEM_EXERC = ÚLTIMO", "removed": 400, "reason": "Prior-year restated figures removed" },
      { "name": "Holding company exclusion", "removed": 200, "reason": "Separate legal entities excluded" }
    ]
  }
}
```
**Frontend display:** Waterfall/funnel chart showing rows dropping at each filter stage. Each filter has a brief explanation of why it's needed (this is the data quality education moment).

### Step 3: DRE Transformation
**Endpoint:** `POST /api/step/3`
**What it does:** Resolves DFP/ITR overlap (when annual and quarterly filings cover the same period, DFP takes precedence). Converts YTD cumulative ITR figures to standalone quarterly values. Deduplicates.
**Output:**
```json
{
  "data": {
    "before_dedup": 2600,
    "after_dedup": 2270,
    "duplicates_removed": 330,
    "ytd_conversions": 45,
    "periods_final": ["2020-Q1", "2020-Q2", "...", "2025-Q4"],
    "dedup_rules": [
      { "rule": "DFP/ITR overlap", "description": "Annual filing takes precedence over quarterly for same period", "affected": 200 },
      { "rule": "YTD to standalone", "description": "Cumulative quarterly figures converted to standalone by subtracting prior quarters", "affected": 45 }
    ]
  }
}
```
**Frontend display:** Before/after comparison. A small table showing an example of a YTD-to-standalone conversion (e.g., Q3 cumulative - Q2 cumulative = Q3 standalone) to make the logic concrete.

### Step 4: EBITDA Drivers Construction
**Endpoint:** `POST /api/step/4`
**What it does:** Calculates derived metrics from the clean DRE data: Gross Margin %, EBIT Margin %, COGS as % of Revenue, EBITDA (if D&A available), and period-over-period changes.
**Output:**
```json
{
  "data": {
    "metrics_computed": ["Gross_Margin_pct", "EBIT_Margin_pct", "COGS_pct_Revenue", "Revenue_YoY_pct", "COGS_YoY_pct"],
    "periods": 20,
    "time_series": [
      { "period": "2020-12-31", "Gross_Margin_pct": 22.3, "EBIT_Margin_pct": 12.1, "COGS_pct_Revenue": 77.7 },
      { "period": "2021-12-31", "Gross_Margin_pct": 18.5, "EBIT_Margin_pct": 8.4, "COGS_pct_Revenue": 81.5 }
    ]
  }
}
```
**Frontend display:** This is where the first real chart appears. Multi-line chart showing Gross Margin, EBIT Margin, and COGS/Revenue over time. The audience sees the COGS trajectory climbing from 75% to 92% for the first time. This is the visual hook.

### Step 5: Data Quality Scan
**Endpoint:** `POST /api/step/5`
**What it does:** Scans computed metrics for anomalies. Flags implausible values (e.g., gross margin > 100% from YTD artifacts that weren't caught), classifies anomalies (DATA_ISSUE, ACCOUNTING_EVENT, LOW_CONFIDENCE_SIGNAL), assigns confidence scores.
**Output:**
```json
{
  "data": {
    "total_data_points": 100,
    "clean": 85,
    "flagged": 15,
    "flags": [
      { "period": "2021-Q1", "metric": "EBIT_Margin_pct", "value": 29.7, "flag": "STATISTICAL_ANOMALY", "reason": "Outside 2σ range", "confidence": "HIGH" }
    ],
    "quality_score": 0.85
  }
}
```
**Frontend display:** Data quality summary card (clean/flagged counts, quality score). Table of flagged items with color-coded severity. This step establishes credibility — you're not just running numbers, you're validating them.

### Step 6: Core Analytics (Pattern Detection)
**Endpoint:** `POST /api/step/6`
**What it does:** Runs the five detection algorithms: margin trend analysis, cost composition drift, revenue-cost decoupling, statistical anomaly detection, YoY quarter comparison. (Peer comparison disabled in Phase 1 since it's Braskem-only.)
**Output:**
```json
{
  "data": {
    "algorithms_run": ["margin_trends", "cost_composition_drift", "revenue_cost_decoupling", "statistical_anomaly", "yoy_quarter_comparison"],
    "raw_findings": 15,
    "findings": [
      {
        "id": "F001",
        "pattern": "Cost composition drift",
        "severity": "HIGH",
        "metric": "COGS_pct_Revenue",
        "description": "COGS burden shifted from 75.2% to 92.1% of revenue — a 16.8pp deterioration",
        "data_points": { "first_half_avg": 75.25, "second_half_avg": 92.07, "shift_pp": 16.82 }
      }
    ]
  }
}
```
**Frontend display:** Findings list with severity indicators. For each finding, a supporting mini-chart (e.g., the COGS drift finding shows the COGS/Revenue trendline with the first-half and second-half averages marked). This is the analytical core of the demo.

### Step 7: Enrichment Layer
**Endpoint:** `POST /api/step/7`
**What it does:** Adds macro context annotations to each finding (maps periods to economic events), classifies anomalies (valid signal vs. event-driven), generates composite signals (STRUCTURAL_COMPETITIVENESS_ISSUE, NEGATIVE_OPERATING_LEVERAGE), and calculates risk score.
**Output:**
```json
{
  "data": {
    "findings_enriched": 15,
    "macro_annotations_added": 8,
    "composite_signals": [
      { "signal": "STRUCTURAL_COMPETITIVENESS_ISSUE", "severity": "HIGH", "confidence": "HIGH", "supporting_findings": ["F001", "F003"] },
      { "signal": "NEGATIVE_OPERATING_LEVERAGE", "severity": "HIGH", "confidence": "HIGH", "supporting_findings": ["F002", "F005"] }
    ],
    "risk_score": 90.8,
    "risk_level": "CRITICAL"
  }
}
```
**Frontend display:** Enriched findings table (now with macro context column). Composite signals summary cards. Risk score gauge or indicator. Timeline visualization showing findings mapped against macro events.

### Step 8: Reporting and Narrative
**Endpoint:** `POST /api/step/8`
**What it does:** Generates the automated company narrative summary and structures the final findings report. Produces the natural-language synthesis of all signals.
**Output:**
```json
{
  "data": {
    "narrative": "COGS burden increased 16.8pp over the analysis period while EBIT margin compressed 3.1pp/year to -1.4%...",
    "key_findings_summary": [
      { "rank": 1, "finding": "Structural COGS deterioration", "evidence": "75.2% → 92.1% (+16.8pp)" },
      { "rank": 2, "finding": "Negative operating leverage in 2022", "evidence": "Revenue -8.6%, COGS +15.8%" }
    ],
    "data_limitations": [
      "No COGS sub-account breakdown (3.02.x)",
      "Quarterly granularity only",
      "Consolidated view (no subsidiary-level)"
    ]
  }
}
```
**Frontend display:** The generated narrative displayed as formatted text. Key findings in a ranked summary card. Data limitations section — this is where the "what internal data would unlock" message lives. Clean, report-like layout.

### Step 9: LLM Analysis Layer
**Endpoint:** WebSocket `/ws/llm`
**What it does:** User selects a finding from Step 6/7. The app sends the finding + company context + macro context to Claude API. The response streams back in real-time, generating possible theories and causes.
**Input (sent over WebSocket):**
```json
{
  "finding_id": "F001",
  "finding": { "pattern": "Cost composition drift", "description": "...", "data_points": { } },
  "company_context": { "name": "BRASKEM S.A.", "sector": "Petrochemical", "period": "2020-2025" },
  "macro_context": ["COVID-19 disruption", "Commodity supercycle", "China oversupply"],
  "instruction": "Generate 5-7 hypotheses for what could drive this pattern. For each hypothesis, explain the mechanism and identify what internal data source would confirm or refute it."
}
```
**Output:** Streamed text from Claude API, displayed token-by-token in the UI.
**Frontend display:** Split view — finding card with supporting chart on the left, streaming LLM response on the right. The response builds up visually as it streams. After completion, the presenter adds verbal domain interpretation.

**Claude API prompt design considerations:**
- System prompt should establish the role: "You are a financial analyst examining public financial data from Brazilian companies."
- Include the specific numerical evidence in the prompt, not just the finding label
- Ask for structured output: each hypothesis as a numbered item with mechanism + data source needed
- Do NOT include Ricardo's own theories — let the model generate independently
- Temperature slightly above default (0.7-0.8) to get varied hypotheses across demo runs

---

## 3. Frontend Components

### Layout
```
┌──────────────────────────────────────────────────┐
│  Logo/Title    [PT-BR|EN]  [Live|Cache]          │  ← Header
├────────┬─────────────────────────────────────────┤
│        │                                         │
│ Step 1 │                                         │
│ Step 2 │         Main Content Area               │
│ Step 3 │                                         │
│  ...   │    (changes based on current step)       │
│ Step 9 │                                         │
│        │                                         │
├────────┴─────────────────────────────────────────┤
│  [← Previous]              [Run Step →]          │  ← Footer/Actions
└──────────────────────────────────────────────────┘
```

### Step Navigation (Left Sidebar)
- Vertical list of 9 steps with icons and short labels
- Color states: grey (pending), blue/animated (running), green (complete)
- Click on completed steps to revisit their output (non-destructive)
- Current step highlighted

### Charts Required
1. **Step 2 — Data Funnel:** Waterfall or horizontal funnel showing row counts at each filter stage
2. **Step 4 — Margin Trajectory:** Multi-line time series (Gross Margin, EBIT Margin, COGS/Revenue) — this is the hero chart
3. **Step 4 — Revenue vs. COGS Growth:** Bar chart showing YoY % change for revenue and COGS side by side, highlighting the 2022 divergence
4. **Step 6 — Finding Support Charts:** Small charts per finding (trendlines, before/after comparisons)
5. **Step 7 — Timeline + Macro:** Timeline visualization showing findings plotted against macro events
6. **Step 7 — Risk Score:** Gauge or radial indicator

### i18n Structure
```
/src/i18n/
  en.json    — all English strings
  pt-br.json — all Portuguese strings
```
Keyed by component and step: `step1.title`, `step1.description`, `step1.running_message`, `chart.gross_margin_label`, etc.

---

## 4. Phase 2 Scope (Not in Phase 1 Build)

- Company selector (dropdown or search) — user picks any CVM-registered company
- Dynamic sector classification and peer grouping
- Peer comparison algorithm re-enabled with dynamic peer selection
- Multi-company comparison view
- Export to PDF/PPTX
- Saved analysis history

**Phase 2 architectural preparation (do in Phase 1):**
- Company name/CVM code passed as parameter to all backend functions, never hardcoded in logic
- Macro context annotations stored in a configurable mapping (not inline)
- Sector classification as a lookup, not an if-statement
- All frontend text referencing "Braskem" comes from the config/API response, not hardcoded in components

---

## 5. Project Structure

```
cvm-demo-app/
├── backend/
│   ├── main.py              — FastAPI app, CORS, WebSocket
│   ├── config.py            — App config (company, language, cache settings)
│   ├── steps/
│   │   ├── step1_download.py
│   │   ├── step2_preparation.py
│   │   ├── step3_transformation.py
│   │   ├── step4_ebitda_drivers.py
│   │   ├── step5_quality_scan.py
│   │   ├── step6_pattern_detection.py
│   │   ├── step7_enrichment.py
│   │   ├── step8_reporting.py
│   │   └── step9_llm_analysis.py
│   ├── pipeline/             — Core pipeline logic (refactored from existing scripts)
│   │   ├── cvm_downloader.py
│   │   ├── data_cleaner.py
│   │   ├── metrics_calculator.py
│   │   ├── pattern_detector.py
│   │   ├── enrichment.py
│   │   └── narrative_generator.py
│   ├── cache/                — Cached step outputs (JSON files)
│   ├── data/                 — Downloaded CVM data files
│   ├── i18n/
│   │   ├── en.json
│   │   └── pt_br.json
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── StepWizard.jsx
│   │   │   ├── StepSidebar.jsx
│   │   │   ├── StepContent.jsx
│   │   │   ├── charts/
│   │   │   │   ├── DataFunnel.jsx
│   │   │   │   ├── MarginTrajectory.jsx
│   │   │   │   ├── RevenueCOGSGrowth.jsx
│   │   │   │   ├── FindingChart.jsx
│   │   │   │   ├── MacroTimeline.jsx
│   │   │   │   └── RiskGauge.jsx
│   │   │   ├── LLMStream.jsx
│   │   │   └── LanguageToggle.jsx
│   │   ├── steps/
│   │   │   ├── Step1Download.jsx
│   │   │   ├── Step2Preparation.jsx
│   │   │   ├── ...
│   │   │   └── Step9LLMAnalysis.jsx
│   │   ├── i18n/
│   │   │   ├── en.json
│   │   │   └── pt-br.json
│   │   └── hooks/
│   │       ├── usePipeline.js
│   │       └── useWebSocket.js
│   └── package.json
├── CLAUDE.md                 — Claude Code instructions
└── README.md
```

---

## 6. Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Chart library | Recharts | React-native, lightweight, good enough for financial line/bar charts. D3 is overkill for this scope. |
| State management | React Context + useReducer | 9-step wizard with sequential state. No need for Redux. |
| Backend state | In-memory (Python dict) | Single-user demo app. No database. State resets on server restart. |
| LLM streaming | WebSocket | Smoother UX than SSE for token-by-token display. FastAPI supports natively. |
| i18n approach | JSON key-value files + React context | Simple, no external library needed. Instant toggle without reload. |
| Cache format | JSON files per step | Human-readable, easy to inspect, trivial to load. |
| CSS approach | CSS Modules or Tailwind | Either works. Tailwind is faster to build with. |
| Claude model | claude-sonnet-4-20250514 | Good balance of speed and quality for live demo. Opus would be slower to stream. |

---

## 7. Demo Flow / Presenter Notes

**Before the demo:**
- Run once end-to-end in live mode to populate the cache (fallback safety net)
- Verify CVM portal is accessible
- Have Claude API key configured
- Test projector resolution

**During the demo:**
- Steps 1-3 are "data engineering" — move through briskly, emphasize data quality decisions
- Step 4 is the first "aha" moment — pause on the margin trajectory chart, let it land
- Steps 5-7 are "analytical methodology" — show the rigor but don't linger
- Step 8 is the transition — the automated narrative sets up "what the data says"
- Step 9 is the climax — let Claude generate theories, then you add domain interpretation verbally
- Close with: "This is what public data reveals. Imagine what internal data would show."

---

## 8. Risk Mitigation

| Risk | Mitigation |
|---|---|
| CVM portal down during demo | Cache fallback with subtle UI indicator |
| Claude API slow or unavailable | Pre-cached LLM response as fallback; show cached response and note "this was generated earlier" |
| Data format changes on CVM portal | Pin to known file URLs; cache known-good data |
| Demo runs too long | Each step has timing display; rehearse to know pace |
| Audience asks about other companies | "Phase 2 adds a company selector — the architecture supports it, we just need to configure the macro context mappings" |
| Charts render poorly on projector | Test with low resolution; use high-contrast colors; avoid thin lines |
