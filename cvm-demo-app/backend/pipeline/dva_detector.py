"""Module 5: DVA Value Distribution Detection.

Receives dva_series (list of dicts from step4 _build_dva_series) and produces
findings with code prefix DVA_.

Public API
----------
detect_dva_patterns(dva_series, company_name) -> list[dict]
    Returns findings with module="value_distribution".
"""

import numpy as np


def _va_denominator_check(series: list, share_key: str, abs_key: str) -> dict:
    """Check whether a share-shift finding is driven by total VA collapse/expansion.

    Returns a dict with:
        denominator_driven: bool
        va_change_pct: float | None
        abs_change_pct: float | None
        override_severity: str | None  — None means keep original severity
        override_label_en: str | None
        override_label_pt: str | None
    """
    # Extract total VA series (required field in dva_series)
    va_vals  = [_safe(r, "total_va") for r in series]
    abs_vals = [_safe(r, abs_key)    for r in series]

    va_clean  = [v for v in va_vals  if v is not None]
    abs_clean = [v for v in abs_vals if v is not None]

    if len(va_clean) < 2 or len(abs_clean) < 2:
        return {"denominator_driven": False, "va_change_pct": None,
                "abs_change_pct": None, "override_severity": None,
                "override_label_en": None, "override_label_pt": None}

    mid_va  = len(va_clean)  // 2
    mid_abs = len(abs_clean) // 2
    va_first_half  = float(np.mean(va_clean[:mid_va]))
    va_second_half = float(np.mean(va_clean[mid_va:]))
    abs_first_half  = float(np.mean([abs(v) for v in abs_clean[:mid_abs]]))
    abs_second_half = float(np.mean([abs(v) for v in abs_clean[mid_abs:]]))

    va_change_pct  = (va_second_half  - va_first_half)  / abs(va_first_half)  * 100 if va_first_half  else None
    abs_change_pct = (abs_second_half - abs_first_half) / abs(abs_first_half) * 100 if abs_first_half else None

    if va_change_pct is None or abs(va_change_pct) <= 40:
        return {"denominator_driven": False, "va_change_pct": va_change_pct,
                "abs_change_pct": abs_change_pct, "override_severity": None,
                "override_label_en": None, "override_label_pt": None}

    # Total VA changed >40%; check whether absolute amount also moved
    abs_stable = abs_change_pct is None or abs(abs_change_pct) < 15
    va_direction = "collapse" if va_change_pct < 0 else "expansion"
    va_direction_pt = "colapso" if va_change_pct < 0 else "expansão"

    if abs_stable:
        abs_desc_en = f"absolute compensation stable ({abs_change_pct:.0f}%)" if abs_change_pct is not None else "absolute compensation stable"
        abs_desc_pt = f"compensação absoluta estável ({abs_change_pct:.0f}%)" if abs_change_pct is not None else "compensação absoluta estável"
        return {
            "denominator_driven": True,
            "va_change_pct":    round(va_change_pct, 1),
            "abs_change_pct":   round(abs_change_pct, 1) if abs_change_pct is not None else None,
            "override_severity":  "LOW",
            "override_label_en": f"Share shift driven by value added {va_direction} — {abs_desc_en}",
            "override_label_pt": f"Variação de participação causada por {va_direction_pt} do valor adicionado — {abs_desc_pt}",
        }
    # Both share AND absolute amount moved — keep original severity
    return {
        "denominator_driven": False,
        "va_change_pct":    round(va_change_pct, 1),
        "abs_change_pct":   round(abs_change_pct, 1) if abs_change_pct is not None else None,
        "override_severity":  None,
        "override_label_en": None,
        "override_label_pt": None,
    }


def _safe(record: dict, key: str, default=None):
    v = record.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f  # NaN check
    except (TypeError, ValueError):
        return default


def _pct_fmt(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v:.1f}%"


# =============================================================================
# DVA-1: LENDER_SHARE_ESCALATION
# Lenders' share of value distributed has been rising — signals that creditors
# are capturing an increasing fraction of the value the company creates.
# =============================================================================

