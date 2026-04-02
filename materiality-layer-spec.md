# Materiality Layer — Economic Impact Estimation — Claude Code Spec

> **What this is:** Instructions for adding estimated economic impact (in BRL) to each
> finding in Step 6. This converts pattern detection findings from percentage-point
> observations into quantified value leakage estimates that CFOs understand.
>
> **Scope:** Backend computation in Step 6 + frontend display on finding cards.
> Do NOT change detection algorithms, thresholds, or DQ classification.
> Do NOT change Steps 1-5 or Steps 7-9.
>
> **Branch:** Build this on a separate feature branch.

---

## Why This Matters

Current findings say: "COGS ratio deteriorated 15.7pp"
With materiality layer: "COGS ratio deteriorated 15.7pp — estimated ~R$ X.X bi annual margin pressure"

CFOs think in money, not percentage points. This moves the tool from pattern
detection to quantified value leakage estimation.

---

## Backend Changes

### File: `backend/pipeline/materiality.py` (NEW)

```python
"""Materiality layer — converts percentage-point findings into BRL estimates.

Uses absolute revenue and COGS figures from the metrics pipeline to translate
relative findings (pp shifts, compression rates) into order-of-magnitude
economic impact estimates.

Public API
----------
estimate_impact(findings, metrics_df) -> list
    Adds estimated_impact dict to each finding in-place. Returns the same list.
"""

import pandas as pd


def estimate_impact(findings: list, metrics_df: pd.DataFrame) -> list:
    """Add estimated_impact to each finding based on absolute financials.

    Args:
        findings: List of findings from detect_patterns (Step 6 output).
        metrics_df: The annual metrics DataFrame from Step 4, must include
                    columns: DT_REFER, revenue_abs, cogs_abs (absolute values).

    Each finding gets an estimated_impact dict:
    {
        "value_brl": float,          # estimated impact in BRL
        "formatted": "~R$ 9.4 bi",   # human-readable string
        "basis": str,                 # what the estimate is based on
        "caveat": str,                # why it's approximate
    }

    Findings that can't be quantified get estimated_impact = None.
    """
    if metrics_df is None or metrics_df.empty:
        return findings

    # Get the most recent annual revenue and COGS (absolute values)
    metrics_sorted = metrics_df.sort_values("DT_REFER", ascending=False)
    latest = metrics_sorted.iloc[0] if len(metrics_sorted) > 0 else None

    if latest is None:
        return findings

    latest_revenue = abs(latest.get("revenue_abs", 0))
    latest_cogs = abs(latest.get("cogs_abs", 0))

    # Also get historical baseline (first period) for drift calculations
    earliest = metrics_sorted.iloc[-1] if len(metrics_sorted) > 1 else latest
    baseline_revenue = abs(earliest.get("revenue_abs", 0))

    if latest_revenue == 0:
        return findings

    for f in findings:
        pattern = f.get("pattern", "")
        impact = None

        if pattern == "Cost composition drift":
            # shift_pp × current revenue = margin pressure
            shift_pp = abs(f.get("shift_pp", 0) or 0)
            if shift_pp > 0:
                value = (shift_pp / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value),
                    "basis": f"{shift_pp:.1f}pp COGS drift × current annual revenue",
                    "caveat": "Order of magnitude estimate — does not isolate volume, mix, or price effects",
                }

        elif pattern == "Margin compression":
            # annual_change_pp × current revenue = annual margin erosion rate
            annual_pp = abs(f.get("annual_change_pp", 0) or 0)
            if annual_pp > 0:
                value = (annual_pp / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value),
                    "basis": f"{annual_pp:.1f}pp/year compression × current annual revenue",
                    "caveat": "Annual run-rate estimate — actual impact depends on revenue trajectory",
                }

        elif pattern == "Revenue-cost decoupling":
            # For negative divergence (COGS grew faster than revenue):
            # divergence_pp × revenue at time = excess cost in that period
            divergence = f.get("divergence_pp", 0) or 0
            if divergence > 0:  # COGS outpaced revenue
                # Use the period's revenue if available, otherwise latest
                value = (divergence / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value),
                    "basis": f"{divergence:.1f}pp cost-revenue divergence × annual revenue",
                    "caveat": "Single-period estimate — may include one-time items",
                }

        elif pattern == "Peer divergence":
            # gap_pp × current revenue = improvement potential if gap were closed
            gap_pp = abs(f.get("gap_pp", 0) or 0)
            if gap_pp > 0:
                # Estimate if HALF the gap were closed (conservative)
                value = (gap_pp / 2 / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value),
                    "basis": f"Half of {gap_pp:.1f}pp peer gap × current annual revenue",
                    "caveat": "Assumes half the peer gap is closable — different business models may explain part of the gap",
                }

        elif pattern == "YoY quarter comparison":
            # yoy_change_pp × quarterly revenue = quarterly impact
            yoy_pp = abs(f.get("yoy_change_pp", 0) or 0)
            if yoy_pp > 0:
                quarterly_revenue = latest_revenue / 4  # approximate
                value = (yoy_pp / 100) * quarterly_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value),
                    "basis": f"{yoy_pp:.1f}pp YoY change × estimated quarterly revenue",
                    "caveat": "Quarterly estimate — annualize with caution",
                }

        # Statistical anomaly and High margin volatility are not easily
        # quantifiable in BRL terms — leave as None

        f["estimated_impact"] = impact

    return findings


def _format_brl(value: float) -> str:
    """Format a BRL value into human-readable string.

    Examples:
        1_500_000_000 → "~R$ 1.5 bi"
        350_000_000   → "~R$ 350 mi"
        45_000_000    → "~R$ 45 mi"
        2_300_000     → "~R$ 2.3 mi"
    """
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"~R$ {abs_val / 1_000_000_000:.1f} bi"
    elif abs_val >= 1_000_000:
        return f"~R$ {abs_val / 1_000_000:.0f} mi"
    elif abs_val >= 1_000:
        return f"~R$ {abs_val / 1_000:.0f} mil"
    else:
        return f"~R$ {abs_val:.0f}"
```

