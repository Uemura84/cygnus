"""Module 2: Balance Sheet Health Detection.

Receives the balance_sheet_series (list of dicts) from Step 4 and produces
findings with code prefix BS_.

Public API
----------
detect_bs_patterns(bs_series, company_name) -> list[dict]
    Run all 7 balance sheet detection algorithms.
    Returns findings with module="balance_sheet_health".
"""

import numpy as np


def _safe(record: dict, key: str, default=None):
    v = record.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f  # NaN check
    except (TypeError, ValueError):
        return default


def _fmtbrl(v: float | None) -> str:
    if v is None:
        return "N/A"
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        return f"BRL {v/1_000_000:,.1f}B"
    if abs_v >= 1_000:
        return f"BRL {v/1_000:,.0f}M"
    return f"BRL {v:,.0f}K"


# =============================================================================
# BS-1: LEVERAGE_ESCALATION
# =============================================================================

def _check_leverage_escalation(series: list, company: str) -> list:
    findings = []
    de_vals = [(r["period"][:4], _safe(r, "debt_to_ebitda")) for r in series if _safe(r, "debt_to_ebitda") is not None]
    if not de_vals:
        return findings

    periods, values = zip(*de_vals)
    latest = values[-1]
    nd_latest = _safe(series[-1], "net_debt")

    # Threshold triggers
    severity = None
    if latest > 5.0:
        severity = "CRITICAL"
    elif latest > 3.5:
        severity = "HIGH"

    # Trend trigger: increased > 1.0× over last 3 periods
    if severity is None and len(values) >= 3:
        trend_delta = values[-1] - values[-3]
        if trend_delta > 1.0:
            severity = "MEDIUM"

    if severity is None:
        return findings

    # 3-period linear trend
    if len(values) >= 3:
        xs = np.arange(len(values))
        slope = float(np.polyfit(xs, values, 1)[0])
        trend_direction = "deteriorating" if slope > 0 else "improving"
    else:
        trend_direction = "deteriorating"

    findings.append({
        "code":           "BS_LEVERAGE_ESCALATION",
        "module":         "balance_sheet_health",
        "pattern":        "Leverage escalation",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "debt_to_ebitda",
        "metric_values":  {
            "latest_debt_to_ebitda": round(latest, 2),
            "first_debt_to_ebitda":  round(values[0], 2),
            "change":                round(latest - values[0], 2),
        },
        "periods_affected": list(periods[-3:]),
        "trend_direction":  trend_direction,
        "materiality_brl":  nd_latest,
        "description": (
            f"{company}: Debt/EBITDA reached {latest:.1f}× "
            f"(was {values[0]:.1f}× at start). "
            f"{'Critical' if severity == 'CRITICAL' else 'Elevated'} leverage "
            f"{'constrains refinancing capacity' if severity in ('CRITICAL','HIGH') else 'is trending upward'}."
        ),
        "description_pt": (
            f"{company}: Dívida/EBITDA atingiu {latest:.1f}× "
            f"(era {values[0]:.1f}× no início). "
            f"Alavancagem {'crítica' if severity == 'CRITICAL' else 'elevada'} "
            f"{'restringe a capacidade de refinanciamento' if severity in ('CRITICAL','HIGH') else 'com tendência de alta'}."
        ),
        "insight": (
            f"{company}: Debt/EBITDA at {latest:.1f}×."
        ),
    })
    return findings


# =============================================================================
# BS-2: WORKING_CAPITAL_DETERIORATION
# =============================================================================

