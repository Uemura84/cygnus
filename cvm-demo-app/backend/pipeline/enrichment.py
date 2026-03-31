"""Enrichment layer — composite signal engine and risk scoring.

All analytical logic is ported verbatim from 02_pattern_discovery.py.

Public API
----------
enrich(findings, df) -> dict
    Step 7: build composite signals, score company risk, return enriched data dict.
"""

from collections import defaultdict

import pandas as pd


# Sector map for peer comparison — only companies in the same sector are compared.
# Keys are uppercase name fragments matching DENOM_CIA values.
SECTOR_MAP = {
    "BRASKEM":   "Petrochemical",
    "UNIPAR":    "Petrochemical",
    "ELEKEIROZ": "Petrochemical",
    "SUZANO":    "Pulp & Paper",
    "GERDAU":    "Steel",
    "VALE":      "Mining",
}

# Macro context lookup — maps year-halves to key economic events.
MACRO_CONTEXT = {
    "2020-H1": "COVID-19 demand collapse — industrial output down globally",
    "2020-H2": "COVID recovery — fiscal stimulus, demand rebound in China",
    "2021-H1": "Post-COVID demand surge — commodity supercycle begins",
    "2021-H2": "Commodity supercycle peak — naphtha/ethylene at multi-year highs",
    "2022-H1": "Ukraine war — energy spike, Brent >$100/bbl; naphtha cost surge",
    "2022-H2": "Global tightening cycle — Fed raises 400bps, demand destruction begins",
    "2023-H1": "Post-war normalization — petrochemical margins under China oversupply pressure",
    "2023-H2": "China restart — polyethylene/PVC export pressure intensifies",
    "2024-H1": "Fiscal uncertainty — BRL weakness adds import cost pressure",
    "2024-H2": "Commodity cycle trough — petrochemical spreads at cycle lows",
    "2025-H1": "Potential recovery — monitor spread recovery and demand rebound signals",
}


# =============================================================================
# Composite Signal Engine helpers
# =============================================================================

# Maps legacy anomaly_type strings (written before the unified DQ taxonomy) to their
# current equivalents. Used by normalize_findings() for backward compatibility.
_LEGACY_ANOMALY_TYPE_MAP: dict = {
    "likely_data_artifact":    "DATA_ISSUE",
    "likely_structural_shift": "VALID_SIGNAL",
    "likely_one_time_event":   "LOW_CONFIDENCE_SIGNAL",
}


def normalize_findings(findings: list) -> list:
    """Return a normalized, filtered copy of findings for composite signal building.

    1. Filters out SUMMARY-severity findings and Company Narrative entries.
    2. Migrates legacy anomaly_type strings to the current unified DQ taxonomy.
    """
    normalized = []
    for f in findings:
        if f.get("severity") == "SUMMARY" or f.get("pattern") == "Company Narrative":
            continue
        norm = dict(f)
        legacy = _LEGACY_ANOMALY_TYPE_MAP.get(norm.get("anomaly_type", ""))
        if legacy:
            norm["anomaly_type"] = legacy
        normalized.append(norm)
    return normalized


def _compute_composite_confidence(base_confidence: str, supporting_findings: list) -> str:
    """Downgrade composite confidence based on supporting findings' data quality.

    Rules (applied in priority order):
    - If ALL supporting findings have confidence_score 'LOW' → return 'LOW'
    - If more than half have confidence_score 'LOW' → cap at 'MEDIUM'
    - Otherwise → return base_confidence unchanged
    """
    if not supporting_findings:
        return base_confidence
    scores    = [f.get("confidence_score", "MEDIUM") for f in supporting_findings]
    low_count = sum(1 for s in scores if s == "LOW")
    if low_count == len(scores):
        return "LOW"
    if low_count > len(scores) / 2:
        return "MEDIUM" if base_confidence == "HIGH" else base_confidence
    return base_confidence


