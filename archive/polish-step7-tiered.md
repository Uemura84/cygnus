# Polish — Step 7 AI Industry Specialist: Tiered Display + Prompt Restructure

> **What this is:** Build spec for Claude Code. Restructures the Step 7 AI output
> from a dense research report into a scannable, tiered briefing with collapsible
> sections. Changes both the LLM prompt (what it generates) and the frontend
> (how it renders).
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 7 backend prompt + frontend display. No detection or stacking changes.

---

## 1. Problem

Step 7 generates excellent financial analysis but presents it as a continuous
wall of text that:
- Gets truncated (the CF and stacked diagnosis sections may never be seen)
- Overwhelms a CFO audience (7 hypotheses for a single finding, each multi-paragraph)
- Cannot be navigated during a demo (no way to skip to what matters)
- Mixes macro context, per-finding hypotheses, and data source mapping into one stream

## 2. Target: Structured JSON Response, Not Markdown

### 2.1 Change the output format

Instead of generating a single markdown document, the LLM should return a
**structured JSON response** that the frontend can render as interactive,
collapsible sections.

### 2.2 Response structure

```json
{
  "macro_context": {
    "summary": "Braskem rode the 2021 petrochemical super-cycle to record margins, then absorbed a violent correction compounded by Chinese overcapacity, Alagoas disaster liabilities, and Petrobras feedstock pricing constraints.",
    "full_narrative": "The Petrochemical Super-Cycle and Its Violent Reversal... [full text, multiple paragraphs]"
  },
  "modules": {
    "profitability": {
      "module_summary": "All profitability findings trace to one root cause: structural compression of the naphtha-to-polymer spread, amplified by Alagoas operational disruption and BRL/USD dynamics.",
      "findings": [
        {
          "finding_code": "F003",
          "finding_name": "Cost composition drift",
          "top_hypothesis": {
            "title": "Chinese overcapacity permanently compressed naphtha-to-polymer spreads",
            "confidence": "HIGH",
            "explanation": "Chinese integrated complexes with scale advantages drove global polymer prices to their marginal cost floor. Braskem's naphtha costs remained elevated due to Petrobras pricing constraints, structurally narrowing the spread from ~20pp to ~5pp.",
            "confirmation_data": [
              "Segment-level revenue per tonne vs. naphtha cost per tonne (internal management accounts)",
              "IHS Markit/ICIS polymer spread data for PE and PP benchmarks",
              "Petrobras naphtha contract terms and pricing formula"
            ]
          },
          "additional_hypotheses": [
            {
              "title": "Alagoas production disruption increasing fixed cost absorption",
              "confidence": "HIGH",
              "explanation": "Forced closure of Alagoas operations reduced production volumes, spreading fixed costs over fewer tonnes. If Alagoas contributed ~15% of Brazilian production, fixed cost per tonne at remaining plants rises ~5-8%.",
              "confirmation_data": [
                "Utilization rates by plant (quarterly operational reports)",
                "Fixed vs. variable cost breakdown in segment reporting"
              ]
            },
            {
              "title": "Feedstock mix shift toward naphtha from ethane/NGL",
              "confidence": "MEDIUM",
              "explanation": "Gas supply constraints may have forced greater naphtha dependence. Each percentage point shift toward naphtha adds ~8-12% to ethylene production costs.",
              "confirmation_data": [
                "Feedstock consumption breakdown by type (annual reports)",
                "Petrobras gas supply contract terms"
              ]
            }
          ]
        }
      ]
    },
    "balance_sheet": {
      "module_summary": "...",
      "findings": [...]
    },
    "cash_flow": {
      "module_summary": "...",
      "findings": [...]
    },
    "cross_module": {
      "module_summary": "Three cross-module diagnoses confirm that Braskem's situation is not merely a cyclical downturn but a structural deterioration across profitability, leverage, and cash generation simultaneously.",
      "diagnoses": [
        {
          "diagnosis_code": "DX001",
          "diagnosis_name": "Financial Distress Risk",
          "interpretation": "The combination of margin compression, leverage at 14.4× EBITDA, negative equity, and 6 consecutive periods of negative FCF creates a self-reinforcing distress spiral. The company cannot generate enough cash to service debt, fund operations, and pay Alagoas liabilities simultaneously.",
          "what_would_change_this": "A sustained recovery in polymer spreads (unlikely given Chinese capacity) or a structured Alagoas liability settlement with extended payment terms could break the cycle."
        }
      ]
    }
  }
}
```

### 2.3 Key constraints on the LLM output

- **Macro context summary:** Maximum 3 sentences. The full narrative is available
  but hidden by default.
- **Module summary:** Maximum 2 sentences per module. Sets the frame before
  individual findings.
- **Top hypothesis:** One per finding. The most likely explanation. Maximum
  3 sentences for the explanation.
