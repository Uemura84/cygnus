"""Sector configurations for the distress scoring engine (v1.5).

Maps sector names → config records with plausibility bounds, distress
thresholds, signal weights, and cycle-length metadata.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_SIGNAL_WEIGHTS: dict[str, int] = {
    "margin_compression":        5,
    "cost_composition_drift":    8,
    "leverage_escalation":      10,
    "fcf_erosion":               8,
    "capex_starvation":          5,
    "fx_debt_exposure":          5,
    "earnings_quality_gap":      5,
    "lender_share_escalation":   5,
    "shareholder_value_erosion": 5,
}


def _cfg(sector_id, display_name, cycle_years, bounds, thresholds, weights=None):
    return {
        "sector_id": sector_id,
        "display_name": display_name,
        "cycle_length_years": cycle_years,
        "plausibility_bounds": bounds,
        "distress_thresholds": thresholds,
        "signal_weights": weights or dict(_SIGNAL_WEIGHTS),
    }


SECTOR_CONFIGS: dict[str, dict[str, Any]] = {
    # ── Fixture sectors (exact match with spec test data) ─────────────────
    "PETROCHEMICAL": _cfg(
        "PETROCHEMICAL", "Petrochemicals (naphtha-based)", 4,
        {"gross_margin_pct": {"min": -20, "max": 40}, "ebit_margin_pct": {"min": -40, "max": 25},
         "debt_to_ebitda": {"min": -2, "max": 25}, "current_ratio": {"min": 0.3, "max": 5},
         "cogs_to_revenue_pct": {"min": 60, "max": 120}},
        {"debt_to_ebitda_structural": 12, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 4},
    ),
    "PULP": _cfg(
        "PULP", "Pulp and paper (eucalyptus pulp producer)", 3,
        {"gross_margin_pct": {"min": 10, "max": 70}, "ebit_margin_pct": {"min": -20, "max": 60},
         "debt_to_ebitda": {"min": -2, "max": 20}, "current_ratio": {"min": 0.3, "max": 8},
         "cogs_to_revenue_pct": {"min": 30, "max": 90}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3},
    ),
    "DEFAULT": _cfg(
        "DEFAULT", "Default / uncategorized", 3,
        {"gross_margin_pct": {"min": 0, "max": 60}, "ebit_margin_pct": {"min": -20, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 15}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 40, "max": 100}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3},
    ),

    # ── Additional sectors (from company_sectors.yaml classification) ─────
    "Mining":                    _cfg("MINING", "Mining", 4,
        {"gross_margin_pct": {"min": 10, "max": 70}, "ebit_margin_pct": {"min": -10, "max": 60},
         "debt_to_ebitda": {"min": -2, "max": 15}, "current_ratio": {"min": 0.5, "max": 6},
         "cogs_to_revenue_pct": {"min": 30, "max": 90}},
        {"debt_to_ebitda_structural": 8, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Steel & Metals":            _cfg("STEEL", "Steel & Metals", 4,
        {"gross_margin_pct": {"min": 5, "max": 45}, "ebit_margin_pct": {"min": -20, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 20}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 55, "max": 95}},
        {"debt_to_ebitda_structural": 8, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 4}),
    "Oil & Gas":                 _cfg("OIL_GAS", "Oil & Gas", 4,
        {"gross_margin_pct": {"min": 10, "max": 65}, "ebit_margin_pct": {"min": -15, "max": 50},
         "debt_to_ebitda": {"min": -2, "max": 20}, "current_ratio": {"min": 0.4, "max": 5},
         "cogs_to_revenue_pct": {"min": 35, "max": 90}},
        {"debt_to_ebitda_structural": 8, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 4}),
    "Industrial Manufacturing":  _cfg("INDUSTRIAL", "Industrial Manufacturing", 3,
        {"gross_margin_pct": {"min": 10, "max": 55}, "ebit_margin_pct": {"min": -10, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 12}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 45, "max": 90}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Utilities":                 _cfg("UTILITIES", "Utilities", 5,
        {"gross_margin_pct": {"min": 15, "max": 65}, "ebit_margin_pct": {"min": -5, "max": 40},
         "debt_to_ebitda": {"min": -1, "max": 15}, "current_ratio": {"min": 0.4, "max": 4},
         "cogs_to_revenue_pct": {"min": 35, "max": 85}},
        {"debt_to_ebitda_structural": 8, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 4}),
    "Telecom":                   _cfg("TELECOM", "Telecommunications", 3,
        {"gross_margin_pct": {"min": 20, "max": 70}, "ebit_margin_pct": {"min": -10, "max": 35},
         "debt_to_ebitda": {"min": -1, "max": 12}, "current_ratio": {"min": 0.4, "max": 4},
         "cogs_to_revenue_pct": {"min": 30, "max": 80}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Food & Beverage":           _cfg("FOOD_BEV", "Food & Beverage", 3,
        {"gross_margin_pct": {"min": 15, "max": 65}, "ebit_margin_pct": {"min": -5, "max": 30},
         "debt_to_ebitda": {"min": -1, "max": 10}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 35, "max": 85}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Retail":                    _cfg("RETAIL", "Retail", 3,
        {"gross_margin_pct": {"min": 15, "max": 50}, "ebit_margin_pct": {"min": -10, "max": 20},
         "debt_to_ebitda": {"min": -2, "max": 10}, "current_ratio": {"min": 0.5, "max": 4},
         "cogs_to_revenue_pct": {"min": 50, "max": 85}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Consumer Goods":            _cfg("CONSUMER", "Consumer Goods", 3,
        {"gross_margin_pct": {"min": 20, "max": 65}, "ebit_margin_pct": {"min": -5, "max": 30},
         "debt_to_ebitda": {"min": -1, "max": 10}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 35, "max": 80}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Healthcare":                _cfg("HEALTHCARE", "Healthcare", 3,
        {"gross_margin_pct": {"min": 15, "max": 70}, "ebit_margin_pct": {"min": -10, "max": 30},
         "debt_to_ebitda": {"min": -1, "max": 10}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 30, "max": 85}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Education":                 _cfg("EDUCATION", "Education", 3,
        {"gross_margin_pct": {"min": 20, "max": 65}, "ebit_margin_pct": {"min": -10, "max": 25},
         "debt_to_ebitda": {"min": -1, "max": 10}, "current_ratio": {"min": 0.5, "max": 4},
         "cogs_to_revenue_pct": {"min": 35, "max": 80}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Real Estate":               _cfg("REAL_ESTATE", "Real Estate", 4,
        {"gross_margin_pct": {"min": 10, "max": 60}, "ebit_margin_pct": {"min": -15, "max": 40},
         "debt_to_ebitda": {"min": -2, "max": 15}, "current_ratio": {"min": 0.3, "max": 5},
         "cogs_to_revenue_pct": {"min": 40, "max": 90}},
        {"debt_to_ebitda_structural": 8, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 4}),
    "Technology":                _cfg("TECHNOLOGY", "Technology", 3,
        {"gross_margin_pct": {"min": 20, "max": 80}, "ebit_margin_pct": {"min": -30, "max": 35},
         "debt_to_ebitda": {"min": -2, "max": 10}, "current_ratio": {"min": 0.5, "max": 6},
         "cogs_to_revenue_pct": {"min": 20, "max": 80}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Transportation & Logistics":_cfg("TRANSPORT", "Transportation & Logistics", 3,
        {"gross_margin_pct": {"min": 5, "max": 50}, "ebit_margin_pct": {"min": -20, "max": 25},
         "debt_to_ebitda": {"min": -2, "max": 15}, "current_ratio": {"min": 0.3, "max": 4},
         "cogs_to_revenue_pct": {"min": 50, "max": 95}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Construction & Engineering":_cfg("CONSTRUCTION", "Construction & Engineering", 3,
        {"gross_margin_pct": {"min": 10, "max": 45}, "ebit_margin_pct": {"min": -10, "max": 25},
         "debt_to_ebitda": {"min": -2, "max": 12}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 55, "max": 90}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Agribusiness":              _cfg("AGRIBUSINESS", "Agribusiness", 3,
        {"gross_margin_pct": {"min": 5, "max": 50}, "ebit_margin_pct": {"min": -15, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 12}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 50, "max": 95}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Pulp & Paper":              _cfg("PULP", "Pulp & Paper", 3,
        {"gross_margin_pct": {"min": 10, "max": 70}, "ebit_margin_pct": {"min": -20, "max": 60},
         "debt_to_ebitda": {"min": -2, "max": 20}, "current_ratio": {"min": 0.3, "max": 8},
         "cogs_to_revenue_pct": {"min": 30, "max": 90}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Petrochemical":             _cfg("PETROCHEMICAL", "Petrochemicals", 4,
        {"gross_margin_pct": {"min": -20, "max": 40}, "ebit_margin_pct": {"min": -40, "max": 25},
         "debt_to_ebitda": {"min": -2, "max": 25}, "current_ratio": {"min": 0.3, "max": 5},
         "cogs_to_revenue_pct": {"min": 60, "max": 120}},
        {"debt_to_ebitda_structural": 12, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 4}),
    "Banking":                   _cfg("BANKING", "Banking", 5,
        {"gross_margin_pct": {"min": 30, "max": 90}, "ebit_margin_pct": {"min": -10, "max": 50},
         "debt_to_ebitda": {"min": -5, "max": 50}, "current_ratio": {"min": 0.2, "max": 3},
         "cogs_to_revenue_pct": {"min": 10, "max": 70}},
        {"debt_to_ebitda_structural": 20, "current_ratio_stress": 0.8, "fcf_negative_streak_structural": 4}),
    "Insurance":                 _cfg("INSURANCE", "Insurance", 5,
        {"gross_margin_pct": {"min": 10, "max": 70}, "ebit_margin_pct": {"min": -10, "max": 40},
         "debt_to_ebitda": {"min": -5, "max": 30}, "current_ratio": {"min": 0.3, "max": 4},
         "cogs_to_revenue_pct": {"min": 30, "max": 90}},
        {"debt_to_ebitda_structural": 15, "current_ratio_stress": 0.8, "fcf_negative_streak_structural": 4}),
    "Financial Services":        _cfg("FINANCIAL_SERVICES", "Financial Services", 3,
        {"gross_margin_pct": {"min": 20, "max": 80}, "ebit_margin_pct": {"min": -15, "max": 40},
         "debt_to_ebitda": {"min": -5, "max": 30}, "current_ratio": {"min": 0.3, "max": 5},
         "cogs_to_revenue_pct": {"min": 20, "max": 80}},
        {"debt_to_ebitda_structural": 10, "current_ratio_stress": 0.8, "fcf_negative_streak_structural": 3}),
    "Holding Company":           _cfg("HOLDING", "Holding Company", 3,
        {"gross_margin_pct": {"min": -10, "max": 80}, "ebit_margin_pct": {"min": -20, "max": 50},
         "debt_to_ebitda": {"min": -5, "max": 20}, "current_ratio": {"min": 0.3, "max": 6},
         "cogs_to_revenue_pct": {"min": 20, "max": 110}},
        {"debt_to_ebitda_structural": 8, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "In Bankruptcy":             _cfg("BANKRUPTCY", "In Bankruptcy", 3,
        {"gross_margin_pct": {"min": -50, "max": 50}, "ebit_margin_pct": {"min": -80, "max": 20},
         "debt_to_ebitda": {"min": -10, "max": 50}, "current_ratio": {"min": 0.1, "max": 5},
         "cogs_to_revenue_pct": {"min": 50, "max": 150}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 2}),
    "Media & Entertainment":     _cfg("MEDIA", "Media & Entertainment", 3,
        {"gross_margin_pct": {"min": 15, "max": 65}, "ebit_margin_pct": {"min": -15, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 10}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 35, "max": 85}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Environmental Services":    _cfg("ENVIRONMENTAL", "Environmental Services", 3,
        {"gross_margin_pct": {"min": 15, "max": 55}, "ebit_margin_pct": {"min": -5, "max": 30},
         "debt_to_ebitda": {"min": -1, "max": 10}, "current_ratio": {"min": 0.5, "max": 4},
         "cogs_to_revenue_pct": {"min": 45, "max": 85}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Diversified / Conglomerate":_cfg("DIVERSIFIED", "Diversified / Conglomerate", 3,
        {"gross_margin_pct": {"min": 10, "max": 60}, "ebit_margin_pct": {"min": -10, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 12}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 40, "max": 90}},
        {"debt_to_ebitda_structural": 6, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
    "Other":                     _cfg("OTHER", "Other / unclassified", 3,
        {"gross_margin_pct": {"min": 0, "max": 60}, "ebit_margin_pct": {"min": -20, "max": 30},
         "debt_to_ebitda": {"min": -2, "max": 15}, "current_ratio": {"min": 0.5, "max": 5},
         "cogs_to_revenue_pct": {"min": 40, "max": 100}},
        {"debt_to_ebitda_structural": 5, "current_ratio_stress": 1.0, "fcf_negative_streak_structural": 3}),
}


def get_sector_config(sector_name: str) -> dict[str, Any]:
    """Look up a sector config by name or sector_id. Falls back to DEFAULT."""
    if sector_name in SECTOR_CONFIGS:
        return SECTOR_CONFIGS[sector_name]
    for cfg in SECTOR_CONFIGS.values():
        if cfg["sector_id"] == sector_name:
            return cfg
    logger.warning("No sector config for '%s' — using DEFAULT", sector_name)
    return SECTOR_CONFIGS["DEFAULT"]
