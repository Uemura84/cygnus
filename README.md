# CVM Financial Analysis Demo

A live demo application that downloads public Brazilian financial data from the CVM (Comissão de Valores Mobiliários) open data portal, transforms it through a 9-step analytical pipeline, detects financial patterns, and streams AI-generated analysis via the Claude API.

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
| 7 | AI Industry Specialist | Claude streams expert hypotheses and a data readiness assessment |
| 8 | Executive Summary | Claude merges Step 6 findings and Step 7 analysis into a structured narrative |
| 9 | Open Q&A | Conversational chat with the AI specialist, informed by the full pipeline context |

---

## Stack

**Backend:** Python · FastAPI · uvicorn · pandas · Anthropic SDK
**Frontend:** React 18 · Vite · Recharts · CSS Modules
**Transport:** REST (`/api/step/N`) + WebSocket (`/ws/llm`) for LLM streaming (Steps 7, 8, 9)

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- `ANTHROPIC_API_KEY` in environment — required for Steps 7, 8, 9. Without it the backend streams mock text so the UI can still be demonstrated.

### Backend

```bash
cd cvm-demo-app/backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-... uvicorn main:app --reload --port 8000
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
│   ├── main.py                  FastAPI app, CORS, REST + WebSocket routing
│   ├── config.py                AppConfig dataclass + in-memory pipeline_state
│   ├── cache_utils.py           Read/write JSON cache per step
│   ├── requirements.txt
│   ├── pipeline/                Core analytical logic
│   │   ├── cvm_downloader.py    CVM portal HTTP client
│   │   ├── data_cleaner.py      DRE filtering + deduplication
│   │   ├── metrics_calculator.py  Margin + YoY calculations
│   │   ├── pattern_detector.py  6 detection algorithms (pure CVM data, no macro context)
│   │   ├── enrichment.py        Composite signals + risk scoring
│   │   └── narrative_generator.py   Story arc helpers (legacy, not called from step 8+)
│   ├── steps/                   One module per pipeline step
│   │   ├── step1_download.py … step6_core_analysis.py
│   │   ├── step7_ai_agent.py    Claude: industry specialist hypotheses (streaming)
│   │   ├── step8_reporting.py   Claude: executive summary merging Step 6 + 7 (streaming)
│   │   └── step9_llm_analysis.py  Claude: open Q&A with full pipeline context (streaming)
│   ├── cache/                   JSON cache files (gitignored)
│   ├── data/                    Downloaded CSVs + analysis outputs (gitignored)
│   └── i18n/                    Backend status strings (en, pt-br)
└── frontend/
    └── src/
        ├── App.jsx              Root: i18n context, useReducer state, dispatch context
        ├── components/
        │   ├── MarkdownView.jsx  Custom markdown renderer (headers, bold, lists, tables)
        │   ├── StepWizard.jsx    Layout shell + navigation
        │   ├── StepContent.jsx   Mounts the correct step component
        │   ├── StepSidebar.jsx   Step list with completion states
        │   └── charts/           DataFunnel, MarginTrajectory, RevenueCOGSGrowth,
        │                         FindingChart, RiskGauge
        ├── steps/
        │   ├── Step1Download.jsx … Step6CoreAnalysis.jsx
        │   ├── Step7AIAgent.jsx   "Consult AI Agent" button + streaming markdown output
        │   ├── Step8Summary.jsx   "Generate Summary" button + streaming markdown output
        │   └── Step9QA.jsx        Chat interface with suggested questions + streaming markdown
        ├── i18n/                en.json, pt-br.json
        └── hooks/               usePipeline.js, useWebSocket.js
```

---

## Key conventions

### Backend

- Every step exposes `run(config: AppConfig, pipeline_state: dict) -> dict`
- Return shape: `{ "status": "complete", "data": {...}, "metadata": {...}, "timing": {...} }`
- `timing` is injected by `main.py`
- Company name flows through `config.company_name` — never hardcoded in analytical logic
- Cache is per-step: `cache/stepN.json`; auto-fallback on live failure
- Steps 7, 8, 9 also expose `stream(payload, config, ...)` async generators consumed by the WebSocket handler

### Frontend

- All user-visible strings come from `useI18n()` — never write raw EN/PT in JSX
- All pipeline state lives in `AppStateContext` via `useReducer` in `App.jsx`
- Step components receive `stepState` (`"pending"|"running"|"complete"`) and `data` (full API response)
- Charts are pure display components — no API calls, data shaped by parent
- LLM responses are rendered through `MarkdownView` — no external markdown dependency

---

## LLM streaming (Steps 7, 8, 9)

All three AI steps share the same WebSocket endpoint (`/ws/llm`). The `step` field in the JSON payload dispatches to the correct handler:

| `step` | Handler | Trigger |
|--------|---------|---------|
| 7 | `step7_ai_agent.stream()` | "Consult AI Agent" button |
| 8 | `step8_reporting.stream()` | "Generate Summary" button |
| 9 | `step9_llm_analysis.stream()` | Chat input or suggested question chip |

Responses are rendered in real time via `MarkdownView`, which handles `##`/`###` headers, `**bold**`, bullet and numbered lists, and pipe tables — including tables where the LLM emits blank lines between rows.

The language toggle controls the response language: all three handlers read `language` from the payload and instruct the model accordingly.

---

## Cache mode

The header toggles between **Live** (hits the CVM portal on each run) and **Cache** (reads from `backend/cache/stepN.json`). Cache mode is useful for demos when the CVM portal is slow or unavailable.

---

## Demo flow

- **Steps 1–3** — data engineering, move briskly
- **Step 4** — first "aha": pause on the margin trajectory and COGS divergence charts
- **Steps 5–6** — analytical rigour: quality scan → pattern detection → risk scoring
- **Step 7** — AI industry specialist generates hypotheses and flags data gaps
- **Step 8** — AI merges quantitative findings with specialist analysis into an executive narrative
- **Step 9** — open conversation: let Claude answer follow-up questions, then add verbal domain interpretation
- **Close with:** *"This is what public data reveals. Imagine what internal data would show."*

---

## Phase 2 notes

The architecture is already prepared for multi-company use:
- `config.company_name` never hardcoded in analytical logic
- Sector maps in `pattern_detector.py` and `enrichment.py` are configurable dicts
- All frontend company references come from the API config response