- **Additional hypotheses:** Maximum 3 per finding (not 7). Each has a one-sentence
  title, confidence level, 2-sentence explanation, and confirmation data sources.
- **Confirmation data:** 2-4 bullet points per hypothesis. Specific data sources
  the client would need to provide.
- **Cross-module diagnoses:** One paragraph interpretation + one sentence on what
  would change the assessment.
- **Total response:** The structured output should be comprehensive but bounded.
  The LLM should prioritize the highest-confidence hypotheses and cut lower ones.

---

## 3. Updated Step 7 Prompt

### 3.1 System prompt

```
You are a senior financial analyst specializing in {sector} industry analysis.
You are presenting findings to a CFO who needs to understand what the data
means and what to investigate next.

CRITICAL FORMAT REQUIREMENT:
Respond ONLY with a JSON object in the exact structure specified below.
Do not include any markdown, preamble, or text outside the JSON.

Your analysis must be:
- Specific: reference actual numbers from the findings
- Actionable: each hypothesis maps to confirmable internal data
- Prioritized: top hypothesis first, ordered by confidence
- Concise: explanations are 2-3 sentences, not paragraphs
- Expert: use industry-specific terminology a CFO would expect

Maximum constraints:
- macro_context.summary: 3 sentences max
- module_summary: 2 sentences max per module
- top_hypothesis.explanation: 3 sentences max
- additional_hypotheses: maximum 3 per finding
- additional_hypotheses[].explanation: 2 sentences max
- confirmation_data: 2-4 items per hypothesis
```

### 3.2 User prompt structure

```
Company: {company_name}
Sector: {sector}
Analysis Period: {date_range}

MODULE 1 — PROFITABILITY FINDINGS
{profitability findings with metric values}

MODULE 2 — BALANCE SHEET FINDINGS
{BS findings with metric values}

MODULE 3 — CASH FLOW FINDINGS
{CF findings with metric values}

CROSS-MODULE DIAGNOSES
{stacked diagnoses with contributing signals}

Respond with the JSON structure as specified in the system prompt.
```

### 3.3 Streaming consideration

The current Step 7 uses WebSocket streaming (text appears as it generates).
With a JSON response, streaming raw JSON is not useful to display progressively.

**Two approaches:**

**Option A (recommended): Stream the text, parse the JSON after completion.**
Let the LLM stream its response. Show a loading state with progress indicator
("Analyzing profitability findings...", "Generating balance sheet hypotheses...",
"Building cross-module interpretation..."). When the stream completes, parse the
JSON and render the tiered display. This gives the user feedback that analysis
is happening without showing raw JSON streaming.

**Option B: Request markdown with structured headers, parse into sections.**
If JSON streaming is too complex, keep the LLM output as markdown but with
strict section headers that the frontend can parse into collapsible sections.
Less clean but simpler to implement.

Pick whichever is more practical given the current WebSocket implementation.

---

## 4. Frontend: Tiered Display

### 4.1 Layout structure

