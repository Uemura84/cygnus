# Polish — Step 2 Fixes

> **What this is:** Focused fix spec for Claude Code. Addresses specific issues
> in the Step 2 Data Quality Filters display identified during visual review.
>
> **Branch:** Continue on `polish-data-transparency` (or current working branch).
>
> **Scope:** Step 2 frontend + backend instrumentation only. No analytical changes.

---

## 1. Show Filtering for All Statement Types (Not Just DRE)

### 1.1 Problem

The data funnel and filter waterfall only show DRE (income statement) row counts.
The system also filters BPA, BPP, and DFC files through the same quality pipeline
(ORDEM_EXERC, company filter, DFP/ITR overlap). Step 2 should show the full picture.

### 1.2 Fix

Update the funnel and waterfall to show aggregate counts across all statement types,
with a breakdown by statement type.

**Data funnel:** Show total rows across all statements (DRE + BPA + BPP + DFC) at
each filter stage. The funnel should visualize the overall data reduction.

**Filter waterfall cards:** Each card shows:
- Aggregate before/after counts (all statement types combined)
- A small breakdown row showing per-statement counts:

```
ORDEM_EXERC Filter
Keeps only the most recent exercise (ÚLTIMO) per filing
Removes prior-year restated comparison rows

BEFORE → AFTER                                    -50.0%
10,088    5,044

  DRE: 3,142 → 1,571  |  BPA: 2,856 → 1,428  |  BPP: 2,214 → 1,107  |  DFC: 1,876 → 938
```

The per-statement breakdown can be a single line in JetBrains Mono at smaller
size (11px), slate color. It provides detail without cluttering the card.

### 1.3 Backend

The filtering functions need to return per-statement-type counts at each stage.
Update the filter stats structure:

```python
filter_stats = {
    "ordem_exerc": {
        "before": {"total": 10088, "DRE": 3142, "BPA": 2856, "BPP": 2214, "DFC": 1876},
        "after":  {"total": 5044,  "DRE": 1571, "BPA": 1428, "BPP": 1107, "DFC": 938},
    },
    "company_filter": {
        "before": {"total": ..., "DRE": ..., "BPA": ..., "BPP": ..., "DFC": ...},
        "after":  {"total": ..., "DRE": ..., "BPA": ..., "BPP": ..., "DFC": ...},
    },
    # ...
}
```

---

## 2. Remove "DRE Account Filter" Card

### 2.1 Problem

The "DRE Account Filter" card shows 3,142 → 3,142 (-0.0%). It removes nothing
because the data is already filtered to DRE accounts before this point. Showing
a no-op filter is confusing.

### 2.2 Fix

Remove the "DRE Account Filter" card from the waterfall entirely. If this filter
is applied during parsing (selecting CD_CONTA codes starting with '3.' for income
statement), it's an internal implementation detail, not a data quality step the
user needs to see.

The remaining waterfall cards should be:
1. ORDEM_EXERC Filter
2. Company Filter
3. DFP / ITR Overlap Resolution
4. YTD-to-Standalone Conversion

Also remove the corresponding bar from the data funnel chart ("After DRE Filter").

---

## 3. Remove "Holding Company Exclusion" Card

### 3.1 Problem

The "Holding Company Exclusion" card shows -0.0% for Braskem (no holding entity
exists). For companies that do have holdings to exclude (like Gerdau), this filter
is meaningful — but it's handled internally and doesn't need user-facing visibility.

### 3.2 Fix

Remove the "Holding Company Exclusion" card from the waterfall. Also remove the
corresponding bar from the data funnel chart.

The final waterfall cards should be:
1. ORDEM_EXERC Filter
2. Company Filter
3. DFP / ITR Overlap Resolution
4. YTD-to-Standalone Conversion

---

## 4. Align Funnel Labels with Waterfall Card Names

### 4.1 Problem

The data funnel chart uses different labels than the waterfall cards:
- Funnel: "After DRE Filter" vs. Card: "DRE Account Filter"
- Funnel: "After Year-End Filter" vs. Card: "ORDEM_EXERC Filter"
- Funnel: "After Holding Exclusion" vs. Card: "Holding Company Exclusion"

### 4.2 Fix

After removing the DRE and Holding filters, the funnel bars should be:

```
Raw Rows                    ████████████████████████  10,088
After ORDEM_EXERC           ████████████             5,044
After Company Filter        ██████                   1,847
After DFP/ITR Overlap       █████                    1,623
```

Labels match the waterfall card names exactly. The YTD conversion doesn't appear
in the funnel (it's a transformation, not a row-reducing filter).

---

## 5. Update Step 2 Description Text

### 5.1 Problem

The current description says: "Applies sequential filters to the raw CVM data:
selects income statement accounts (DRE), removes prior-year restated rows, and
excludes holding entities."

This is outdated — it only mentions DRE and references the two filters we're removing.

### 5.2 Fix

Update to: "Applies sequential filters to the raw CVM data across all financial
statements (DRE, BPA, BPP, DFC): removes prior-year restated rows, filters to the
selected company, resolves filing overlaps, and converts quarterly figures to
standalone periods."

PT-BR: "Aplica filtros sequenciais aos dados brutos da CVM em todas as demonstrações
financeiras (DRE, BPA, BPP, DFC): remove linhas reapresentadas de exercícios
anteriores, filtra pela empresa selecionada, resolve sobreposições de arquivos e
converte valores trimestrais para períodos standalone."

---

## 6. Summary of Changes

| Item | Action |
|------|--------|
| DRE Account Filter card | Remove |
| Holding Company Exclusion card | Remove |
| Data funnel bars for removed filters | Remove |
| Remaining funnel bar labels | Align with waterfall card names |
| Filter stats | Show all statement types (DRE + BPA + BPP + DFC), not just DRE |
| Waterfall cards | Show per-statement breakdown line under the aggregate counts |
| Step 2 description text | Update to mention all statement types |
| Funnel chart | Show aggregate totals across all statements |

---

## 7. i18n Updates

Update both EN and PT-BR:

- Remove i18n keys for "DRE Account Filter" and "Holding Company Exclusion"
- Update Step 2 description text (both languages, see Section 5.2)
- Add per-statement breakdown label if needed

---

## 8. Testing

- [ ] "DRE Account Filter" card removed from waterfall
- [ ] "Holding Company Exclusion" card removed from waterfall
- [ ] Data funnel shows 4 bars: Raw → ORDEM_EXERC → Company → DFP/ITR Overlap
- [ ] Funnel bar labels match waterfall card names
- [ ] Waterfall cards show aggregate counts across all statement types
- [ ] Waterfall cards show per-statement breakdown (DRE/BPA/BPP/DFC)
- [ ] YTD card unchanged (already correct)
- [ ] Step 2 description updated
- [ ] Displays correctly for Braskem
- [ ] Displays correctly for Vale
- [ ] Displays correctly for Votorantim
- [ ] All regression tests still pass
- [ ] EN + PT-BR labels updated

---

## 9. Definition of Done

- [ ] Two filter cards removed (DRE Account, Holding Company)
- [ ] Funnel updated (4 bars, aligned labels)
- [ ] All filters show counts across all statement types
- [ ] Per-statement breakdown visible on waterfall cards
- [ ] Description text updated (both languages)
- [ ] All 3 test companies display correctly
- [ ] All regressions pass