def _check_working_capital_deterioration(series: list, company: str) -> list:
    findings = []

    def _get_vals(key):
        return [(r["period"][:4], _safe(r, key)) for r in series if _safe(r, key) is not None]

    rd_vals  = _get_vals("receivable_days")
    inv_vals = _get_vals("inventory_days")
    ccc_vals = _get_vals("cash_conversion_cycle")

    signals = []

    if rd_vals:
        _, rd = zip(*rd_vals)
        latest_rd = rd[-1]
        if latest_rd > 120:
            signals.append(("HIGH", f"receivable days={latest_rd:.0f}d (>120)"))
        elif latest_rd > 90:
            signals.append(("MEDIUM", f"receivable days={latest_rd:.0f}d (>90)"))

    if inv_vals and len(inv_vals) >= 2:
        _, inv = zip(*inv_vals)
        inv_chg_pct = (inv[-1] - inv[0]) / abs(inv[0]) * 100 if inv[0] else 0
        if inv_chg_pct > 20:
            signals.append(("MEDIUM", f"inventory days up {inv_chg_pct:.0f}% over period"))

    if ccc_vals and len(ccc_vals) >= 2:
        _, ccc = zip(*ccc_vals)
        ccc_delta = ccc[-1] - ccc[0]
        if ccc_delta > 15:
            signals.append(("MEDIUM", f"CCC expanded {ccc_delta:.0f}d"))

    if not signals:
        return findings

    # Compound trigger
    n_deteriorating = len(signals)
    if n_deteriorating >= 2:
        severity = "HIGH"
    else:
        severity = signals[0][0]

    wc_first = _safe(series[0], "working_capital")
    wc_last  = _safe(series[-1], "working_capital")
    wc_delta = (wc_last - wc_first) if (wc_last is not None and wc_first is not None) else None

    findings.append({
        "code":           "BS_WORKING_CAPITAL_DETERIORATION",
        "module":         "balance_sheet_health",
        "pattern":        "Working capital deterioration",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "cash_conversion_cycle",
        "metric_values":  {
            "receivable_days_latest":  round(rd_vals[-1][1], 1) if rd_vals else None,
            "inventory_days_latest":   round(inv_vals[-1][1], 1) if inv_vals else None,
            "ccc_latest":              round(ccc_vals[-1][1], 1) if ccc_vals else None,
        },
        "periods_affected": [],
        "trend_direction":  "deteriorating",
        "materiality_brl":  wc_delta,
        "description": (
            f"{company}: Working capital under pressure — "
            + "; ".join(s[1] for s in signals) + ". "
            f"{'Multiple sub-metrics deteriorating simultaneously.' if n_deteriorating >= 2 else ''}"
        ),
        "description_pt": (
            f"{company}: Capital de giro sob pressão — "
            + "; ".join(s[1] for s in signals) + ". "
            f"{'Múltiplas sub-métricas deteriorando simultaneamente.' if n_deteriorating >= 2 else ''}"
        ),
        "insight": f"{company}: WC signals: " + "; ".join(s[1] for s in signals),
    })
    return findings


# =============================================================================
# BS-3: LIQUIDITY_STRESS
# =============================================================================

