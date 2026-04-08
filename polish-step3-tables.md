# Polish — Step 3 Balance Sheet & Cash Flow Summary Tables + Fixes

> **What this is:** Build spec for Claude Code. Adds balance sheet and cash flow
> summary value tables to Step 3 (matching the existing income statement table),
> fixes the account mapping coverage inconsistency, and renames Step 4.
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 3 frontend + Step 4 sidebar name. No analytical changes.

---

## 0. Remove Dedup Summary Cards from Step 3

### 0.1 Problem

Step 3 displays four summary cards at the top: "Before Dedup: 1,571",
"After Dedup: 1,043", "Duplicates Removed: 528", "YTD Conversions: 18".

This deduplication (DFP/ITR overlap resolution) is a data quality filter — it
already happens and is displayed in Step 2 (the "DFP / ITR Overlap Resolution"
waterfall card). Showing it again in Step 3 is redundant and confusing: Step 3's
role is mapping, not filtering.

### 0.2 Fix

Remove the four dedup/YTD summary cards from the top of Step 3 entirely.

Replace with a simple summary of what Step 3 receives as input and what it produces:

```
INPUT                              OUTPUT
1,043 filtered records             3 mapped financial statements
across 4 file types                275 annual + 768 quarterly periods
(DRE, BPA, BPP, DFC)              
```

Or simply let the three "Data Sources" cards (DRE, BPA+BPP, DFC) serve as the
step summary — they already show the record counts and period breakdowns. In that
case, just remove the dedup cards and keep the "Data Sources" section as the
first thing the user sees.

### 0.3 What stays

- The "Data Sources" cards (DRE, BPA+BPP, DFC) — keep
- The "Deduplication Rules" table — keep (it explains the rules, which is useful
  for transparency even though the filtering happened in Step 2)
- The income statement values table — keep
- The mapping tables (BS, CF) — keep
- Everything being added in this spec (BS/CF summary tables) — add as specified

---

## 1. Add Balance Sheet Summary Table

### 1.1 What exists

Step 3 shows the balance sheet mapping status (field → CVM code → ✓ mapped / — not found)
but does NOT show the actual values. The income statement has a full table with
values per year. The balance sheet should have the same.

### 1.2 Add summary table

Below the balance sheet mapping table, add a values table showing annual data:

```
BALANCE SHEET (ANNUAL, BRL THOUSANDS)

ACCOUNT                      2021            2022            2023            2024            2025
────────────────────────────────────────────────────────────────────────────────────────────────
Current Assets          25,432,000      28,190,000      19,876,000      22,341,000      20,115,000
  Cash & Equivalents     5,612,000       4,890,000       3,210,000       4,567,000       3,890,000
  Accounts Receivable    6,234,000       7,123,000       5,432,000       5,890,000       5,234,000
  Inventories            8,901,000       9,456,000       7,123,000       7,654,000       7,012,000
Non-Current Assets      52,345,000      54,123,000      48,901,000      50,234,000      49,876,000
  PP&E                  38,901,000      39,456,000      35,678,000      36,234,000      35,890,000
  Intangible Assets      6,789,000       6,543,000       6,123,000       5,890,000       5,678,000
Total Assets            77,777,000      82,313,000      68,777,000      72,575,000      69,991,000
────────────────────────────────────────────────────────────────────────────────────────────────
Current Liabilities     18,901,000      21,345,000      16,789,000      17,890,000      16,543,000
  Accounts Payable       4,567,000       5,234,000       3,890,000       4,123,000       3,876,000
  Short-term Debt        8,901,000       9,876,000       7,654,000       8,123,000       7,543,000
Non-Current Liabilities 45,678,000      48,901,000      42,345,000      43,567,000      42,890,000
  Long-term Debt        38,901,000      41,234,000      35,678,000      36,890,000      36,123,000
Total Liabilities       64,579,000      70,246,000      59,134,000      61,457,000      59,433,000
────────────────────────────────────────────────────────────────────────────────────────────────
Total Equity            13,198,000      12,067,000       9,643,000      11,118,000      10,558,000
  Retained Earnings            —               —               —               —               —
```

**Structure:**
- Same visual pattern as the income statement table (Image 2 from review)
- Subtotal rows (Total Assets, Total Liabilities, Total Equity) in bold (DM Sans 500)
- Detail rows indented with 2 spaces
- Separator lines between Assets / Liabilities / Equity sections
- Fields that are None show "—" (em dash)
- Numbers in JetBrains Mono, right-aligned
- Account names in DM Sans 400
- Annual data only (not quarterly — too many columns)

### 1.3 Data source

The balance sheet values are already available on the `BalanceSheet` dataclass
objects. The backend should return the annual balance sheet values in the Step 3
response (or the frontend can extract them from the Step 4 balance_sheet_series
if already available).

---

## 2. Add Cash Flow Summary Table

### 2.1 Add summary table

Below the cash flow mapping and sub-account sections, add a values table:

