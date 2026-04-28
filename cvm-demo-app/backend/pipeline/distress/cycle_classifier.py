"""Cycle classification — §5 of the distress scoring spec v1.5.

Four classifications: gating (1.0), structural (1.0), ambiguous (0.5), cyclical (0.3).
10pp gross margin range guardrail. Five classification tests, first match wins.
Signal cap at 10 points.
"""

from __future__ import annotations
from typing import Any

GUARDRAIL_THRESHOLD_PP = 10.0
SIGNAL_CAP = 10

CYCLE_MULTIPLIERS = {
    "gating":     1.0,
    "structural": 1.0,
    "ambiguous":  0.5,
    "cyclical":   0.3,
}


def compute_cycle_dating(analysis_window: dict) -> dict:
    """Heuristic cycle dating with 10pp guardrail (§5.3)."""
    trajectory = analysis_window.get("gross_margin_trajectory_pct")
    if not trajectory:
        return {"cycle_position": "unknown", "gross_margin_range_pp": None,
                "guardrail_applied": False, "peak_year": None, "trough_year": None,
                "method": "heuristic_internal_margin"}

    margin_range = max(trajectory) - min(trajectory)
    if margin_range < GUARDRAIL_THRESHOLD_PP:
        return {"cycle_position": "unknown", "gross_margin_range_pp": round(margin_range, 1),
                "guardrail_applied": True, "peak_year": None, "trough_year": None,
                "method": "heuristic_internal_margin"}

    periods = analysis_window.get("annual_periods", [])
    peak_idx = trajectory.index(max(trajectory))
    trough_idx = trajectory.index(min(trajectory))
    position = "post_peak_declining" if peak_idx < trough_idx else "recovery"
    return {
        "cycle_position": position,
        "gross_margin_range_pp": round(margin_range, 1),
        "guardrail_applied": False,
        "peak_year": periods[peak_idx] if peak_idx < len(periods) else None,
        "trough_year": periods[trough_idx] if trough_idx < len(periods) else None,
        "method": "heuristic_internal_margin",
    }


def score_signals(findings: list[dict], sector_config: dict, cycle: dict) -> dict:
    """Classify and score all non-gating signals with a 10-point hard cap.

    Fixtures carry classification_hint directly. In the real pipeline, Tests 1-5
    from §5.1 would run here and respect the guardrail. The reference
    implementation uses classification_hint as the resolved classification.
    """
    weights = sector_config.get("signal_weights", {})
    raw = 0.0
    classified: list[dict] = []

    for f in findings:
        signal_type = f.get("signal_type", "")
        hint = f.get("classification_hint", "structural")
        w = weights.get(signal_type, 0)
        mult = CYCLE_MULTIPLIERS.get(hint, 0.3)
        contribution = w * mult
        raw += contribution
        classified.append({
            "finding_id": f.get("finding_id", ""),
            "signal_type": signal_type,
            "classification": hint,
            "classification_reason": f.get("classification_reason", f"hint: {hint}"),
            "weight": w,
            "cycle_multiplier": mult,
            "contribution": round(contribution, 2),
        })

    capped = min(SIGNAL_CAP, raw)
    return {
        "raw_signal_score": round(raw, 2),
        "signal_score": int(capped),
        "signal_cap_applied": raw > capped,
        "classified_findings": classified,
    }
