"""Auditor finding generators — AUD001, AUD002, AUD003.

Takes classified Parecer results and generates structured findings for Step 6.

Public API
----------
detect_auditor_patterns(classifications, company_name) -> list[dict]
    Run all 3 auditor detection algorithms.
    Returns findings with module="auditor".
"""

from __future__ import annotations

import re


_FIRM_SUFFIXES = re.compile(
    r"\b(auditores? independentes?|ltda|s\.?a\.?|s\.?s\.?|eireli|associados?|"
    r"contadores?|consultores?|parceiros?)\b",
    re.IGNORECASE,
)


def _normalize_firm(name: str) -> str:
    """Normalise a firm name for comparison: lowercase, strip legal suffixes."""
    if not name or name == "Unknown":
        return name.lower()
    name = re.sub(r"\([^)]*\)", "", name)   # strip parentheticals e.g. ("KPMG")
    name = _FIRM_SUFFIXES.sub("", name)
    name = re.sub(r"[,.\-\"\']+", " ", name)
    return re.sub(r"\s+", " ", name).strip().lower()


def _short_year(period: str) -> str:
    """'2024-12-31' → 'FY 2024'"""
    try:
        return f"FY {period[:4]}"
    except Exception:
        return period


# =============================================================================
# AUD001 — Going Concern Emphasis
# =============================================================================

def _aud001_going_concern(
    classifications: list[dict], company_name: str
) -> list[dict]:
    gc_periods = [
        c for c in classifications
        if c.get("has_going_concern") is True
    ]
    if not gc_periods:
        return []

    total = len(classifications)
    gc_count = len(gc_periods)
    gc_period_strs = sorted(c["period"] for c in gc_periods)
    latest_period = gc_period_strs[-1] if gc_period_strs else ""
    first_period  = gc_period_strs[0] if gc_period_strs else ""
    latest_year   = latest_period[:4] if latest_period else ""
    all_years     = [_short_year(p) for p in gc_period_strs]
    years_str     = ", ".join(all_years)

    # Use the firm from the latest going-concern period (not the most common overall)
    latest_gc = max(gc_periods, key=lambda c: c["period"])
    auditor_firm = latest_gc.get("auditor_firm") or "Unknown"

    # Trend: is going concern still present in the latest period?
    latest_classification = max(classifications, key=lambda c: c["period"])
    is_current = latest_classification.get("has_going_concern", False)

    # Is this new (first appeared recently)?
    all_sorted = sorted(classifications, key=lambda c: c["period"])
    if len(all_sorted) >= 2:
        earlier_has_gc = any(c.get("has_going_concern") for c in all_sorted[:-1])
        if is_current and not earlier_has_gc:
            gc_trend = "new"
        elif is_current and earlier_has_gc:
            gc_trend = "continuing"
        else:
            gc_trend = "resolved"
    else:
        gc_trend = "new" if is_current else "resolved"

    severity = "CRITICAL" if is_current else "HIGH"
    trend_label = {"new": "emerging", "continuing": "continuing", "resolved": "resolved"}.get(gc_trend, gc_trend)

    description = (
        f"{company_name}: Auditor ({auditor_firm}) included going concern emphasis "
        f"in {gc_count} of {total} reports ({years_str}). "
        f"Independent external validation of financial distress ({trend_label} risk)."
    )
    _trend_label_pt = {"new": "emergente", "continuing": "contínuo", "resolved": "resolvido"}.get(gc_trend, gc_trend)
    description_pt = (
        f"{company_name}: Auditor ({auditor_firm}) incluiu ênfase em continuidade operacional "
        f"em {gc_count} de {total} relatórios ({years_str}). "
        f"Validação externa independente de dificuldades financeiras (risco {_trend_label_pt})."
    )

    return [{
        "finding_id":  "AUD001",
        "algorithm":   "auditor_going_concern",
        "type":        "going_concern",
        "pattern":     "Going concern emphasis",
        "code":        "AUD001",
        "severity":    severity,
        "confidence":  "HIGH",
        "confidence_score": "HIGH",
        "module":      "auditor",
        "company":     company_name,
        "description":    description,
        "description_pt": description_pt,
        "period":      latest_period,
        "category":    "Core",
        "trend_direction": "deteriorating" if is_current else "improving",
        "auditor_firm":         auditor_firm,
        "periods_with_gc":      gc_period_strs,
        "total_periods":        total,
        "first_gc_period":      first_period,
        "latest_gc_period":     latest_period,
        "gc_trend":             gc_trend,
        "gc_count":             gc_count,
        "gc_years":             years_str,
        "latest_year":          latest_year,
    }]


