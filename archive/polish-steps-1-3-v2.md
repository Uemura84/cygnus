# Polish — Steps 1-3 Data Loading Transparency

> **What this is:** Build spec for Claude Code. Improves transparency across
> Steps 1-3 by renaming outdated step labels, breaking down row counts by
> financial statement type, showing what was found inside downloaded ZIPs,
> and surfacing the data quality filtering story.
>
> **Branch:** `polish-data-transparency`
>
> **Scope:** Frontend + minimal backend changes to surface file stats. No changes
> to detection, stacking, AI prompts, or any analytical logic.

---

## 1. Step Naming Updates

### 1.1 Current names (outdated)

```
1  Download CVM Data
2  Data Preparation
3  DRE Transformation
```

Step 3's name ("DRE Transformation") only references income statements. The system
now transforms three financial statements. Step 2's name is generic and doesn't
tell the user what's happening.

### 1.2 New names

```
1  Download CVM Data           ← keep (still accurate)
2  Data Quality Filters        ← renamed (tells the user what this step does)
3  Financial Statement Mapping  ← renamed (reflects all three statements)
```

Update in:
- Sidebar step labels (StepWizard component)
- Any step header text inside the step components
- i18n files (EN + PT-BR)

PT-BR translations:
- "Data Quality Filters" → "Filtros de Qualidade de Dados"
- "Financial Statement Mapping" → "Mapeamento de Demonstrações Financeiras"

---

## 2. Step 1 — Download CVM Data (Updated Display)

### 2.1 Current state

Shows: company name, DFP rows, ITR rows, total rows, date range, files downloaded.

The row counts are only for income statement (DRE) data, but the labels say
"DFP ROWS" and "ITR ROWS" — which is misleading because each DFP/ITR ZIP contains
multiple file types (DRE, BPA, BPP, DFC, DVA).

### 2.2 Target state

Step 1 shows what was **downloaded and discovered**. The user should understand:
which ZIPs were fetched, and what financial statement files exist inside them.

**Top section (keep as-is but clarify):**

```
COMPANY              FILING YEARS         DATE RANGE
BRASKEM S.A.         2020–2025            2020-03-31 → 2025-12-31
```

**Files downloaded section (keep as-is):**
The ZIP file badges are good — they show exactly what was fetched.

**NEW: Statements found section:**

After the ZIP badges, add a summary showing which CSV file types were found
inside the ZIPs:

```
STATEMENTS FOUND

┌─────────────────────────┬─────────────┬──────────────┬──────────────┐
│  STATEMENT              │  DFP FILES  │  ITR FILES   │  TOTAL ROWS  │
├─────────────────────────┼─────────────┼──────────────┼──────────────┤
│  Income Statement (DRE) │  6          │  6           │  3,142       │
│  Balance Sheet (BPA)    │  6          │  6           │  2,856       │
│  Balance Sheet (BPP)    │  6          │  6           │  2,214       │
│  Cash Flow (DFC)        │  6          │  6           │  1,876       │
└─────────────────────────┴─────────────┴──────────────┴──────────────┘
```

This tells the user: "We downloaded 12 ZIPs. Inside them, we found income
statement, balance sheet (assets and liabilities), and cash flow files.
Here's how much raw data is in each."

**Design:**
- Section label: "STATEMENTS FOUND" in JetBrains Mono uppercase, Signal Blue
- Table: standard Cygnus card with off-white background
- Statement names in DM Sans
- Numbers in JetBrains Mono
- File type abbreviations in parentheses (DRE, BPA, BPP, DFC) — these are
  recognizable to anyone who works with CVM data

### 2.3 Remove misleading "DFP ROWS / ITR ROWS" cards

The current "DFP ROWS: 550" and "ITR ROWS: 2,592" cards are confusing because
they count only DRE rows but the labels suggest they count all rows in the ZIP.
Replace with the "Statements Found" table above, which breaks down by statement
type and filing type.

If you want to keep a total count, show it as a single summary:
"Total records across all statements: 10,088"

---

## 3. Step 2 — Data Quality Filters (Updated Display)

### 3.1 Current state

Step 2 is called "Data Preparation" and likely shows minimal information about
what filtering was applied.

### 3.2 Target state

Step 2 shows the **before and after** story for each filter. The user should
understand: what data quality rules were applied, and how much data was removed
by each one.

