# CVM Financial Analysis Demo — Claude Code Instructions

## What this project is

Live demo application: downloads public Brazilian financial data (CVM/B3 portal), transforms it through a 9-step pipeline, detects financial patterns, and streams AI-generated hypotheses via Claude API. Hardcoded to Braskem S.A. in Phase 1.

**Stack:** React + Vite (frontend) · FastAPI + uvicorn (backend) · Recharts · Claude API (streaming over WebSocket)

---

## Running the app

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Set `ANTHROPIC_API_KEY` in the environment to enable real Claude API calls in Step 9. Without it, Step 9 streams mock text.

### Frontend

```bash
cd frontend
npm install
npm run dev      # → http://localhost:5173
```

The Vite dev server proxies `/api/*` and `/ws/*` to `localhost:8000`.

---

## Project layout

```
cvm-demo-app/
├── backend/
│   ├── main.py              FastAPI app, CORS, WebSocket, step routing
│   ├── config.py            AppConfig dataclass + in-memory pipeline_state dict
│   ├── steps/               One file per pipeline step; each exposes run(config, pipeline_state)
│   ├── pipeline/            Core logic modules (CVM download, cleaning, metrics, etc.)
│   ├── cache/               JSON cache files, one per step output
│   ├── data/                Downloaded CVM CSV files
│   └── i18n/                Backend status strings (en.json, pt_br.json)
└── frontend/
    └── src/
        ├── App.jsx           Root: i18n context, app state (useReducer), dispatch context
        ├── components/       StepWizard, StepSidebar, StepContent, LLMStream, LanguageToggle, charts/
        ├── steps/            Step1Download…Step9LLMAnalysis — one component per step
        ├── i18n/             en.json, pt-br.json — all UI strings
        └── hooks/            usePipeline.js, useWebSocket.js
```

---

## Key conventions

### Backend

- **Every step** module exposes a single function: `run(config: AppConfig, pipeline_state: dict) -> dict`
- Return shape: `{ "status": "complete", "data": {...}, "metadata": {...}, "timing": {...} }`
- `timing` is injected by `main.py`; steps don't need to compute it
- **Company name** is always passed via `config.company_name` — never hardcode "BRASKEM" in logic
- Cache read/write lives in each step module (will be centralized in Phase 2)
- `pipeline_state["stepN"]` holds the `.data` dict from the previous step's response

### Frontend

- **i18n:** All user-visible strings come from `useI18n()` (returns the active locale JSON). Never write raw English/Portuguese in JSX.
- **State:** All pipeline state lives in `AppStateContext` (via `useReducer` in `App.jsx`). Components read via `useAppState()` / dispatch via `useAppDispatch()`.
- **Step components** receive two props: `stepState` (`"pending" | "running" | "complete"`) and `data` (the full API response object, or `null`).
- **Charts** are pure display components — they receive pre-shaped data props, no API calls.
- CSS Modules (`.module.css`) co-located with each component or shared via `Step.module.css`.

---

## What's implemented

### Backend — complete
- Full directory structure
- FastAPI app with all 9 endpoints
- WebSocket `/ws/llm` with real Claude API streaming (falls back to mock when no API key)
- All pipeline modules live: `cvm_downloader`, `data_cleaner`, `metrics_calculator`, `pattern_detector`, `enrichment`, `narrative_generator`
- Steps 1–8 wired to live pipeline logic; Step 9 wired to Claude API
- Cache layer: all steps read/write `cache/stepN.json`; auto-fallback to cache on live failure

### Frontend — skeleton (renders mock data correctly)
- React wizard UI: header, sidebar, step navigation, footer
- All 9 step display components
- All chart components (DataFunnel, MarginTrajectory, RevenueCOGSGrowth, FindingChart, MacroTimeline, RiskGauge)
- Full i18n for EN + PT-BR; language toggle; cache mode toggle

## TODO

- **End-to-end smoke test:** run Steps 1–8 via API against real CVM data; verify response shapes
- **Frontend wiring:** confirm charts render real API response shapes (field names may differ from mock)
- **`npm install`** must be run manually in `frontend/` (node/npm not in PATH)

---

## Demo flow reminder (from spec)

- Steps 1-3: data engineering — move briskly
- Step 4: first "aha" — pause on the margin trajectory chart
- Steps 5-7: analytical rigor
- Step 8: automated narrative sets up the story
- Step 9: let Claude generate hypotheses, then add verbal domain interpretation
- Close with: *"This is what public data reveals. Imagine what internal data would show."*

---

## Phase 2 preparation (already in architecture)

- Company name flows through `config.company_name` — never hardcoded in logic
- Macro context map in `enrichment.py` will be a configurable dict, not if-statements
- All frontend company references come from API config response
