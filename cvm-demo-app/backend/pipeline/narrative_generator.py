"""Narrative generator — per-company narrative synthesis.

All analytical logic is ported verbatim from 02_pattern_discovery.py.

Public API
----------
generate_narrative(company_name, findings, df, composite_signals, risk_scores) -> dict
    Step 8: synthesize company narrative and key findings summary.
"""

from collections import defaultdict

import pandas as pd


DATA_LIMITATIONS = [
    "Account-level detail only (no sub-ledger or cost center breakdown)",
    "Quarterly granularity — monthly patterns invisible",
    "Consolidated view — subsidiary-level patterns not visible",
    "No operational KPIs (production volumes, utilization rates)",
    "D&A not consistently available for all periods — EBITDA may be partial",
]


def synthesize_company_narratives(findings: list, df: pd.DataFrame) -> list:
    """Generate a 2-4 sentence narrative per company by correlating findings.

    Looks for compound signals:
    - Cost drift + Margin compression → deteriorating/improving cost structure
    - Revenue-cost decoupling → inflection point in cost behaviour
    - Peer divergence → structural vs. cyclical underperformance
    """
    narrative_findings = []

    by_company: dict = defaultdict(list)
    for f in findings:
        if f.get("pattern") != "Company Narrative":
            by_company[f.get("company", "")].append(f)

    for company, cfinding in sorted(by_company.items()):
        drift    = [f for f in cfinding if f["pattern"] == "Cost composition drift"]
        compress = [f for f in cfinding if f["pattern"] in ("Margin compression", "Margin expansion")]
        decouple = [f for f in cfinding if f["pattern"] == "Revenue-cost decoupling"]
        peers    = [f for f in cfinding if f["pattern"] == "Peer divergence"]

        sentences = []

        # Sentence 1: cost structure headline
        cogs_drift = next((f for f in drift if "COGS" in f.get("metric", "")), None)
        ebit_comp  = next((f for f in compress if "EBIT" in f.get("metric", "")), None)
        gross_comp = next((f for f in compress if "Gross" in f.get("metric", "")), None)

        if cogs_drift and (ebit_comp or gross_comp):
            cf     = ebit_comp or gross_comp
            mname  = "EBIT margin" if ebit_comp else "Gross margin"
            direction = "increased" if cogs_drift["shift_pp"] > 0 else "decreased"
            move   = "compressed" if cf["annual_change_pp"] < 0 else "expanded"
            sentences.append(
                f"COGS burden {direction} {abs(cogs_drift['shift_pp']):.1f}pp over the "
                f"analysis period while {mname} {move} "
                f"{abs(cf['annual_change_pp']):.1f}pp/year to {cf['current_level']:.1f}% "
                f"— the cost structure is "
                f"{'deteriorating' if cogs_drift['shift_pp'] > 0 else 'improving'}."
            )
        elif cogs_drift:
            direction = "increased" if cogs_drift["shift_pp"] > 0 else "decreased"
            sentences.append(
                f"COGS burden {direction} {abs(cogs_drift['shift_pp']):.1f}pp "
                f"({cogs_drift['first_half_avg']:.1f}% → "
                f"{cogs_drift['second_half_avg']:.1f}% of revenue)."
            )
        elif gross_comp or ebit_comp:
            cf     = ebit_comp or gross_comp
            mname  = "EBIT margin" if ebit_comp else "Gross margin"
            move   = "compressing" if cf["annual_change_pp"] < 0 else "expanding"
            sentences.append(
                f"{mname} is {move} at {abs(cf['annual_change_pp']):.1f}pp/year, "
                f"now at {cf['current_level']:.1f}%."
            )

        # Sentence 2: inflection point from decoupling
        if decouple:
            pf = max(decouple, key=lambda f: abs(f.get("divergence_pp", 0)))
            sentences.append(
                f"A revenue-cost decoupling in {pf['period']} "
                f"(revenue {pf['revenue_change_pct']:+.1f}%, "
                f"COGS {pf['cogs_change_pct']:+.1f}%) marked a key inflection point."
            )

        # Sentence 3: peer context (n=2 absolute-gap findings have gap_pp)
        n2_peers = [f for f in peers if "gap_pp" in f]
        if n2_peers:
            pf          = max(n2_peers, key=lambda f: f.get("gap_pp", 0))
            metric_name = pf["metric"].replace("_pct", "").replace("_", " ")
            short       = company.split()[0]
            sentences.append(
                f"{short} trails its sector peer by {pf['gap_pp']:.0f}pp on "
                f"{metric_name} ({pf['company_value']:.1f}% vs {pf['peer_value']:.1f}%), "
                f"suggesting a structural disadvantage beyond commodity cycle effects."
            )

        if not sentences:
            high_n = sum(1 for f in cfinding if f.get("severity") == "HIGH")
            sentences.append(
                f"{high_n} high-severity signal(s) detected. "
                f"Review individual findings below for detail."
            )

        narrative_findings.append({
            "company":          company,
            "pattern":          "Company Narrative",
            "severity":         "SUMMARY",
            "confidence_score": "SUMMARY",
            "insight":          " ".join(sentences),
        })

    return narrative_findings