```
CASH FLOW (ANNUAL, BRL THOUSANDS)

ACCOUNT                      2021            2022            2023            2024            2025
────────────────────────────────────────────────────────────────────────────────────────────────
Operating Cash Flow     12,345,000       8,901,000       5,678,000       7,234,000       6,543,000
  D&A                    4,567,000       4,890,000       4,234,000       4,123,000       3,987,000
Investing Cash Flow     -6,789,000      -5,432,000      -3,456,000      -4,123,000      -3,876,000
  Capex                 -5,678,000      -4,567,000      -2,890,000      -3,456,000      -3,234,000
  Acquisitions            -890,000        -654,000        -432,000        -543,000        -521,000
Financing Cash Flow     -4,321,000      -2,890,000       1,234,000      -2,345,000      -1,987,000
  Debt Issuance          8,901,000       6,543,000       9,876,000       7,654,000       6,890,000
  Debt Repayment        -9,876,000      -7,654,000      -6,543,000      -7,890,000      -6,789,000
  Dividends Paid        -2,345,000      -1,234,000        -890,000        -987,000        -876,000
────────────────────────────────────────────────────────────────────────────────────────────────
Free Cash Flow           5,556,000       3,469,000       2,222,000       3,111,000       2,667,000
```

**Structure:**
- Same pattern as income statement and balance sheet tables
- Top-level flows (Operating, Investing, Financing) in bold
- Sub-accounts indented
- Free Cash Flow as a derived subtotal at the bottom (bold)
- Negative values shown with minus sign (cash outflows)
- Fields that are None show "—"
- Annual data only

---

## 3. Fix Account Mapping Coverage Inconsistency

### 3.1 Problem

The balance sheet data source card (Image 1) shows "14 / 14" accounts mapped,
but the mapping table (Image 3) shows "retained_earnings: — not found" and
"total_liabilities: ✓ computed (derived)". If retained_earnings wasn't found,
the coverage count is wrong.

### 3.2 Fix

The coverage count should reflect the actual mapping table:
- Count "✓ mapped" and "✓ computed" as mapped
- Count "— not found" as not mapped
- Display: "15 of 16 fields mapped" (or whatever the correct numbers are)

Ensure the data source card count and the mapping table are computed from the
same source of truth. The mapping stats returned by the backend should drive both.

---

## 4. Rename Step 4

### 4.1 Problem

Step 4 is called "EBITDA Drivers" in the sidebar. It now shows balance sheet
metrics (liquidity, leverage, working capital) and cash flow metrics (FCF,
capex ratios, earnings quality) alongside profitability. The name is too narrow.

### 4.2 Fix

Rename to "Financial Metrics" in the sidebar, step header, and i18n files.

PT-BR: "Métricas Financeiras"

---

## 5. i18n

### New labels (EN / PT-BR)

**Balance Sheet table:**
- "Balance Sheet (Annual, BRL Thousands)" / "Balanço Patrimonial (Anual, BRL Milhares)"
- "Current Assets" / "Ativo Circulante"
- "Cash & Equivalents" / "Caixa e Equivalentes"
- "Accounts Receivable" / "Contas a Receber"
- "Inventories" / "Estoques"
- "Non-Current Assets" / "Ativo Não Circulante"
- "PP&E" / "Imobilizado"
- "Intangible Assets" / "Intangível"
- "Total Assets" / "Ativo Total"
- "Current Liabilities" / "Passivo Circulante"
- "Accounts Payable" / "Fornecedores"
- "Short-term Debt" / "Empréstimos CP"
- "Non-Current Liabilities" / "Passivo Não Circulante"
- "Long-term Debt" / "Empréstimos LP"
- "Total Liabilities" / "Passivo Total"
- "Total Equity" / "Patrimônio Líquido"
- "Retained Earnings" / "Lucros Acumulados"

**Cash Flow table:**
- "Cash Flow (Annual, BRL Thousands)" / "Fluxo de Caixa (Anual, BRL Milhares)"
- "Operating Cash Flow" / "Fluxo de Caixa Operacional"
- "D&A" / "Depreciação e Amortização"
- "Investing Cash Flow" / "Fluxo de Caixa de Investimento"
- "Capex" / "Investimentos (Capex)"
- "Acquisitions" / "Aquisições"
- "Financing Cash Flow" / "Fluxo de Caixa de Financiamento"
- "Debt Issuance" / "Captação de Empréstimos"
- "Debt Repayment" / "Pagamento de Empréstimos"
- "Dividends Paid" / "Dividendos Pagos"
- "Free Cash Flow" / "Fluxo de Caixa Livre"

**Step 4 rename:**
- "Financial Metrics" / "Métricas Financeiras"

---

## 6. Testing

- [ ] Dedup summary cards (Before Dedup, After Dedup, Duplicates Removed, YTD Conversions) removed from Step 3
- [ ] Data Sources cards still visible as the first section
- [ ] Deduplication Rules table still visible (explains the rules)
- [ ] Balance sheet summary table renders with annual values for Braskem
- [ ] Balance sheet table shows proper indentation (detail under subtotals)
- [ ] Balance sheet table shows "—" for None fields (e.g., retained_earnings)
- [ ] Cash flow summary table renders with annual values for Braskem
- [ ] Cash flow table shows negative values for outflows
- [ ] Free Cash Flow derived row appears at bottom
- [ ] Account mapping coverage count matches the mapping table exactly
- [ ] Step 4 renamed to "Financial Metrics" in sidebar and header
- [ ] All tables render correctly for Vale
- [ ] All tables render correctly for Votorantim
- [ ] Bilingual labels work (EN + PT-BR)
- [ ] All regression tests pass
- [ ] No analytical logic changed

---

## 7. Definition of Done

- [ ] Dedup summary cards removed from Step 3 top section
- [ ] Balance sheet summary value table added to Step 3
- [ ] Cash flow summary value table added to Step 3
- [ ] Mapping coverage count fixed (consistent with mapping table)
- [ ] Step 4 renamed to "Financial Metrics"
- [ ] All labels bilingual
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