def _check_lender_share_escalation(series: list, company: str) -> list:
    findings = []
    vals = [(r["period"][:4], _safe(r, "lenders_share_pct")) for r in series
            if _safe(r, "lenders_share_pct") is not None]
    if len(vals) < 3:
        return findings

    periods, values = zip(*vals)
    values = list(values)

    # Linear trend
    x = np.arange(len(values), dtype=float)
    slope = np.polyfit(x, values, 1)[0]
    current = values[-1]
    first_half_avg = float(np.mean(values[:len(values)//2]))
    second_half_avg = float(np.mean(values[len(values)//2:]))
    shift_pp = second_half_avg - first_half_avg

    severity = None
    if shift_pp > 8 or current > 30:
        severity = "HIGH"
    elif shift_pp > 4 or current > 20:
        severity = "MEDIUM"

    if severity:
        denom = _va_denominator_check(series, "lenders_share_pct", "lenders_abs")
        final_severity = denom["override_severity"] or severity
        description_en = (
            denom["override_label_en"] or
            f"Lenders' share of value distributed rose from "
            f"{_pct_fmt(first_half_avg)} to {_pct_fmt(second_half_avg)} "
            f"(+{shift_pp:.1f}pp). Current: {_pct_fmt(current)}. "
            f"Creditors are claiming a growing share of created value."
        )
        description_pt = (
            denom["override_label_pt"] or
            f"A participação dos credores no valor distribuído subiu de "
            f"{_pct_fmt(first_half_avg)} para {_pct_fmt(second_half_avg)} "
            f"(+{shift_pp:.1f}pp). Atual: {_pct_fmt(current)}. "
            f"Credores capturam parcela crescente do valor gerado."
        )
        findings.append({
            "code":        "DVA_LENDER_SHARE_ESCALATION",
            "pattern":     "Lender share escalation",
            "module":      "value_distribution",
            "company":     company,
            "severity":    final_severity,
            "description": description_en,
            "description_pt": description_pt,
            "metric_name":  "lenders_share_pct",
            "first_half_avg": round(first_half_avg, 2),
            "second_half_avg": round(second_half_avg, 2),
            "shift_pp":     round(shift_pp, 2),
            "current":      round(current, 2),
            "periods":      list(periods),
            "values":       [round(v, 2) for v in values],
            "trend_direction": "deteriorating",
            "category":    "Supporting",
            "denominator_driven": denom["denominator_driven"],
            "va_change_pct":     denom["va_change_pct"],
            "abs_change_pct":    denom.get("abs_change_pct"),
        })
    return findings


# =============================================================================
# DVA-2: SHAREHOLDER_VALUE_EROSION
# Shareholders are receiving a declining or negative share of distributed value.
# Negative = loss allocated to equity — company is value-destructive.
# =============================================================================

def _check_shareholder_value_erosion(series: list, company: str) -> list:
    findings = []
    vals = [(r["period"][:4], _safe(r, "shareholders_share_pct")) for r in series
            if _safe(r, "shareholders_share_pct") is not None]
    if len(vals) < 2:
        return findings

    periods, values = zip(*vals)
    values = list(values)
    current = values[-1]
    prior   = values[-2]

    denom = _va_denominator_check(series, "shareholders_share_pct", "shareholders_abs")

    # Trigger 1: currently negative (shareholders absorbing losses)
    if current < 0:
        severity = "HIGH" if current < -20 else "MEDIUM"
        final_severity = denom["override_severity"] or severity
        desc_en = (
            denom["override_label_en"] or
            f"Shareholders' share of distributed value is {_pct_fmt(current)}, "
            f"indicating losses allocated to equity. "
            f"The company is distributing value to all other stakeholders "
            f"while equity holders absorb the shortfall."
        )
        desc_pt = (
            denom["override_label_pt"] or
            f"A participação dos acionistas no valor distribuído é {_pct_fmt(current)}, "
            f"indicando perdas alocadas ao patrimônio líquido. "
            f"A empresa distribui valor a todos os demais stakeholders "
            f"enquanto os acionistas absorvem o déficit."
        )
        findings.append({
            "code":        "DVA_SHAREHOLDER_VALUE_EROSION",
            "pattern":     "Shareholder value erosion",
            "module":      "value_distribution",
            "company":     company,
            "severity":    final_severity,
            "description": desc_en,
            "description_pt": desc_pt,
            "metric_name": "shareholders_share_pct",
            "current":     round(current, 2),
            "prior":       round(prior, 2),
            "periods":     list(periods),
            "values":      [round(v, 2) for v in values],
            "trend_direction": "deteriorating",
            "category":    "Core",
            "denominator_driven": denom["denominator_driven"],
            "va_change_pct":     denom["va_change_pct"],
            "abs_change_pct":    denom.get("abs_change_pct"),
        })
        return findings

    # Trigger 2: significant YoY decline (≥15pp in latest period)
    if len(values) >= 2:
        decline = prior - current
        if decline >= 15:
            severity = "HIGH" if decline >= 25 else "MEDIUM"
            final_severity = denom["override_severity"] or severity
            desc_en = (
                denom["override_label_en"] or
                f"Shareholders' share of distributed value fell {decline:.1f}pp "
                f"from {_pct_fmt(prior)} to {_pct_fmt(current)}. "
                f"Equity holders are capturing a materially smaller share of value created."
            )
            desc_pt = (
                denom["override_label_pt"] or
                f"Participação dos acionistas caiu {decline:.1f}pp "
                f"de {_pct_fmt(prior)} para {_pct_fmt(current)}. "
                f"Acionistas capturam parcela menor do valor criado."
            )
            findings.append({
                "code":        "DVA_SHAREHOLDER_VALUE_EROSION",
                "module":      "value_distribution",
                "company":     company,
                "severity":    final_severity,
                "description": desc_en,
                "description_pt": desc_pt,
                "metric_name": "shareholders_share_pct",
                "current":     round(current, 2),
                "prior":       round(prior, 2),
                "decline_pp":  round(decline, 2),
                "periods":     list(periods),
                "values":      [round(v, 2) for v in values],
                "trend_direction": "deteriorating",
                "category":    "Supporting",
                "denominator_driven": denom["denominator_driven"],
                "va_change_pct":     denom["va_change_pct"],
                "abs_change_pct":    denom.get("abs_change_pct"),
            })
    return findings


# =============================================================================
# DVA-3: LABOR_COMPRESSION
# Employees' share is declining while total value distributed grows —
# suggests productivity gains are not being shared with the workforce,
# or headcount reduction / wage suppression.
# =============================================================================

def _check_labor_compression(series: list, company: str) -> list:
    findings = []
    emp_vals = [(r["period"][:4], _safe(r, "employees_share_pct")) for r in series
                if _safe(r, "employees_share_pct") is not None]
    if len(emp_vals) < 3:
        return findings

    periods, emp_shares = zip(*emp_vals)
    emp_shares = list(emp_shares)

    x = np.arange(len(emp_shares), dtype=float)
    slope = float(np.polyfit(x, emp_shares, 1)[0])

    first_half = emp_shares[:len(emp_shares)//2]
    second_half = emp_shares[len(emp_shares)//2:]
    shift_pp = float(np.mean(second_half)) - float(np.mean(first_half))

    if shift_pp < -5 or (slope < -1.5 and shift_pp < -3):
        severity = "HIGH" if shift_pp < -10 else "MEDIUM"
        denom = _va_denominator_check(series, "employees_share_pct", "employees_abs")
        final_severity = denom["override_severity"] or severity
        description_en = (
            denom["override_label_en"] or
            f"Employees' share of distributed value declined {abs(shift_pp):.1f}pp "
            f"(from {_pct_fmt(float(np.mean(first_half)))} to "
            f"{_pct_fmt(float(np.mean(second_half)))}). "
            f"Labor is capturing a shrinking fraction of total value created."
        )
        description_pt = (
            denom["override_label_pt"] or
            f"Participação dos empregados no valor distribuído caiu {abs(shift_pp):.1f}pp "
            f"(de {_pct_fmt(float(np.mean(first_half)))} para "
            f"{_pct_fmt(float(np.mean(second_half)))}). "
            f"Mão de obra captura parcela menor do valor total criado."
        )
        findings.append({
            "code":        "DVA_LABOR_COMPRESSION",
            "pattern":     "Labor share compression",
            "module":      "value_distribution",
            "company":     company,
            "severity":    final_severity,
            "description": description_en,
            "description_pt": description_pt,
            "metric_name": "employees_share_pct",
            "shift_pp":    round(shift_pp, 2),
            "slope":       round(slope, 4),
            "periods":     list(periods),
            "values":      [round(v, 2) for v in emp_shares],
            "trend_direction": "deteriorating",
            "category":    "Contextual",
            "denominator_driven": denom["denominator_driven"],
            "va_change_pct":     denom["va_change_pct"],
            "abs_change_pct":    denom.get("abs_change_pct"),
        })
    return findings


# =============================================================================
# Public API
# =============================================================================

def detect_dva_patterns(dva_series: list, company_name: str) -> list:
    """Run all DVA detection algorithms.

    *dva_series* is the annual list from step4 _build_dva_series().
    Returns findings with module="value_distribution".
    """
    if not dva_series:
        return []

    findings: list = []
    findings.extend(_check_lender_share_escalation(dva_series, company_name))
    findings.extend(_check_shareholder_value_erosion(dva_series, company_name))
    findings.extend(_check_labor_compression(dva_series, company_name))
    return findings
