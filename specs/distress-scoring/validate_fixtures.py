"""
Reference implementation that simulates the scoring engine against all fixtures.
This proves the expected outputs are mathematically consistent with the inputs.

If Claude Code implements the real engine correctly, it should produce
the same results as this reference.
"""
import json

GATING_WEIGHTS = {
    "G01": 25, "G02": 25, "G03": 15, "G04": 10, "G05": 10, "G06": 10
}

BAND_THRESHOLDS = [
    (0, 20, "Healthy"),
    (20, 40, "Stable"),
    (40, 60, "Watchlist"),
    (60, 80, "High Risk"),
    (80, 90, "Distress"),
    (90, 101, "Severe Distress"),
]

def map_to_band(score):
    for low, high, name in BAND_THRESHOLDS:
        if low <= score < high:
            return name
    return "Severe Distress"  # score = 100 edge case

def score_profitability(ebit_margin_pct):
    if ebit_margin_pct < 0:
        return 10
    if ebit_margin_pct < 10:
        return 5
    return 0

def score_cash_generation(fcf_latest, fcf_last_3_years):
    negative_count = sum(1 for y in fcf_last_3_years if y["fcf_brl_b"] < 0)
    if fcf_latest < 0 and negative_count >= 2:
        return 8
    if fcf_latest < 0:
        return 4
    return 0

def score_leverage(debt_to_ebitda, sector_config):
    threshold = sector_config["distress_thresholds"]["debt_to_ebitda_structural"]
    half = threshold / 2
    if debt_to_ebitda is None or debt_to_ebitda > threshold:
        return 6
    if debt_to_ebitda >= half:
        return 3
    return 0

def score_liquidity(current_ratio):
    if current_ratio < 1.0:
        return 6
    if current_ratio <= 1.5:
        return 3
    return 0

def score_fundamentals(f, sector_config):
    prof = score_profitability(f["ebit_margin_pct"])
    cash = score_cash_generation(f["free_cash_flow_brl_b_latest"], f["fcf_last_3_years"])
    lev = score_leverage(f["debt_to_ebitda"], sector_config)
    liq = score_liquidity(f["current_ratio"])
    return {
        "profitability": prof, "cash_generation": cash,
        "leverage": lev, "liquidity": liq,
        "total": prof + cash + lev + liq
    }

def compute_cycle_dating(analysis_window):
    """Heuristic cycle dating with 10pp guardrail (§5.3)."""
    trajectory = analysis_window.get("gross_margin_trajectory_pct")
    if not trajectory:
        # Trajectory not provided — guardrail treated as not applicable, cycle unknown
        return {
            "cycle_position": "unknown",
            "gross_margin_range_pp": None,
            "guardrail_applied": False,
            "peak_year": None,
            "trough_year": None
        }
    margin_range = max(trajectory) - min(trajectory)
    if margin_range < 10.0:
        return {
            "cycle_position": "unknown",
            "gross_margin_range_pp": margin_range,
            "guardrail_applied": True,
            "peak_year": None,
            "trough_year": None
        }
    periods = analysis_window["annual_periods"]
    peak_idx = trajectory.index(max(trajectory))
    trough_idx = trajectory.index(min(trajectory))
    return {
        "cycle_position": "post_peak_declining" if peak_idx < trough_idx else "recovery",
        "gross_margin_range_pp": margin_range,
        "guardrail_applied": False,
        "peak_year": periods[peak_idx],
        "trough_year": periods[trough_idx]
    }

def score_signals(findings, sector_config, cycle):
    weights = sector_config["signal_weights"]
    multipliers = {"structural": 1.0, "ambiguous": 0.5, "cyclical": 0.3}
    raw = 0.0
    for f in findings:
        w = weights.get(f["signal_type"], 0)
        mult = multipliers.get(f["classification_hint"], 0.3)
        raw += w * mult
    capped = min(10, raw)
    return {
        "raw_signal_score": raw,
        "signal_score": capped,
        "signal_cap_applied": raw > capped
    }

def score_gating(gating_inputs):
    fired = []
    total = 0
    for g_id, g_data in gating_inputs.items():
        if g_data.get("fires"):
            short_id = g_id.split("_")[0]
            fired.append(short_id)
            total += GATING_WEIGHTS[short_id]
    return {"gating_score": total, "gating_facts_fired": fired}

def apply_overrides(score, band, gating_fired, fundamentals_inputs):
    g01 = "G01" in gating_fired
    g02 = "G02" in gating_fired
    fcf_neg = fundamentals_inputs["free_cash_flow_brl_b_latest"] < 0
    curr_ratio_low = fundamentals_inputs["current_ratio"] < 1.0

    o1 = g01 and g02
    o2 = g01 and fcf_neg and curr_ratio_low

    pre_score = score
    pre_band = band
    applied = None
    secondary = []

    if o1:
        score = max(score, 80)
        band = map_to_band(score)  # re-map: could be Distress or Severe Distress depending on final score
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
        "secondary_overrides_matched": secondary
    }

