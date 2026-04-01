# Phase 2: Company Selector — Claude Code Spec

> **What this is:** Instructions for adding a company selector to the CVM Demo App,
> allowing users to run the full 9-step pipeline for any company in the CVM database.
>
> **Prerequisite:** Phase 1 must be complete (Steps 1-9 working for Braskem).
>
> **CRITICAL:** Do NOT change the detection algorithms in `pattern_detector.py`.
> Do NOT change the AI agent prompts in Steps 7-9 (they are already company-agnostic).
> Do NOT change Steps 1-5 pipeline logic (only parameterize the company filter).

---

## Architecture Principle

The current app flows `config.company_name` through every step. No pipeline logic
is hardcoded to "BRASKEM". The AI agent in Steps 7-9 adapts to whatever company
and findings it receives. Phase 2 is primarily:

1. A frontend company selector
2. A company lookup/search endpoint
3. Sector detection for enrichment
4. Testing and edge case handling

---

## 1. Company Lookup Endpoint

### New endpoint: `GET /api/companies`

Returns the list of available companies from CVM data. Two modes:

**Mode A — From cached company list (fast, default):**

On first run of Step 1 (or on app startup), scan the downloaded DFP files and
extract the unique list of `DENOM_CIA` values. Cache this as `cache/companies.json`.

