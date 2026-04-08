"""Module 3: Cash Flow Quality Detection.

Receives the cash_flow_series (list of dicts) from Step 4 and produces
findings with code prefix CF_.

Public API
----------
detect_cf_patterns(cf_series, company_name) -> list[dict]
    Run all 6 cash flow detection algorithms.
    Returns findings with module="cash_flow_quality".
"""


def _safe(record: dict, key: str, default=None):
    v = record.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


# =============================================================================
# CF-1: EARNINGS_QUALITY_GAP
# =============================================================================

def _check_earnings_quality(series: list, company: str) -> list:
    findings = []

    ratio_vals = [(r["period"][:4], _safe(r, "ocf_to_net_income")) for r in series
                  if _safe(r, "ocf_to_net_income") is not None]
    if not ratio_vals:
        return findings

    periods, ratios = zip(*ratio_vals)
    latest = ratios[-1]

    severity = None
    reason = ""
    if latest < 0.5:
        severity = "HIGH"
        reason = f"OCF/NI ratio {latest:.2f} — less than half of earnings converting to cash"
    elif latest < 0.8:
        severity = "MEDIUM"
        reason = f"OCF/NI ratio {latest:.2f} — earnings-to-cash conversion below threshold"
    elif len(ratios) >= 2 and (ratios[0] - latest) > 0.3:
        severity = "MEDIUM"
        reason = f"OCF/NI ratio declining {ratios[0]:.2f} → {latest:.2f}"

    # Sign divergence check
    if severity is None:
        ocf_latest = _safe(series[-1], "operating_cash_flow")
        ni_proxy = None
        if ratio_vals and ocf_latest is not None:
            ratio = _safe(series[-1], "ocf_to_net_income")
            if ratio and ratio != 0:
                ni_proxy = ocf_latest / ratio
        if ocf_latest is not None and ni_proxy is not None:
            if (ocf_latest > 0) != (ni_proxy > 0):
                severity = "HIGH"
                reason = "OCF and net income have opposite signs (sign divergence)"

    if severity is None:
        return findings

    ocf = _safe(series[-1], "operating_cash_flow")
    mat = abs(ocf - (ocf / latest)) if (ocf is not None and latest and latest != 0) else None

    findings.append({
        "code":           "CF_EARNINGS_QUALITY_GAP",
        "module":         "cash_flow_quality",
        "pattern":        "Earnings quality gap",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "ocf_to_net_income",
        "metric_values":  {
            "ratio_latest": round(latest, 3),
            "ratio_first":  round(ratios[0], 3) if len(ratios) > 1 else None,
            "ocf_latest":   round(ocf, 0) if ocf is not None else None,
        },
        "periods_affected": list(periods[-2:]),
        "trend_direction":  "deteriorating" if (len(ratios) >= 2 and latest < ratios[0]) else "stable",
        "materiality_brl":  mat,
        "description":      f"{company}: {reason}.",
        "insight":          f"{company}: {reason}.",
    })
    return findings


# =============================================================================
# CF-2: CAPEX_STARVATION
# =============================================================================