def _check_liquidity_stress(series: list, company: str) -> list:
    findings = []

    cr_vals = [(r["period"][:4], _safe(r, "current_ratio")) for r in series if _safe(r, "current_ratio") is not None]
    qr_vals = [(r["period"][:4], _safe(r, "quick_ratio"))   for r in series if _safe(r, "quick_ratio")   is not None]

    if not cr_vals:
        return findings

    periods_cr, cr = zip(*cr_vals)
    latest_cr = cr[-1]
    wc_val = _safe(series[-1], "working_capital")

    severity = None
    reason = ""
    reason_pt = ""
    if latest_cr < 1.0:
        severity = "HIGH"
        reason    = f"current ratio {latest_cr:.2f} < 1.0 (liabilities exceed current assets)"
        reason_pt = f"índice de liquidez corrente {latest_cr:.2f} < 1,0 (passivos superam os ativos circulantes)"
    elif latest_cr < 1.2:
        severity = "MEDIUM"
        reason    = f"current ratio {latest_cr:.2f} < 1.2 (approaching stress zone)"
        reason_pt = f"índice de liquidez corrente {latest_cr:.2f} < 1,2 (aproximando-se da zona de estresse)"
    elif len(cr) >= 2 and (cr[0] - cr[-1]) > 0.3:
        severity = "MEDIUM"
        reason    = f"current ratio declined {cr[0] - cr[-1]:.2f} over analysis period"
        reason_pt = f"índice de liquidez corrente caiu {cr[0] - cr[-1]:.2f} ao longo do período de análise"

    if severity is None and qr_vals:
        _, qr = zip(*qr_vals)
        if qr[-1] < 0.8 and latest_cr >= 1.0:
            severity = "MEDIUM"
            reason    = f"quick ratio {qr[-1]:.2f} < 0.8 while current ratio looks adequate (inventory masking)"
            reason_pt = f"liquidez seca {qr[-1]:.2f} < 0,8 enquanto o índice corrente parece adequado (estoque mascarando)"

    if severity is None:
        return findings

    findings.append({
        "code":           "BS_LIQUIDITY_STRESS",
        "module":         "balance_sheet_health",
        "pattern":        "Liquidity stress",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "current_ratio",
        "metric_values":  {
            "current_ratio_latest": round(latest_cr, 3),
            "current_ratio_first":  round(cr[0], 3) if len(cr) > 1 else None,
            "quick_ratio_latest":   round(qr_vals[-1][1], 3) if qr_vals else None,
        },
        "periods_affected": list(periods_cr[-2:]),
        "trend_direction":  "deteriorating" if (len(cr) >= 2 and cr[-1] < cr[0]) else "stable",
        "materiality_brl":  wc_val,
        "description":      f"{company}: {reason}.",
        "description_pt":   f"{company}: {reason_pt}.",
        "insight":          f"{company}: {reason}.",
    })

    # Consecutive current_ratio decline streak (from most recent backward)
    cr_list = list(cr)
    streak = 0
    for i in range(len(cr_list) - 1, 0, -1):
        if cr_list[i] < cr_list[i - 1]:
            streak += 1
        else:
            break
    if streak >= 3:
        findings.append({
            "code":           "BS_LIQUIDITY_STRESS_STREAK",
            "module":         "balance_sheet_health",
            "pattern":        "Persistent liquidity deterioration",
            "severity":       "HIGH",
            "category":       "Core",
            "company":        company,
            "metric_name":    "current_ratio",
            "consecutive_decline_periods": streak,
            "from_value":     round(cr_list[-(streak + 1)], 3),
            "to_value":       round(cr_list[-1], 3),
            "periods_affected": list(periods_cr[-(streak + 1):]),
            "trend_direction": "deteriorating",
            "description": (
                f"{company}: Current ratio declined for {streak} consecutive periods "
                f"(from {cr_list[-(streak+1)]:.2f} to {cr_list[-1]:.2f}). "
                f"Persistent liquidity deterioration."
            ),
            "description_pt": (
                f"{company}: Índice de liquidez corrente caiu por {streak} períodos consecutivos "
                f"(de {cr_list[-(streak+1)]:.2f} para {cr_list[-1]:.2f}). "
                f"Deterioração persistente de liquidez."
            ),
            "insight": (
                f"{company}: Current ratio declined for {streak} consecutive periods "
                f"(from {cr_list[-(streak+1)]:.2f} to {cr_list[-1]:.2f})."
            ),
        })

    return findings


# =============================================================================
# BS-4: ASSET_EFFICIENCY_DECLINE
# =============================================================================