def _build_evidence_string(f: dict) -> str:
    """Build a compact, human-readable evidence string from a finding's numeric fields."""
    pattern = f.get("pattern", "")

    try:
        if pattern == "Cost composition drift":
            fh = f.get("first_half_avg")
            sh = f.get("second_half_avg")
            sp = f.get("shift_pp")
            if fh is not None and sh is not None and sp is not None:
                return f"{float(fh):.1f}% → {float(sh):.1f}% ({float(sp):+.1f}pp)"

        elif pattern in ("Margin compression", "Margin expansion"):
            chg = f.get("annual_change_pp")
            lvl = f.get("current_level")
            metric = f.get("metric", "").replace("_pct", "").replace("_", " ")
            if chg is not None and lvl is not None:
                return f"{metric}: {float(chg):+.1f}pp/year, now {float(lvl):.1f}%"

        elif pattern == "Revenue-cost decoupling":
            rev  = f.get("revenue_change_pct")
            cogs = f.get("cogs_change_pct")
            if rev is not None and cogs is not None:
                return f"Revenue {float(rev):+.1f}%, COGS {float(cogs):+.1f}%"

        elif pattern == "Statistical anomaly":
            val   = f.get("value")
            nr    = f.get("normal_range", "")
            metric_short = f.get("metric", "").replace("_pct", "").replace("_", " ").strip()
            if val is not None and nr:
                parts = nr.split(" - ", 1)
                if len(parts) == 2:
                    return f"{metric_short}: {float(val):.1f}% vs range {parts[0]}% to {parts[1]}%"
                return f"{metric_short}: {float(val):.1f}% vs range {nr}%"

        elif pattern == "YoY quarter comparison":
            chg = f.get("yoy_change_pp")
            cur = f.get("current_value")
            period = f.get("period", "")
            if chg is not None:
                base = f"{period}: " if period else ""
                cur_str = f" (now {float(cur):.1f}%)" if cur is not None else ""
                return f"{base}{float(chg):+.1f}pp YoY{cur_str}"

        elif pattern == "Peer divergence":
            cv = f.get("company_value")
            pv = f.get("peer_average")
            if cv is not None and pv is not None:
                return f"{float(cv):.1f}% vs peer avg {float(pv):.1f}%"

    except (TypeError, ValueError):
        pass

    # Fallback: clean up the insight text to a single short line
    insight = f.get("insight", "")
    first_sentence = insight.split(".")[0].strip()
    return (first_sentence[:80] + "…") if len(first_sentence) > 80 else first_sentence


def _build_key_findings_summary(findings: list, top_n: int = 5) -> list:
    """Build ranked key findings summary from the findings list."""
    # Exclude SUMMARY and LOW confidence
    actionable = [
        f for f in findings
        if f.get("severity") not in ("SUMMARY",) and f.get("confidence_score") != "LOW"
    ]
    # Sort: HIGH first, then by pattern
    sorted_f = sorted(actionable, key=lambda f: (0 if f.get("severity") == "HIGH" else 1))

    summary = []
    for rank, f in enumerate(sorted_f[:top_n], start=1):
        summary.append({
            "rank":     rank,
            "id":       f.get("id", ""),
            "finding":  f.get("pattern", "Unknown"),
            "severity": f.get("severity", "MEDIUM"),
            "evidence": _build_evidence_string(f),
        })
    return summary


# =============================================================================
# Public API
# =============================================================================

def generate_narrative(
    company_name: str,
    findings: list,
    df: pd.DataFrame,
    composite_signals: list = None,
    risk_scores: list = None,
) -> dict:
    """Synthesize company narrative and key findings summary (Step 8).

    Args:
        company_name:      Target company for narrative focus.
        findings:          All findings from Steps 5-6 (after DQ enrichment).
        df:                Enriched metrics DataFrame.
        composite_signals: Optional list from Step 7.
        risk_scores:       Optional list from Step 7.

    Returns dict with narrative, key_findings_summary, data_limitations.
    """
    # Generate narratives for all companies in findings
    narratives = synthesize_company_narratives(findings, df)
    all_findings_with_narratives = list(findings) + narratives

    # Find target company narrative
    company_key = company_name.split()[0].upper()
    narrative_text = ""
    for nf in narratives:
        if company_key in nf.get("company", "").upper():
            narrative_text = nf.get("insight", "")
            break

    if not narrative_text:
        # Fallback: build from composite signals
        company_composites = [
            s for s in (composite_signals or [])
            if company_key in s.get("company", "").upper()
        ]
        if company_composites:
            explanations = [s["explanation"] for s in company_composites[:2]]
            narrative_text = " ".join(explanations)
        else:
            narrative_text = (
                f"Analysis complete for {company_name}. "
                f"Review individual findings for detail."
            )

    # Key findings for target company
    company_findings = [
        f for f in findings
        if company_key in f.get("company", "").upper()
    ]
    key_findings_summary = _build_key_findings_summary(company_findings)

    return {
        "narrative":            narrative_text,
        "key_findings_summary": key_findings_summary,
        "data_limitations":     DATA_LIMITATIONS,
        "source":               "live",
    }
