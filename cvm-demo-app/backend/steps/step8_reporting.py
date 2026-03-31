"""Step 8: Executive Summary — narrative + story arc + transition to offer."""

import json

import pandas as pd

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline import narrative_generator


def _load_findings(company_name: str, data_dir, pipeline_state: dict) -> list:
    company_key   = company_name.split()[0].lower()
    findings_path = data_dir / "analysis" / f"findings_{company_key}.json"
    if findings_path.exists():
        with open(findings_path, encoding="utf-8") as jf:
            return json.load(jf)

    step6 = pipeline_state.get("step6") or {}
    shaped = step6.get("findings", [])
    raw = []
    for f in shaped:
        raw.append({
            "company":          f.get("company", ""),
            "pattern":          f.get("pattern", ""),
            "severity":         f.get("severity", "MEDIUM"),
            "metric":           f.get("metric", ""),
            "confidence_score": f.get("confidence", "MEDIUM"),
            "insight":          f.get("description", ""),
            "period":           f.get("period", ""),
            "anomaly_type":     f.get("anomaly_type", ""),
            **f.get("data_points", {}),
        })
    return raw


def _load_df(company_name: str, data_dir) -> pd.DataFrame:
    company_key = company_name.split()[0].lower()
    for suffix in ("enriched", "metrics", "pivot"):
        path = data_dir / "analysis" / f"{suffix}_{company_key}.csv"
        if path.exists():
            return pd.read_csv(path, low_memory=False)
    return pd.DataFrame()


def build_story_arc(findings: list, composite_signals: list, hypotheses_data: dict) -> dict:
    cogs_drift = next((f for f in findings if f.get("pattern") == "Cost composition drift"), None)
    margin_comp = next(
        (f for f in findings if f.get("pattern") == "Margin compression"
         and "Gross" in f.get("metric", "")),
        next((f for f in findings if f.get("pattern") == "Margin compression"), None),
    )
    worst_decoupling = next(
        (f for f in findings
         if f.get("pattern") == "Revenue-cost decoupling"
         and (f.get("divergence_pp") or 0) > 0),
        None,
    )

    first_half  = cogs_drift.get("first_half_avg", "N/A") if cogs_drift else "N/A"
    second_half = cogs_drift.get("second_half_avg", "N/A") if cogs_drift else "N/A"
    shift       = cogs_drift.get("shift_pp", 0) if cogs_drift else 0
    annual_chg  = margin_comp.get("annual_change_pp", 0) if margin_comp else 0
    current_margin = margin_comp.get("current_level", "N/A") if margin_comp else "N/A"
    h_count     = hypotheses_data.get("hypothesis_count", 0) if hypotheses_data else 0

    try:
        setup = (
            f"Between 2020 and 2025, the company's cost structure deteriorated significantly. "
            f"COGS as a percentage of revenue shifted from {float(first_half):.1f}% to "
            f"{float(second_half):.1f}%, a {abs(float(shift)):.1f} percentage point increase."
        )
    except (TypeError, ValueError):
        setup = "The company's cost structure deteriorated significantly over the analysis period."

    try:
        evidence = (
            f"Gross margin compressed at {abs(float(annual_chg)):.1f}pp per year, "
            f"reaching {float(current_margin):.1f}% — approaching the viability floor for "
            f"capital-intensive manufacturing."
        )
    except (TypeError, ValueError):
        evidence = "Gross margin compressed meaningfully over the analysis period."

    if worst_decoupling:
        period   = worst_decoupling.get("period", "")
        rev_chg  = worst_decoupling.get("revenue_change_pct", 0) or 0
        cogs_chg = worst_decoupling.get("cogs_change_pct", 0) or 0
        inflection = (
            f"The critical inflection came in {period}, when revenue fell {abs(float(rev_chg)):.1f}% "
            f"but COGS rose {float(cogs_chg):.1f}%. Costs did not normalize when revenue recovered — "
            f"indicating a structural shift, not a cyclical one."
        )
    else:
        inflection = "The deterioration has been persistent across periods, without recovery."

    try:
        implication = (
            f"At the current compression rate of {abs(float(annual_chg)):.1f}pp per year, "
            f"operating margins will continue eroding unless the underlying cost drivers are addressed."
        )
    except (TypeError, ValueError):
        implication = "Operating margins will continue eroding unless the underlying cost drivers are addressed."

    question = (
        f"{h_count} hypotheses could explain this deterioration, but confirming which "
        f"requires internal data that public filings do not provide — specifically, "
        f"the decomposition of the COGS line into feedstock, energy, labor, and overhead components."
    )

    return {
        "setup":       setup,
        "evidence":    evidence,
        "inflection":  inflection,
        "implication": implication,
        "question":    question,
    }