def _check_capex_starvation(series: list, company: str) -> list:
    findings = []

    da_vals = [(r["period"][:4], _safe(r, "capex_to_depreciation")) for r in series
               if _safe(r, "capex_to_depreciation") is not None]
    rev_vals = [(r["period"][:4], _safe(r, "capex_to_revenue")) for r in series
                if _safe(r, "capex_to_revenue") is not None]

    if not da_vals:
        return findings

    periods, ratios = zip(*da_vals)
    latest = ratios[-1]

    severity = None
    reason = ""
    if latest < 0.5:
        severity = "HIGH"
        reason = f"capex/D&A {latest:.2f} — spending less than half of depreciation rate"
    elif latest < 0.8:
        severity = "MEDIUM"
        reason = f"capex/D&A {latest:.2f} — below replacement rate"
    elif sum(1 for r in ratios if r < 1.0) >= 3:
        severity = "MEDIUM"
        reason = "capex/D&A < 1.0 for 3+ consecutive periods (sustained harvest mode)"

    # Revenue trend trigger
    if severity is None and rev_vals and len(rev_vals) >= 2:
        _, rv = zip(*rev_vals)
        if rv[0] and rv[0] > 0:
            capex_decline_pct = (rv[-1] - rv[0]) / rv[0] * 100
            if capex_decline_pct < -30:
                severity = "MEDIUM"
                reason = f"capex/revenue declining {abs(capex_decline_pct):.0f}% over period"

    if severity is None:
        return findings

    # Materiality: D&A - |capex| for latest period
    capex_abs = _safe(series[-1], "capex")
    da_val = _safe(series[-1], "depreciation_amortization")
    mat = None
    if capex_abs is not None and da_val is not None:
        mat = abs(da_val) - abs(capex_abs)
        if mat < 0:
            mat = None

    findings.append({
        "code":           "CF_CAPEX_STARVATION",
        "module":         "cash_flow_quality",
        "pattern":        "Capex starvation",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "capex_to_depreciation",
        "metric_values":  {
            "capex_to_da_latest": round(latest, 2),
            "capex_to_da_first":  round(ratios[0], 2) if len(ratios) > 1 else None,
            "consecutive_below_1": sum(1 for r in ratios if r < 1.0),
        },
        "periods_affected": list(periods[-3:]),
        "trend_direction":  "deteriorating",
        "materiality_brl":  mat,
        "description":      f"{company}: {reason}. Asset base may be shrinking in real terms.",
        "insight":          f"{company}: {reason}.",
    })
    return findings


# =============================================================================
# CF-3: FREE_CASH_FLOW_EROSION
# =============================================================================

def _check_fcf_erosion(series: list, company: str) -> list:
    findings = []

    fcf_vals = [(r["period"][:4], _safe(r, "free_cash_flow")) for r in series
                if _safe(r, "free_cash_flow") is not None]
    if not fcf_vals:
        return findings

    periods, fcf = zip(*fcf_vals)
    latest = fcf[-1]

    # Count consecutive negative periods (from end of series)
    neg_streak = 0
    for v in reversed(fcf):
        if v < 0:
            neg_streak += 1
        else:
            break

    severity = None
    reason = ""
    if neg_streak >= 3:
        severity = "HIGH"
        reason = f"FCF negative for {neg_streak} consecutive periods"
    elif neg_streak >= 2:
        severity = "MEDIUM"
        reason = f"FCF negative for {neg_streak} consecutive periods"
    elif fcf[0] > 0 > latest:
        severity = "MEDIUM"
        reason = f"FCF turned negative (was {fcf[0]:,.0f}K, now {latest:,.0f}K)"
    elif len(fcf) >= 2 and fcf[0] > 0 and latest > 0:
        decline_pct = (latest - fcf[0]) / abs(fcf[0]) * 100
        if decline_pct < -50:
            severity = "MEDIUM"
            reason = f"FCF declined {abs(decline_pct):.0f}% over analysis period"

    if severity is None:
        return findings

    findings.append({
        "code":           "CF_FCF_EROSION",
        "module":         "cash_flow_quality",
        "pattern":        "FCF erosion",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "free_cash_flow",
        "metric_values":  {
            "fcf_latest":         round(latest, 0),
            "fcf_first":          round(fcf[0], 0),
            "consecutive_negative": neg_streak,
        },
        "periods_affected": list(periods[-neg_streak:]) if neg_streak else [periods[-1]],
        "trend_direction":  "deteriorating" if latest < 0 else "stable",
        "materiality_brl":  latest,
        "description":      f"{company}: {reason}.",
        "insight":          f"{company}: {reason}.",
    })
    return findings


# =============================================================================
# CF-4: DEBT_DEPENDENCY
# =============================================================================

