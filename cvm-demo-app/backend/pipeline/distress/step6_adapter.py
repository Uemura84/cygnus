"""Adapter that extracts distress-scorer inputs from Step 6 pipeline data (v1.5).

Translates balance_sheet_series, cash_flow_series, time_series, dmpl_series,
auditor_classifications, and Step 6 findings into the structured inputs that
compute_distress_score() expects.
"""

from __future__ import annotations

from typing import Any

from pipeline.distress.sector_config import get_sector_config


# ---------------------------------------------------------------------------
# Finding code → signal_type mapping (for signal_weights in sector config)
# ---------------------------------------------------------------------------

_CODE_TO_SIGNAL: dict[str, str] = {
    "Margin compression":         "margin_compression",
    "Persistent margin decline":  "margin_compression",
    "Sustained margin decline":   "margin_compression",
    "Cost composition drift":     "cost_composition_drift",
    "BS_LEVERAGE_ESCALATION":     "leverage_escalation",
    "CF_FCF_EROSION":             "fcf_erosion",
    "CF_CAPEX_STARVATION":        "capex_starvation",
    "BS_FX_DEBT_CONCENTRATION":   "fx_debt_exposure",
    "BS_MATURITY_WALL":           "fx_debt_exposure",
    "CF_EARNINGS_QUALITY_GAP":    "earnings_quality_gap",
    "DVA_LENDER_SHARE_ESCALATION":    "lender_share_escalation",
    "DVA_SHAREHOLDER_VALUE_EROSION":  "shareholder_value_erosion",
}


def extract_distress_inputs(
    step4_data: dict,
    step6_data: dict,
    company_name: str,
    sector_name: str,
) -> dict:
    """Extract all inputs needed by compute_distress_score() from pipeline data."""
    bs_annual = _annual_series(step4_data.get("balance_sheet_series", []))
    cf_annual = _annual_series(step4_data.get("cash_flow_series", []))
    ts = step4_data.get("time_series", [])
    dmpl = step4_data.get("dmpl_series", [])
    auditor = step6_data.get("auditor_classifications", [])
    findings = step6_data.get("findings", [])

    sector_config = get_sector_config(sector_name)

    return {
        "gating_inputs":       _build_gating_inputs(bs_annual, cf_annual, dmpl, auditor),
        "fundamentals_inputs": _build_fundamentals_inputs(bs_annual, cf_annual, ts, sector_config),
        "findings":            _build_signal_findings(findings, ts, sector_config),
        "analysis_window":     _build_analysis_window(ts, bs_annual),
        "sector_config":       sector_config,
    }


# ---------------------------------------------------------------------------
# Gating inputs
# ---------------------------------------------------------------------------