def build_headline(company_name: str, findings: list) -> str:
    cogs_drift = next((f for f in findings if f.get("pattern") == "Cost composition drift"), None)
    if cogs_drift:
        try:
            fh = float(cogs_drift.get("first_half_avg", 0))
            sh = float(cogs_drift.get("second_half_avg", 0))
            name = company_name.split()[0].title()
            return f"{name}: Structural COGS Deterioration — {fh:.0f}% → {sh:.0f}% Over 5 Years"
        except (TypeError, ValueError):
            pass
    return f"{company_name.split()[0].title()}: Structural Cost Deterioration Identified"


def build_transition(findings: list, hypotheses_data: dict) -> str:
    cogs_drift = next((f for f in findings if f.get("pattern") == "Cost composition drift"), None)
    try:
        shift = abs(float(cogs_drift.get("shift_pp", 0))) if cogs_drift else 0
    except (TypeError, ValueError):
        shift = 0
    h_count = hypotheses_data.get("hypothesis_count", 0) if hypotheses_data else 0
    return (
        f"This analysis identified a structural COGS deterioration of {shift:.1f}pp and generated "
        f"{h_count} hypotheses for its root cause. Confirming which hypotheses apply requires "
        f"access to internal data behind the 3.02 COGS line — feedstock costs, product margins, "
        f"segment P&L, and utilization rates."
    )


def run(config, pipeline_state: dict) -> dict:
    STEP = 8

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached

    try:
        findings = _load_findings(config.company_name, DATA_DIR, pipeline_state)
        df       = _load_df(config.company_name, DATA_DIR)

        # Stamp F00N IDs onto raw findings so they align with step6's _shape_findings()
        # This lets _build_key_findings_summary include the ID for category lookup.
        for i, f in enumerate(findings, start=1):
            f["id"] = f"F{i:03d}"

        step6 = pipeline_state.get("step6") or {}
        composite_signals = step6.get("composite_signals", [])
        risk_scores       = step6.get("risk_scores", [])

        step7 = pipeline_state.get("step7") or {}

        narrative = narrative_generator.generate_narrative(
            company_name=config.company_name,
            findings=findings,
            df=df,
            composite_signals=composite_signals,
            risk_scores=risk_scores,
        )

        headline       = build_headline(config.company_name, findings)
        story_arc      = build_story_arc(findings, composite_signals, step7)
        transition     = build_transition(findings, step7)

        # Annotate key_findings_summary with category
        finding_categories = step6.get("finding_categories", {})
        id_to_category = {}
        for cat, ids in finding_categories.items():
            for fid in ids:
                id_to_category[fid] = cat

        key_findings = narrative.get("key_findings_summary", [])
        for kf in key_findings:
            kf["category"] = id_to_category.get(kf.get("id", ""), "contextual")

        result_data = {
            **narrative,
            "headline":           headline,
            "story_arc":          story_arc,
            "transition_to_offer": transition,
            "key_findings_summary": key_findings,
        }

        result = {
            "status": "complete",
            "data":   result_data,
            "metadata": {"cache_used": False, "source": "live"},
        }
        save_cache(STEP, result, CACHE_DIR)
        return result

    except Exception as exc:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            cached["metadata"]["source"] = "cache"
            cached["metadata"]["reason"] = str(exc)
            return cached

        return {
            "status": "error",
            "data":   {},
            "metadata": {"cache_used": False, "source": "live"},
            "error":  str(exc),
        }
