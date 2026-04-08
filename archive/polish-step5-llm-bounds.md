# Polish — Step 5 Metric Validation: LLM-Generated Sector-Aware Bounds

> **What this is:** Fix spec for Claude Code. The BS and CF plausibility checks
> aren't producing visible results. This spec fixes the pipeline, then replaces
> hardcoded sector profiles with LLM-generated plausibility bounds that adapt
> to any company and sector automatically.
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 5 backend (plausibility logic + one LLM call) + frontend display.

---

## 1. Diagnose and Fix Missing BS/CF Plausibility Data

### 1.1 Problem

The Step 5 display shows:
- Profitability: 0 points, 0 flags (should show actual point counts)
- Balance Sheet: 0 points, 0 flags (checks not running or not returning data)
- Cash Flow: 0 points, 0 flags (same)
- Quality Score: —% (can't compute with 0 points)
- No Balance Sheet or Cash Flow plausibility tables visible

### 1.2 Fix checklist

Before implementing LLM bounds, first verify and fix the pipeline:

1. **Check the backend:** Are BS/CF plausibility functions defined? Do they get called?
2. **Check the data flow:** Does Step 5 receive balance_sheet_series and cash_flow_series?
3. **Check the API response:** Does the Step 5 response include BS/CF plausibility results?
4. **Check the frontend:** Does the component look for BS/CF data in the response?
5. **Check profitability point counts:** Why does it show "0 points"?

Fix each issue. The pipeline must work with hardcoded fallback bounds before
adding the LLM layer.

---

## 2. Hardcoded DEFAULT Bounds (Safety Net)

### 2.1 Purpose

Define a conservative DEFAULT profile that serves as:
- The fallback if the LLM call fails
- The initial bounds used while the LLM call is in progress
- The safety net for any edge case

These bounds should be wide enough to never produce false positives but narrow
enough to catch genuine data errors (e.g., revenue of negative one trillion).

### 2.2 DEFAULT profile

```python
DEFAULT_BOUNDS = {
    "label_en": "General Industrial",
    "label_pt": "Industrial Geral",
    "source": "default",
    "profitability": {
        "Gross Margin %":     {"min": -80,  "max": 95,  "rationale_en": "General range; values outside suggest data error.", "rationale_pt": "Faixa geral; valores fora sugerem erro de dados."},
        "EBIT Margin %":      {"min": -80,  "max": 80,  "rationale_en": "General range.", "rationale_pt": "Faixa geral."},
        "COGS / Revenue %":   {"min": 5,    "max": 150, "rationale_en": "Very low or very high COGS flags data error.", "rationale_pt": "COGS muito baixo ou alto indica erro de dados."},
        "SGA / Revenue %":    {"min": 0,    "max": 60,  "rationale_en": "SGA above 60% is unusual for any industrial.", "rationale_pt": "SGA acima de 60% é incomum para qualquer indústria."},
    },
    "balance_sheet": {
        "Current Ratio":            {"min": 0.05, "max": 20,   "rationale_en": "Extreme values suggest data error.", "rationale_pt": "Valores extremos sugerem erro de dados."},
        "Debt / EBITDA":            {"min": -10,  "max": 50,   "rationale_en": "Wide default range.", "rationale_pt": "Faixa padrão ampla."},
        "Working Capital Change %": {"min": -300, "max": 300,  "rationale_en": "Swings exceeding ±300% suggest anomaly.", "rationale_pt": "Variações acima de ±300% sugerem anomalia."},
        "Asset Turnover":           {"min": 0,    "max": 10,   "rationale_en": "Above 10× is unusual.", "rationale_pt": "Acima de 10× é incomum."},
        "ROA %":                    {"min": -100, "max": 100,  "rationale_en": "Values outside ±100% suggest scaling error.", "rationale_pt": "Valores fora de ±100% sugerem erro de escala."},
        "ROE %":                    {"min": -500, "max": 500,  "rationale_en": "Extreme values flag for review.", "rationale_pt": "Valores extremos requerem revisão."},
    },
    "cash_flow": {
        "OCF / Net Income":   {"min": -15, "max": 15,  "rationale_en": "Extreme values suggest data inconsistency.", "rationale_pt": "Valores extremos sugerem inconsistência de dados."},
        "Capex / Revenue %":  {"min": 0,   "max": 60,  "rationale_en": "Capex above 60% of revenue is unusual.", "rationale_pt": "Capex acima de 60% da receita é incomum."},
        "Capex / D&A":        {"min": 0,   "max": 8,   "rationale_en": "Above 8× suggests major expansion or error.", "rationale_pt": "Acima de 8× sugere grande expansão ou erro."},
        "FCF / Revenue %":    {"min": -150,"max": 150,  "rationale_en": "FCF exceeding 150% of revenue flags anomaly.", "rationale_pt": "FCL acima de 150% da receita indica anomalia."},
    },
}
```

This DEFAULT profile is always available and never requires an LLM call.

---

## 3. LLM-Generated Sector-Aware Bounds

### 3.1 Concept

Instead of maintaining hardcoded profiles for every sector, use a single LLM
call to generate plausibility bounds specific to the company's industry. The
LLM knows industry-specific financial characteristics and can produce bounds
with expert-quality rationale for any sector.

### 3.2 When it runs

After Step 5 receives the computed metrics from Step 4:

1. Step 5 starts with DEFAULT bounds (instant — no waiting)
2. Step 5 makes a single LLM call to generate sector-specific bounds
3. When the LLM responds, replace DEFAULT bounds with sector-specific bounds
4. Re-run plausibility checks with the new bounds
5. Update the display

If the LLM call fails or times out, the DEFAULT bounds remain in use. The
step never fails because of an LLM issue.

### 3.3 LLM prompt

```
You are a senior financial analyst specializing in industry-specific
financial analysis.

Company: {company_name}
Sector: {sector_description}
Country: Brazil
Data source: CVM (Brazilian Securities Commission) public filings

For the metrics listed below, provide plausibility bounds (min and max)
that are appropriate for this specific industry sector. These bounds are
used to flag potential DATA ERRORS — not to detect business problems.
Values inside the bounds are considered plausible; values outside suggest
a data quality issue that needs investigation.

Be specific to this industry. For example:
- A petrochemical company has COGS/Revenue typically 70-95%, so a plausible
  range might be 20-130%
- A mining company has very low asset turnover (heavy fixed assets), so a
  plausible range might be 0-2×
- A software company has very low COGS, so a plausible range might be 5-60%

Metrics to define bounds for:

PROFITABILITY:
- Gross Margin % (revenue minus COGS, as percentage of revenue)
- EBIT Margin % (operating profit as percentage of revenue)
- COGS / Revenue % (cost of goods sold as percentage of revenue)
- SGA / Revenue % (selling, general & admin as percentage of revenue)

BALANCE SHEET:
- Current Ratio (current assets / current liabilities)
- Debt / EBITDA (net debt / EBITDA, times)
- Working Capital Change % (year-over-year percentage change)
- Asset Turnover (revenue / total assets)
- ROA % (net income / total assets)
- ROE % (net income / total equity)

CASH FLOW:
- OCF / Net Income (operating cash flow / net income)
- Capex / Revenue % (capital expenditure as percentage of revenue)
- Capex / D&A (capital expenditure / depreciation & amortization)
- FCF / Revenue % (free cash flow as percentage of revenue)

Respond ONLY with a JSON object in this exact format, no other text:

{
  "sector_label_en": "Petrochemical",
  "sector_label_pt": "Petroquímico",
  "profitability": {
    "Gross Margin %": {
      "min": -50,
      "max": 80,
      "rationale_en": "Petrochemical gross margins rarely exceed 80%...",
      "rationale_pt": "Margens brutas petroquímicas raramente excedem 80%..."
    },
    ...
  },
  "balance_sheet": { ... },
  "cash_flow": { ... }
}
```

### 3.4 Model

Use Claude Sonnet — this is a structured knowledge task, not deep reasoning.

### 3.5 Sector identification

The LLM prompt needs the company's sector. Sources:

1. **CVM sector classification** — if available from the company data
2. **Company name inference** — "BRASKEM S.A." → the LLM knows it's petrochemical
3. **Explicit mapping** — a simple dict for known companies:

```python
COMPANY_SECTOR_HINTS = {
    "BRASKEM S.A.": "Petrochemical manufacturer (naphtha-based, commodity chemicals)",
    "VALE S.A.": "Mining (iron ore, nickel, base metals)",
    "VOTORANTIM CIMENTOS S.A.": "Building materials (cement, concrete, aggregates)",
}
```

For unknown companies, pass just the company name and let the LLM identify the
sector from its knowledge. If the company is truly unknown, the LLM can use
generic industrial bounds (similar to DEFAULT but with better rationale).

### 3.6 Caching

Cache LLM-generated bounds per company name + language. The bounds for
"BRASKEM S.A." don't change between analyses — cache them permanently
(or until cache is manually cleared).

Store in the same cache layer used for Step 4 LLM chart interpretations.

### 3.7 Response parsing

Parse the LLM JSON response. Validate that:
- All expected metrics are present
- Min < Max for every metric
- Values are numbers (not strings)

If parsing fails or validation fails, fall back to DEFAULT bounds and log
a warning.

---

## 4. Frontend Display

### 4.1 Three plausibility tables

Each section renders a table showing the bounds and rationale, labeled with
the sector:

```
PROFITABILITY PLAUSIBILITY (PETROCHEMICAL)      ← sector from LLM

METRIC              MIN     MAX     RATIONALE
─────────────────────────────────────────────────────────
Gross Margin %      -50%    80%     Petrochemical gross margins rarely...
EBIT Margin %       -50%    60%     EBIT below -50% typically indicates...
COGS / Revenue %    20%     130%    COGS below 20% is unrealistic for...
SGA / Revenue %     0%      40%     SGA above 40% is implausible for...

All checks passed.
```

Same table for Balance Sheet and Cash Flow sections.

### 4.2 Source indicator

Show a subtle indicator of whether bounds came from the LLM or the fallback:

- LLM-generated: section header shows "(PETROCHEMICAL)" — no extra indicator needed,
  the sector name IS the indicator that LLM-specific bounds are active
- DEFAULT fallback: section header shows "(GENERAL INDUSTRIAL)" and a small note:
  "Using default bounds — sector-specific analysis unavailable"
  in DM Sans 400, 12px, slate, italic

### 4.3 Loading state

While the LLM call is in progress:
- Show the plausibility tables with DEFAULT bounds
- Add a subtle loading note: "Generating sector-specific bounds..."
  in DM Sans 400, 12px, slate, italic
- When LLM response arrives, smoothly replace with sector-specific bounds

### 4.4 Failed checks

When a metric value falls outside the bounds:

```
⚠ 1 flag:
  Debt / EBITDA = 35.2× in 2025 (exceeds max 30×)
```

Amber (#EF9F27) for the warning indicator.

### 4.5 Summary cards

Show per-section breakdown with correct counts:

```
PROFITABILITY          BALANCE SHEET          CASH FLOW             QUALITY SCORE
24 points · 0 flags    36 points · 1 flag     24 points · 0 flags   98.8%
```

Quality Score = (total_clean / total_points) × 100.

---

## 5. i18n

### Section headers
- "Profitability Plausibility" / "Plausibilidade de Rentabilidade"
- "Balance Sheet Plausibility" / "Plausibilidade do Balanço Patrimonial"
- "Cash Flow Plausibility" / "Plausibilidade do Fluxo de Caixa"

### Loading/fallback messages
- "Generating sector-specific bounds..." / "Gerando limites específicos do setor..."
- "Using default bounds — sector-specific analysis unavailable" / "Usando limites padrão — análise setorial indisponível"

### Flag messages
- "flag" / "alerta"
- "flags" / "alertas"
- "exceeds max" / "excede máximo"
- "below min" / "abaixo do mínimo"
- "in [year]" / "em [ano]"
- "points" / "pontos"

### Metric names (same as previous spec)
All metric names need EN + PT-BR — reuse existing translations where available.

### LLM-generated rationale
The LLM prompt asks for both `rationale_en` and `rationale_pt` in the response,
so no separate translation step is needed.

---

## 6. Testing

### 6.1 Pipeline fix
- [ ] Profitability plausibility shows correct point count (not 0)
- [ ] Balance Sheet plausibility table renders with bounds and rationale
- [ ] Cash Flow plausibility table renders with bounds and rationale
- [ ] Summary cards show correct counts
- [ ] Quality Score computes (not —%)

### 6.2 LLM-generated bounds
- [ ] LLM call fires during Step 5 execution
- [ ] Braskem gets petrochemical-specific bounds
- [ ] Vale gets mining-specific bounds
- [ ] Votorantim gets building-materials-specific bounds
- [ ] Bounds differ between companies (spot-check: Asset Turnover max differs)
- [ ] Sector label displays correctly in section headers
- [ ] Rationale text is specific to the sector (not generic)
- [ ] Both EN and PT-BR rationale present in LLM response

### 6.3 Fallback behavior
- [ ] DEFAULT bounds display if LLM call fails
- [ ] "(GENERAL INDUSTRIAL)" label and fallback note appear
- [ ] Loading state shows while LLM call is in progress
- [ ] Tables render with DEFAULT bounds during loading

### 6.4 Validation results
- [ ] Failed checks show flagged values with period and actual value
- [ ] Amber severity indicator for out-of-range values
- [ ] "All checks passed" shows when no flags

### 6.5 Regression
- [ ] All regression tests pass
- [ ] Full pipeline works for Braskem, Vale, Votorantim
- [ ] Steps 6–9 unaffected
- [ ] Cross-Statement Consistency still works
- [ ] Cash reconciliation summary collapse still works

---

## 7. Definition of Done

- [ ] BS and CF plausibility checks produce visible results
- [ ] Summary cards show correct counts and quality score
- [ ] DEFAULT bounds defined as hardcoded fallback
- [ ] LLM generates sector-specific bounds per company
- [ ] Bounds cached per company + language
- [ ] Sector label displayed in section headers
- [ ] Fallback to DEFAULT if LLM fails
- [ ] Loading state during LLM call
- [ ] Failed checks displayed with context
- [ ] All rationale bilingual (EN + PT-BR from LLM)
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
