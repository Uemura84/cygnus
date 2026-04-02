"""Materiality layer — converts percentage-point findings into BRL estimates.

Uses absolute revenue and COGS figures from the metrics pipeline to translate
relative findings (pp shifts, compression rates) into order-of-magnitude
economic impact estimates.

Public API
----------
estimate_impact(findings, metrics_df, language) -> list
    Adds estimated_impact dict to each finding in-place. Returns the same list.
"""

import pandas as pd


def estimate_impact(findings: list, metrics_df: pd.DataFrame, language: str = "pt") -> list:
    """Add estimated_impact to each finding based on absolute financials.

    Args:
        findings: List of findings from detect_patterns (Step 6 output).
        metrics_df: The annual metrics DataFrame from Step 4, must include
                    columns: period, revenue_abs, cogs_abs (absolute values).
        language: "en" or "pt-br" — controls bi/bn and mi/mn formatting.

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
        for f in findings:
            f["estimated_impact"] = None
        return findings

    if "revenue_abs" not in metrics_df.columns or "cogs_abs" not in metrics_df.columns:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    # Get the most recent annual revenue and COGS (absolute values)
    metrics_sorted = metrics_df.sort_values("period", ascending=False)
    latest = metrics_sorted.iloc[0] if len(metrics_sorted) > 0 else None

    if latest is None:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    latest_revenue = abs(float(latest.get("revenue_abs", 0) or 0))

    if latest_revenue == 0:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    lang = "en" if language == "en" else "pt"

    for f in findings:
        pattern = f.get("pattern", "")
        impact = None

        if pattern == "Cost composition drift":
            shift_pp = abs(f.get("shift_pp", 0) or 0)
            if shift_pp > 0:
                value = (shift_pp / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{shift_pp:.1f}pp COGS drift × current annual revenue",
                    "caveat": "Order of magnitude estimate — does not isolate volume, mix, or price effects",
                }

        elif pattern == "Margin compression":
            annual_pp = abs(f.get("annual_change_pp", 0) or 0)
            if annual_pp > 0:
                value = (annual_pp / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{annual_pp:.1f}pp/year compression × current annual revenue",
                    "caveat": "Annual run-rate estimate — actual impact depends on revenue trajectory",
                }

        elif pattern == "Revenue-cost decoupling":
            divergence = f.get("divergence_pp", 0) or 0
            if divergence > 0:  # COGS outpaced revenue (margin pressure)
                value = (divergence / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{divergence:.1f}pp cost-revenue divergence × annual revenue",
                    "caveat": "Single-period estimate — may include one-time items",
                }

        elif pattern == "Peer divergence":
            gap_pp = abs(f.get("gap_pp", 0) or 0)
            if gap_pp > 0:
                # Conservative: assume half the gap is closable
                value = (gap_pp / 2 / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"Half of {gap_pp:.1f}pp peer gap × current annual revenue",
                    "caveat": "Assumes half the peer gap is closable — different business models may explain part of the gap",
                }

        elif pattern == "YoY quarter comparison":
            yoy_pp = abs(f.get("yoy_change_pp", 0) or 0)
            if yoy_pp > 0:
                quarterly_revenue = latest_revenue / 4
                value = (yoy_pp / 100) * quarterly_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{yoy_pp:.1f}pp YoY change × estimated quarterly revenue",
                    "caveat": "Quarterly estimate — annualize with caution",
                }

        # Statistical anomaly and High margin volatility are not quantifiable in BRL

        f["estimated_impact"] = impact

    return findings


def _format_brl(value: float, language: str = "pt") -> str:
    """Format a BRL value into human-readable string.

    Examples (pt):  1_500_000_000 → "~R$ 1.5 bi",  350_000_000 → "~R$ 350 mi"
    Examples (en):  1_500_000_000 → "~R$ 1.5 bn",  350_000_000 → "~R$ 350 mn"
    """
    abs_val = abs(value)
    if language == "en":
        if abs_val >= 1_000_000_000:
            return f"~R$ {abs_val / 1_000_000_000:.1f} bn"
        elif abs_val >= 1_000_000:
            return f"~R$ {abs_val / 1_000_000:.0f} mn"
        elif abs_val >= 1_000:
            return f"~R$ {abs_val / 1_000:.0f} k"
        else:
            return f"~R$ {abs_val:.0f}"
    else:
        if abs_val >= 1_000_000_000:
            return f"~R$ {abs_val / 1_000_000_000:.1f} bi"
        elif abs_val >= 1_000_000:
            return f"~R$ {abs_val / 1_000_000:.0f} mi"
        elif abs_val >= 1_000:
            return f"~R$ {abs_val / 1_000:.0f} mil"
        else:
            return f"~R$ {abs_val:.0f}"