def _check_debt_dependency(series: list, company: str) -> list:
    findings = []

    fin_vals = [(r["period"][:4], _safe(r, "financing_cash_flow")) for r in series
                if _safe(r, "financing_cash_flow") is not None]
    ocf_vals = [(r["period"][:4], _safe(r, "operating_cash_flow")) for r in series
                if _safe(r, "operating_cash_flow") is not None]
    if not fin_vals:
        return findings

    periods_fin, fin = zip(*fin_vals)
    ocf_map = {p: v for p, v in ocf_vals}

    # Count consecutive positive financing CF
    pos_streak = 0
    for p, v in zip(reversed(periods_fin), reversed(fin)):
        if v > 0:
            pos_streak += 1
        else:
            break

    if pos_streak < 3:
        # Check if debt_issuance > debt_repayment consistently
        di_exceeds = 0
        for r in series:
            di = _safe(r, "debt_issuance")
            dr = _safe(r, "debt_repayment")
            if di is not None and dr is not None and di > abs(dr):
                di_exceeds += 1
        if di_exceeds < 3:
            return findings

    severity = "MEDIUM"
    reason = f"financing CF positive for {pos_streak} consecutive periods"

    # Escalate if OCF also insufficient
    if pos_streak >= 3:
        ocf_neg_while_fin_pos = sum(
            1 for p, fv in zip(periods_fin[-pos_streak:], fin[-pos_streak:])
            if fv > 0 and (ocf_map.get(p, 0) or 0) < 0
        )
        if ocf_neg_while_fin_pos >= 2:
            severity = "HIGH"
            reason += " while OCF is negative (borrowing to survive)"

    # Materiality: cumulative net borrowing
    cum_fin = sum(v for v in fin if v > 0)

    findings.append({
        "code":           "CF_DEBT_DEPENDENCY",
        "module":         "cash_flow_quality",
        "pattern":        "Debt dependency",
        "severity":       severity,
        "category":       "Supporting",
        "company":        company,
        "metric_name":    "financing_cash_flow",
        "metric_values":  {
            "consecutive_positive_fin": pos_streak,
            "latest_financing_cf": round(fin[-1], 0) if fin else None,
        },
        "periods_affected": list(periods_fin[-pos_streak:]) if pos_streak else [],
        "trend_direction":  "deteriorating",
        "materiality_brl":  cum_fin,
        "description":      f"{company}: {reason}.",
        "insight":          f"{company}: {reason}.",
    })
    return findings


# =============================================================================
# CF-5: DIVIDEND_SUSTAINABILITY
# =============================================================================

def _check_dividend_sustainability(series: list, company: str) -> list:
    findings = []

    div_vals = [_safe(r, "dividends_paid") for r in series if _safe(r, "dividends_paid") is not None]
    if not div_vals or all(v == 0 for v in div_vals):
        return findings  # No dividends paid — skip

    over_count = 0
    neg_fcf_with_div = 0
    for r in series:
        div = _safe(r, "dividends_paid")
        fcf = _safe(r, "free_cash_flow")
        if div is None or fcf is None:
            continue
        if abs(div) > fcf:
            over_count += 1
        if fcf < 0 and abs(div) > 0:
            neg_fcf_with_div += 1

    if over_count < 2 and neg_fcf_with_div < 1:
        return findings

    severity = "HIGH" if (over_count >= 3 or neg_fcf_with_div >= 1) else "MEDIUM"

    # Latest overshoot
    latest_div = _safe(series[-1], "dividends_paid")
    latest_fcf = _safe(series[-1], "free_cash_flow")
    mat = (abs(latest_div) - latest_fcf) if (latest_div is not None and latest_fcf is not None) else None

    findings.append({
        "code":           "CF_DIVIDEND_SUSTAINABILITY",
        "module":         "cash_flow_quality",
        "pattern":        "Dividend sustainability risk",
        "severity":       severity,
        "category":       "Supporting",
        "company":        company,
        "metric_name":    "dividends_paid",
        "metric_values":  {
            "periods_div_exceeds_fcf":   over_count,
            "periods_neg_fcf_with_div":  neg_fcf_with_div,
            "latest_dividends":          round(latest_div, 0) if latest_div is not None else None,
            "latest_fcf":                round(latest_fcf, 0) if latest_fcf is not None else None,
        },
        "periods_affected": [],
        "trend_direction":  "deteriorating",
        "materiality_brl":  mat,
        "description": (
            f"{company}: Dividends exceeded FCF in {over_count} periods"
            + (f"; paid while FCF negative {neg_fcf_with_div}×" if neg_fcf_with_div else "") + "."
        ),
        "insight": (
            f"{company}: Dividends exceeded FCF {over_count}× — unsustainable payout."
        ),
    })
    return findings