def _check_asset_efficiency(series: list, company: str) -> list:
    findings = []

    roa_vals = [(r["period"][:4], _safe(r, "return_on_assets"))  for r in series if _safe(r, "return_on_assets") is not None]
    at_vals  = [(r["period"][:4], _safe(r, "asset_turnover"))    for r in series if _safe(r, "asset_turnover")   is not None]

    signals = []

    if roa_vals and len(roa_vals) >= 3:
        _, roa = zip(*roa_vals)
        xs = np.arange(len(roa))
        slope = float(np.polyfit(xs, roa, 1)[0])
        if slope < -2:  # > 2pp/year decline (annual periods)
            signals.append(f"ROA declining {abs(slope):.1f}pp/period")

    at_delta_pct = None
    if at_vals and len(at_vals) >= 2:
        _, at = zip(*at_vals)
        if at[0] and at[0] != 0:
            at_delta_pct = (at[-1] - at[0]) / abs(at[0]) * 100
            if at_delta_pct < -15:
                signals.append(f"asset turnover down {abs(at_delta_pct):.0f}%")

    if not signals:
        return findings

    severity = "HIGH" if len(signals) >= 2 else "MEDIUM"

    # Materiality: revenue gap if turnover had held constant
    ta_latest = _safe(series[-1], "total_assets")
    mat = None
    if at_delta_pct is not None and ta_latest is not None and at_vals:
        _, at = zip(*at_vals)
        mat = abs(at_delta_pct / 100) * at[0] * ta_latest if at[0] else None

    findings.append({
        "code":           "BS_ASSET_EFFICIENCY_DECLINE",
        "module":         "balance_sheet_health",
        "pattern":        "Asset efficiency decline",
        "severity":       severity,
        "category":       "Supporting",
        "company":        company,
        "metric_name":    "asset_turnover",
        "metric_values":  {
            "roa_latest":          round(roa_vals[-1][1], 2) if roa_vals else None,
            "asset_turnover_latest": round(at_vals[-1][1], 3) if at_vals else None,
            "at_delta_pct":         round(at_delta_pct, 1) if at_delta_pct is not None else None,
        },
        "periods_affected": [],
        "trend_direction":  "deteriorating",
        "materiality_brl":  mat,
        "description": (
            f"{company}: Asset efficiency weakening — "
            + "; ".join(signals) + "."
        ),
        "description_pt": (
            f"{company}: Eficiência de ativos deteriorando — "
            + "; ".join(signals) + "."
        ),
        "insight": f"{company}: " + "; ".join(signals),
    })

    # Consecutive ROA decline streak (from most recent backward)
    if roa_vals and len(roa_vals) >= 3:
        _, roa_list = zip(*roa_vals)
        roa_list = list(roa_list)
        roa_streak = 0
        for i in range(len(roa_list) - 1, 0, -1):
            if roa_list[i] < roa_list[i - 1]:
                roa_streak += 1
            else:
                break
        if roa_streak >= 3:
            roa_periods = [p for p, _ in roa_vals]
            findings.append({
                "code":           "BS_ASSET_EFFICIENCY_STREAK",
                "module":         "balance_sheet_health",
                "pattern":        "Sustained asset efficiency decline",
                "severity":       "MEDIUM",
                "category":       "Supporting",
                "company":        company,
                "metric_name":    "return_on_assets",
                "consecutive_decline_periods": roa_streak,
                "from_value":     round(roa_list[-(roa_streak + 1)], 2),
                "to_value":       round(roa_list[-1], 2),
                "periods_affected": roa_periods[-(roa_streak + 1):],
                "trend_direction": "deteriorating",
                "description": (
                    f"{company}: ROA declined for {roa_streak} consecutive periods "
                    f"(from {roa_list[-(roa_streak+1)]:.1f}% to {roa_list[-1]:.1f}%). "
                    f"Sustained asset efficiency decline."
                ),
                "description_pt": (
                    f"{company}: ROA caiu por {roa_streak} períodos consecutivos "
                    f"(de {roa_list[-(roa_streak+1)]:.1f}% para {roa_list[-1]:.1f}%). "
                    f"Declínio sustentado de eficiência de ativos."
                ),
                "insight": (
                    f"{company}: ROA declined for {roa_streak} consecutive periods "
                    f"(from {roa_list[-(roa_streak+1)]:.1f}% to {roa_list[-1]:.1f}%)."
                ),
            })

    return findings


# =============================================================================
# BS-5: CCC_EXPANSION
# =============================================================================

