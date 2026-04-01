"""Step 8: Executive Summary — LLM-generated narrative merging Step 6 data and Step 7 analysis."""

import asyncio
import json
import os
from typing import AsyncIterator

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


def build_story_arc(findings: list, composite_signals: list, step7_data: dict) -> dict:
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

    first_half     = cogs_drift.get("first_half_avg", "N/A") if cogs_drift else "N/A"
    second_half    = cogs_drift.get("second_half_avg", "N/A") if cogs_drift else "N/A"
    shift          = cogs_drift.get("shift_pp", 0) if cogs_drift else 0
    annual_chg     = margin_comp.get("annual_change_pp", 0) if margin_comp else 0
    current_margin = margin_comp.get("current_level", "N/A") if margin_comp else "N/A"

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
        "An AI industry specialist has generated hypotheses that may explain this deterioration, "
        "but confirming which requires internal data that public filings do not provide — "
        "specifically, the decomposition of the COGS line into feedstock, energy, labor, "
        "and overhead components."
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


def build_transition(findings: list, step7_data: dict) -> str:
    return (
        "This analysis identified structural patterns in the company's financials "
        "using only public CVM data. An AI industry specialist generated hypotheses "
        "and identified data gaps that require internal data to resolve — specifically, "
        "the decomposition of the COGS line into its underlying cost components."
    )


_MOCK_SUMMARY = """\
## Executive Summary

Braskem S.A. experienced a structural collapse in cost competitiveness between 2020 and 2025, with COGS as a percentage of revenue rising from 81% to 95% — a permanent shift that has erased most of the company's operating margin and cannot be explained by a single cyclical event.

## What Happened

The company's gross margin peaked at 30% in 2021 during the post-COVID commodity supercycle and has since compressed at 4.6pp per year, reaching 2.2% by 2024. This is not a recession-driven dip: revenue recovered in nominal terms while COGS remained structurally elevated, confirming a permanent shift in the cost structure rather than a demand shortfall. The composite signals STRUCTURAL_COMPETITIVENESS_ISSUE and NEGATIVE_OPERATING_LEVERAGE both fired with HIGH severity.

## How Serious It Is

At the current compression rate of 4.6pp per year, Braskem's gross margin will turn negative within one year without structural cost intervention. The risk score of 71.2/100 (HIGH) reflects confirmation across five independent signal types: cost drift, margin compression, revenue-cost decoupling, peer underperformance, and YoY deterioration. The 2022 inflection — when revenue fell 8.6% but COGS rose 15.8% — was the clearest structural break point.

## When Things Turned

The critical break occurred in 2022, when the Ukraine war drove naphtha above $100/bbl while simultaneous Chinese capacity additions suppressed polyethylene selling prices. Unlike US cracker operators who use ethane from shale gas, Braskem's naphtha-based crackers have no lower-cost feedstock alternative. Costs surged immediately; prices could not follow. Crucially, when energy prices partially normalized in 2023–2024, COGS/Revenue did not recover — confirming that the deterioration is structural, not energy-cycle-driven.

## What Comes Next

Without COGS decomposition data, it is impossible to target the right intervention. If the driver is feedstock cost (H1 from specialist analysis), the solution is long-term naphtha hedging or feedstock diversification. If it is fixed-cost deleverage from volume decline (H4), the solution is utilization optimization. If it is China spread compression (H2), only product mix differentiation or capacity rationalization will restore margins. All three interventions require different capital allocation decisions — and all are invisible in public filings.

## What We Can't Answer

The key unresolved question is the **composition of the COGS line**. Public CVM filings aggregate all production costs into a single account (3.02). The specialist assessment identified five hypotheses that could explain the deterioration, but confirming which are primary requires: (1) feedstock cost per tonne by quarter, (2) product realization prices by polymer grade, (3) plant-level utilization rates, and (4) FX hedging program coverage. None of these are disclosed in DFP or ITR filings.

## Key Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | Cost composition drift | HIGH | COGS/Rev: 80.9% → 95.3% (+11.4pp shift) |
| 2 | Margin compression (Gross) | HIGH | −4.6pp/year, now 2.2% |
| 3 | Margin compression (EBIT) | HIGH | −4.4pp/year, now −2.5% |
| 4 | Revenue-cost decoupling | HIGH | 2022: Revenue −8.6%, COGS +15.8% |
| 5 | Peer divergence | MEDIUM | 11.5pp below sector average gross margin |

## Next Step

Resolving these open questions requires access to internal management accounts — specifically the sub-line COGS decomposition that sits behind the single 3.02 line in every public filing.
"""