def explain_composite_signal(
    signal_type: str,
    company: str,
    supporting_findings: list,
    sector_context: dict = None,
) -> tuple:
    """Generate (explanation, recommended_investigation_angle) for a composite signal."""
    ctx = sector_context or {}

    if signal_type == "STRUCTURAL_COMPETITIVENESS_ISSUE":
        drift      = [f for f in supporting_findings if f.get("pattern") == "Cost composition drift"]
        comp       = [f for f in supporting_findings if f.get("pattern") == "Margin compression"]
        shift_pp   = max((f.get("shift_pp", 0) or 0 for f in drift), default=0)
        annual_chg = min((f.get("annual_change_pp", 0) or 0 for f in comp), default=0)
        return (
            f"{company} shows rising COGS burden (+{shift_pp:.1f}pp shift) "
            f"alongside margin compression ({annual_chg:.1f}pp/year). "
            f"The simultaneous cost increase and margin deterioration points to a "
            f"structural competitiveness problem rather than a one-time event.",
            "Benchmark cost structure vs peers at sub-account level. "
            "Decompose COGS into raw materials, labor, and overhead to identify the primary driver.",
        )

    if signal_type == "NEGATIVE_OPERATING_LEVERAGE":
        decouple = [f for f in supporting_findings if f.get("pattern") == "Revenue-cost decoupling"]
        worst    = max(decouple, key=lambda f: abs(f.get("divergence_pp", 0) or 0), default={})
        rev_chg  = worst.get("revenue_change_pct", 0) or 0
        cogs_chg = worst.get("cogs_change_pct", 0) or 0
        return (
            f"{company} exhibits negative operating leverage: revenue changed {rev_chg:+.1f}% "
            f"while COGS changed {cogs_chg:+.1f}% in the worst period, amplifying margin compression. "
            f"Fixed cost structure is not providing the expected leverage on revenue growth.",
            "Decompose COGS into fixed vs variable components. "
            "Assess whether fixed cost absorption is declining due to volume or utilization changes.",
        )

    if signal_type == "SECTOR_CYCLE_PRESSURE":
        n_with  = ctx.get("peers_with_compression", 0)
        n_total = ctx.get("n_peers", 1)
        return (
            f"{company} margin compression appears sector-wide, with "
            f"{n_with} of {n_total - 1} peers also showing compression. "
            f"This is consistent with a cyclical sector downturn rather than a company-specific issue.",
            "Monitor commodity spread recovery. "
            "Compare relative margin performance to assess if company is outperforming or underperforming the cycle.",
        )

    if signal_type == "NON_RECURRING_EVENT":
        periods      = sorted({f.get("period", "") for f in supporting_findings if f.get("period")})
        period_label = ", ".join(periods) if periods else "flagged periods"
        return (
            f"{company} shows isolated statistical anomalies ({period_label}) "
            f"without underlying trend deterioration. "
            f"No sustained margin compression or cost drift accompanies these spikes, "
            f"suggesting a non-recurring event (e.g., write-off, one-time charge).",
            "Review quarterly filings for the flagged periods to identify specific one-time items. "
            "Confirm the anomaly does not recur in subsequent periods.",
        )

    if signal_type == "RELATIVE_OUTPERFORMANCE":
        has_exp = any(f.get("pattern") == "Margin expansion" for f in supporting_findings)
        return (
            f"{company} is outperforming sector peers on key metrics "
            f"{'with expanding margins reinforcing the advantage' if has_exp else 'while maintaining stable margins'}. "
            f"This may indicate superior operational efficiency, pricing power, or product mix advantages.",
            "Investigate the source of competitive advantage. "
            "Assess sustainability: is it structural (cost position, scale) or temporary (pricing cycle)?",
        )

    if signal_type == "RELATIVE_UNDERPERFORMANCE":
        return (
            f"{company} is underperforming vs sector peers while experiencing margin compression, "
            f"in a period where sector-wide pressure does not explain the gap. "
            f"This points to a company-specific operational or strategic issue.",
            "Investigate company-specific cost drivers, pricing strategy, and operational efficiency. "
            "Compare product mix and capacity utilization with outperforming peers.",
        )

    if signal_type == "COST_INFLATION_PRESSURE":
        drift    = [f for f in supporting_findings if f.get("pattern") == "Cost composition drift"]
        shift_pp = max((f.get("shift_pp", 0) or 0 for f in drift), default=0)
        return (
            f"{company} faces cost inflation pressure: COGS burden is rising (+{shift_pp:.1f}pp) "
            f"and costs are growing faster than revenue. "
            f"Margins have not yet compressed significantly, but pressure is building.",
            "Monitor input cost hedging and pricing pass-through ability. "
            "Assess whether current pricing can absorb further cost increases before margin impact becomes severe.",
        )

    if signal_type == "RECOVERY_SIGNAL":
        has_yoy = any(f.get("pattern") == "YoY quarter comparison" for f in supporting_findings)
        has_dec = any(f.get("pattern") == "Revenue-cost decoupling" for f in supporting_findings)
        detail  = (
            "favorable YoY comparison and improving cost-revenue dynamics"
            if (has_yoy and has_dec)
            else "improving trends in revenue-cost dynamics or YoY comparison"
        )
        return (
            f"{company} shows recovery signals: margin expansion is accompanied by {detail}. "
            f"Early recovery from prior compression cycle may be underway.",
            "Assess whether recovery is driven by pricing recovery, volume growth, or cost reduction. "
            "Monitor sustainability over next 2-3 quarters to confirm structural improvement.",
        )

    # Fallback for unrecognized types
    return (
        f"{company}: {signal_type} detected based on {len(supporting_findings)} supporting signals.",
        "Review supporting findings for further investigation.",
    )


