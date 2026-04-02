"""Step 7: AI Industry Specialist Agent — streams expert analysis via WebSocket."""

import asyncio
import os
from typing import AsyncIterator

from config import CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline.enrichment import SECTOR_MAP


MOCK_RESPONSE = """\
## Macro Context: 2020–2025

The patterns detected align closely with three major macro-economic episodes:

**2021 Commodity Supercycle (Tailwind)**
Following COVID-19 recovery, global demand surged while petrochemical supply remained constrained. Ethylene and propylene spreads hit multi-year highs in H1 2021. This explains the gross margin peak (~30%) in 2021 — naphtha feedstock costs remained manageable while polyethylene and polypropylene pricing was elevated. The favorable COGS/Revenue ratio in 2020-2021 reflects this spread expansion window.

**2022 Input Cost Shock (Inflection Point)**
Russia's invasion of Ukraine in February 2022 drove Brent crude above $100/bbl, directly transmitting into naphtha feedstock costs. Unlike US cracker operators who use cheap shale ethane, Brazilian crackers have no affordable alternative feedstock, making them structurally exposed to crude oil price spikes. COGS/Revenue shifted from ~70% to ~86% in 2022-2023 — this is the structural break point.

**2023-2024 China Oversupply (Structural Pressure)**
China commissioned ~15 million tonnes of new polyethylene/polypropylene capacity between 2022-2024, dramatically changing global supply dynamics. Chinese exports at distressed prices compressed petrochemical spreads globally. Brazilian producers faced margin pressure from both sides: high input costs (naphtha) AND lower selling prices (PE/PP). This explains why COGS deterioration did not reverse even as energy prices normalized.

---

## Hypotheses for Structural COGS Deterioration

**H1: Naphtha Feedstock Cost Disadvantage (HIGH confidence)**
Braskem processes primarily naphtha-based crackers, while US competitors use ethane from shale gas. The naphtha-to-ethane spread widened dramatically post-2022. Mechanism: every $10/bbl increase in Brent translates directly to higher naphtha costs with no equivalent pass-through to polyethylene pricing in a commoditized market. Internal data needed: feedstock cost per tonne vs. product realization price by product line.

**H2: China Capacity Overhang Compressing Spreads (HIGH confidence)**
New Chinese PE/PP capacity exceeded domestic Chinese demand growth, forcing Chinese producers to export at low margins. This depressed global polyethylene prices 20-30% from 2022 peaks. Mechanism: Braskem's selling prices declined while feedstock costs remained elevated, creating a margin squeeze that appears as COGS/Revenue deterioration. Internal data needed: product realization prices vs. cash cost of production by polymer.

**H3: BRL Depreciation Amplifying Import Cost Exposure (MEDIUM confidence)**
USD-denominated inputs (naphtha, crude derivatives) represent a large fraction of the cost base. BRL weakened 30%+ vs. USD between 2020-2024. Mechanism: even if dollar-denominated input costs stabilize, BRL-denominated COGS increases automatically. Internal data needed: FX sensitivity analysis in treasury reports, hedging program coverage.

**H4: Operational Leverage Decline from Volume Reduction (MEDIUM confidence)**
If production volumes declined post-2022 due to demand destruction or margin-driven curtailments, fixed costs are absorbed across fewer tonnes, mechanically increasing COGS/Revenue. Mechanism: cracker utilization rates directly drive fixed cost absorption. Internal data needed: production volumes by plant, utilization rates, fixed vs. variable cost decomposition.

**H5: Product Mix Shift Toward Lower-Margin Commodities (LOW confidence)**
The company may have shifted product mix toward lower-value commodity grades to maintain volume during the downturn, accepting lower margins. Mechanism: higher-value specialty grades have better spreads but may require different feedstocks or configurations. Internal data needed: revenue and margin by product grade, specialty vs. commodity mix over time.

---

## Data Readiness Assessment

The most critical data gap is the **sub-line COGS decomposition**. Public CVM filings aggregate all production costs into a single line. Without splitting into:
- **Feedstock costs** (naphtha, ethylene, propylene) — estimated ~55-60% of COGS
- **Energy costs** (steam crackers are energy-intensive)
- **Labor and overhead** (relatively fixed)
- **Maintenance and depreciation**

...it is impossible to determine whether the deterioration is input-cost driven, operational efficiency driven, or volume/absorption driven. This distinction is critical for remediation strategy.

The public filing analysis has definitively established THAT deterioration is structural and persistent. Understanding WHY requires internal data.
"""


