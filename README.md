# Cygnus — Revealing Hidden Value in Financial Data

**Decision Intelligence for CFOs.**

Cygnus downloads public financial filings from Brazil's securities regulator (CVM), runs them through a 9-step analytical pipeline, detects structural financial patterns using statistical algorithms, and streams expert-level hypotheses via the Claude API.

The output: quantified value leakage estimates, peer comparisons, and a CFO-ready executive narrative — entirely from public data. The closing question: *"This is what public data reveals. Imagine what internal data would show."*

---

## What it does

| Step | Name | What happens |
|------|------|--------------|
| 1 | **Download** | Fetches DFP (annual) and ITR (quarterly) filings from the CVM portal |
| 2 | **Data Preparation** | Filters to income statement accounts, drops restated rows, excludes holding entities |
| 3 | **DRE Transformation** | Deduplicates filings, pivots accounts into columns, builds income statement |
| 4 | **EBITDA Drivers** | Computes Gross Margin, EBIT, EBITDA, COGS/Revenue, YoY growth, absolute BRL values |
| 5 | **Data Quality Scan** | Validates metrics against plausibility bounds, assigns confidence scores |
| 6 | **Pattern Detection** | Runs 6 algorithms, estimates BRL impact per finding, scores company risk |
| 7 | **AI Industry Specialist** | Claude streams macro context and root-cause hypotheses |
| 8 | **Executive Summary** | Claude merges Step 6 findings + Step 7 analysis into a structured CFO narrative |
| 9 | **Open Q&A** | Conversational chat with the AI, informed by the full pipeline context |

---

## Stack

**Backend:** Python · FastAPI · uvicorn · pandas · Anthropic SDK
**Frontend:** React 18 · Vite · Recharts · CSS Modules
**Fonts:** DM Sans · DM Serif Display · JetBrains Mono (Google Fonts)
**Transport:** REST (`/api/step/N`) + WebSocket (`/ws/llm`) for LLM streaming

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- `ANTHROPIC_API_KEY` in environment — required for Steps 7, 8, 9. Without it the backend streams mock text so the app can still be demonstrated.

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
│   ├── cache_utils.py           Read/write JSON cache per step, per company
│   ├── requirements.txt
│   ├── pipeline/
│   │   ├── cvm_downloader.py    CVM portal HTTP client + company list extractor
│   │   ├── data_cleaner.py      DRE filtering + financial institution detection
│   │   ├── metrics_calculator.py  Margin ratios, D&A from DFC, EBITDA, absolute BRL values
│   │   ├── pattern_detector.py  6 detection algorithms (no external macro context)
│   │   ├── enrichment.py        Composite signals, risk scoring, SECTOR_MAP
│   │   ├── materiality.py       BRL impact estimates from pp findings × revenue
│   │   └── narrative_generator.py  Story arc helpers
│   ├── steps/                   One module per pipeline step
│   │   ├── step1_download.py … step6_core_analysis.py
│   │   ├── step7_ai_agent.py    Streams industry specialist analysis via Claude
│   │   ├── step8_reporting.py   Streams executive summary via Claude
│   │   └── step9_llm_analysis.py  Multi-turn Q&A via Claude
│   ├── cache/{company}/         Per-company JSON cache (gitignored)
│   └── data/                    Downloaded ZIPs + analysis outputs (gitignored)
└── frontend/
    └── src/
        ├── index.css            CSS custom properties (Cygnus design tokens)
        ├── App.jsx              Root: i18n, useReducer state, dispatch context
        ├── components/
        │   ├── StepWizard.jsx   Layout shell (navy header/footer, off-white body)
        │   ├── StepSidebar.jsx  Step list on navy sidebar with completion states
        │   ├── CompanySelector.jsx  Search-enabled company picker with sector badges
        │   ├── MarkdownView.jsx Custom streaming markdown renderer
        │   └── charts/          DataFunnel, MarginTrajectory, RevenueCOGSGrowth,
        │                        FindingChart, RiskGauge
        ├── steps/
        │   ├── Step1Download.jsx … Step5QualityScan.jsx
        │   ├── Step6CoreAnalysis.jsx  Finding cards with severity borders + BRL impact
        │   ├── Step7AIAgent.jsx   Streaming markdown AI analysis
        │   ├── Step8Summary.jsx   Streaming executive summary in DM Serif Display
        │   └── Step9QA.jsx        Chat interface with streaming markdown responses
        └── i18n/                en.json, pt-br.json
```

---

## Design system

Cygnus uses three font families, each with a distinct voice:

| Font | Voice | Where used |
|------|-------|------------|
| **DM Sans 400/500/600** | Product | All UI: headings, navigation, buttons, body text |
| **DM Serif Display** | Authority | Step 8 executive summary only — signals human interpretation |
| **JetBrains Mono** | Data | Finding codes, metric values, risk scores, section labels, data tags |

**Color tokens** (CSS custom properties in `index.css`):

```css
--navy:      #0b1f3a   /* Header, sidebar, footer */
--blue:      #1e90ff   /* Accent, interactive, signal */
--offwhite:  #f5f7fa   /* Content background */
--charcoal:  #2b2b2b   /* Primary text */
--gray:      #4a5568   /* Secondary text */
--blue-dim:  rgba(30,144,255,0.08)  /* Tag backgrounds */
--blue-line: rgba(30,144,255,0.25)  /* Hover borders */
```

---

## Key conventions

### Backend

- Every step exposes `run(config: AppConfig, pipeline_state: dict) -> dict`
- Return shape: `{ "status": "complete", "data": {...}, "metadata": {...}, "timing": {...} }`
- Company name flows through `config.company_name` — never hardcoded in analytical logic
- Cache is per-company per-step: `cache/{COMPANY_NAME}/stepN.json`
- Steps 7, 8, 9 expose `stream()` async generators for WebSocket delivery

### Frontend

- All user-visible strings come from `useI18n()` — never write raw EN/PT in JSX
- All pipeline state lives in `AppStateContext` via `useReducer` in `App.jsx`
- Step components receive `stepState` (`"pending"|"running"|"complete"`) and `data`
- Charts are pure display components — no API calls
- LLM responses are rendered via `MarkdownView` — no external markdown dependency

---

## LLM streaming (Steps 7, 8, 9)

All three AI steps share one WebSocket endpoint (`/ws/llm`). The `step` field in the JSON payload dispatches to the correct handler:

| `step` | Handler | Model params |
|--------|---------|--------------|
| 7 | Industry specialist | `claude-sonnet-4-6`, 4000 tokens, temp 0.7 |
| 8 | Executive summary | `claude-sonnet-4-6`, 2000 tokens, temp 0.5 |
| 9 | Open Q&A | `claude-sonnet-4-6`, 2000 tokens, temp 0.7 |

The language toggle controls response language for all three handlers.

---

## Demo flow

- **Steps 1–3** — data engineering, move briskly
- **Step 4** — first "aha": pause on the margin trajectory and COGS divergence
- **Steps 5–6** — analytical rigor: quality scan → 6-algorithm pattern detection → BRL impact estimates
- **Step 7** — AI industry specialist generates hypotheses and data readiness gaps
- **Step 8** — executive narrative in DM Serif Display — the CFO-facing output
- **Step 9** — open conversation; let Claude answer follow-ups, then add verbal domain interpretation
- **Close with:** *"This is what public data reveals. Imagine what internal data would show."*