def _build_gating_inputs(
    bs_annual: list[dict],
    cf_annual: list[dict],
    dmpl: list[dict],
    auditor: list[dict],
) -> dict:
    latest_bs = bs_annual[-1] if bs_annual else {}
    latest_eq = latest_bs.get("total_equity", 0) or 0

    # G01: negative book equity
    g01 = {
        "fires": latest_eq < 0,
        "closing_equity_brl_b": round(latest_eq / 1e6, 1),
        "period": latest_bs.get("period", ""),
    }

    # G02: auditor going-concern
    latest_aud = auditor[-1] if auditor else {}
    g02 = {
        "fires": bool(latest_aud.get("has_going_concern")),
        "auditor": latest_aud.get("auditor_firm", ""),
        "period": latest_aud.get("period", ""),
    }

    # G03: current ratio < 1.0 for ≥2 consecutive annual periods
    cr_history = [
        {"period": b.get("period", "")[:4], "value": b.get("current_ratio", 999)}
        for b in bs_annual
    ]
    consecutive = 0
    max_consecutive = 0
    for cr in cr_history:
        if cr["value"] < 1.0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    g03 = {"fires": max_consecutive >= 2, "current_ratio_history": cr_history}

    # G04 / G05: dividend-related
    cf_by_year: dict[str, dict] = {}
    for cf in cf_annual:
        cf_by_year[cf.get("period", "")[:4]] = cf

    dmpl_by_year: dict[str, dict] = {}
    for d in dmpl:
        dmpl_by_year[str(d.get("period", ""))[:4]] = d

    # G04: dividends declared in a loss year
    g04_fires = False
    for y, d in dmpl_by_year.items():
        dividends = abs(d.get("total_dividends", 0) or 0)
        net_income = d.get("net_income", 0) or 0
        if dividends > 0 and net_income < 0:
            g04_fires = True
            break

    # G05: dividends in ≥3 periods where FCF < 0
    periods_fcf_neg_with_div = 0
    counted_years: set[str] = set()
    for y, cf in cf_by_year.items():
        fcf = cf.get("free_cash_flow", 0) or 0
        div_cf = abs(cf.get("dividends_paid", 0) or 0)
        if fcf < 0 and div_cf > 0 and y not in counted_years:
            periods_fcf_neg_with_div += 1
            counted_years.add(y)
    for y, d in dmpl_by_year.items():
        if y in counted_years:
            continue
        dividends = abs(d.get("total_dividends", 0) or 0)
        cf = cf_by_year.get(y, {})
        fcf = cf.get("free_cash_flow", 0) or 0
        if dividends > 0 and fcf < 0:
            periods_fcf_neg_with_div += 1
            counted_years.add(y)

    g05_fires = periods_fcf_neg_with_div >= 3

    g04 = {
        "fires": g04_fires and not g05_fires,
        "reason_not_fired": "G05 takes precedence when both match" if g04_fires and g05_fires else "",
    }
    g05 = {
        "fires": g05_fires,
        "periods_fcf_negative_with_dividends": periods_fcf_neg_with_div,
    }

    # G06: equity declining ≥3 consecutive years AND latest < 50% of opening
    equity_trajectory = [b.get("total_equity", 0) or 0 for b in bs_annual]
    consecutive_decline = 0
    max_decline = 0
    for i in range(1, len(equity_trajectory)):
        if equity_trajectory[i] < equity_trajectory[i - 1]:
            consecutive_decline += 1
            max_decline = max(max_decline, consecutive_decline)
        else:
            consecutive_decline = 0

    opening = equity_trajectory[0] if equity_trajectory else 1
    latest_val = equity_trajectory[-1] if equity_trajectory else 0
    below_50 = opening > 0 and latest_val < opening * 0.5
    g06 = {"fires": max_decline >= 3 and below_50}

    return {
        "G01_negative_equity": g01,
        "G02_going_concern": g02,
        "G03_persistent_liquidity_stress": g03,
        "G04_distributing_while_insolvent": g04,
        "G05_financing_dependence_for_payouts": g05,
        "G06_technical_insolvency_trajectory": g06,
    }


# ---------------------------------------------------------------------------
# Fundamentals inputs
# ---------------------------------------------------------------------------

def _build_fundamentals_inputs(
    bs_annual: list[dict],
    cf_annual: list[dict],
    ts: list[dict],
    sector_config: dict,
) -> dict:
    latest_bs = bs_annual[-1] if bs_annual else {}
    latest_cf = cf_annual[-1] if cf_annual else {}

    ebit_margin = None
    for t in reversed(ts):
        if t.get("EBIT_Margin_pct") is not None:
            ebit_margin = t["EBIT_Margin_pct"]
            break
    if ebit_margin is None:
        ebit_margin = 0.0

    fcf_latest = (latest_cf.get("free_cash_flow", 0) or 0) / 1e6
    fcf_last_3 = [
        {"year": cf.get("period", "")[:4],
         "fcf_brl_b": (cf.get("free_cash_flow", 0) or 0) / 1e6}
        for cf in cf_annual[-3:]
    ]

    return {
        "ebit_margin_pct": ebit_margin,
        "free_cash_flow_brl_b_latest": fcf_latest,
        "fcf_last_3_years": fcf_last_3,
        "debt_to_ebitda": latest_bs.get("debt_to_ebitda"),
        "current_ratio": latest_bs.get("current_ratio") or 1.5,
    }


# ---------------------------------------------------------------------------
# Signal findings
# ---------------------------------------------------------------------------