def compute(fixture, sector_configs):
    sector = sector_configs[fixture["company"]["sector_id"]]
    cycle = compute_cycle_dating(fixture["analysis_window"])
    gating = score_gating(fixture["gating_inputs"])
    fundamentals = score_fundamentals(fixture["fundamentals_inputs"], sector)
    signals = score_signals(fixture["findings"], sector, cycle)
    pre_override_score = min(100, gating["gating_score"] + fundamentals["total"] + signals["signal_score"])
    pre_override_band = map_to_band(pre_override_score)
    overrides = apply_overrides(
        pre_override_score, pre_override_band,
        gating["gating_facts_fired"], fixture["fundamentals_inputs"]
    )
    return {
        "distress_score": int(overrides["score"]),
        "band": overrides["band"],
        "gating_score": gating["gating_score"],
        "fundamentals_score": fundamentals["total"],
        "signal_score": int(signals["signal_score"]),
        "raw_signal_score": signals["raw_signal_score"],
        "signal_cap_applied": signals["signal_cap_applied"],
        "gating_facts_fired": gating["gating_facts_fired"],
        "fundamentals_components": {k: v for k, v in fundamentals.items() if k != "total"},
        "override_applied": overrides["override_applied"],
        "pre_override_score": overrides["pre_override_score"],
        "pre_override_band": overrides["pre_override_band"],
        "secondary_overrides_matched": overrides["secondary_overrides_matched"],
        "cycle_position": cycle["cycle_position"],
        "guardrail_applied": cycle["guardrail_applied"]
    }

def check(name, computed, expected):
    """Return list of mismatch strings (empty if all pass)."""
    mismatches = []
    checks = [
        ("distress_score", computed["distress_score"], expected["distress_score"]),
        ("band", computed["band"], expected["band"]),
        ("gating_score", computed["gating_score"], expected["score_breakdown"]["gating_score"]),
        ("fundamentals_score", computed["fundamentals_score"], expected["score_breakdown"]["fundamentals_score"]),
        ("signal_score", computed["signal_score"], expected["score_breakdown"]["signal_score"]),
        ("signal_cap_applied", computed["signal_cap_applied"], expected["score_breakdown"]["signal_cap_applied"]),
        ("override_applied", computed["override_applied"], expected["override"]["applied"]),
        ("pre_override_score", computed["pre_override_score"], expected["override"]["pre_override_score"]),
        ("pre_override_band", computed["pre_override_band"], expected["override"]["pre_override_band"]),
        ("secondary_overrides", sorted(computed["secondary_overrides_matched"]),
                                sorted(expected["override"]["secondary_overrides_matched"])),
        ("gating_facts_fired", sorted(computed["gating_facts_fired"]),
                                sorted(expected["gating_facts_fired"])),
    ]
    for fund_key, fund_val in expected["fundamentals_components_expected"].items():
        checks.append((f"fund.{fund_key}", computed["fundamentals_components"][fund_key], fund_val))
    if "cycle_expected" in expected:
        checks.append(("cycle_position", computed["cycle_position"], expected["cycle_expected"]["cycle_position"]))
        checks.append(("guardrail_applied", computed["guardrail_applied"], expected["cycle_expected"]["guardrail_applied"]))
    for field, got, want in checks:
        if got != want:
            mismatches.append(f"  {field}: got {got!r}, expected {want!r}")
    return mismatches

def main():
    with open("sector_configs.json") as f:
        sector_configs = json.load(f)
    with open("expected_outputs.json") as f:
        expected = json.load(f)

    fixtures = [
        ("braskem", "braskem.json"),
        ("suzano", "suzano.json"),
        ("synthetic_s1_o1_test", "synthetic_s1_o1_test.json"),
        ("synthetic_s2_o2_test", "synthetic_s2_o2_test.json"),
        ("synthetic_s3_guardrail_test", "synthetic_s3_guardrail_test.json"),
    ]

    all_pass = True
    for name, path in fixtures:
        with open(path) as f:
            fixture = json.load(f)
        computed = compute(fixture, sector_configs)
        mismatches = check(name, computed, expected[name])
        if not mismatches:
            print(f"PASS  {name}  score={computed['distress_score']} band={computed['band']}")
        else:
            all_pass = False
            print(f"FAIL  {name}")
            for m in mismatches:
                print(m)
            print(f"  computed: {json.dumps(computed, indent=2)}")

    print()
    print("ALL PASS" if all_pass else "SOME TESTS FAILED")
    return 0 if all_pass else 1

if __name__ == "__main__":
    exit(main())
