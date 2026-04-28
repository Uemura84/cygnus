"""Fundamental Health Scoring — §4 of the distress scoring spec v1.5.

4 metrics, max 30 points total. Scored from the latest annual period.
"""

from __future__ import annotations
from typing import Any


def score_profitability(ebit_margin_pct: float) -> dict:
    if ebit_margin_pct < 0:
        pts, reason = 10, f"EBIT margin {ebit_margin_pct:.1f}% < 0%"
    elif ebit_margin_pct < 10:
        pts, reason = 5, f"EBIT margin {ebit_margin_pct:.1f}% between 0% and 10%"
    else:
        pts, reason = 0, f"EBIT margin {ebit_margin_pct:.1f}% >= 10%"
    return {"metric": "ebit_margin", "value": ebit_margin_pct, "points": pts, "reason": reason}


def score_cash_generation(fcf_latest: float, fcf_last_3: list[dict]) -> dict:
    neg_count = sum(1 for y in fcf_last_3 if y.get("fcf_brl_b", 0) < 0)
    if fcf_latest < 0 and neg_count >= 2:
        pts = 8
        reason = f"FCF negative in latest year and in {neg_count} of last {len(fcf_last_3)} years"
    elif fcf_latest < 0:
        pts, reason = 4, "FCF negative in latest year only"
    else:
        pts, reason = 0, "FCF positive in latest year"
    return {"metric": "free_cash_flow", "value_latest": fcf_latest,
            "negative_years_in_last_3": neg_count, "points": pts, "reason": reason}


def score_leverage(debt_to_ebitda: float | None, sector_config: dict) -> dict:
    threshold = sector_config["distress_thresholds"]["debt_to_ebitda_structural"]
    half = threshold / 2
    if debt_to_ebitda is None or debt_to_ebitda > threshold:
        pts = 6
        reason = ("EBITDA <= 0, Debt/EBITDA undefined — treated as above threshold"
                  if debt_to_ebitda is None
                  else f"Debt/EBITDA {debt_to_ebitda:.1f}x exceeds sector threshold {threshold}x")
    elif debt_to_ebitda >= half:
        pts = 3
        reason = f"Debt/EBITDA {debt_to_ebitda:.1f}x between {half:.1f}x and {threshold}x"
    else:
        pts = 0
        reason = f"Debt/EBITDA {debt_to_ebitda:.1f}x below half-threshold {half:.1f}x"
    return {"metric": "debt_to_ebitda", "value": debt_to_ebitda,
            "threshold": threshold, "points": pts, "reason": reason}


def score_liquidity(current_ratio: float) -> dict:
    if current_ratio < 1.0:
        pts, reason = 6, f"Current ratio {current_ratio:.2f} < 1.0"
    elif current_ratio <= 1.5:
        pts, reason = 3, f"Current ratio {current_ratio:.2f} between 1.0 and 1.5"
    else:
        pts, reason = 0, f"Current ratio {current_ratio:.2f} > 1.5"
    return {"metric": "current_ratio", "value": current_ratio,
            "points": pts, "reason": reason}


def compute_fundamentals(inputs: dict[str, Any], sector_config: dict) -> dict:
    prof = score_profitability(inputs["ebit_margin_pct"])
    cash = score_cash_generation(inputs["free_cash_flow_brl_b_latest"],
                                  inputs.get("fcf_last_3_years", []))
    lev = score_leverage(inputs.get("debt_to_ebitda"), sector_config)
    liq = score_liquidity(inputs["current_ratio"])
    total = prof["points"] + cash["points"] + lev["points"] + liq["points"]
    return {"fundamentals_contribution": total,
            "components": {"profitability": prof, "cash_generation": cash,
                           "leverage": lev, "liquidity": liq}}