async def stream(payload: dict, config) -> AsyncIterator[str]:
    """Yield analysis tokens. Uses Claude API if key is available, else streams mock."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        words = MOCK_RESPONSE.split(" ")
        for i, word in enumerate(words):
            token = word if i == len(words) - 1 else word + " "
            yield token
            await asyncio.sleep(0.02)
        return

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)

    findings        = payload.get("findings", [])
    composite_sigs  = payload.get("composite_signals", [])
    risk_score      = payload.get("risk_score", 0)
    risk_level      = payload.get("risk_level", "UNKNOWN")
    company_name    = payload.get("company_name", "Unknown Company")
    date_range      = payload.get("date_range", "2020-2025")
    language        = payload.get("language", "en")
    finding_cats    = payload.get("finding_categories", {})

    lang_str = "Portuguese (Brazilian)" if language == "pt-br" else "English"
    company_key = company_name.split()[0].upper()
    sector = SECTOR_MAP.get(company_key, "Unknown")
    sector_str = sector if sector != "Unknown" else "Unknown (infer from company name and findings)"

    system_prompt = (
        "You are a senior industry specialist and financial analyst with deep expertise in "
        "Brazilian capital markets, commodity-driven industries, and corporate financial "
        "analysis. You have access to CVM (Securities Commission of Brazil) public filings.\n\n"
        "You have been given the results of an automated financial pattern detection analysis "
        "on a Brazilian company. The analysis used only public CVM data (DFP annual and ITR "
        "quarterly filings) and detected patterns using statistical methods — no external "
        "context was applied.\n\n"
        "Your task is to provide expert context and interpretation:\n\n"
        "1. MACRO CONTEXT: What economic, industry, and market events during the analysis "
        "period (2020-2025) might explain the patterns detected? Be specific about timing "
        "and mechanisms — don't just list events, explain how they connect to the specific "
        "findings.\n\n"
        "2. HYPOTHESES: For each structural finding (cost deterioration, margin compression), "
        "generate 5-7 possible root causes. For each hypothesis:\n"
        "   - State the theory clearly\n"
        "   - Explain the specific mechanism (how would this cause show up in the numbers?)\n"
        "   - Identify what internal data source would confirm or refute it\n"
        "   - Rate your confidence (HIGH/MEDIUM/LOW)\n\n"
        "3. DATA READINESS ASSESSMENT: What questions does this analysis raise that public "
        "data cannot answer? For each question, identify the specific internal data source "
        "needed and why it matters.\n\n"
        "Be specific to the company and sector. Reference actual industry dynamics, not "
        f"generic financial theory. Write in {lang_str}."
    )

    def _findings_block(cat_name: str, ids: list) -> str:
        if not ids:
            return ""
        id_set = set(ids)
        relevant = [f for f in findings if f.get("id", "") in id_set]
        if not relevant:
            return ""
        lines = [f"### {cat_name}"]
        for f in relevant:
            dp = f.get("data_points", {})
            key_dp = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:4]) if dp else ""
            lines.append(
                f"- {f.get('id','')}: {f.get('pattern','')} — {f.get('description','')}"
                + (f"\n  Data: {key_dp}" if key_dp else "")
            )
        return "\n".join(lines)

    core_block       = _findings_block("Core Findings",       finding_cats.get("core", []))
    supporting_block = _findings_block("Supporting Evidence", finding_cats.get("supporting", []))
    contextual_block = _findings_block("Contextual Patterns", finding_cats.get("contextual", []))
    anomaly_block    = _findings_block("Anomalies",           finding_cats.get("anomalies", []))
    cs_types = ", ".join(s.get("composite_signal_type", "") for s in composite_sigs) or "None"

    user_prompt = (
        f"## Company\n{company_name} — {sector_str}\n\n"
        f"## Analysis Period\n{date_range}\n\n"
        f"## Risk Assessment\nRisk Score: {risk_score}/100 ({risk_level})\n"
        f"Composite Signals: {cs_types}\n\n"
        f"## Findings (ordered by narrative importance)\n\n"
        + "\n\n".join(filter(None, [core_block, supporting_block, contextual_block, anomaly_block]))
        + "\n\nProvide your expert analysis."
    )

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        temperature=0.7,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream_obj:
        async for text in stream_obj.text_stream:
            yield text


def run(config, pipeline_state: dict) -> dict:
    """REST endpoint handler — returns cached/pipeline_state data or pending status."""
    STEP = 7

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            return cached

    # Return existing pipeline_state data if streaming has completed
    step7_state = pipeline_state.get("step7")
    if step7_state and step7_state.get("response_text"):
        result = {
            "status": "complete",
            "data": step7_state,
            "metadata": {"cache_used": False, "source": "websocket"},
        }
        save_cache(STEP, result, CACHE_DIR, company_name=config.company_name)
        return result

    return {
        "status": "pending",
        "data": {},
        "metadata": {"cache_used": False, "source": "live"},
    }