### File: `backend/steps/step6_core_analysis.py` — Integration

After `detect_patterns()` and `enrich()` are called, add the materiality estimation:

```python
from pipeline.materiality import estimate_impact

# ... existing Step 6 logic ...

# After findings are produced:
# Get absolute revenue/COGS from Step 4 metrics
step4_data = pipeline_state.get("step4", {}).get("data", {})
time_series = step4_data.get("time_series", [])

# Build a simple df with absolute values for the materiality layer
if time_series:
    metrics_df = pd.DataFrame(time_series)
else:
    metrics_df = pd.DataFrame()

# Add materiality estimates
findings = estimate_impact(findings, metrics_df)
```

**IMPORTANT:** This requires that `time_series` from Step 4 includes absolute
revenue and COGS values, not just percentages. Check if `revenue_abs` and `cogs_abs`
are already in the Step 4 output. If not, add them to `metrics_calculator.py`:

```python
# In compute_metrics(), for each annual period, include:
{
    "period": "2025-12-31",
    "revenue_abs": 59_000_000_000,   # absolute revenue in BRL
    "cogs_abs": 57_700_000_000,      # absolute COGS in BRL (positive)
    "Gross_Margin_pct": 2.2,
    "EBIT_Margin_pct": -2.6,
    "COGS_pct_Revenue": 97.8,
    # ... other existing fields
}
```

The absolute values should come from the DRE data that's already in the pipeline —
specifically account 3.01 (revenue) and 3.02 (COGS). The raw values are in the
pivot table from Step 3. Step 4 just needs to carry them forward.

### File: `backend/pipeline/metrics_calculator.py` — Add absolute values

In `compute_metrics()`, ensure the time_series output includes:

```python
record["revenue_abs"] = float(row.get("Receita de Venda de Bens e/ou Serviços", 0))
record["cogs_abs"] = abs(float(row.get("Custo dos Bens e/ou Serviços Vendidos", 0)))
```

These are the raw BRL values from the DRE, before any ratio computation.

---

## Frontend Changes

### File: `frontend/src/steps/Step6CoreAnalysis.jsx` — Finding card enhancement

For each finding card that has `estimated_impact`, display the estimate prominently.

**Layout within each finding card:**

```
┌─────────────────────────────────────────────────────────────┐
│ F003  Cost composition drift   HIGH   Confidence: HIGH      │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  📊 Estimated Impact: ~R$ 9.4 bi annual margin pressure │ │
│ │  Basis: 15.7pp COGS drift × current annual revenue      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ BRASKEM S.A.: COGS burden shifted from 79.6% to 95.3%...   │
│                                                             │
│ First Half Avg: 79.6  Second Half Avg: 95.3  Shift Pp: 15.7│
│ ▼ Show chart                                                │
└─────────────────────────────────────────────────────────────┘
```

**Styling:**
- The impact estimate sits in a highlighted box (light yellow or light orange background)
  inside the finding card, positioned between the finding header and the description
- The `formatted` value is large and bold (e.g., "~R$ 9.4 bi")
- The `basis` is shown in smaller muted text below
- The `caveat` is shown on hover as a tooltip (not inline — it would clutter the card)
- If `estimated_impact` is null, don't render the impact box (some findings like
  statistical anomalies can't be quantified)

**For findings WITHOUT estimated_impact** (statistical anomalies, high volatility):
No impact box shown. The finding card renders as before.