# =============================================================================
# AUD002 — Qualified / Adverse Opinion
# =============================================================================

def _aud002_opinion_qualification(
    classifications: list[dict], company_name: str
) -> list[dict]:
    non_clean = [
        c for c in classifications
        if c.get("opinion_type") in ("com_ressalva", "adverso", "abstencao")
    ]
    findings = []
    for c in non_clean:
        opinion = c["opinion_type"]
        period  = c.get("period", "")
        summary = c.get("opinion_summary", "")
        auditor = c.get("auditor_firm", "Unknown")

        label_map = {
            "com_ressalva": "qualified",
            "adverso":      "adverse",
            "abstencao":    "disclaimer of opinion",
        }
        sev = "CRITICAL" if opinion == "adverso" else "HIGH"
        label = label_map.get(opinion, opinion)
        label_pt_map = {
            "qualified":             "com ressalva",
            "adverse":               "adversa",
            "disclaimer of opinion": "abstenção de opinião",
        }
        label_pt = label_pt_map.get(label, label)

        description = (
            f"{company_name}: Auditor ({auditor}) issued {label} opinion in {_short_year(period)}."
        )
        if summary:
            description += f" {summary}"
        description_pt = (
            f"{company_name}: Auditor ({auditor}) emitiu opinião {label_pt} em {_short_year(period)}."
        )
        if summary:
            description_pt += f" {summary}"

        findings.append({
            "finding_id":  "AUD002",
            "algorithm":   "auditor_opinion_qualification",
            "type":        "opinion_qualification",
            "pattern":     "Qualified/adverse opinion",
            "code":        "AUD002",
            "severity":    sev,
            "confidence":  "HIGH",
            "confidence_score": "HIGH",
            "module":      "auditor",
            "company":     company_name,
            "description":    description,
            "description_pt": description_pt,
            "period":      period,
            "category":    "Core",
            "trend_direction": "deteriorating",
            "opinion_type":  opinion,
            "opinion_label": label,
            "auditor_firm":  auditor,
        })
    return findings


# =============================================================================
# AUD003 — Auditor Change
# =============================================================================

def _aud003_auditor_change(
    classifications: list[dict], company_name: str
) -> list[dict]:
    sorted_cs = sorted(classifications, key=lambda c: c.get("period", ""))
    findings = []
    prev_firm = None
    for c in sorted_cs:
        firm   = c.get("auditor_firm", "Unknown")
        period = c.get("period", "")
        if (
            prev_firm is not None
            and firm != "Unknown"
            and prev_firm != "Unknown"
            and _normalize_firm(firm) != _normalize_firm(prev_firm)
        ):
            description = (
                f"{company_name}: Audit firm changed from {prev_firm} to {firm} "
                f"in {_short_year(period)}. Investigate reason for change."
            )
            description_pt = (
                f"{company_name}: Firma de auditoria mudou de {prev_firm} para {firm} "
                f"em {_short_year(period)}. Investigar motivo da mudança."
            )
            findings.append({
                "finding_id":  "AUD003",
                "algorithm":   "auditor_change_detection",
                "type":        "auditor_change",
                "pattern":     "Auditor change",
                "code":        "AUD003",
                "severity":    "MEDIUM",
                "confidence":  "HIGH",
                "confidence_score": "HIGH",
                "module":      "auditor",
                "company":     company_name,
                "description":    description,
                "description_pt": description_pt,
                "period":      period,
                "category":    "Supporting",
                "trend_direction": "neutral",
                "old_firm":   prev_firm,
                "new_firm":   firm,
            })
        if firm != "Unknown":
            prev_firm = firm
    return findings