**Display: one card per filter, showing the effect:**

```
DATA QUALITY FILTERS

┌──────────────────────────────────────────────────────────┐
│  ORDEM_EXERC FILTER                                      │
│  Keeps only the most recent exercise (ÚLTIMO) per filing │
│  Removes prior-year restated comparison rows             │
│                                                          │
│  Before: 10,088 rows    After: 6,412 rows    -36.4%     │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  COMPANY FILTER                                          │
│  Keeps only BRASKEM S.A. rows                            │
│  Excludes holding companies and unrelated entities       │
│                                                          │
│  Before: 6,412 rows     After: 1,847 rows    -71.2%     │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  DFP / ITR OVERLAP RESOLUTION                            │
│  When annual (DFP) and quarterly (ITR) filings cover     │
│  the same period, DFP takes precedence                   │
│                                                          │
│  Before: 1,847 rows     After: 1,623 rows    -12.1%     │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  YTD-TO-STANDALONE CONVERSION                            │
│  Quarterly income statement and cash flow figures are    │
│  reported as year-to-date cumulative. Converted to       │
│  standalone quarters by subtracting prior quarter.       │
│  Balance sheet data is not converted (point-in-time).    │
│                                                          │
│  Applied to: DRE (income), DFC (cash flow)               │
│  Not applied to: BPA, BPP (balance sheet)                │
└──────────────────────────────────────────────────────────┘
```

**Design:**
- Section label: "DATA QUALITY FILTERS" in JetBrains Mono uppercase, Signal Blue
- Each filter: standard card, off-white background
- Filter name: DM Sans 500, navy
- Description: DM Sans 400, slate
- Before/After numbers: JetBrains Mono
- Percentage reduction: JetBrains Mono, slate
- The YTD card doesn't show row counts (it's a transformation, not a filter)
  — instead it shows which statement types were affected

### 3.3 Backend support

The filtering functions need to return counts. Add instrumentation:

```python
filter_stats = {
    "ordem_exerc": {
        "before": total_rows_before,
        "after": total_rows_after,
    },
    "company_filter": {
        "before": ...,
        "after": ...,
    },
    "dfp_itr_overlap": {
        "before": ...,
        "after": ...,
    },
    "ytd_conversion": {
        "applied_to": ["DRE", "DFC"],
        "not_applied_to": ["BPA", "BPP"],
    },
}
```

Return these stats in the Step 2 API response. Do NOT change any filtering logic —
only add counting.

---

## 4. Step 3 — Financial Statement Mapping (Updated Display)

### 4.1 Current state

Step 3 is called "DRE Transformation" and shows the income statement account
mapping. Balance sheet and cash flow mapping details are not shown.

### 4.2 Target state

Step 3 shows the **mapping results** for all three statement types. The user
should understand: what CVM accounts were mapped to common model fields, how
many fields were populated, and which sub-accounts were found by keyword matching.

**Display: three panels (or tabs), one per statement type:**

**Income Statement panel** — keep existing content (account mapping table, etc.)
but update the header from "DRE Transformation" to "Income Statement (DRE)".

**Balance Sheet panel:**

```
BALANCE SHEET (BPA + BPP)

Periods mapped: 6 annual + 20 quarterly

Account mapping:
┌───────────────────────────────┬──────────┬────────────────────┐
│  Common Model Field           │  CVM Code│  Status            │
├───────────────────────────────┼──────────┼────────────────────┤
│  total_assets                 │  1       │  ✓ mapped          │
│  current_assets               │  1.01    │  ✓ mapped          │
│  cash_and_equivalents         │  1.01.01 │  ✓ mapped          │
│  accounts_receivable          │  1.01.03 │  ✓ mapped          │
│  inventories                  │  1.01.04 │  ✓ mapped          │
│  non_current_assets           │  1.02    │  ✓ mapped          │
│  property_plant_equipment     │  1.02.03 │  ✓ mapped          │
│  intangible_assets            │  1.02.04 │  ✓ mapped          │
│  total_liabilities            │  derived │  ✓ computed        │
│  current_liabilities          │  2.01    │  ✓ mapped          │
│  accounts_payable             │  2.01.02 │  — not found       │
│  short_term_debt              │  2.01.04 │  ✓ mapped          │
│  non_current_liabilities      │  2.02    │  ✓ mapped          │
│  long_term_debt               │  2.02.01 │  ✓ mapped          │
│  total_equity                 │  2.03    │  ✓ mapped          │
│  retained_earnings            │  2.03.04 │  — not found       │
└───────────────────────────────┴──────────┴────────────────────┘

Coverage: 14 of 16 fields mapped
```

