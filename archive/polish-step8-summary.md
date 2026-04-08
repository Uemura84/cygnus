# Polish — Step 8 Executive Summary Visual Overhaul

> **What this is:** Build spec for Claude Code. Fixes bilingual headers, adjusts
> typography weight, and enriches the executive summary with mixed media
> (tables, key metrics, and inline charts alongside narrative text).
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 8 frontend + prompt adjustments. No detection or stacking changes.

---

## 1. Fix Section Headers — Bilingual

### 1.1 Problem

When the app is in PT-BR mode, the story arc headers remain in English:
"What Happened", "How Serious It Is", "When Things Turned", "What Comes Next",
"What We Can't Answer", "Key Findings", "Next Step".

### 1.2 Fix

The headers should match the selected language. Two approaches:

**Option A (recommended): Frontend renders the headers, not the LLM.**

Don't rely on the LLM to generate the section headers. Instead, the frontend
renders fixed, translated headers and the LLM generates only the content for
each section. This guarantees consistent headers regardless of LLM behavior.

The Step 8 prompt should request a structured response (like Step 7) with
keys for each section, and the frontend maps them to translated headers:

```json
{
  "executive_summary": "...",
  "what_happened": "...",
  "how_serious": "...",
  "when_things_turned": "...",
  "what_comes_next": "...",
  "what_we_cant_answer": "...",
  "key_findings": [...],
  "next_step": "..."
}
```

Frontend header translations:

| Key | EN | PT-BR |
|-----|-----|-------|
| executive_summary | Executive Summary | Sumário Executivo |
| what_happened | What Happened | O Que Aconteceu |
| how_serious | How Serious It Is | Qual a Gravidade |
| when_things_turned | When Things Turned | Quando Mudou |
| what_comes_next | What Comes Next | O Que Vem a Seguir |
| what_we_cant_answer | What We Can't Answer | O Que Não Conseguimos Responder |
| key_findings | Key Findings | Principais Achados |
| next_step | Next Step | Próximo Passo |

Add these to the i18n files (en.json and pt-br.json).

**Option B: Instruct the LLM to use the correct language for headers.**

Less reliable — LLMs sometimes revert to English headers even when prompted
in Portuguese. Option A is preferred.

---

## 2. Fix Typography Weight

### 2.1 Problem

The narrative text appears too bold. The executive summary should use DM Serif
Display for the narrative sections (this is the only step that uses it, per the
design system), but the weight should be regular (400), not bold.

### 2.2 Fix

Check the CSS for Step 8's narrative content:

- **Section headers** (What Happened, etc.): DM Sans 500, 18-20px, navy. NOT bold.
  These are structural markers, not headlines.
- **Narrative paragraphs**: DM Serif Display 400, 16-17px, charcoal. Regular weight,
  not bold. This is the "authority voice" — it should feel editorial, like a
  well-written report, not like someone shouting.
- **Key Findings table**: DM Sans 400 for content, JetBrains Mono for finding codes
  and severity badges. Same pattern as Step 6.
- **"Next Step" section**: DM Serif Display 400 italic, to distinguish it as a
  recommendation rather than a finding.

Check if the current CSS has `font-weight: bold` or `font-weight: 700` on the
narrative text and remove it. DM Serif Display at regular weight is already
visually distinctive — it doesn't need bold.

---

## 3. Mixed Media: Enrich with Metrics, Tables, and Charts

### 3.1 Problem

The executive summary is currently pure text — long paragraphs for each section.
A CFO reads this as "another report." Mixing in structured data elements (metric
callouts, mini tables, and key charts) makes it scannable and visually credible.

### 3.2 Target layout

Each section of the story arc gets appropriate mixed media:

**Executive Summary (opening)**
```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │RISK SCORE│  │NET EQUITY│  │DEBT/EBITDA│ │   FCF    │    │
│  │  100/100 │  │-R$16.5B  │  │  14.4×   │  │ 6 periods│    │
│  │ CRITICAL │  │ CRITICAL │  │ CRITICAL │  │ negative │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                              │
│  [1-2 sentence narrative summary]                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The metric callout cards at the top give the CFO the headline numbers before
they read a single word. These are the same numbers from Step 6 — just
displayed prominently as the opening of the executive summary.

**What Happened**
```
[2-3 sentence narrative]

┌─────────────────────────────────────────────────┐
│  MARGIN TRAJECTORY (mini chart)                  │
│  [Gross Margin line chart, compact, 150px tall]  │
│  19.1% (2020) → 30.4% (2021) → 2.2% (2025)     │
└─────────────────────────────────────────────────┘
```

Embed a compact version of the Step 4 Margin Trajectory chart. The chart
reinforces the narrative — the reader sees the collapse visually.

**How Serious It Is**
```
[2-3 sentence narrative]

┌────────────────────────────────────────────┐
│  CROSS-MODULE DIAGNOSIS SUMMARY            │
│                                            │
│  ● Financial Distress Risk    CRITICAL     │
│  ● Working Capital Trap       HIGH         │
│  ● Low Quality Growth         HIGH         │
└────────────────────────────────────────────┘
```

Pull the stacked diagnoses from Step 6 as a compact summary list.

**When Things Turned**
```
[2-3 sentence narrative identifying the inflection point]
```

Text only is fine here — the inflection point is a date and a mechanism,
not a data visualization.

**What Comes Next**
```
[2-3 sentence narrative on trajectory and risks]
```

Text only — forward-looking assessment.

**What We Can't Answer**
```
[2-3 sentence narrative on data gaps]

