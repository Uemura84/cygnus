"""Band overrides — §2.5 of the distress scoring spec v1.5.

O1: G01+G02 → Distress minimum (score ≥80, band re-mapped).
O2: G01+FCF<0+CR<1.0 → High Risk minimum (score ≥60).
Six bands with Distress/Severe Distress split at 90.
"""

from __future__ import annotations
from typing import Any

from pipeline.distress.gating_facts import has_gating

BAND_THRESHOLDS = [
    (0,  20,  "Healthy"),
    (20, 40,  "Stable"),
    (40, 60,  "Watchlist"),
    (60, 80,  "High Risk"),
    (80, 90,  "Distress"),
    (90, 101, "Severe Distress"),
]

BAND_DESCRIPTIONS = {
    "Healthy":          "No action",
    "Stable":           "Monitor routinely",
    "Watchlist":        "Quarterly review, investigate drivers",
    "High Risk":        "Board-level attention, scenario planning",
    "Distress":         "Immediate action required — restructuring candidate",
    "Severe Distress":  "Acute crisis — existential refinancing / solvency window",
}


def map_to_band(score: int) -> str:
    for low, high, name in BAND_THRESHOLDS:
        if low <= score < high:
            return name
    return "Severe Distress"


def apply_overrides(
    score: int,
    band: str,
    gating_findings: list[dict],
    fundamentals_inputs: dict[str, Any],
) -> dict:
    pre_score = score
    pre_band = band
    applied: str | None = None
    secondary: list[str] = []

    g01 = has_gating(gating_findings, "G01")
    g02 = has_gating(gating_findings, "G02")
    fcf_neg = fundamentals_inputs.get("free_cash_flow_brl_b_latest", 0) < 0
    cr_low = fundamentals_inputs.get("current_ratio", 999) < 1.0

    o1 = g01 and g02
    o2 = g01 and fcf_neg and cr_low

    if o1:
        score = max(score, 80)
        band = map_to_band(score)
        applied = "O1_insolvency_plus_going_concern"
        if o2:
            secondary.append("O2_insolvency_plus_cash_burn_plus_illiquidity")
    elif o2 and band in ("Healthy", "Stable", "Watchlist"):
        score = max(score, 60)
        band = "High Risk"
        applied = "O2_insolvency_plus_cash_burn_plus_illiquidity"

    return {
        "score": score, "band": band,
        "pre_override_score": pre_score, "pre_override_band": pre_band,
        "override_applied": applied,
        "secondary_overrides_matched": secondary,
    }