def _check_ccc_expansion(series: list, company: str) -> list:
    findings = []

    ccc_vals = [(r["period"][:4], _safe(r, "cash_conversion_cycle")) for r in series if _safe(r, "cash_conversion_cycle") is not None]
    if len(ccc_vals) < 2:
        return findings

    periods_ccc, ccc = zip(*ccc_vals)
    delta = ccc[-1] - ccc[0]

    severity = None
    if abs(delta) > 40:
        severity = "HIGH"
    elif abs(delta) > 20:
        severity = "MEDIUM"
    # CCC turning from negative to positive
    elif ccc[0] < 0 <= ccc[-1]:
        severity = "MEDIUM"

    if severity is None:
        return findings

    # Decompose driver
    rd_delta  = _safe(series[-1], "receivable_days", 0) - _safe(series[0], "receivable_days", 0) if series else 0
    inv_delta = _safe(series[-1], "inventory_days",  0) - _safe(series[0], "inventory_days",  0) if series else 0
    pd_delta  = _safe(series[-1], "payable_days",    0) - _safe(series[0], "payable_days",    0) if series else 0

    deltas = {"receivables": rd_delta, "inventory": inv_delta, "payables": -pd_delta}
    driver = max(deltas, key=lambda k: abs(deltas[k]))

    # Materiality: cash tied up
    rev_latest = _safe(series[-1], "revenue_abs") if "revenue_abs" in (series[-1] if series else {}) else None
    mat = abs(delta / 365 * rev_latest) if (rev_latest and rev_latest > 0) else None

    findings.append({
        "code":           "BS_CCC_EXPANSION",
        "module":         "balance_sheet_health",
        "pattern":        "Cash conversion cycle expansion",
        "severity":       severity,
        "category":       "Supporting",
        "company":        company,
        "metric_name":    "cash_conversion_cycle",
        "metric_values":  {
            "ccc_first":   round(ccc[0], 1),
            "ccc_latest":  round(ccc[-1], 1),
            "delta_days":  round(delta, 1),
            "primary_driver": driver,
        },
        "periods_affected": [periods_ccc[0], periods_ccc[-1]],
        "trend_direction":  "deteriorating" if delta > 0 else "improving",
        "materiality_brl":  mat,
        "description": (
            f"{company}: Cash conversion cycle expanded {delta:+.0f} days "
            f"({ccc[0]:.0f}d → {ccc[-1]:.0f}d), primarily driven by {driver}."
        ),
        "description_pt": (
            f"{company}: Ciclo de conversão de caixa expandiu {delta:+.0f} dias "
            f"({ccc[0]:.0f}d → {ccc[-1]:.0f}d), principalmente impulsionado por {driver}."
        ),
        "insight": f"{company}: CCC {ccc[0]:.0f}d → {ccc[-1]:.0f}d ({delta:+.0f}d).",
    })
    return findings


# =============================================================================
# BS-6: DEBT_MATURITY_CONCENTRATION
# =============================================================================

def _check_debt_maturity(series: list, company: str) -> list:
    findings = []

    def _ratios():
        out = []
        for r in series:
            std = _safe(r, "short_term_debt")
            ltd = _safe(r, "long_term_debt")
            if std is None or ltd is None:
                continue
            total = std + ltd
            if total <= 0:
                continue
            out.append((r["period"][:4], std / total, std))
        return out

    ratio_vals = _ratios()
    if not ratio_vals:
        return findings

    periods, ratios, stds = zip(*ratio_vals)
    latest_ratio = ratios[-1]
    latest_std   = stds[-1]

    severity = None
    reason = ""
    reason_pt = ""
    if latest_ratio > 0.6:
        severity  = "HIGH"
        reason    = f"short-term debt is {latest_ratio*100:.0f}% of total debt"
        reason_pt = f"dívida de curto prazo representa {latest_ratio*100:.0f}% da dívida total"
    elif latest_ratio > 0.4:
        severity  = "MEDIUM"
        reason    = f"short-term debt is {latest_ratio*100:.0f}% of total debt (>40%)"
        reason_pt = f"dívida de curto prazo representa {latest_ratio*100:.0f}% da dívida total (>40%)"
    elif len(ratios) >= 2 and (ratios[-1] - ratios[0]) > 0.15:
        severity = "MEDIUM"
        delta_pp  = (ratios[-1] - ratios[0]) * 100
        reason    = f"short-term share increased {delta_pp:.0f}pp over period"
        reason_pt = f"participação de curto prazo aumentou {delta_pp:.0f}pp ao longo do período"

    if severity is None:
        return findings

    findings.append({
        "code":           "BS_DEBT_MATURITY_CONCENTRATION",
        "module":         "balance_sheet_health",
        "pattern":        "Debt maturity concentration",
        "severity":       severity,
        "category":       "Supporting",
        "company":        company,
        "metric_name":    "short_term_debt_ratio",
        "metric_values":  {
            "short_term_ratio_latest": round(latest_ratio, 3),
            "short_term_ratio_first":  round(ratios[0], 3),
        },
        "periods_affected": [periods[-1]],
        "trend_direction":  "deteriorating" if (len(ratios) >= 2 and ratios[-1] > ratios[0]) else "stable",
        "materiality_brl":  latest_std,
        "description":      f"{company}: {reason}. Refinancing risk is elevated.",
        "description_pt":   f"{company}: {reason_pt}. Risco de refinanciamento elevado.",
        "insight":          f"{company}: {reason}.",
    })
    return findings