# =============================================================================
# AUD004 — Auditor Independence Risk (FRE-based)
# =============================================================================

def _aud004_independence_risk(
    auditor_profiles: list[dict], company_name: str
) -> list[dict]:
    """Detect independence concerns from high non-audit fees or very long tenure.

    Input: list of AuditorProfile dicts from fre_parser.parse_fre_auditor().
    Returns [] when auditor_profiles is empty (graceful degradation).
    """
    if not auditor_profiles:
        return []

    # Use the latest profile
    latest = max(auditor_profiles, key=lambda p: p.get("period", ""))
    firm       = latest.get("firm_name", "Unknown")
    tenure     = latest.get("tenure_years", 0)
    audit_fees = latest.get("audit_fees", 0.0)
    non_audit  = latest.get("non_audit_fees", 0.0)
    ratio      = latest.get("non_audit_ratio", 0.0)
    period     = latest.get("period", "")

    severity = None
    reason = ""
    reason_pt = ""

    if ratio > 1.0:
        severity  = "HIGH"
        reason    = f"non-audit fees ({ratio:.2f}×) exceed audit fees — auditor independence risk"
        reason_pt = f"honorários não-auditoria ({ratio:.2f}×) superam honorários de auditoria — risco à independência do auditor"
    elif ratio > 0.5 and tenure > 10:
        severity  = "HIGH"
        reason    = f"non-audit fees at {ratio:.0%} of audit fees AND tenure {tenure} years — compounded independence signals"
        reason_pt = f"honorários não-auditoria em {ratio:.0%} dos honorários de auditoria E mandato de {tenure} anos — sinais compostos de independência"
    elif ratio > 0.5:
        severity  = "MEDIUM"
        reason    = f"non-audit fees at {ratio:.0%} of audit fees"
        reason_pt = f"honorários não-auditoria em {ratio:.0%} dos honorários de auditoria"
    elif tenure > 10:
        severity  = "MEDIUM"
        reason    = f"{firm} has audited {company_name} for {tenure} consecutive years"
        reason_pt = f"{firm} audita {company_name} por {tenure} anos consecutivos"

    if severity is None:
        return []

    total_fees = audit_fees + non_audit

    return [{
        "finding_id":  "AUD004",
        "algorithm":   "auditor_independence_risk",
        "type":        "independence_risk",
        "pattern":     "Auditor independence risk",
        "code":        "AUD004",
        "severity":    severity,
        "confidence":  "MEDIUM",
        "confidence_score": "MEDIUM",
        "module":      "auditor",
        "company":     company_name,
        "description":    f"{company_name}: {reason}.",
        "description_pt": f"{company_name}: {reason_pt}.",
        "period":         period,
        "category":       "Supporting",
        "trend_direction": "deteriorating" if severity == "HIGH" else "stable",
        "materiality_brl": total_fees,
        "audit_fees":      audit_fees,
        "non_audit_fees":  non_audit,
        "non_audit_ratio": ratio,
        "tenure_years":    tenure,
        "firm_name":       firm,
    }]


# =============================================================================
# AUD005 — Auditor Fee Trend (FRE-based)
# =============================================================================