### i18n keys

**English:**
```json
{
  "materiality": {
    "estimated_impact": "Estimated Impact",
    "basis": "Basis",
    "caveat_tooltip": "This is an order-of-magnitude estimate",
    "annual_margin_pressure": "annual margin pressure",
    "annual_margin_erosion": "annual margin erosion rate",
    "cost_revenue_divergence": "cost-revenue divergence impact",
    "improvement_potential": "improvement potential (half gap)",
    "quarterly_impact": "quarterly margin impact"
  }
}
```

**Portuguese:**
```json
{
  "materiality": {
    "estimated_impact": "Impacto Estimado",
    "basis": "Base de Cálculo",
    "caveat_tooltip": "Estimativa de ordem de grandeza",
    "annual_margin_pressure": "pressão anual na margem",
    "annual_margin_erosion": "taxa anual de erosão de margem",
    "cost_revenue_divergence": "impacto da divergência custo-receita",
    "improvement_potential": "potencial de melhoria (metade do gap)",
    "quarterly_impact": "impacto trimestral na margem"
  }
}
```

---

## How the BRL Formatting Works for i18n

The `_format_brl()` function uses Portuguese conventions (bi/mi) which work in
both languages for a Brazilian context. However, for English display you may want
to use "bn/mn":

```python
def _format_brl(value: float, language: str = "pt") -> str:
    abs_val = abs(value)
    if language == "en":
        if abs_val >= 1_000_000_000:
            return f"~R$ {abs_val / 1_000_000_000:.1f} bn"
        elif abs_val >= 1_000_000:
            return f"~R$ {abs_val / 1_000_000:.0f} mn"
    else:
        if abs_val >= 1_000_000_000:
            return f"~R$ {abs_val / 1_000_000_000:.1f} bi"
        elif abs_val >= 1_000_000:
            return f"~R$ {abs_val / 1_000_000:.0f} mi"
    # ... rest of function
```

The language should come from `config.language`. Pass it through to `estimate_impact()`.

---

## Cache Impact

Step 4 cache (`cache/{company}/step4.json`) will now include `revenue_abs` and
`cogs_abs` in the time_series. Delete existing Step 4+ cache files to force
regeneration after this change.

Step 6 cache will now include `estimated_impact` in each finding. Delete existing
Step 6 cache files.

---

## Testing

Verify with Braskem data:

- F003 (Cost composition drift, +15.7pp): should produce ~R$ 9-10 bi estimate
  (15.7% × ~R$60bi revenue)
- F001 (Margin compression, -4.6pp/year): should produce ~R$ 2-3 bi annual estimate
- F005 (Revenue-cost decoupling, 24.4pp divergence, COGS > revenue): should produce
  a large estimate
- F004 (Revenue-cost decoupling, -25.0pp divergence, revenue > COGS): this is positive
  divergence (margin expansion), so estimated_impact should be None (we only quantify
  negative outcomes)
- F006/F007 (Statistical anomalies): estimated_impact should be None

Verify the formatted strings use "bi" for billions and "mi" for millions.
Verify the tooltip shows the caveat text on hover.

---

## Files to CREATE

- `backend/pipeline/materiality.py`

## Files to MODIFY

- `backend/pipeline/metrics_calculator.py` — add `revenue_abs` and `cogs_abs` to time_series
- `backend/steps/step6_core_analysis.py` — call `estimate_impact()` after pattern detection
- `frontend/src/steps/Step6CoreAnalysis.jsx` — render estimated impact on finding cards
- `frontend/src/i18n/en.json` — add materiality keys
- `frontend/src/i18n/pt-br.json` — add materiality keys

## Files NOT to MODIFY

- `backend/pipeline/pattern_detector.py` — no changes to detection logic
- `backend/pipeline/enrichment.py` — no changes
- Steps 7, 8, 9 — no changes (but the AI agent will see the impact estimates
  in the findings it receives, which enriches its analysis)

---

## Verification Checklist

- [ ] Step 4 time_series includes revenue_abs and cogs_abs (absolute BRL values)
- [ ] Step 6 findings include estimated_impact for quantifiable patterns
- [ ] Step 6 findings have estimated_impact = null for statistical anomalies
- [ ] BRL formatting works correctly (bi for billions, mi for millions)
- [ ] Impact box renders on finding cards with highlighted styling
- [ ] Caveat shows on hover tooltip
- [ ] Revenue-cost decoupling with positive divergence (margin expansion) has no impact estimate
- [ ] Language toggle switches between bi/bn and mi/mn formatting
- [ ] Existing Step 4 and Step 6 cache cleared and regenerated
- [ ] All i18n keys present in both EN and PT-BR
