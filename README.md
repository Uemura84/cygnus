# Cygnus — Revealing Hidden Value in Financial Data

**Decision Intelligence for CFOs.**

Cygnus downloads public financial filings from Brazil's securities regulator (CVM), runs them through a 9-step analytical pipeline, detects structural financial patterns using statistical algorithms, and streams expert-level hypotheses via the Claude API.

The output: quantified value leakage estimates, peer comparisons, and a CFO-ready executive briefing — entirely from public data. The closing question: *"This is what public data reveals. Imagine what internal data would show."*

---

## What it does

| Step | Name | What happens |
|------|------|--------------|
| 1 | **Download** | Fetches DFP (annual) and ITR (quarterly) filings from the CVM portal |
| 2 | **Data Preparation** | Filters to income statement accounts, drops restated rows, excludes holding entities |
| 3 | **DRE Transformation** | Deduplicates filings, pivots accounts into columns, builds income statement |
| 4 | **EBITDA Drivers** | Computes Gross Margin, EBIT, EBITDA, COGS/Revenue, YoY growth, balance sheet series, FCF |
| 5 | **Data Quality Scan** | Validates metrics against plausibility bounds, assigns confidence scores |
| 6 | **Pattern Detection** | Runs 6 algorithms across profitability, balance sheet, and cash flow; stacks cross-module signals; scores company risk with BRL impact estimates |
| 7 | **AI Industry Specialist** | Claude streams macro context, module-level hypotheses, and cross-module diagnosis |
| 8 | **Executive Summary** | Claude generates a structured JSON briefing: metric cards, margin chart, key findings table, data gaps, and company-specific follow-up questions for Step 9 |
| 9 | **Open Q&A** | Conversational chat with company-specific question chips seeded from Step 8 |

---

## Stack

**Backend:** Python 3.11+ · FastAPI · uvicorn · pandas · numpy · Anthropic SDK
**Frontend:** React 18 · Vite · Recharts · CSS Modules
**Fonts:** DM Sans · JetBrains Mono (Google Fonts)
**Transport:** REST (`/api/step/N`) + WebSocket (`/ws/llm`) for LLM streaming

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- `ANTHROPIC_API_KEY` in environment — required for Steps 7, 8, 9. Without it the backend yields mock responses so the app can be demonstrated offline.

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
│   │   ├── metrics_calculator.py  Margin ratios, D&A from DFC, EBITDA, balance sheet series
│   │   ├── pattern_detector.py  Profitability detection (6 algorithms)
│   │   ├── bs_detector.py       Balance sheet health detection module
│   │   ├── cf_detector.py       Cash flow quality detection module
│   │   ├── signal_stacker.py    Cross-module composite signal stacking
│   │   ├── enrichment.py        Risk scoring, SECTOR_MAP, composite signal labels
│   │   ├── materiality.py       BRL impact estimates from pp findings × revenue
│   │   └── narrative_generator.py  Prompt assembly helpers
│   ├── steps/                   One module per pipeline step
│   │   ├── step1_download.py … step6_core_analysis.py
│   │   ├── step7_ai_agent.py    5-call architecture: macro + 3 modules + cross-module
│   │   ├── step8_reporting.py   Structured JSON executive briefing via Claude
│   │   └── step9_llm_analysis.py  Multi-turn Q&A with full pipeline context
│   ├── tests/
│   │   ├── test_regression.py   Regression suite against captured baselines
│   │   └── regression/          Braskem, Vale, Votorantim baseline JSONs
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
        │                        FindingChart, MacroTimeline, RiskGauge
        ├── steps/
        │   ├── Step1Download.jsx … Step5QualityScan.jsx
        │   ├── Step6CoreAnalysis.jsx  Finding cards with severity borders + BRL impact
        │   ├── Step7AIAgent.jsx   Tiered streaming display: macro → modules → cross-module
        │   ├── Step8Reporting.jsx Mixed-media briefing: metric cards, mini chart,
        │   │                      diagnosis summary, findings table, data gaps list
        │   └── Step9QA.jsx        Chat with question chips seeded from Step 8
        └── i18n/                en.json, pt-br.json
```

---

## Detection modules (Step 6)

Six statistical algorithms run across three modules, then stacked into cross-module composite signals:

| Module | Algorithms |
|--------|-----------|
| **Profitability** | Margin trend (linear regression), cost composition drift (half-period shift), revenue-cost decoupling (pct-change divergence), peer comparison (z-score / gap), statistical anomaly (IQR), YoY same-quarter |
| **Balance Sheet** | Negative equity, Debt/EBITDA threshold breach, equity erosion trend |
| **Cash Flow** | Consecutive negative FCF, OCF-to-EBITDA conversion quality |
| **Cross-module** | `signal_stacker.py` combines signals from all three modules into composite diagnoses (e.g. "Structural margin compression + leverage trap") |

Each finding includes severity (`LOW / MEDIUM / HIGH / CRITICAL`), a BRL impact estimate in thousands, and confidence score.

---

## Design system

| Font | Voice | Where used |
|------|-------|------------|
| **DM Sans 400/500/700** | Product | All UI: headings, navigation, buttons, body text, narrative paragraphs |
| **JetBrains Mono** | Data | Finding codes, metric values, risk scores, section labels, data tags |

> **DM Serif Display** is available in the brand kit for consultant-facing content (articles, Substack, slide headers) but is **not used in the Cygnus product UI**.

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
- Steps 7, 8, 9 expose `stream()` async generators consumed by the WebSocket handler in `main.py`

### Frontend

- All user-visible strings come from `useI18n()` — never write raw EN/PT in JSX
- All pipeline state lives in `AppStateContext` via `useReducer` in `App.jsx`
- Step components receive `stepState` (`"pending"|"running"|"complete"`) and `data`
- Charts are pure display components — no API calls
- LLM responses are rendered via `MarkdownView` — no external markdown dependency

---

## LLM streaming (Steps 7, 8, 9)

All three AI steps share one WebSocket endpoint (`/ws/llm`). The `step` field in the JSON payload dispatches to the correct handler:

| `step` | Handler | Architecture | Model params |
|--------|---------|-------------|--------------|
| 7 | Industry specialist | 5 parallel batch calls (macro + profitability + balance sheet + cash flow + cross-module) | `claude-sonnet-4-6`, up to 3000 tokens/call, temp 0.7 |
| 8 | Executive summary | 1 batch call → structured JSON | `claude-sonnet-4-6`, 1500 tokens, temp 0.5 |
| 9 | Open Q&A | Token streaming | `claude-sonnet-4-6`, 2000 tokens, temp 0.7 |

Step 8 returns a JSON object including `suggested_questions` — 4–5 company-specific follow-up questions that populate the question chips in Step 9.

The language toggle controls response language for all three handlers (EN / PT-BR).

---

## Demo flow

- **Steps 1–3** — data engineering; move briskly
- **Step 4** — first "aha": pause on the margin trajectory and COGS divergence charts
- **Steps 5–6** — analytical rigor: quality scan → 6-algorithm pattern detection → BRL impact estimates → risk score
- **Step 7** — AI industry specialist: macro context, root-cause hypotheses, cross-module diagnosis
- **Step 8** — executive briefing: metric callout cards, mini margin chart, structured narrative, key findings table, data gaps
- **Step 9** — open conversation using company-specific questions from Step 8; add verbal domain interpretation
- **Close with:** *"This is what public data reveals. Imagine what internal data would show."*