# =============================================================================
# CF-6: WORKING_CAPITAL_CASH_DRAIN
# =============================================================================

def _check_wc_cash_drain(series: list, company: str) -> list:
    findings = []

    wc_vals = [(r["period"][:4], _safe(r, "working_capital_change")) for r in series
               if _safe(r, "working_capital_change") is not None]
    ocf_vals = [(r["period"][:4], _safe(r, "operating_cash_flow")) for r in series
                if _safe(r, "operating_cash_flow") is not None]

    if not wc_vals or not ocf_vals:
        return findings  # data not available

    periods_wc, wc = zip(*wc_vals)
    ocf_map = {p: v for p, v in ocf_vals}

    # Count consecutive negative WC change (cash drain)
    neg_streak = sum(1 for v in wc if v < 0)
    neg_from_end = 0
    for v in reversed(wc):
        if v < 0:
            neg_from_end += 1
        else:
            break

    if neg_from_end < 3:
        return findings  # Need 3+ consecutive drain periods

    # Check absorption ratio
    absorb_count = 0
    for p, wv in zip(periods_wc, wc):
        ocf = ocf_map.get(p)
        if ocf is not None and ocf > 0 and wv < 0:
            if abs(wv) > 0.3 * ocf:
                absorb_count += 1

    severity = "HIGH" if (neg_from_end >= 3 and absorb_count >= 2) else "MEDIUM"

    latest_wc_chg = wc[-1]

    findings.append({
        "code":           "CF_WORKING_CAPITAL_DRAIN",
        "module":         "cash_flow_quality",
        "pattern":        "Working capital cash drain",
        "severity":       severity,
        "category":       "Supporting",
        "company":        company,
        "metric_name":    "working_capital_change",
        "metric_values":  {
            "consecutive_drain_periods": neg_from_end,
            "absorption_periods":        absorb_count,
            "latest_wc_change":          round(latest_wc_chg, 0),
        },
        "periods_affected": list(periods_wc[-neg_from_end:]),
        "trend_direction":  "deteriorating",
        "materiality_brl":  latest_wc_chg,
        "description": (
            f"{company}: Working capital change is negative for {neg_from_end} consecutive periods, "
            f"absorbing operating cash flow."
        ),
        "insight": (
            f"{company}: WC change negative {neg_from_end} consecutive periods."
        ),
    })
    return findings


# =============================================================================
# Public API
# =============================================================================

def detect_cf_patterns(cf_series: list, company_name: str) -> list:
    """Run all 6 CF quality algorithms. Returns list of finding dicts."""
    if not cf_series or len(cf_series) < 4:
        return []

    findings = []
    findings += _check_earnings_quality(cf_series, company_name)
    findings += _check_capex_starvation(cf_series, company_name)
    findings += _check_fcf_erosion(cf_series, company_name)
    findings += _check_debt_dependency(cf_series, company_name)
    findings += _check_dividend_sustainability(cf_series, company_name)
    findings += _check_wc_cash_drain(cf_series, company_name)
    return findings
