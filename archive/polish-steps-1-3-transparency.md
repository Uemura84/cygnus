# Polish — Steps 1-3 Data Loading Transparency

> **What this is:** Build spec for Claude Code. Extends the data loading display
> in Steps 1-3 to show balance sheet and cash flow file statistics alongside
> the existing income statement stats.
>
> **Branch:** Create `polish-data-transparency` from `master` (merge phase3 first
> if not already merged).
>
> **Scope:** Frontend + minimal backend changes to surface file stats. No changes
> to detection, stacking, AI prompts, or any analytical logic.

---

## 1. Current State

Steps 1-3 currently display data loading progress and statistics for income
statement (DRE) files only:
- Which company was selected
- Which years are being loaded
- How many DRE records were found
- How many survived filtering (ORDEM_EXERC, dedup, overlap resolution)

Balance sheet (BPA/BPP) and cash flow (DFC) files are parsed in the backend
(added in Sprint 2) but their loading statistics are not surfaced in the UI.

---

## 2. Target State

Steps 1-3 should show the same level of detail for all three statement types.
The user should see at a glance: what data went in, how much survived quality
filters, and what's available for analysis.

### 2.1 Data stats to surface

For each file type, show:

**Income Statement (DRE)** — already shown, keep as-is:
- Records loaded
- Records after filtering
- Periods available (annual + quarterly count)

**Balance Sheet (BPA + BPP):**
- BPA records loaded (assets)
- BPP records loaded (liabilities + equity)
- Records after filtering (ORDEM_EXERC, dedup, overlap)
- Periods available
- Accounts mapped (how many of the common model fields were populated)

**Cash Flow (DFC):**
- DFC records loaded
- Records after filtering
- Periods available
- Sub-accounts matched by keyword (capex, D&A, debt, dividends — show which
  were found and which returned None)

### 2.2 Display format

Follow the existing pattern for income statement stats. Add two new sections
(or extend the existing display) for balance sheet and cash flow.

**Recommended layout:** Three columns or three collapsible panels, one per
statement type:

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   INCOME STATEMENT  │  │   BALANCE SHEET      │  │   CASH FLOW         │
│   DRE               │  │   BPA + BPP          │  │   DFC               │
│                     │  │                      │  │                     │
│   Records: 1,247    │  │   BPA records: 892   │  │   Records: 634      │
│   After filter: 186 │  │   BPP records: 756   │  │   After filter: 98  │
│   Periods: 6 annual │  │   After filter: 214  │  │   Periods: 6 annual │
│   + 20 quarterly    │  │   Periods: 6 annual  │  │   + 20 quarterly    │
│                     │  │   + 20 quarterly     │  │                     │
│                     │  │   Accounts mapped:   │  │   Sub-accounts:     │
│                     │  │   12 of 16 fields    │  │   ✓ D&A             │
│                     │  │                      │  │   ✓ Capex           │
│                     │  │                      │  │   ✓ Dividends       │
│                     │  │                      │  │   — Debt issuance   │
│                     │  │                      │  │   — Acquisitions    │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

Use the Cygnus design system:
- Section labels: JetBrains Mono, uppercase, Signal Blue
- Numbers: JetBrains Mono
- Body text: DM Sans
- Cards: off-white background, standard border
- Checkmarks (✓) for found sub-accounts in Signal Blue
- Dashes (—) for missing sub-accounts in Slate

### 2.3 Which step shows what

This depends on the current step structure. The stats could appear in:
- **Step 1** (download) — raw record counts per file type
- **Step 2** (clean) — before/after filter counts, showing what was removed
- **Step 3** (map) — final mapped periods, account coverage, sub-account matches

Inspect the current implementation to see how Steps 1-3 divide the work.
Place the stats where they logically belong. If all three steps are
currently collapsed into one visible step, show all stats together.

---

## 3. Backend Changes

### 3.1 Surface parsing stats

The backend parsers (`parse_balance_sheets()` and `parse_cash_flows()` in
`metrics_calculator.py`) already do the work but don't return statistics
about what they processed. Add metadata to their return values or to the
step response:

```python
bs_stats = {
    "bpa_records_loaded": ...,
    "bpp_records_loaded": ...,
    "records_after_filter": ...,
    "periods_available": ...,
    "annual_periods": ...,
    "quarterly_periods": ...,
    "fields_mapped": ...,      # count of non-None fields in the model
    "fields_total": 16,        # total possible BS fields
}

cf_stats = {
    "dfc_records_loaded": ...,
    "records_after_filter": ...,
    "periods_available": ...,
    "annual_periods": ...,
    "quarterly_periods": ...,
    "sub_accounts_found": {
        "depreciation_amortization": True/False,
        "capex": True/False,
        "debt_issuance": True/False,
        "debt_repayment": True/False,
        "dividends_paid": True/False,
        "acquisitions": True/False,
        "working_capital_change": True/False,
    },
}
```

Return these stats in the API response for the relevant step(s) so the
frontend can display them.

### 3.2 Existing income statement stats

Check what stats are currently returned for the income statement. Ensure
the same fields exist for consistency. If the income statement stats are
computed in the frontend from the data itself (not returned by the backend),
follow the same approach for BS and CF.

### 3.3 Do NOT change parsing logic

The parsers themselves must not change. Only add instrumentation to count
records and report what was found. This is a read-only addition.

---

## 4. Frontend Changes

### 4.1 Extend step component(s)

Add the BS and CF stats display to the relevant step component(s). Follow
the exact same visual pattern used for income statement stats.

### 4.2 Bilingual

All new labels need EN + PT-BR translations:
- "Balance Sheet" / "Balanço Patrimonial"
- "Cash Flow" / "Fluxo de Caixa"
- "Records loaded" / "Registros carregados"
- "After filter" / "Após filtro"
- "Periods available" / "Períodos disponíveis"
- "Accounts mapped" / "Contas mapeadas"
- "Sub-accounts" / "Subcontas"
- "of _ fields" / "de _ campos"
- Sub-account names in both languages

### 4.3 Handle missing data

If BPA/BPP or DFC files are not found (unlikely for CVM but possible for
future adapters), show "Not available" instead of zeros. Use the same
unavailability message pattern from Step 4 charts.

---

## 5. Testing

- [ ] Steps 1-3 show income statement stats (unchanged from current)
- [ ] Steps 1-3 show balance sheet stats (BPA + BPP record counts, periods, fields mapped)
- [ ] Steps 1-3 show cash flow stats (DFC record counts, periods, sub-account matches)
- [ ] Sub-account checklist shows which were found vs. missing
- [ ] Bilingual labels work (EN and PT-BR)
- [ ] Stats display correctly for Braskem
- [ ] Stats display correctly for Vale
- [ ] Stats display correctly for Votorantim
- [ ] All regression tests still pass
- [ ] Full 9-step pipeline works end-to-end
- [ ] No backend analytical logic changed

---

## 6. Definition of Done

- [ ] Balance sheet file stats visible in Steps 1-3
- [ ] Cash flow file stats visible in Steps 1-3
- [ ] Sub-account match/miss indicators for cash flow
- [ ] Account mapping coverage for balance sheet
- [ ] EN + PT-BR translations for all new labels
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
- [ ] Code committed and pushed