# =============================================================================
# BS-7: EQUITY_EROSION
# =============================================================================

def _check_equity_erosion(series: list, company: str) -> list:
    findings = []

    eq_vals = [(r["period"][:4], _safe(r, "total_equity")) for r in series if _safe(r, "total_equity") is not None]
    if not eq_vals:
        return findings

    periods_eq, eq = zip(*eq_vals)
    latest_eq = eq[-1]
    first_eq  = eq[0]

    severity = None
    reason = ""
    reason_pt = ""
    if latest_eq < 0:
        severity  = "CRITICAL"
        reason    = f"total equity negative ({_fmtbrl(latest_eq)}) — technically insolvent"
        reason_pt = f"patrimônio líquido negativo ({_fmtbrl(latest_eq)}) — tecnicamente insolvente"
    elif first_eq and first_eq > 0:
        chg_pct = (latest_eq - first_eq) / abs(first_eq) * 100
        if chg_pct < -40:
            severity  = "HIGH"
            reason    = f"equity declined {abs(chg_pct):.0f}% over analysis period"
            reason_pt = f"patrimônio líquido caiu {abs(chg_pct):.0f}% ao longo do período de análise"
        elif chg_pct < -20:
            severity  = "MEDIUM"
            reason    = f"equity declined {abs(chg_pct):.0f}% over analysis period"
            reason_pt = f"patrimônio líquido caiu {abs(chg_pct):.0f}% ao longo do período de análise"

    if severity is None:
        return findings

    equity_change = latest_eq - first_eq

    findings.append({
        "code":           "BS_EQUITY_EROSION",
        "module":         "balance_sheet_health",
        "pattern":        "Equity erosion",
        "severity":       severity,
        "category":       "Core",
        "company":        company,
        "metric_name":    "total_equity",
        "metric_values":  {
            "equity_first":   round(first_eq, 0),
            "equity_latest":  round(latest_eq, 0),
            "equity_change":  round(equity_change, 0),
        },
        "periods_affected": [periods_eq[0], periods_eq[-1]],
        "trend_direction":  "deteriorating" if latest_eq < first_eq else "improving",
        "materiality_brl":  equity_change,
        "description":      f"{company}: {reason}.",
        "description_pt":   f"{company}: {reason_pt}.",
        "insight":          f"{company}: {reason}.",
    })
    return findings


# =============================================================================
# BS-8: DEBT_MATURITY_WALL (FRE-based)
# =============================================================================