**Cash Flow panel:**

```
CASH FLOW (DFC)

Periods mapped: 6 annual + 20 quarterly

Top-level accounts (by CVM code):
┌───────────────────────────────┬──────────┬────────────────────┐
│  Common Model Field           │  CVM Code│  Status            │
├───────────────────────────────┼──────────┼────────────────────┤
│  operating_cash_flow          │  6.01    │  ✓ mapped          │
│  investing_cash_flow          │  6.02    │  ✓ mapped          │
│  financing_cash_flow          │  6.03    │  ✓ mapped          │
└───────────────────────────────┴──────────┴────────────────────┘

Sub-accounts (by keyword matching on DS_CONTA):
┌───────────────────────────────┬──────────────────────────────────┐
│  Common Model Field           │  Status                          │
├───────────────────────────────┼──────────────────────────────────┤
│  depreciation_amortization    │  ✓ found ("Depreciação e...")    │
│  capex                        │  ✓ found ("Aquisição de imob.") │
│  debt_issuance                │  ✓ found ("Captação de emp...")  │
│  debt_repayment               │  ✓ found ("Pagamento de emp..")│
│  dividends_paid               │  ✓ found ("Dividendos pagos")   │
│  acquisitions                 │  — not found                     │
│  working_capital_change       │  — not found                     │
└───────────────────────────────┴──────────────────────────────────┘

Coverage: 5 of 7 sub-accounts matched
```

The sub-account panel is especially important for transparency — it shows
exactly which keywords matched, so the user can verify the mapping makes sense.
Show a truncated version of the actual DS_CONTA text that matched.

**Design:**
- Section labels: JetBrains Mono uppercase, Signal Blue
- Table: standard Cygnus card
- ✓ mapped / ✓ found: Signal Blue checkmark + text
- ✓ computed: Signal Blue checkmark + italic text (for derived fields like total_liabilities)
- — not found: Slate dash + text
- CVM codes: JetBrains Mono
- DS_CONTA excerpts: JetBrains Mono, slate, truncated with ellipsis
- Coverage summary: DM Sans 500, navy

### 4.3 Backend support

The mapping functions need to report what they found. Add metadata:

```python
bs_mapping_stats = {
    "periods_annual": 6,
    "periods_quarterly": 20,
    "fields": [
        {"field": "total_assets", "cvm_code": "1", "status": "mapped"},
        {"field": "current_assets", "cvm_code": "1.01", "status": "mapped"},
        {"field": "accounts_payable", "cvm_code": "2.01.02", "status": "not_found"},
        {"field": "total_liabilities", "cvm_code": "derived", "status": "computed"},
        # ...
    ],
    "fields_mapped": 14,
    "fields_total": 16,
}

cf_mapping_stats = {
    "periods_annual": 6,
    "periods_quarterly": 20,
    "top_level": [
        {"field": "operating_cash_flow", "cvm_code": "6.01", "status": "mapped"},
        {"field": "investing_cash_flow", "cvm_code": "6.02", "status": "mapped"},
        {"field": "financing_cash_flow", "cvm_code": "6.03", "status": "mapped"},
    ],
    "sub_accounts": [
        {"field": "depreciation_amortization", "status": "found",
         "matched_description": "Depreciação e Amortização"},
        {"field": "capex", "status": "found",
         "matched_description": "Aquisição de Imobilizado e Intangível"},
        {"field": "acquisitions", "status": "not_found",
         "matched_description": None},
        # ...
    ],
    "sub_accounts_found": 5,
    "sub_accounts_total": 7,
}
```

Return these in the Step 3 API response. Do NOT change any mapping logic.

---

## 5. Summary of All Changes

| Step | Name change | Content change |
|------|-------------|----------------|
| 1 | No | Replace misleading DFP/ITR row cards with "Statements Found" table showing row counts per statement type |
| 2 | "Data Preparation" → "Data Quality Filters" | Add filter-by-filter before/after cards showing what was removed |
| 3 | "DRE Transformation" → "Financial Statement Mapping" | Add BS and CF mapping panels showing field coverage and keyword matches |