```
┌──────────────────────────────────────────────────────────────┐
│ MACRO CONTEXT                                                │
│                                                              │
│ Braskem rode the 2021 petrochemical super-cycle to record    │
│ margins, then absorbed a violent correction compounded by     │
│ Chinese overcapacity and Alagoas disaster liabilities.        │
│                                                              │
│ ▶ Read full macro context                                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ PROFITABILITY ANALYSIS                                       │
│                                                              │
│ All profitability findings trace to structural compression    │
│ of the naphtha-to-polymer spread.                            │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ F003  Cost composition drift     HIGH                  │   │
│ │                                                        │   │
│ │ TOP HYPOTHESIS                        Confidence: HIGH │   │
│ │ Chinese overcapacity permanently compressed             │   │
│ │ naphtha-to-polymer spreads                             │   │
│ │                                                        │   │
│ │ Chinese integrated complexes drove global polymer       │   │
│ │ prices to their marginal cost floor while Braskem's     │   │
│ │ naphtha costs remained elevated due to Petrobras        │   │
│ │ pricing constraints.                                    │   │
│ │                                                        │   │
│ │ ▶ What data would confirm this (3 sources)             │   │
│ │ ▶ 3 additional hypotheses                              │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ F001  Margin compression          MEDIUM               │   │
│ │ ...                                                    │   │
│ └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ BALANCE SHEET HEALTH                                         │
│ ...                                                          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ CASH FLOW QUALITY                                            │
│ ...                                                          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ CROSS-MODULE DIAGNOSES                                       │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ DX001  Financial Distress Risk     CRITICAL            │   │
│ │                                                        │   │
│ │ The combination of margin compression, leverage at     │   │
│ │ 14.4× EBITDA, negative equity, and 6 consecutive       │   │
│ │ periods of negative FCF creates a self-reinforcing     │   │
│ │ distress spiral.                                        │   │
│ │                                                        │   │
│ │ What would change this: A sustained recovery in        │   │
│ │ polymer spreads or a structured Alagoas liability       │   │
│ │ settlement with extended payment terms.                 │   │
│ └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Collapsible sections

| Element | Default state |
|---------|---------------|
| Macro context full narrative | Collapsed |
| Module sections (Profitability, BS, CF, Cross-Module) | Expanded |
| Module summary | Always visible |
| Finding cards | Expanded (showing top hypothesis) |
| "What data would confirm this" | Collapsed |
| "Additional hypotheses" | Collapsed |
| Cross-module "What would change this" | Expanded |

### 4.3 Design

- Section labels: JetBrains Mono uppercase, Signal Blue
- Module summaries: DM Sans 400, 14px, slate, italic
- Finding code badges: same as Step 6 (JetBrains Mono, blue on blue-dim)
- "TOP HYPOTHESIS" label: JetBrains Mono 10px uppercase, Signal Blue
- Confidence badges: same style as Step 6 severity badges
- Hypothesis title: DM Sans 500, 15px, navy
- Explanation text: DM Sans 400, 14px, charcoal
- Confirmation data items: DM Sans 400, 13px, slate, with bullet markers
- Expand/collapse toggles: Signal Blue, DM Sans 400, 13px
- Cross-module diagnosis cards: blue-dim background (matching Step 6 DiagnosisCard)

### 4.4 Loading state

While the LLM is generating:

```
┌──────────────────────────────────────────────────┐
│ Analyzing 20 findings across 3 modules...        │
│                                                  │
│ ████████████░░░░░░░░░  Generating hypotheses     │
└──────────────────────────────────────────────────┘
```

Show a progress bar or staged messages:
1. "Analyzing macro context..."
2. "Generating profitability hypotheses..."
3. "Analyzing balance sheet findings..."
4. "Interpreting cash flow patterns..."
5. "Building cross-module synthesis..."

These are cosmetic stages (the LLM generates everything at once), but they
give the user feedback and make the wait feel purposeful.

---

## 5. Handling Related Findings

### 5.1 Problem

Some findings are closely related (F001 and F002 are both margin compression
for different metrics; F004 and F005 are both revenue-cost decoupling for
different periods). Generating separate hypotheses for each is redundant.

### 5.2 Solution

The prompt should instruct the LLM to **group related findings** and generate
hypotheses for the group, not for each individual finding:

```
If multiple findings describe the same underlying pattern (e.g., margin
compression across different metrics, or revenue-cost decoupling in
different periods), group them and provide one set of hypotheses for the
group. Reference all finding codes in the group header.
```

The response structure supports this:

```json
{
  "finding_code": "F001 / F002",
  "finding_name": "Margin compression (Gross + EBIT)",
  "top_hypothesis": { ... }
}
```

---

## 6. Bilingual

The LLM prompt should generate the response in the user's selected language.

Add to the system prompt:
- EN: "Generate all text in English."
- PT-BR: "Gere todo o texto em português brasileiro."

Cache per company + language (same as chart interpretations and plausibility bounds).

---

## 7. What Does NOT Change

- Step 6 detection logic — unchanged
- Step 8 Executive Summary — unchanged (separate prompt)
- Step 9 Q&A — unchanged (separate prompt)
- The analytical depth — the LLM still generates expert-level analysis, just
  in a structured format instead of a continuous essay

---

## 8. Testing

- [ ] LLM returns valid JSON (or parseable structured response)
- [ ] Macro context summary renders (max 3 sentences)
- [ ] Macro context full narrative expands on click
- [ ] Module summaries render for all 4 modules
- [ ] Each finding shows top hypothesis with confidence badge
- [ ] Confirmation data section expands on click
- [ ] Additional hypotheses section expands on click (max 3 per finding)
- [ ] Related findings are grouped (F001/F002, F004/F005)
- [ ] Cross-module diagnoses render with interpretation
- [ ] "What would change this" visible for each diagnosis
- [ ] Loading state shows progress messages during generation
- [ ] No truncation — all modules and findings render completely
- [ ] Bilingual (EN and PT-BR)
- [ ] Braskem generates full analysis across all modules
- [ ] Vale generates analysis
- [ ] Votorantim generates analysis
- [ ] All regression tests pass

---

## 9. Definition of Done

- [ ] Step 7 prompt restructured to request JSON response
- [ ] LLM generates structured, bounded output (not unbounded essay)
- [ ] Frontend renders tiered display with collapsible sections
- [ ] Macro context collapsible (summary visible, full text hidden)
- [ ] Top hypothesis prominent per finding, additional hypotheses expandable
- [ ] Confirmation data sources listed per hypothesis
- [ ] Related findings grouped
- [ ] Cross-module diagnoses with interpretation and "what would change this"
- [ ] Loading state with staged progress messages
- [ ] No truncation
- [ ] Bilingual
- [ ] All 3 companies work
- [ ] All regressions pass