def _aud005_fee_trend(
    auditor_profiles: list[dict], company_name: str, revenue_series: list[dict] | None = None
) -> list[dict]:
    """Detect significant changes in audit fees over the analysis period.

    Input: list of AuditorProfile dicts from fre_parser.parse_fre_auditor().
    Requires >= 3 years of fee data.
    Returns [] when insufficient data (graceful degradation).
    """
    fee_data = [
        (p["period"], p["audit_fees"])
        for p in sorted(auditor_profiles, key=lambda x: x.get("period", ""))
        if (p.get("audit_fees") or 0) > 0
    ]
    if len(fee_data) < 3:
        return []

    first_period, first_fee = fee_data[0]
    last_period, last_fee = fee_data[-1]
    fee_change_pct = (last_fee - first_fee) / abs(first_fee) * 100 if first_fee else 0

    # Revenue change context (if provided)
    rev_change_pct: float | None = None
    if revenue_series and len(revenue_series) >= 2:
        rev_first = revenue_series[0].get("revenue_abs") or revenue_series[0].get("revenue")
        rev_last  = revenue_series[-1].get("revenue_abs") or revenue_series[-1].get("revenue")
        if rev_first and rev_last and rev_first != 0:
            rev_change_pct = (rev_last - rev_first) / abs(rev_first) * 100

    severity = None
    direction = "stable"
    reason = ""
    reason_pt = ""

    if fee_change_pct > 50 and (rev_change_pct is None or rev_change_pct < 5):
        severity  = "MEDIUM"
        direction = "escalating"
        reason    = f"audit fees grew {fee_change_pct:.0f}% while revenue was flat/declining — scope expansion signal"
        reason_pt = f"honorários cresceram {fee_change_pct:.0f}% enquanto a receita estava estagnada/em queda — sinal de expansão de escopo"
    elif fee_change_pct < -30:
        severity  = "MEDIUM"
        direction = "declining"
        reason    = f"audit fees declined {abs(fee_change_pct):.0f}% — potential scope reduction or fee low-balling"
        reason_pt = f"honorários caíram {abs(fee_change_pct):.0f}% — possível redução de escopo ou baixa de preço"

    if severity is None:
        return []

    return [{
        "finding_id":  "AUD005",
        "algorithm":   "auditor_fee_trend",
        "type":        "fee_trend",
        "pattern":     "Auditor fee trend",
        "code":        "AUD005",
        "severity":    severity,
        "confidence":  "MEDIUM",
        "confidence_score": "MEDIUM",
        "module":      "auditor",
        "company":     company_name,
        "description":    f"{company_name}: {reason}.",
        "description_pt": f"{company_name}: {reason_pt}.",
        "period":         last_period,
        "category":       "Contextual",
        "trend_direction": direction,
        "materiality_brl": last_fee,
        "fee_change_pct":      round(fee_change_pct, 1),
        "revenue_change_pct":  round(rev_change_pct, 1) if rev_change_pct is not None else None,
        "fee_trend_direction": direction,
        "first_period":        first_period,
        "last_period":         last_period,
    }]


# =============================================================================
# Public API
# =============================================================================

def detect_auditor_patterns(
    classifications: list[dict], company_name: str
) -> list[dict]:
    """Run all 3 auditor detection algorithms (Parecer-based).

    Args:
        classifications: Output of classify_parecer().
        company_name: Company name string.

    Returns:
        List of finding dicts with module="auditor".
    """
    if not classifications:
        return []

    findings: list[dict] = []
    findings += _aud001_going_concern(classifications, company_name)
    findings += _aud002_opinion_qualification(classifications, company_name)
    # AUD003 (auditor change) removed — routine event, weak signal.
    return findings


def detect_auditor_fre_patterns(
    auditor_profiles: list[dict],
    company_name: str,
    revenue_series: list[dict] | None = None,
) -> list[dict]:
    """Run FRE-based auditor algorithms (AUD-4, AUD-5).

    Separate from detect_auditor_patterns() so FRE findings are only added
    when FRE data is available. Returns [] when auditor_profiles is empty.
    """
    findings: list[dict] = []
    findings += _aud004_independence_risk(auditor_profiles, company_name)
    findings += _aud005_fee_trend(auditor_profiles, company_name, revenue_series)
    return findings