def _check_fre_maturity_wall(foreign_bonds: list, company: str) -> list:
    """Detect dangerous near-term concentration of foreign bond maturities.

    Input: list of ForeignBondObligation dicts from fre_parser.parse_fre_foreign_bonds().
    Returns [] when called with an empty list (graceful degradation).
    """
    if not foreign_bonds:
        return []

    from datetime import date as _date

    today = _date.today()
    total = sum(b.get("outstanding_amount", 0) or 0 for b in foreign_bonds)
    if total <= 0:
        return []

    buckets = {"<1yr": 0.0, "1-2yr": 0.0, "2-3yr": 0.0, "3-5yr": 0.0, ">5yr": 0.0, "Indet": 0.0}
    maturity_year_counts: dict[str, float] = {}

    for b in foreign_bonds:
        amt = b.get("outstanding_amount", 0) or 0
        mat = b.get("maturity_date", "Indeterminado")
        if mat == "Indeterminado":
            buckets["Indet"] += amt
            continue
        try:
            mat_date = _date.fromisoformat(mat[:10])
            years_to = (mat_date - today).days / 365.25
            yr_str = str(mat_date.year)
            maturity_year_counts[yr_str] = maturity_year_counts.get(yr_str, 0) + amt
            if years_to < 1:
                buckets["<1yr"] += amt
            elif years_to < 2:
                buckets["1-2yr"] += amt
            elif years_to < 3:
                buckets["2-3yr"] += amt
            elif years_to < 5:
                buckets["3-5yr"] += amt
            else:
                buckets[">5yr"] += amt
        except Exception:
            buckets["Indet"] += amt

    near_term = buckets["<1yr"] + buckets["1-2yr"]
    near_term_pct = near_term / total * 100

    # Largest single-year concentration
    largest_yr = max(maturity_year_counts, key=lambda k: maturity_year_counts[k], default=None)
    largest_yr_pct = (maturity_year_counts[largest_yr] / total * 100) if largest_yr else 0.0

    findings = []

    # Near-term concentration trigger
    severity = None
    if near_term_pct > 50:
        severity = "HIGH"
    elif near_term_pct > 35:
        severity = "MEDIUM"
    elif largest_yr_pct > 30:
        severity = "HIGH"

    if severity:
        bucket_pcts = {k: round(v / total * 100, 1) for k, v in buckets.items()}
        period = foreign_bonds[0].get("period", "") if foreign_bonds else ""
        desc = (
            f"{company}: {near_term_pct:.0f}% of foreign bond debt "
            f"({_fmtbrl(near_term)}) matures within 2 years. "
            f"Refinancing concentration risk (FRE foreign bonds only)."
        )
        desc_pt = (
            f"{company}: {near_term_pct:.0f}% da dívida em títulos externos "
            f"({_fmtbrl(near_term)}) vence em 2 anos. "
            f"Risco de concentração de refinanciamento (apenas títulos externos do FRE)."
        )
        findings.append({
            "code":              "BS_MATURITY_WALL",
            "module":            "balance_sheet_health",
            "pattern":           "Foreign debt maturity wall",
            "severity":          severity,
            "category":          "Core",
            "company":           company,
            "metric_name":       "near_term_foreign_debt_pct",
            "metric_values": {
                "near_term_pct":     round(near_term_pct, 1),
                "near_term_amount":  near_term,
                "total_foreign_debt": total,
                "bucket_pcts":       bucket_pcts,
                "largest_single_year":     largest_yr,
                "largest_single_year_pct": round(largest_yr_pct, 1),
            },
            "period":            period,
            "periods_affected":  [period],
            "trend_direction":   "deteriorating",
            "materiality_brl":   near_term,
            "description":       desc,
            "description_pt":    desc_pt,
            "insight":           f"{company}: {near_term_pct:.0f}% of foreign bonds mature within 2 years.",
        })

    return findings


# =============================================================================
# BS-9: FX_DEBT_CONCENTRATION (FRE-based)
# =============================================================================

