# CVM Financial Analysis Demo

A live demo application that downloads public Brazilian financial data from the CVM (Comissão de Valores Mobiliários) open data portal, transforms it through a 9-step analytical pipeline, detects financial patterns, and streams AI-generated hypotheses via the Claude API.

Hardcoded to **Braskem S.A.** in Phase 1.

---

## What it does

The pipeline takes raw CVM filings and produces a structured financial analysis in nine steps:

| Step | Name | What happens |
|------|------|--------------|
| 1 | Download CVM Data | Downloads DFP (annual) and ITR (quarterly) filings |
| 2 | Data Preparation | Filters to income statement accounts, drops restated rows, excludes holding entities |
| 3 | DRE Transformation | Deduplicates filings, pivots accounts into columns, computes margin ratios |
| 4 | EBITDA Drivers | Calculates Gross Margin, EBIT Margin, COGS/Revenue, and YoY changes |
| 5 | Data Quality Scan | Validates metrics against sector plausibility bounds, assigns confidence scores |
| 6 | Pattern Detection & Risk | Runs 6 detection algorithms, builds composite signals, scores company risk |
| 7 | Hypothesis Generation | Deterministic rule-based hypotheses from a sector domain knowledge map |
| 8 | Executive Summary | Story arc narrative + key findings table + transition to offer |
| 9 | AI Deep Dive | Claude API streams analysis of individual findings informed by Step 7 hypotheses |

---

## Stack

**Backend:** Python · FastAPI · uvicorn · pandas · Anthropic SDK
**Frontend:** React 18 · Vite · Recharts · CSS Modules
**Transport:** REST (`/api/step/N`) + WebSocket (`/ws/llm`) for Step 9 streaming

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) `ANTHROPIC_API_KEY` in environment for real Claude API calls in Step 9

### Backend

```bash
cd cvm-demo-app/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd cvm-demo-app/frontend
npm install
npm run dev        # → http://localhost:5173
```

The Vite dev server proxies `/api/*` and `/ws/*` to `localhost:8000`.

---

## Project layout

```
cvm-demo-app/
├── backend/
│   ├── main.py                  FastAPI app, CORS, WebSocket, step routing
│   ├── config.py                AppConfig dataclass + in-memory pipeline_state
│   ├── cache_utils.py           Read/write JSON cache per step
│   ├── requirements.txt
│   ├── pipeline/                Core analytical logic
│   │   ├── cvm_downloader.py    CVM portal HTTP client
│   │   ├── data_cleaner.py      DRE filtering + deduplication
│   │   ├── metrics_calculator.py  Margin + YoY calculations
│   │   ├── pattern_detector.py  6 detection algorithms
│   │   ├── enrichment.py        Composite signals + risk scoring + macro timeline
│   │   ├── hypothesis_generator.py  Deterministic sector knowledge map
│   │   └── narrative_generator.py   Story arc + key findings summary
│   ├── steps/                   One module per pipeline step
│   │   ├── step1_download.py … step9_llm_analysis.py
│   ├── cache/                   JSON cache files (gitignored)
│   ├── data/                    Downloaded CSVs + analysis outputs (gitignored)
│   └── i18n/                    Backend status strings (en, pt-br)
└── frontend/
    └── src/
        ├── App.jsx              Root: i18n context, useReducer state, dispatch context
        ├── components/          StepWizard, StepSidebar, StepContent, charts/
        │   └── charts/          DataFunnel, MarginTrajectory, RevenueCOGSGrowth,
        │                        FindingChart, MacroTimeline, RiskGauge
        ├── steps/               Step1Download … Step9LLMAnalysis
        ├── i18n/                en.json, pt-br.json
        └── hooks/               usePipeline.js, useWebSocket.js
```

---

## Key conventions

### Backend

- Every step exposes `run(config: AppConfig, pipeline_state: dict) -> dict`
- Return shape: `{ "status": "complete", "data": {...}, "metadata": {...}, "timing": {...} }`
- `timing` is injected by `main.py`
- Company name flows through `config.company_name` — never hardcoded in logic
- Cache is per-step: `cache/stepN.json`; auto-fallback on live failure

### Frontend

- All user-visible strings come from `useI18n()` — never write raw EN/PT in JSX
- All pipeline state lives in `AppStateContext` via `useReducer` in `App.jsx`
- Step components receive `stepState` (`"pending"|"running"|"complete"`) and `data` (full API response)
- Charts are pure display components — no API calls, data shaped by parent

---

## Cache mode

The header toggles between **Live** (hits the CVM portal on each run) and **Cache** (reads from `backend/cache/stepN.json`). Cache mode is useful for demos when the CVM portal is slow or unavailable.

---

## Step 9 — AI Deep Dive

Step 9 streams Claude's analysis of individual findings over a WebSocket connection. It requires `ANTHROPIC_API_KEY` to be set. Without it, the backend streams mock text so the UI can still be demonstrated.

The prompt automatically includes the top 3 hypotheses from Step 7 as context, so Claude builds on domain knowledge rather than starting from scratch.

---

## Demo flow

- **Steps 1–3** — data engineering, move briskly
- **Step 4** — first "aha": pause on the margin trajectory and COGS divergence charts
- **Steps 5–7** — analytical rigour: quality scan → pattern detection → hypothesis map
- **Step 8** — automated narrative sets up the story arc
- **Step 9** — let Claude generate further hypotheses, then add verbal domain interpretation
- **Close with:** *"This is what public data reveals. Imagine what internal data would show."*

---

## Phase 2 notes

The architecture is already prepared for multi-company use:
- `config.company_name` never hardcoded in logic
- Macro context map in `enrichment.py` is a configurable dict
- Sector map in `pattern_detector.py` is a configurable dict
- All frontend company references come from the API config response