---

## 6. i18n — All New Labels

### Step names
- "Data Quality Filters" / "Filtros de Qualidade de Dados"
- "Financial Statement Mapping" / "Mapeamento de Demonstrações Financeiras"

### Step 1
- "Statements Found" / "Demonstrações Encontradas"
- "Statement" / "Demonstração"
- "DFP Files" / "Arquivos DFP"
- "ITR Files" / "Arquivos ITR"
- "Total Rows" / "Total de Registros"
- "Income Statement (DRE)" / "Demonstração de Resultado (DRE)"
- "Balance Sheet (BPA)" / "Balanço Patrimonial — Ativo (BPA)"
- "Balance Sheet (BPP)" / "Balanço Patrimonial — Passivo (BPP)"
- "Cash Flow (DFC)" / "Fluxo de Caixa (DFC)"

### Step 2
- "Data Quality Filters" / "Filtros de Qualidade de Dados"
- "ORDEM_EXERC Filter" / "Filtro ORDEM_EXERC"
- "Keeps only the most recent exercise (ÚLTIMO) per filing" / "Mantém apenas o exercício mais recente (ÚLTIMO) por arquivo"
- "Removes prior-year restated comparison rows" / "Remove linhas de comparação reapresentadas do exercício anterior"
- "Company Filter" / "Filtro de Empresa"
- "Excludes holding companies and unrelated entities" / "Exclui holdings e entidades não relacionadas"
- "DFP / ITR Overlap Resolution" / "Resolução de Sobreposição DFP / ITR"
- "When annual (DFP) and quarterly (ITR) filings cover the same period, DFP takes precedence" / "Quando arquivos anuais (DFP) e trimestrais (ITR) cobrem o mesmo período, DFP tem precedência"
- "YTD-to-Standalone Conversion" / "Conversão YTD para Standalone"
- "Applied to" / "Aplicado a"
- "Not applied to" / "Não aplicado a"
- "Before" / "Antes"
- "After" / "Após"

### Step 3
- "Account Mapping" / "Mapeamento de Contas"
- "Periods mapped" / "Períodos mapeados"
- "annual" / "anuais"
- "quarterly" / "trimestrais"
- "Common Model Field" / "Campo do Modelo"
- "CVM Code" / "Código CVM"
- "Status" / "Status"
- "mapped" / "mapeado"
- "computed" / "calculado"
- "found" / "encontrado"
- "not found" / "não encontrado"
- "Top-level accounts" / "Contas de nível superior"
- "Sub-accounts (by keyword matching)" / "Subcontas (por busca de palavra-chave)"
- "Coverage" / "Cobertura"
- "of _ fields mapped" / "de _ campos mapeados"
- "of _ sub-accounts matched" / "de _ subcontas encontradas"

---

## 7. Testing

- [ ] Step 1 name unchanged, Step 2 renamed, Step 3 renamed
- [ ] Step 1 shows "Statements Found" table with per-statement row counts
- [ ] Step 1 old "DFP ROWS / ITR ROWS" cards removed or replaced
- [ ] Step 2 shows filter cards with before/after counts
- [ ] Step 2 YTD card shows which statements were affected
- [ ] Step 3 shows Income Statement mapping (existing, preserved)
- [ ] Step 3 shows Balance Sheet mapping with field coverage
- [ ] Step 3 shows Cash Flow mapping with sub-account keyword matches
- [ ] All labels bilingual (EN + PT-BR)
- [ ] Displays correctly for Braskem
- [ ] Displays correctly for Vale
- [ ] Displays correctly for Votorantim
- [ ] All regression tests still pass
- [ ] Full 9-step pipeline works end-to-end
- [ ] No analytical logic changed

---

## 8. Definition of Done

- [ ] Step 2 and 3 renamed in sidebar + headers + i18n
- [ ] Step 1 shows per-statement-type row counts
- [ ] Step 2 shows filter-by-filter before/after stats
- [ ] Step 3 shows BS and CF mapping panels with coverage indicators
- [ ] Cash flow sub-account keyword match details visible
- [ ] All labels in EN + PT-BR
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
- [ ] Code committed and pushed