def _check_fre_fx_concentration(
    foreign_bonds: list, company: str, bs_total_debt: float | None = None
) -> list:
    """Detect excessive foreign-currency debt exposure.

    All titulo_exterior bonds are treated as USD-denominated (no Moeda column present).
    fx_pct is computed relative to bs_total_debt when provided; otherwise the finding
    is informational (MEDIUM) reporting the absolute amount.

    Returns [] when called with an empty list (graceful degradation).
    """
    if not foreign_bonds:
        return []

    fx_total = sum(b.get("outstanding_amount", 0) or 0 for b in foreign_bonds)
    if fx_total <= 0:
        return []

    period             = foreign_bonds[0].get("period", "") if foreign_bonds else ""
    currency_breakdown = {"USD": round(fx_total, 0)}

    # Compute severity using spec thresholds when total debt is known
    if bs_total_debt and bs_total_debt > 0:
        fx_pct = fx_total / bs_total_debt * 100
        if fx_pct > 50:
            severity = "HIGH"
        elif fx_pct > 30:
            severity = "MEDIUM"
        else:
            severity = "LOW"
        fx_pct_str = f"{fx_pct:.0f}%"
    else:
        # No total debt available — report amount only
        fx_pct     = None
        severity   = "MEDIUM"
        fx_pct_str = "unknown % of total"

    desc = (
        f"{company}: {_fmtbrl(fx_total)} in USD-denominated foreign bonds "
        f"({fx_pct_str} of total debt, {len(foreign_bonds)} instruments). "
        f"Direct FX exposure to BRL depreciation."
    )
    desc_pt = (
        f"{company}: {_fmtbrl(fx_total)} em títulos externos denominados em USD "
        f"({fx_pct_str} da dívida total, {len(foreign_bonds)} instrumentos). "
        f"Exposição cambial direta à depreciação do BRL."
    )

    return [{
        "code":          "BS_FX_DEBT_CONCENTRATION",
        "module":        "balance_sheet_health",
        "pattern":       "Foreign currency debt exposure",
        "severity":      severity,
        "category":      "Supporting",
        "company":       company,
        "metric_name":   "fx_debt_pct",
        "metric_values": {
            "fx_amount":          fx_total,
            "fx_pct":             round(fx_pct, 1) if fx_pct is not None else None,
            "currency_breakdown": currency_breakdown,
            "dominant_currency":  "USD",
            "bond_count":         len(foreign_bonds),
        },
        "period":           period,
        "periods_affected": [period],
        "trend_direction":  "deteriorating",
        "materiality_brl":  fx_total,
        "description":    desc,
        "description_pt": desc_pt,
        "insight": f"{company}: {_fmtbrl(fx_total)} USD-denominated foreign bonds ({fx_pct_str} of total debt).",
    }]


# =============================================================================
# Public API
# =============================================================================

def detect_bs_patterns(bs_series: list, company_name: str) -> list:
    """Run all 7 BS health algorithms. Returns list of finding dicts."""
    if not bs_series or len(bs_series) < 4:
        return []

    findings = []
    findings += _check_leverage_escalation(bs_series, company_name)
    findings += _check_working_capital_deterioration(bs_series, company_name)
    findings += _check_liquidity_stress(bs_series, company_name)
    findings += _check_asset_efficiency(bs_series, company_name)
    findings += _check_ccc_expansion(bs_series, company_name)
    findings += _check_debt_maturity(bs_series, company_name)
    findings += _check_equity_erosion(bs_series, company_name)
    return findings


def detect_bs_fre_patterns(
    foreign_bonds: list, company_name: str, bs_total_debt: float | None = None
) -> list:
    """Run FRE-based BS algorithms (BS-8, BS-9). Returns list of finding dicts.

    Separate from detect_bs_patterns() so FRE findings are only added
    when FRE data is available. Returns [] when foreign_bonds is empty.

    Args:
        foreign_bonds:  Output of parse_fre_foreign_bonds().
        company_name:   Company name string.
        bs_total_debt:  Balance sheet total debt (BRL thousands) for BS-9 fx_pct
                        computation. When None, BS-9 reports the absolute amount
                        as MEDIUM without threshold-based severity.
    """
    findings = []
    findings += _check_fre_maturity_wall(foreign_bonds, company_name)
    findings += _check_fre_fx_concentration(foreign_bonds, company_name, bs_total_debt=bs_total_debt)
    return findings
