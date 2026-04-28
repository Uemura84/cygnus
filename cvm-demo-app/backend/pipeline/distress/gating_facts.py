"""Gating facts detector — §3 of the distress scoring spec v1.5."""

from __future__ import annotations
from typing import Any

GATING_WEIGHTS = {"G01": 25, "G02": 25, "G03": 15, "G04": 10, "G05": 10, "G06": 10}
GATING_NAMES = {
    "G01": "Negative book equity",
    "G02": "Auditor going-concern emphasis",
    "G03": "Persistent liquidity stress",
    "G04": "Distributing while insolvent",
    "G05": "Financing dependence for payouts",
    "G06": "Technical insolvency trajectory",
}

_KEYS = {
    "G01": "G01_negative_equity",
    "G02": "G02_going_concern",
    "G03": "G03_persistent_liquidity_stress",
    "G04": "G04_distributing_while_insolvent",
    "G05": "G05_financing_dependence_for_payouts",
    "G06": "G06_technical_insolvency_trajectory",
}


def detect_gating_facts(gating_inputs: dict[str, Any]) -> list[dict]:
    """Detect which gating facts fire. Handles G04/G05 non-double-counting."""
    fired: list[dict] = []

    for gid in ("G01", "G02", "G03"):
        key = _KEYS[gid]
        if gating_inputs.get(key, {}).get("fires"):
            fired.append(_make(gid, gating_inputs[key]))

    g04_fires = gating_inputs.get(_KEYS["G04"], {}).get("fires", False)
    g05_fires = gating_inputs.get(_KEYS["G05"], {}).get("fires", False)
    if g05_fires:
        fired.append(_make("G05", gating_inputs[_KEYS["G05"]]))
    elif g04_fires:
        fired.append(_make("G04", gating_inputs[_KEYS["G04"]]))

    if gating_inputs.get(_KEYS["G06"], {}).get("fires"):
        fired.append(_make("G06", gating_inputs[_KEYS["G06"]]))

    return fired


def _make(gid: str, evidence: dict) -> dict:
    return {
        "finding_id": gid, "name": GATING_NAMES[gid],
        "classification": "gating", "weight": GATING_WEIGHTS[gid],
        "cycle_multiplier": 1.0, "contribution": GATING_WEIGHTS[gid],
        "evidence": {k: v for k, v in evidence.items() if k != "fires"},
    }


def gating_score(findings: list[dict]) -> int:
    return sum(g["weight"] for g in findings)


def has_gating(findings: list[dict], gid: str) -> bool:
    return any(g["finding_id"] == gid for g in findings)