┌─────────────────────────────────────────────────┐
│  INTERNAL DATA NEEDED                            │
│                                                  │
│  1. Naphtha contract terms (Petrobras)           │
│  2. Debt maturity schedule 2025-2027             │
│  3. Alagoas contingent liability true exposure   │
└─────────────────────────────────────────────────┘
```

The data gaps as a structured list — this is the bridge to the consulting
engagement. A CFO reads this and thinks "I have this data, we should talk."

**Key Findings (table — already exists, keep it)**

The table in Image 3 is good. Keep it as-is. Ensure it uses Cygnus design
system styling (JetBrains Mono for codes and severity, DM Sans for content).

**Next Step**
```
[1-2 sentence call to action in DM Serif Display italic]
```

### 3.3 Implementation approach

**Option A (recommended): Frontend assembles the mixed media.**

The LLM generates the narrative text for each section (structured JSON, like
Step 7). The frontend renders the section headers, embeds the metric cards
and mini charts from Step 4/6 data already available, and places the LLM
narrative alongside them. The LLM doesn't need to generate charts or metric
cards — the data is already computed.

This means the Step 8 prompt generates LESS content (just narrative per section
+ key findings table + data gaps list), and the frontend adds the visual
elements from data already in memory.

**Option B: LLM generates everything including chart data.**

The LLM includes structured chart data in its JSON response, which the
frontend renders. More complex, more fragile, and unnecessary since the
chart data already exists.

Pick Option A.

### 3.4 Metric callout cards

The opening metric cards pull from Step 6 results:
- Risk Score: from Step 6 risk_score
- Net Equity: from balance_sheet_series latest total_equity
- Debt/EBITDA: from balance_sheet_series latest debt_to_ebitda
- FCF streak: from cash_flow_series count of consecutive negative FCF periods

These are computed values, not LLM-generated. The frontend reads them from
the cached Step 4/6 data.

### 3.5 Mini charts

Embed compact versions of Step 4 charts within the relevant sections:
- Margin Trajectory in "What Happened" — 150px tall, no legend (the narrative
  explains it), just the line with start/end annotations
- FCF bar chart in "How Serious" — 100px tall, positive blue / negative red,
  showing the 6-period negative streak

These are simplified versions of the full Step 4 charts. Use the same Recharts
components with reduced height and minimal decoration.

### 3.6 What the LLM generates (Step 8 JSON structure)

```json
{
  "executive_summary": "A Braskem apresenta risco máximo (100/100)...",
  "what_happened": "A margem bruta colapsou de 12,6% para 2,2%...",
  "how_serious": "O patrimônio negativo de R$16,5B...",
  "when_things_turned": "O ponto de inflexão foi Q2/2022...",
  "what_comes_next": "Sem reestruturação de dívida...",
  "what_we_cant_answer": "Três questões críticas exigem dados internos...",
  "data_gaps": [
    "Composição e prazo dos contratos de nafta com a Petrobras",
    "Cronograma detalhado de vencimentos de dívida 2025-2027",
    "Dimensão real do passivo de Alagoas ainda não provisionado"
  ],
  "key_findings": [
    {
      "module": "Balanço",
      "finding": "Patrimônio líquido negativo em R$16,5B",
      "severity": "CRÍTICO",
      "evidence": "Insolvência técnica; dívida dolarizada amplifica destruição patrimonial cambial"
    },
    ...
  ],
  "next_step": "O acesso a dados internos é determinante..."
}
```

---

## 4. i18n

### Section headers (see Section 1.2 table)

### New labels
- "Internal Data Needed" / "Dados Internos Necessários"
- "Cross-Module Diagnosis Summary" / "Resumo de Diagnósticos Cross-Module"
- "Risk Score" / "Score de Risco"
- "Net Equity" / "Patrimônio Líquido"
- "consecutive periods negative" / "períodos consecutivos negativo"

---

## 5. Testing

- [ ] Section headers render in correct language (EN or PT-BR)
- [ ] Narrative text uses DM Serif Display 400 (not bold)
- [ ] Section headers use DM Sans 500 (not bold)
- [ ] Metric callout cards render at top of executive summary
- [ ] Mini Margin Trajectory chart renders in "What Happened"
- [ ] Cross-module diagnosis summary renders in "How Serious"
- [ ] Data gaps list renders in "What We Can't Answer"
- [ ] Key Findings table renders correctly (matches Image 3 quality)
- [ ] Next Step in DM Serif Display italic
- [ ] All content renders for Braskem
- [ ] All content renders for Vale
- [ ] All content renders for Votorantim
- [ ] Bilingual toggle works correctly
- [ ] All regression tests pass

---

## 6. Definition of Done

- [ ] Section headers bilingual (frontend-rendered, not LLM-generated)
- [ ] Typography weight fixed (DM Serif Display 400 for narrative)
- [ ] Metric callout cards at top of executive summary
- [ ] Mini chart embedded in "What Happened"
- [ ] Diagnosis summary in "How Serious"
- [ ] Data gaps list in "What We Can't Answer"
- [ ] Step 8 prompt restructured to return JSON
- [ ] All labels bilingual
- [ ] All 3 test companies render correctly
- [ ] All regressions pass
