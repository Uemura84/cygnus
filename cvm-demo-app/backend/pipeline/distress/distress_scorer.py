"""Distress Scoring Engine — orchestrator (§7 of the spec v1.5).

Combines gating facts + fundamental health + capped signal score (cap=10),
applies band overrides, returns a fully auditable DistressScoreResult.
Six bands: Healthy/Stable/Watchlist/High Risk/Distress/Severe Distress.
"""

from __future__ import annotations
from typing import Any

from pipeline.distress.gating_facts import detect_gating_facts, gating_score
from pipeline.distress.fundamentals_scorer import compute_fundamentals
from pipeline.distress.cycle_classifier import compute_cycle_dating, score_signals
from pipeline.distress.band_overrides import map_to_band, apply_overrides, BAND_DESCRIPTIONS


def compute_distress_score(
    gating_inputs: dict[str, Any],
    fundamentals_inputs: dict[str, Any],
    findings: list[dict],
    analysis_window: dict,
    sector_config: dict,
) -> dict:
    # 1. Cycle dating
    cycle = compute_cycle_dating(analysis_window)

    # 2. Gating facts
    gating_findings = detect_gating_facts(gating_inputs)
    g_score = gating_score(gating_findings)

    # 3. Fundamental health (max 30)
    fundamentals = compute_fundamentals(fundamentals_inputs, sector_config)
    f_score = fundamentals["fundamentals_contribution"]

    # 4+5. Classify and score signals (cap=10)
    signals = score_signals(findings, sector_config, cycle)
    s_score = signals["signal_score"]

    # 6. Combine (cap 100)
    distress_score = min(100, g_score + f_score + s_score)

    # 7. Band + overrides
    band = map_to_band(distress_score)
    overrides = apply_overrides(distress_score, band, gating_findings, fundamentals_inputs)

    # Signal profile
    classified = signals.get("classified_findings", [])
    structural_count = sum(1 for c in classified if c["classification"] == "structural")
    ambiguous_count  = sum(1 for c in classified if c["classification"] == "ambiguous")
    cyclical_count   = sum(1 for c in classified if c["classification"] == "cyclical")

    return {
        "distress_score": overrides["score"],
        "band": overrides["band"],
        "band_description": BAND_DESCRIPTIONS.get(overrides["band"], ""),
        "score_breakdown": {
            "gating_score": g_score,
            "fundamentals_score": f_score,
            "signal_score": s_score,
            "raw_signal_score": signals["raw_signal_score"],
            "signal_cap_applied": signals["signal_cap_applied"],
        },
        "override": {
            "applied": overrides["override_applied"],
            "pre_override_score": overrides["pre_override_score"],
            "pre_override_band": overrides["pre_override_band"],
            "secondary_overrides_matched": overrides["secondary_overrides_matched"],
        },
        "cycle": {
            "peak_year": cycle.get("peak_year"),
            "trough_year": cycle.get("trough_year"),
            "position": cycle["cycle_position"],
            "gross_margin_range_pp": cycle.get("gross_margin_range_pp"),
            "guardrail_applied": cycle.get("guardrail_applied", False),
            "method": cycle.get("method", "heuristic_internal_margin"),
        },
        "signal_profile": {
            "total_findings": len(findings),
            "structural_count": structural_count,
            "ambiguous_count": ambiguous_count,
            "cyclical_count": cyclical_count,
            "gating_count": len(gating_findings),
        },
        "gating_facts_triggered": [
            {"id": g["finding_id"], "name": g["name"],
             "contribution": g["contribution"], "evidence": g.get("evidence", {})}
            for g in gating_findings
        ],
        "fundamentals": {
            k: {"value": v.get("value", v.get("value_latest")), "points": v["points"]}
            for k, v in fundamentals["components"].items()
        },
        "classified_findings": classified,
        "sector_id": sector_config.get("sector_id", "DEFAULT"),
    }