def _is_below_peer(finding: dict) -> bool:
    """True if peer divergence finding shows company performing worse than peers."""
    if finding.get("pattern") != "Peer divergence":
        return False
    metric = finding.get("metric", "")
    if "gap_pp" in finding:
        company_val = finding.get("company_value")
        peer_val    = finding.get("peer_value")
        if company_val is None or peer_val is None:
            return False
        if "Margin" in metric:
            return company_val < peer_val
        else:
            return company_val > peer_val
    if "z_score" in finding:
        z = finding.get("z_score", 0)
        if "Margin" in metric:
            return z < 0
        else:
            return z > 0
    return False


def _is_above_peer(finding: dict) -> bool:
    """True if peer divergence finding shows company performing better than peers."""
    if finding.get("pattern") != "Peer divergence":
        return False
    metric = finding.get("metric", "")
    if "gap_pp" in finding:
        company_val = finding.get("company_value")
        peer_val    = finding.get("peer_value")
        if company_val is None or peer_val is None:
            return False
        if "Margin" in metric:
            return company_val > peer_val
        else:
            return company_val < peer_val
    if "z_score" in finding:
        z = finding.get("z_score", 0)
        if "Margin" in metric:
            return z > 0
        else:
            return z < 0
    return False


def build_composite_signals(findings: list, df: pd.DataFrame) -> list:
    """Build composite signals by correlating multiple findings per company.

    8 rule-based classifiers:
      1. STRUCTURAL_COMPETITIVENESS_ISSUE
      2. NEGATIVE_OPERATING_LEVERAGE
      3. SECTOR_CYCLE_PRESSURE
      4. NON_RECURRING_EVENT
      5. RELATIVE_OUTPERFORMANCE
      6. RELATIVE_UNDERPERFORMANCE
      7. COST_INFLATION_PRESSURE
      8. RECOVERY_SIGNAL
    """
    composite = []

    # Step 1: Normalize
    active = normalize_findings(findings)

    # Step 2: Group by company
    by_company: dict = defaultdict(list)
    for f in active:
        by_company[f.get("company", "")].append(f)

    # Step 3: Sector-wide view
    all_companies = list(by_company.keys())
    sector_margin_comp_companies = set()
    for comp, cfindings in by_company.items():
        if any(f.get("pattern") == "Margin compression" for f in cfindings):
            sector_margin_comp_companies.add(comp)
    n_peers = len(all_companies)

    for company, cfindings in by_company.items():
        # Categorize findings into semantic buckets
        margin_comp    = [f for f in cfindings if f.get("pattern") == "Margin compression"]
        margin_exp     = [f for f in cfindings if f.get("pattern") == "Margin expansion"]
        cost_drift_pos = [f for f in cfindings if f.get("pattern") == "Cost composition drift"  and (f.get("shift_pp") or 0) > 0]
        cost_drift_neg = [f for f in cfindings if f.get("pattern") == "Cost composition drift"  and (f.get("shift_pp") or 0) < 0]  # noqa: F841
        neg_decouple   = [f for f in cfindings if f.get("pattern") == "Revenue-cost decoupling" and (f.get("divergence_pp") or 0) > 0]
        pos_decouple   = [f for f in cfindings if f.get("pattern") == "Revenue-cost decoupling" and (f.get("divergence_pp") or 0) < 0]
        peers_below    = [f for f in cfindings if _is_below_peer(f)]
        peers_above    = [f for f in cfindings if _is_above_peer(f)]
        anomalies_ot   = [f for f in cfindings
                          if f.get("pattern") == "Statistical anomaly"
                          and f.get("anomaly_type") in ("LOW_CONFIDENCE_SIGNAL", "EVENT_DRIVEN_BUT_PLAUSIBLE")]
        anomalies_str  = [f for f in cfindings  # noqa: F841
                          if f.get("pattern") == "Statistical anomaly"
                          and f.get("anomaly_type") == "VALID_SIGNAL"]
        yoy_worse      = [f for f in cfindings if f.get("pattern") == "YoY quarter comparison" and (f.get("yoy_change_pp") or 0) < -15]  # noqa: F841
        yoy_better     = [f for f in cfindings if f.get("pattern") == "YoY quarter comparison" and (f.get("yoy_change_pp") or 0) > 15]

        # Sector-wide compression check (True when ≥ n-1 peers also compressed)
        peers_with_compression = sector_margin_comp_companies - {company}
        sector_wide = (
            n_peers >= 2 and
            len(peers_with_compression) >= max(2, n_peers - 1)
        )

        # Analysis window
        comp_rows = df[df["DENOM_CIA"] == company] if "DENOM_CIA" in df.columns else pd.DataFrame()
        if not comp_rows.empty and "DT_REFER" in comp_rows.columns:
            dates = pd.to_datetime(comp_rows["DT_REFER"], errors="coerce").dropna()
            analysis_window = (
                f"{dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}"
                if not dates.empty else "unknown"
            )
        else:
            analysis_window = "unknown"

        fired_structural = False

        # Rule 1: STRUCTURAL_COMPETITIVENESS_ISSUE
        if cost_drift_pos and margin_comp:
            signals   = cost_drift_pos + margin_comp + peers_below
            base_conf = "HIGH" if (peers_below or len(signals) >= 3) else "MEDIUM"
            explanation, angle = explain_composite_signal(
                "STRUCTURAL_COMPETITIVENESS_ISSUE", company, signals
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in cost_drift_pos + margin_comp if f.get("period")})) or "multiple periods",
                "analysis_window": analysis_window,
                "composite_signal_type": "STRUCTURAL_COMPETITIVENESS_ISSUE",
                "severity":    "HIGH",
                "confidence":  _compute_composite_confidence(base_conf, signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })
            fired_structural = True

        # Rule 2: NEGATIVE_OPERATING_LEVERAGE
        if neg_decouple and margin_comp:
            signals  = neg_decouple + margin_comp
            all_sev  = [f.get("severity") for f in signals]
            sev      = "HIGH" if "HIGH" in all_sev else "MEDIUM"
            explanation, angle = explain_composite_signal(
                "NEGATIVE_OPERATING_LEVERAGE", company, signals
            )
            composite.append({
                "company":     company,
                "period":      max(neg_decouple, key=lambda f: abs(f.get("divergence_pp", 0) or 0)).get("period", "multiple periods"),
                "analysis_window": analysis_window,
                "composite_signal_type": "NEGATIVE_OPERATING_LEVERAGE",
                "severity":    sev,
                "confidence":  _compute_composite_confidence("HIGH", signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

        # Rule 3: SECTOR_CYCLE_PRESSURE
        if margin_comp and sector_wide and not (cost_drift_pos and peers_below):
            signals    = margin_comp
            sector_ctx = {"peers_with_compression": len(peers_with_compression), "n_peers": n_peers}
            explanation, angle = explain_composite_signal(
                "SECTOR_CYCLE_PRESSURE", company, signals, sector_context=sector_ctx
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in margin_comp if f.get("period")})) or "multiple periods",
                "analysis_window": analysis_window,
                "composite_signal_type": "SECTOR_CYCLE_PRESSURE",
                "severity":    "MEDIUM",
                "confidence":  _compute_composite_confidence("HIGH", signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

        # Rule 4: NON_RECURRING_EVENT
        if anomalies_ot and not margin_comp and not cost_drift_pos:
            signals = anomalies_ot
            explanation, angle = explain_composite_signal(
                "NON_RECURRING_EVENT", company, signals
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in signals if f.get("period")})) or "unknown period",
                "analysis_window": analysis_window,
                "composite_signal_type": "NON_RECURRING_EVENT",
                "severity":    "MEDIUM",
                "confidence":  _compute_composite_confidence("MEDIUM", signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

        # Rule 5: RELATIVE_OUTPERFORMANCE
        if peers_above and (margin_exp or not margin_comp):
            signals   = peers_above + margin_exp
            base_conf = "HIGH" if margin_exp else "MEDIUM"
            explanation, angle = explain_composite_signal(
                "RELATIVE_OUTPERFORMANCE", company, signals
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in signals if f.get("period")})) or "latest period",
                "analysis_window": analysis_window,
                "composite_signal_type": "RELATIVE_OUTPERFORMANCE",
                "severity":    "MEDIUM",
                "confidence":  _compute_composite_confidence(base_conf, signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

        # Rule 6: RELATIVE_UNDERPERFORMANCE
        if peers_below and margin_comp and not sector_wide and not fired_structural:
            signals = peers_below + margin_comp
            explanation, angle = explain_composite_signal(
                "RELATIVE_UNDERPERFORMANCE", company, signals
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in signals if f.get("period")})) or "latest period",
                "analysis_window": analysis_window,
                "composite_signal_type": "RELATIVE_UNDERPERFORMANCE",
                "severity":    "HIGH",
                "confidence":  _compute_composite_confidence("HIGH", signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

        # Rule 7: COST_INFLATION_PRESSURE
        if cost_drift_pos and neg_decouple and not margin_comp:
            signals = cost_drift_pos + neg_decouple
            explanation, angle = explain_composite_signal(
                "COST_INFLATION_PRESSURE", company, signals
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in signals if f.get("period")})) or "multiple periods",
                "analysis_window": analysis_window,
                "composite_signal_type": "COST_INFLATION_PRESSURE",
                "severity":    "MEDIUM",
                "confidence":  _compute_composite_confidence("MEDIUM", signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

        # Rule 8: RECOVERY_SIGNAL
        if margin_exp and (yoy_better or pos_decouple):
            signals   = margin_exp + yoy_better + pos_decouple
            base_conf = "HIGH" if (yoy_better and pos_decouple) else "MEDIUM"
            explanation, angle = explain_composite_signal(
                "RECOVERY_SIGNAL", company, signals
            )
            composite.append({
                "company":     company,
                "period":      ", ".join(sorted({f.get("period", "") for f in signals if f.get("period")})) or "recent periods",
                "analysis_window": analysis_window,
                "composite_signal_type": "RECOVERY_SIGNAL",
                "severity":    "MEDIUM",
                "confidence":  _compute_composite_confidence(base_conf, signals),
                "supporting_signals": list({f.get("pattern") for f in signals}),
                "signal_count": len(signals),
                "explanation": explanation,
                "recommended_investigation_angle": angle,
            })

    return composite


# =============================================================================
# Risk Scoring Engine
# =============================================================================

def _score_magnitude(findings: list) -> float:
    """Score magnitude of deterioration signals (0-20)."""
    margin_comp    = [f for f in findings if f.get("pattern") == "Margin compression"]
    cost_drift_pos = [f for f in findings if f.get("pattern") == "Cost composition drift" and (f.get("shift_pp") or 0) > 0]
    peers_below    = [f for f in findings if _is_below_peer(f)]

    scores = []
    if margin_comp:
        max_chg = max(abs(f.get("annual_change_pp", 0)) for f in margin_comp)
        scores.append(min(20.0, max_chg * 2))
    if cost_drift_pos:
        max_shift = max(f.get("shift_pp", 0) for f in cost_drift_pos)
        scores.append(min(20.0, max_shift * 1.5))
    if peers_below:
        vals = []
        for f in peers_below:
            gap = f.get("gap_pp")
            z   = f.get("z_score")
            if gap is not None:
                vals.append(gap)
            elif z is not None:
                vals.append(abs(z) * 10)
        if vals:
            scores.append(min(20.0, max(vals) * 0.8))

    return max(scores) if scores else 0.0


def _score_persistence(findings: list, df: pd.DataFrame, company: str) -> float:
    """Score persistence of deterioration signals (0-20)."""
    if df is None or df.empty:
        return 10.0  # neutral

    comp_df = df[df["DENOM_CIA"] == company] if "DENOM_CIA" in df.columns else pd.DataFrame()

    if comp_df.empty:
        return 10.0

    # Compute stress fraction from df
    stress_fractions = []
    if "EBIT_Margin_pct" in comp_df.columns:
        series = comp_df["EBIT_Margin_pct"].dropna()
        if len(series) > 0:
            frac_neg_ebit = (series < 0).sum() / len(series)
            stress_fractions.append(frac_neg_ebit)
    if "COGS_pct_Revenue" in comp_df.columns:
        series = comp_df["COGS_pct_Revenue"].dropna()
        if len(series) > 0:
            frac_cogs_above_90 = (series > 90).sum() / len(series)
            stress_fractions.append(frac_cogs_above_90)

    stress_fraction = max(stress_fractions) if stress_fractions else 0.0

    # Finding persistence
    margin_comp_n = sum(1 for f in findings if f.get("pattern") == "Margin compression")
    yoy_worse_n   = sum(1 for f in findings if f.get("pattern") == "YoY quarter comparison" and (f.get("yoy_change_pp") or 0) < -15)
    finding_persistence = min(1.0, (margin_comp_n + yoy_worse_n * 0.5) / 3)

    score = min(20.0, (stress_fraction * 0.5 + finding_persistence * 0.5) * 20)
    return score


def _score_confirmation(findings: list) -> float:
    """Score signal confirmation (0-20) based on distinct deterioration signal types."""
    signal_types = set()
    for f in findings:
        pattern = f.get("pattern", "")
        if pattern == "Margin compression":
            signal_types.add("margin_compression")
        if pattern == "Cost composition drift" and (f.get("shift_pp") or 0) > 0:
            signal_types.add("cost_drift")
        if _is_below_peer(f):
            signal_types.add("peer_gap")
        if pattern == "Revenue-cost decoupling" and (f.get("divergence_pp") or 0) > 0:
            signal_types.add("cost_decoupling")
        if pattern == "YoY quarter comparison" and (f.get("yoy_change_pp") or 0) < -15:
            signal_types.add("yoy_deterioration")

    n = len(signal_types)
    score_map = {0: 0, 1: 4, 2: 10, 3: 15}
    return score_map.get(n, 20) if n <= 3 else 20


def _score_peer_gap(findings: list) -> float:
    """Score peer gap magnitude (0-20)."""
    scores = []
    for f in findings:
        if not _is_below_peer(f):
            continue
        gap = f.get("gap_pp")
        z   = f.get("z_score")
        if gap is not None:
            scores.append(min(20.0, gap * 0.8))
        elif z is not None:
            scores.append(min(20.0, abs(z) * 7))
    return max(scores) if scores else 0.0


def _score_data_confidence(findings: list) -> float:
    """Score data confidence (0-20). Base 10, penalize LOW, reward HIGH."""
    if not findings:
        return 10.0
    n_total    = len(findings)
    n_low      = sum(1 for f in findings if f.get("confidence_score") == "LOW")
    n_high     = sum(1 for f in findings if f.get("confidence_score") == "HIGH")
    low_ratio  = n_low  / n_total
    high_ratio = n_high / n_total
    score = 10.0 - (low_ratio * 8) + (high_ratio * 10)
    return max(0.0, min(20.0, score))


def score_company_risk(
    company: str,
    company_findings: list,
    composite_signals: list,
    df: pd.DataFrame,
) -> dict:
    """Score overall risk for a company (0-100)."""
    # Filter to non-SUMMARY entries
    active = [f for f in company_findings if f.get("severity") != "SUMMARY"]

    # Company composite signals
    company_cs = [s for s in composite_signals if s.get("company") == company]

    # Score dimensions
    mag  = _score_magnitude(active)
    pers = _score_persistence(active, df, company)
    conf = _score_confirmation(active)
    pg   = _score_peer_gap(active)
    dc   = _score_data_confidence(active)

    total = mag + pers + conf + pg + dc

    if total >= 75:
        priority = "CRITICAL"
    elif total >= 50:
        priority = "HIGH"
    elif total >= 25:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # Top drivers
    if company_cs:
        sorted_cs  = sorted(
            company_cs,
            key=lambda s: (0 if s.get("severity") == "HIGH" else 1, -s.get("signal_count", 0))
        )
        top_drivers = [s["composite_signal_type"] for s in sorted_cs[:3]]
    else:
        raw_findings = [f for f in active if f.get("confidence_score") != "LOW"]
        raw_sorted   = sorted(raw_findings, key=lambda f: (0 if f.get("severity") == "HIGH" else 1))
        top_drivers  = [f.get("pattern", "Unknown") for f in raw_sorted[:3]]

    # Executive summary
    cs_types = [s["composite_signal_type"] for s in company_cs]
    if cs_types:
        cs_summary   = ", ".join(cs_types[:2])
        exec_summary = (
            f"{company} is rated {priority} risk (score: {total:.1f}/100). "
            f"Primary concerns: {cs_summary}."
        )
    else:
        exec_summary = (
            f"{company} is rated {priority} risk (score: {total:.1f}/100). "
            f"No composite signals detected; review individual findings."
        )

    return {
        "company":          company,
        "risk_score":       round(total, 1),
        "priority":         priority,
        "top_risk_drivers": top_drivers,
        "score_breakdown": {
            "magnitude":       round(mag, 1),
            "persistence":     round(pers, 1),
            "confirmation":    round(conf, 1),
            "peer_gap":        round(pg, 1),
            "data_confidence": round(dc, 1),
        },
        "composite_signal_count": len(company_cs),
        "composite_signal_types": cs_types,
        "key_supporting_findings": len(active),
        "executive_summary": exec_summary,
    }


# =============================================================================
# Public API
# =============================================================================

def enrich(findings: list, df: pd.DataFrame) -> dict:
    """Build composite signals and score company risk (Step 7).

    Args:
        findings: All findings from detect_patterns (Step 6).
        df:       The enriched metrics DataFrame (with DQ columns from Step 5).

    Returns dict with:
        composite_signals, risk_scores, macro_timeline,
        risk_score (for focus company), risk_level (for focus company).
    """
    composite_signals = build_composite_signals(findings, df)

    # Score risk for each company in the dataset
    by_company_findings: dict = defaultdict(list)
    for f in findings:
        by_company_findings[f.get("company", "")].append(f)

    companies     = sorted(df["DENOM_CIA"].unique()) if "DENOM_CIA" in df.columns else sorted(by_company_findings.keys())
    risk_scores   = []
    for company in companies:
        score = score_company_risk(
            company,
            by_company_findings.get(company, []),
            composite_signals,
            df,
        )
        risk_scores.append(score)
    risk_scores.sort(key=lambda s: s["risk_score"], reverse=True)

    # Macro timeline (sorted by period key)
    macro_timeline = [
        {"period": k, "event": v}
        for k, v in sorted(MACRO_CONTEXT.items())
    ]

    # Primary company risk (highest-scored or first)
    primary = risk_scores[0] if risk_scores else {}

    return {
        "composite_signals":   composite_signals,
        "risk_scores":         risk_scores,
        "macro_timeline":      macro_timeline,
        "risk_score":          primary.get("risk_score", 0.0),
        "risk_level":          primary.get("priority", "LOW"),
        "findings_enriched":   len([f for f in findings if f.get("severity") != "SUMMARY"]),
        "macro_annotations_added": sum(1 for f in findings if "macro_context" in f),
    }