def _build_signal_findings(
    findings: list[dict],
    ts: list[dict],
    sector_config: dict,
) -> list[dict]:
    """Map Step 6 findings to distress-scorer signal format with classification hints."""
    gross_margins = [t.get("Gross_Margin_pct") for t in ts if t.get("Gross_Margin_pct") is not None]
    margin_range = (max(gross_margins) - min(gross_margins)) if len(gross_margins) >= 2 else 0
    guardrail = margin_range < 10.0

    peak_year = None
    if not guardrail and gross_margins:
        periods = [t.get("period", "")[:4] for t in ts if t.get("Gross_Margin_pct") is not None]
        peak_idx = gross_margins.index(max(gross_margins))
        peak_year = periods[peak_idx] if peak_idx < len(periods) else None

    cycle_length = sector_config.get("cycle_length_years", 3)

    out: list[dict] = []
    for f in findings:
        if f.get("module") == "stacked":
            continue
        code = f.get("code") or f.get("pattern", "")
        signal_type = _CODE_TO_SIGNAL.get(code)
        if not signal_type:
            continue

        hint = _classify_finding(f, peak_year, cycle_length, guardrail)
        out.append({
            "finding_id": f.get("id", ""),
            "signal_type": signal_type,
            "classification_hint": hint,
            "classification_reason": f"heuristic: {'guardrail active' if guardrail else f'peak_year={peak_year}'}",
        })
    return out


def _classify_finding(
    finding: dict,
    peak_year: str | None,
    cycle_length: int,
    guardrail: bool,
) -> str:
    """v1.5 classification heuristic with ambiguous support.

    Tests 1-5 from §5.1 simplified for adapter use:
    - guardrail fired + short persistence → ambiguous (Test 5)
    - YoY near peak → cyclical (Test 2, only when guardrail passes)
    - single-period capex/earnings anomaly → ambiguous
    - persistent pattern > cycle_length → structural (Test 4)
    - default → structural (conservative)
    """
    code = finding.get("code") or finding.get("pattern", "")
    dp = finding.get("data_points", {})

    # Test 5: guardrail path — short persistence → ambiguous
    if guardrail:
        decline_periods = dp.get("consecutive_decline_periods", 0) or dp.get("periods_analyzed", 0)
        if decline_periods and decline_periods > cycle_length:
            return "structural"
        return "ambiguous"

    # Test 2: base-effect — YoY/anomaly near cycle peak → cyclical
    if peak_year:
        if code == "Statistical anomaly":
            anomaly_period = str(dp.get("period", ""))[:4]
            if anomaly_period and abs(int(anomaly_period) - int(peak_year)) <= 1:
                return "cyclical"

        if code == "YoY quarter comparison":
            yoy_period = str(dp.get("period", ""))
            if peak_year in yoy_period:
                return "cyclical"

        if code == "Revenue-cost decoupling":
            period = str(dp.get("period", ""))[:4]
            if period and abs(int(period) - int(peak_year)) <= 1:
                return "cyclical"

        if code in ("Margin compression", "Persistent margin decline", "Sustained margin decline",
                     "Cost composition drift"):
            # Check persistence (Test 4)
            decline_periods = dp.get("consecutive_decline_periods", 0) or dp.get("periods_analyzed", 0)
            if decline_periods:
                if decline_periods > cycle_length:
                    return "structural"
                if decline_periods == cycle_length:
                    return "ambiguous"
            return "cyclical"

    # Single-period capex/earnings findings → ambiguous (Test 3 edge case)
    if code in ("CF_CAPEX_STARVATION", "CF_EARNINGS_QUALITY_GAP"):
        return "ambiguous"

    return "structural"


# ---------------------------------------------------------------------------
# Analysis window
# ---------------------------------------------------------------------------

def _build_analysis_window(ts: list[dict], bs_annual: list[dict]) -> dict:
    periods: list[str] = []
    gross_margins: list[float] = []
    for t in ts:
        gm = t.get("Gross_Margin_pct")
        p = t.get("period", "")[:4]
        if gm is not None and p:
            periods.append(p)
            gross_margins.append(gm)

    latest = bs_annual[-1].get("period", "") if bs_annual else ""
    return {
        "latest_annual_period": latest,
        "annual_periods": periods,
        "gross_margin_trajectory_pct": gross_margins,
    }


def _annual_series(series: list[dict]) -> list[dict]:
    annual = [r for r in series if r.get("granularity") == "annual"]
    annual.sort(key=lambda r: r.get("period", ""))
    return annual