**Mode B — From live CVM data (if cache doesn't exist):**

Download a small DFP file (e.g., most recent year), extract unique companies.

**Response shape:**

```json
{
  "companies": [
    {
      "name": "BRASKEM S.A.",
      "cvm_code": "4820",
      "sector": "Petrochemical",
      "sector_source": "mapped"
    },
    {
      "name": "VALE S.A.",
      "cvm_code": "4170",
      "sector": "Mining",
      "sector_source": "mapped"
    },
    {
      "name": "SUZANO S.A.",
      "cvm_code": "8087",
      "sector": "Pulp & Paper",
      "sector_source": "mapped"
    },
    {
      "name": "AMBEV S.A.",
      "cvm_code": "24317",
      "sector": "Unknown",
      "sector_source": "unmapped"
    }
  ],
  "total": 450,
  "mapped_sectors": 12,
  "unmapped": 438
}
```

**Sector detection:** Use the existing `SECTOR_MAP` in `enrichment.py` for known
companies. For unknown companies, set sector to "Unknown" — the AI agent in Step 7
will infer the sector from the company name and findings.

### New endpoint: `GET /api/companies/search?q={query}`

Fuzzy search against company names. Returns top 10 matches.

```json
{
  "results": [
    { "name": "BRASKEM S.A.", "cvm_code": "4820", "sector": "Petrochemical", "score": 1.0 },
    { "name": "BRASIL BROKERS PARTICIPAÇÕES S.A.", "cvm_code": "21610", "sector": "Unknown", "score": 0.45 }
  ]
}
```

**Implementation:** Simple case-insensitive substring match on `DENOM_CIA`. No need
for a fuzzy matching library — CVM company names are formal legal names, and users
will type enough characters to narrow down.

---

## 2. Company Selector UI

### Frontend component: `CompanySelector.jsx`

**Location:** In the app header, between the title and the language/cache toggles.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  CVM Analysis    [🔍 Braskem S.A.        ▼]    [PT|EN]  [Live|Cache] │
└──────────────────────────────────────────────────────────────────────┘
```

**Behavior:**

1. **Default state:** Shows current company name (e.g., "Braskem S.A.") with a
   dropdown indicator.

2. **On click:** Opens a search-enabled dropdown:
   - Text input at top for searching ("Search company..." / "Buscar empresa...")
   - As user types, calls `GET /api/companies/search?q={input}` with debounce (300ms)
   - Results displayed as a scrollable list (max 10 items)
   - Each result shows: company name + sector badge (if mapped)
   - Click a result to select it

3. **On selection:**
   - Calls `POST /api/config` with the new company name
   - Clears all pipeline state (all steps reset to "pending")
   - Resets the wizard to Step 1
   - User must re-run the pipeline for the new company

4. **Visual indicator:** If a company has `sector_source: "unmapped"`, show a
   subtle indicator: "Sector will be detected by AI" / "Setor será detectado por IA"

### Pipeline reset on company change

When the user selects a new company:

**Backend:**
- `POST /api/config` sets `config.company_name` to the new value
- `POST /api/config` clears `pipeline_state` (all steps reset)
- Cache is NOT cleared — each company's cache lives in a company-specific subdirectory

**Frontend:**
- Dispatch `RESET_PIPELINE` action (new action) that sets all steps back to "pending"
- Navigate to Step 1
- Show a brief toast/notification: "Company changed to {name}. Run the pipeline from Step 1."

---

## 3. Backend Changes

### `config.py` — Company management

Add `company_name` to the config that gets set via `POST /api/config`:

```python
@dataclass
class AppConfig:
    company_name: str = "BRASKEM S.A."
    cache_mode: bool = False
    language: str = "en"
```

The `POST /api/config` endpoint should accept:
```json
{
  "company_name": "VALE S.A.",
  "cache_mode": false
}
```

When `company_name` changes, clear `pipeline_state`.

### `cache_utils.py` — Company-specific caching

Change cache directory structure from:
```
cache/step1.json
cache/step2.json
...
```

To:
```
cache/BRASKEM_SA/step1.json
cache/BRASKEM_SA/step2.json
...
cache/VALE_SA/step1.json
cache/VALE_SA/step2.json
...
```

The cache key is the company name sanitized for filesystem use (replace spaces,
periods, slashes with underscores).

This means if a user runs Braskem, switches to Vale, and switches back to Braskem,
the cached Braskem data is still available.

### `pipeline/cvm_downloader.py` — No changes needed

Step 1 downloads DFP and ITR files that contain ALL companies. The company filter
is applied in Step 2. The download step is already company-agnostic.

However, add the company list extraction logic:

```python
def extract_company_list(data_dir: str = "data") -> list[dict]:
    """Scan downloaded DFP files and return unique companies with CVM codes."""
    companies = {}
    for csv_file in Path(data_dir).glob("dfp_*.csv"):
        df = pd.read_csv(csv_file, usecols=["DENOM_CIA", "CD_CVM"], encoding="latin-1", sep=";")
        for _, row in df.drop_duplicates(subset=["DENOM_CIA"]).iterrows():
            name = row["DENOM_CIA"]
            if name not in companies:
                companies[name] = {"name": name, "cvm_code": str(row["CD_CVM"])}
    return sorted(companies.values(), key=lambda c: c["name"])
```

### `pipeline/data_cleaner.py` — Parameterize company filter

Step 2 currently filters for the configured company. Verify that it uses
`config.company_name` and not a hardcoded string. The filter should be:

```python
df = df[df["DENOM_CIA"] == config.company_name]
```

Also add a validation: if the filtered result has zero rows, return an error
response instead of proceeding with empty data:

```python
if len(df) == 0:
    raise ValueError(
        f"Company '{config.company_name}' not found in CVM data. "
        f"Check the company name matches DENOM_CIA exactly."
    )
```

### `pipeline/enrichment.py` — Expand SECTOR_MAP

The current `SECTOR_MAP` only has 6 entries (Braskem, Unipar, Elekeiroz, Suzano,
Gerdau, Vale). Expand it with additional well-known Brazilian companies:

```python
SECTOR_MAP = {
    # Petrochemical
    "BRASKEM": "Petrochemical",
    "UNIPAR": "Petrochemical",
    "ELEKEIROZ": "Petrochemical",
    # Pulp & Paper
    "SUZANO": "Pulp & Paper",
    "KLABIN": "Pulp & Paper",
    # Steel
    "GERDAU": "Steel",
    "USIMINAS": "Steel",
    "CSN": "Steel",
    # Mining
    "VALE": "Mining",
    # Oil & Gas
    "PETROBRAS": "Oil & Gas",
    "PRIO": "Oil & Gas",
    "3R PETROLEUM": "Oil & Gas",
    # Food & Beverage
    "AMBEV": "Food & Beverage",
    "JBS": "Food & Beverage",
    "BRF": "Food & Beverage",
    "MARFRIG": "Food & Beverage",
    # Retail
    "MAGAZINE LUIZA": "Retail",
    "LOJAS RENNER": "Retail",
    "VIA": "Retail",
    # Utilities
    "ELETROBRAS": "Utilities",
    "ENERGISA": "Utilities",
    "EQUATORIAL": "Utilities",
    "ENGIE": "Utilities",
    "CPFL": "Utilities",
    "COPEL": "Utilities",
    # Telecommunications
    "TELEFONICA": "Telecommunications",
    "TIM": "Telecommunications",
    # Banking (likely won't produce meaningful COGS analysis, but include for completeness)
    "ITAU": "Banking",
    "BRADESCO": "Banking",
    "BANCO DO BRASIL": "Banking",
    "SANTANDER": "Banking",
    # Construction / Real Estate
    "MRV": "Construction",
    "CYRELA": "Construction",
    # Transportation
    "LOCALIZA": "Transportation",
    "RUMO": "Transportation",
    "AZUL": "Airlines",
    "GOL": "Airlines",
}
```

For companies NOT in this map, the `_get_sector()` function returns `"_default"`.
The AI agent will infer the sector. This is fine — the AI agent is already
company-agnostic.

### `pipeline/pattern_detector.py` — Edge case handling

Add guards for companies with unusual data profiles:

```python
# In analyze_margin_trends:
if len(comp) < 4:
    continue  # Already exists, but verify

# In analyze_cost_drift:
if len(series) < 4:
    continue  # Already exists

# In detect_anomalies:
if len(series) < 6:
    continue  # Already exists
```

Also add a guard in the main `detect_patterns()` function:

```python
if len(all_findings) == 0:
    # No findings detected — this is valid for some companies
    # Return empty findings with a note, don't raise an error
    pass
```

The risk: some companies may produce 0 findings (stable financials, short history,
or insufficient data). The pipeline should handle this gracefully, not crash.

### `pipeline/metrics_calculator.py` — D&A lookup robustness

Step 4 reads D&A from DFC (cash flow statement) ZIPs. For some companies, D&A
may not be available or may be structured differently. Add error handling:

```python
try:
    da_value = extract_da_from_dfc(company_name, period)
except (KeyError, FileNotFoundError):
    da_value = None  # EBITDA will be computed without D&A adjustment
```

If D&A is not available, EBITDA_Margin_pct should be computed as EBIT + estimated
D&A, or marked as "N/A" in the output. The frontend should handle missing EBITDA
gracefully (show "—" instead of a number).

---

## 4. Frontend Changes

### `App.jsx` — New reducer action

Add `RESET_PIPELINE` action:

```javascript
case 'RESET_PIPELINE':
  return {
    ...state,
    currentStep: 1,
    stepData: {},
    stepStatus: {1: 'pending', 2: 'pending', ...9: 'pending'},
  };
```

### `StepWizard.jsx` or `App.jsx` — Company name display

Currently the app may show "Braskem" in various places. Ensure all company name
references come from the config API response or from Step 1/2 data, never hardcoded
in the frontend.

Check for any hardcoded "Braskem" or "BRASKEM" strings in:
- Step component titles or descriptions
- Chart labels or annotations
- i18n files (these should use `{company}` placeholders, not literal names)

### `CompanySelector.jsx` — New component (described in section 2)

### i18n updates

Add keys for the company selector:

**English:**
```json
{
  "company_selector": {
    "search_placeholder": "Search company...",
    "current_company": "Current company",
    "change_company": "Change company",
    "sector_detected_by_ai": "Sector will be detected by AI",
    "company_changed": "Company changed to {company}. Run the pipeline from Step 1.",
    "no_results": "No companies found",
    "loading": "Loading companies..."
  }
}
```

**Portuguese:**
```json
{
  "company_selector": {
    "search_placeholder": "Buscar empresa...",
    "current_company": "Empresa atual",
    "change_company": "Trocar empresa",
    "sector_detected_by_ai": "Setor será detectado por IA",
    "company_changed": "Empresa alterada para {company}. Execute o pipeline a partir do Passo 1.",
    "no_results": "Nenhuma empresa encontrada",
    "loading": "Carregando empresas..."
  }
}
```

---

## 5. Edge Cases and Error Handling

### Companies with insufficient data

Some CVM companies may have very few periods of data (recently listed, recently
delisted, or small companies with irregular filings). Handle:

- **< 4 periods:** Pattern detection algorithms skip the company (already handled).
  Step 6 may return 0 findings. Step 7 AI agent should be told "No significant
  patterns were detected" and asked to comment on what limited data shows.
- **Missing revenue or COGS:** Some companies (especially financial institutions)
  don't report COGS in the same structure. Step 2 or 4 should detect this and
  return a clear error: "This company's income statement structure is not compatible
  with COGS-based analysis."

### Financial institutions (banks, insurers)

Banks don't have COGS. Their DRE structure is fundamentally different (interest
income, provisions, etc.). The current pipeline assumes an industrial/commercial
income statement. For Phase 2 MVP, it's acceptable to show an error:

"This company is a financial institution. The current analysis is designed for
industrial and commercial companies with COGS-based income statements. Financial
institution analysis will be available in a future version."

Detect financial institutions by checking if `CD_CONTA` starting with `3.02`
(COGS) has zero or null values for all periods.

### Company name matching edge cases

CVM uses formal legal names that may differ from common names:
- "PETRÓLEO BRASILEIRO S.A. - PETROBRAS" (not just "PETROBRAS")
- "ITAÚ UNIBANCO HOLDING S.A." (not just "ITAU")
- "MAGAZINE LUIZA S.A." (not "MAGALU")

The search endpoint should match on substrings, so searching "PETROBRAS" finds
"PETRÓLEO BRASILEIRO S.A. - PETROBRAS". Also handle accented characters
(normalize to ASCII for matching, but display the original name).

---

## 6. Testing Plan

Before declaring Phase 2 complete, test with at least these companies:

| Company | Sector | Why |
|---------|--------|-----|
| BRASKEM S.A. | Petrochemical | Baseline — must produce same results as Phase 1 |
| VALE S.A. | Mining | Capital-intensive, commodity exposure, known data |
| SUZANO S.A. | Pulp & Paper | Different cost structure (biological assets) |
| GERDAU S.A. | Steel | Different margin profile |
| PETRÓLEO BRASILEIRO S.A. - PETROBRAS | Oil & Gas | Very large, complex structure |
| AMBEV S.A. | Food & Beverage | Non-commodity industrial |
| MAGAZINE LUIZA S.A. | Retail | Non-industrial, very different profile |
| ITAÚ UNIBANCO HOLDING S.A. | Banking | Should show "not compatible" error |

For each company, verify:
- [ ] Step 1 downloads data without error
- [ ] Step 2 filters to correct company (non-zero rows)
- [ ] Step 3 dedup and pivot work correctly
- [ ] Step 4 metrics compute (or gracefully handle missing D&A)
- [ ] Step 5 quality scan runs
- [ ] Step 6 produces findings (or empty findings gracefully)
- [ ] Step 7 AI agent generates relevant sector-specific analysis
- [ ] Step 8 executive summary references correct company
- [ ] Step 9 Q&A works with correct context

---

## 7. Project Structure Changes

### New files:
- `frontend/src/components/CompanySelector.jsx`
- `frontend/src/components/CompanySelector.module.css`

### Modified files:
- `backend/main.py` — add `/api/companies` and `/api/companies/search` endpoints
- `backend/config.py` — handle company change + pipeline reset
- `backend/cache_utils.py` — company-specific cache directories
- `backend/pipeline/cvm_downloader.py` — add `extract_company_list()`
- `backend/pipeline/data_cleaner.py` — add zero-row validation
- `backend/pipeline/enrichment.py` — expand `SECTOR_MAP`
- `backend/pipeline/metrics_calculator.py` — D&A error handling
- `frontend/src/App.jsx` — add `RESET_PIPELINE` action, render CompanySelector
- `frontend/src/i18n/en.json` — add company_selector keys
- `frontend/src/i18n/pt-br.json` — add company_selector keys

### No changes needed:
- `backend/pipeline/pattern_detector.py` — already company-agnostic
- `backend/steps/step7_ai_agent.py` — already company-agnostic
- `backend/steps/step8_reporting.py` — already company-agnostic
- `backend/steps/step9_llm_analysis.py` — already company-agnostic
- All chart components — already data-driven

---

## 8. Build Sequence

| Day | Task |
|-----|------|
| 1 | Backend: company list endpoint, search endpoint, company-specific caching, expanded SECTOR_MAP |
| 2 | Frontend: CompanySelector component, RESET_PIPELINE action, wiring |
| 3 | Edge cases: zero-row validation, financial institution detection, missing D&A handling |
| 4 | Testing: run pipeline for all 8 test companies, fix issues |
| 5 | Polish: error messages, loading states, i18n completion |

Estimated: **5 working days** with Claude Code.

---

## 9. Verification Checklist

- [ ] Braskem produces identical results to Phase 1 (regression test)
- [ ] Company selector appears in header with search functionality
- [ ] Selecting a new company resets pipeline and navigates to Step 1
- [ ] Company-specific cache directories work (switch companies, switch back)
- [ ] Vale, Suzano, Gerdau, Petrobras all produce meaningful findings
- [ ] Ambev and Magazine Luiza produce findings (non-commodity companies)
- [ ] Itaú shows "financial institution not compatible" error
- [ ] AI agent (Steps 7-9) generates sector-appropriate analysis for each company
- [ ] All i18n keys present and working
- [ ] No hardcoded "Braskem" or "BRASKEM" strings in frontend
- [ ] Pipeline handles companies with < 4 periods gracefully
- [ ] Pipeline handles missing D&A gracefully