async def stream(payload: dict, config) -> AsyncIterator[str]:
    """Yield executive summary tokens. Uses Claude API if key available, else mock."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        words = _MOCK_SUMMARY.split(" ")
        for i, word in enumerate(words):
            token = word if i == len(words) - 1 else word + " "
            yield token
            await asyncio.sleep(0.02)
        return

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)

    step6_data     = payload.get("step6_data", {})
    step7_response = payload.get("step7_response", "")
    company_name   = payload.get("company_name", "the company")
    language       = payload.get("language", "en")
    lang_str       = "Portuguese (Brazilian)" if language == "pt-br" else "English"

    system_prompt = (
        "You are a senior financial analyst preparing a concise executive summary for a "
        "C-suite audience. You will be given quantitative findings from automated pattern "
        "detection on CVM public filings, and expert analysis from an AI industry specialist "
        "providing macro context and hypotheses.\n\n"
        "Write a well-structured executive summary that integrates both inputs. "
        "Use this exact structure (markdown headers):\n\n"
        "## Executive Summary\n"
        "One tight sentence capturing the central finding with specific numbers.\n\n"
        "## What Happened\n"
        "2-3 sentences. Data-driven. Specific percentages and periods.\n\n"
        "## How Serious It Is\n"
        "2-3 sentences on magnitude, trajectory, and industry context from the specialist.\n\n"
        "## When Things Turned\n"
        "The critical inflection point — specific period, mechanism, why it is structural not cyclical.\n\n"
        "## What Comes Next\n"
        "Forward implications integrating the specialist's hypotheses and the data trajectory.\n\n"
        "## What We Can't Answer\n"
        "Key open questions that require internal data. Be specific about which data sources, "
        "drawing from the specialist's data readiness assessment.\n\n"
        "## Key Findings\n"
        "A markdown table with columns: # | Finding | Severity | Evidence\n"
        "Include the top 4-5 findings.\n\n"
        "## Next Step\n"
        "One sentence framing the value of internal data access.\n\n"
        "Keep the whole summary under 500 words. Be specific and quantitative. "
        f"Write in {lang_str}."
    )

    # Build step 6 summary block
    risk_score  = step6_data.get("risk_score", "N/A")
    risk_level  = step6_data.get("risk_level", "N/A")
    findings    = step6_data.get("findings", [])
    comp_sigs   = step6_data.get("composite_signals", [])
    cs_types    = ", ".join(s.get("composite_signal_type", "") for s in comp_sigs) or "None"

    finding_lines = []
    for f in findings:
        dp = f.get("data_points", {})
        key_dp = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:3]) if dp else ""
        finding_lines.append(
            f"  - {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — "
            f"{f.get('description','')[:120]}"
            + (f" [{key_dp}]" if key_dp else "")
        )

    step6_block = (
        f"Company: {company_name}\n"
        f"Risk Score: {risk_score}/100 ({risk_level})\n"
        f"Composite Signals: {cs_types}\n\n"
        "Findings:\n" + "\n".join(finding_lines)
    )

    user_prompt = (
        f"## Quantitative Analysis (automated pattern detection)\n\n{step6_block}\n\n"
        f"## Expert Analysis (AI industry specialist)\n\n{step7_response or '(Step 7 not yet run)'}\n\n"
        "Generate the executive summary."
    )

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        temperature=0.5,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream_obj:
        async for text in stream_obj.text_stream:
            yield text


def run(config, pipeline_state: dict) -> dict:
    """REST endpoint handler — returns cached/pipeline_state data or pending status."""
    STEP = 8

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            return cached

    step8_state = pipeline_state.get("step8")
    if step8_state and step8_state.get("response_text"):
        result = {
            "status": "complete",
            "data": step8_state,
            "metadata": {"cache_used": False, "source": "websocket"},
        }
        save_cache(STEP, result, CACHE_DIR, company_name=config.company_name)
        return result

    return {
        "status": "pending",
        "data": {},
        "metadata": {"cache_used": False, "source": "live"},
    }
