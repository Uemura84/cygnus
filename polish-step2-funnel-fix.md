# Polish — Step 2 Data Funnel Fix

> **What this is:** Quick fix spec for Claude Code. The data funnel chart starts
> with 6M+ raw rows (all CVM companies), making the post-company-filter bars
> invisible due to scale difference. Fix: start the funnel after company selection.
>
> **Branch:** Continue on current working branch.
> **Scope:** Step 2 frontend + backend stats adjustment only.

---

## 1. Problem

The data funnel shows:
```
Raw Rows:            6,008,989  ████████████████████████
After ORDEM_EXERC:   3,005,548  ████████████
After Company Filter:    8,472  (invisible)
After DFP/ITR Overlap:   7,340  (invisible)
```

The 1000× scale difference between "all CVM companies" and "one company" makes
the last two bars vanish. The interesting filtering story is invisible.

## 2. Fix

**Move the company filter before the funnel.** The funnel should start with
the selected company's data only.

### 2.1 New funnel (4 bars)

```
Braskem Rows (all statements):  8,472  ████████████████████████
After ORDEM_EXERC:              4,236  ████████████
After DFP/ITR Overlap:          3,891  ██████████
Final Dataset:                  3,891  ██████████
```

Or if DFP/ITR overlap doesn't reduce rows significantly, drop to 3 bars:

```
Braskem Rows (all statements):  8,472  ████████████████████████
After ORDEM_EXERC:              4,236  ████████████
After DFP/ITR Overlap:          3,891  ██████████
```

### 2.2 Company selection note

Above the funnel, add a one-line text note explaining the implicit company filter:

```
Selected BRASKEM S.A. from 587 listed companies across 4 statement types (DRE, BPA, BPP, DFC)
```

Style: DM Sans 400, slate, 13px. The company name in DM Sans 500.
The number of listed companies comes from the raw data before company filtering.

### 2.3 First bar label

The first bar should say the company name, not "Raw Rows":

```
BRASKEM S.A.        ████████████████████████  8,472
After ORDEM_EXERC   ████████████              4,236
After DFP/ITR       ██████████                3,891
```

This makes it immediately clear: "we started with this company's data."

## 3. Waterfall Card Update

### 3.1 Remove "Company Filter" card from the waterfall

Since company selection now happens before the funnel, the "Company Filter"
waterfall card (showing 3,005,548 → 8,472, -99.7%) is no longer part of the
sequential filter story. Remove it.

The company selection is shown in the note above the funnel instead.

### 3.2 Final waterfall cards (3 cards)

1. **ORDEM_EXERC Filter** — with before/after counts and per-statement breakdown
2. **DFP / ITR Overlap Resolution** — with before/after counts
3. **YTD-to-Standalone Conversion** — transformation card (no row counts, keep as-is)

## 4. Backend

The backend stats need to return company-filtered counts as the starting point.
Adjust the filter stats to begin counting after company selection:

```python
filter_stats = {
    "company_selected": "BRASKEM S.A.",
    "total_companies_in_source": 587,  # or however many exist
    "company_rows_total": 8472,        # starting point for the funnel
    "ordem_exerc": {
        "before": {"total": 8472, "DRE": ..., "BPA": ..., "BPP": ..., "DFC": ...},
        "after":  {"total": 4236, "DRE": ..., "BPA": ..., "BPP": ..., "DFC": ...},
    },
    "dfp_itr_overlap": {
        "before": {"total": 4236, ...},
        "after":  {"total": 3891, ...},
    },
}
```

## 5. Testing

- [ ] Funnel starts with company-specific rows (not millions)
- [ ] All bars are visually proportional and readable
- [ ] Company selection note shows above the funnel
- [ ] "Company Filter" waterfall card removed
- [ ] Remaining waterfall cards: ORDEM_EXERC, DFP/ITR Overlap, YTD Conversion
- [ ] Per-statement breakdown still visible on remaining cards
- [ ] Displays correctly for Braskem, Vale, Votorantim
- [ ] All regressions pass
