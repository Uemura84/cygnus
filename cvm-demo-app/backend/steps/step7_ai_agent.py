"""Step 7: AI Industry Specialist Agent — streams expert analysis via WebSocket.

Generates structured JSON via 5 focused API calls (one per section) to avoid
token-limit truncation on a single large response:

  1. macro_context       (~1,500 tokens max)
  2. profitability module (~2,000 tokens max)
  3. balance_sheet module (~2,000 tokens max)
  4. cash_flow module     (~2,000 tokens max)
  5. cross_module         (~1,000 tokens max)

Each call produces a small, bounded JSON fragment that is parsed and assembled
server-side. The WebSocket yields a single valid JSON string before [DONE].
"""

import asyncio
import json
import logging
import re
import os
from typing import AsyncIterator

from config import CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline.enrichment import SECTOR_MAP

logger = logging.getLogger(__name__)


# ── Mock response (valid JSON, Braskem-specific) ──────────────────────────────

_MOCK_DATA = {
    "macro_context": {
        "summary": (
            "Braskem's financial deterioration between 2021 and 2024 reflects three "
            "structural forces converging simultaneously: a commodity supercycle reversal, "
            "China's massive petrochemical capacity expansion, and an inherent feedstock cost "
            "disadvantage relative to North American ethane-based competitors. "
            "The 11pp COGS/Revenue shift and persistent margin compression are not a single "
            "shock but the cumulative effect of changes that became structural from 2022 onward. "
            "Understanding whether operational or commercial factors dominate the deterioration "
            "requires internal cost decomposition unavailable from public filings."
        ),
        "full_narrative": (
            "During 2020-2021, Braskem benefited from a post-COVID demand recovery that drove "
            "polyethylene and polypropylene spreads to multi-year highs. Naphtha feedstock costs "
            "remained manageable while end-market prices were elevated — gross margins reached "
            "approximately 30%, representing near-peak conditions for a naphtha-based cracker.\n\n"
            "The structural break came in early 2022, when Russia's invasion of Ukraine drove Brent "
            "crude above $100/bbl, directly transmitting into naphtha costs. Unlike US competitors "
            "using shale-derived ethane at a fraction of the cost, Braskem has no affordable "
            "feedstock alternative — every $10/bbl crude increase translates directly into higher "
            "COGS with limited ability to pass through in a commoditized polymer market.\n\n"
            "From mid-2022 through 2024, China commissioned approximately 15 million tonnes of new "
            "PE/PP capacity, far exceeding domestic demand growth. Chinese producers began exporting "
            "at marginal cost, depressing global polyethylene prices 20-30% from 2022 peaks.\n\n"
            "The 2023-2024 period saw BRL depreciation of approximately 20% vs. USD, mechanically "
            "inflating BRL-denominated input costs even as dollar feedstock prices partially stabilized."
        ),
    },
    "modules": {
        "profitability": {
            "summary": (
                "Profitability findings reveal a structural and persistent deterioration in COGS "
                "efficiency — the 11pp COGS/Revenue shift and 2.8pp/year margin compression together "
                "indicate the cost structure has fundamentally repriced relative to revenue capacity. "
                "The decoupling episodes confirm this is a directional divergence, not a timing mismatch."
            ),
            "finding_groups": [
                {
                    "group_label": "Cost Structure Deterioration (COGS Drift & Margin Compression)",
                    "finding_ids": ["F001", "F002"],
                    "top_hypothesis": {
                        "title": "Naphtha-ethane spread widening creating permanent feedstock cost disadvantage",
                        "confidence": "HIGH",
                        "explanation": (
                            "Braskem's naphtha-cracking model is structurally more expensive than US "
                            "ethane-based crackers — naphtha costs $350-500/tonne while ethane costs "
                            "$80-120/tonne equivalent, a gap that widened dramatically post-2022. "
                            "This feedstock disadvantage shows up directly as COGS/Revenue expansion, "
                            "since Braskem cannot reduce its primary input cost without changing its "
                            "cracker configuration. "
                            "The persistence of the shift after energy price normalization in 2023 "
                            "confirms this is structural, not cyclical."
                        ),
                        "confirmation_data": [
                            "Monthly feedstock cost per tonne vs. product realization price by polymer",
                            "Fixed vs. variable cost decomposition from internal costing system",
                            "Cracker utilization rates by plant",
                        ],
                    },
                    "additional_hypotheses": [
                        {
                            "title": "China PE/PP oversupply compressing product realization prices",
                            "confidence": "HIGH",
                            "explanation": (
                                "Chinese capacity additions of ~15Mt PE/PP between 2022-2024 flooded "
                                "global markets, driving polyethylene prices 20-30% below 2022 peaks. "
                                "Braskem's revenue per tonne declined while COGS remained elevated, "
                                "mechanically increasing COGS/Revenue. "
                                "Internal product-level pricing data would reveal whether Braskem had "
                                "to discount below cost-of-production in any product lines."
                            ),
                            "confirmation_data": [
                                "Revenue per tonne by product (PE, PP, PVC) over time",
                                "Market price benchmarks vs. realized prices",
                            ],
                        },
                        {
                            "title": "BRL depreciation amplifying USD-denominated input cost exposure",
                            "confidence": "MEDIUM",
                            "explanation": (
                                "BRL weakened approximately 30% vs. USD between 2020-2024, mechanically "
                                "increasing the BRL value of naphtha purchases without any physical cost increase. "
                                "This FX channel creates permanent COGS inflation in BRL-reported terms "
                                "that may conceal some improvement in dollar-denominated spreads. "
                                "Treasury hedging data would isolate whether this FX exposure is partially offset."
                            ),
                            "confirmation_data": [
                                "FX hedging coverage and program details from treasury",
                                "COGS decomposition showing USD vs. BRL-denominated cost proportions",
                            ],
                        },
                    ],
                },
            ],
        },
        "balance_sheet": {
            "summary": (
                "Balance sheet findings indicate simultaneous leverage escalation and equity erosion, "
                "suggesting debt-financed investment has not generated returns sufficient to offset "
                "rising financial costs during the commodity downswing. "
                "Working capital deterioration compounds the picture, consistent with a demand-softening "
                "commodity environment."
            ),
            "finding_groups": [
                {
                    "group_label": "Leverage and Equity Deterioration",
                    "finding_ids": ["F009", "F010"],
                    "top_hypothesis": {
                        "title": "Debt-financed capacity expansion commitments made at cycle peak",
                        "confidence": "HIGH",
                        "explanation": (
                            "Braskem likely committed to capital-intensive projects during the "
                            "2020-2021 supercycle peak when EBITDA was strong enough to service "
                            "incremental debt — as spreads compressed from 2022 onward, the same "
                            "debt load became disproportionate to generating capacity. "
                            "Net debt ratios expanded without additional borrowing simply because "
                            "the EBITDA denominator fell. "
                            "Internal capital allocation history would show whether investment decisions "
                            "were made on cycle-peak EBITDA assumptions."
                        ),
                        "confirmation_data": [
                            "Project-level EBITDA projections at investment approval vs. actual returns",
                            "Debt covenant headroom analysis — interest coverage ratios",
                            "EBITDA bridge from 2021 to 2024 by component",
                        ],
                    },
                    "additional_hypotheses": [
                        {
                            "title": "Alagoas geological event requiring extraordinary remediation expenditure",
                            "confidence": "HIGH",
                            "explanation": (
                                "Braskem faces substantial remediation costs related to geological "
                                "subsidence from salt mining operations in Alagoas, compressing equity "
                                "through liability provisioning that appears as erosion partially "
                                "contingent rather than operational. "
                                "The magnitude and timing of provisioning is only partially disclosed "
                                "in CVM footnotes. "
                                "Actuarial assessments of total liability would quantify the ongoing earnings drag."
                            ),
                            "confirmation_data": [
                                "Actuarial assessments of total Alagoas remediation liability",
                                "Legal settlement framework vs. provisions booked",
                            ],
                        },
                    ],
                },
            ],
        },
        "cash_flow": {
            "summary": (
                "Cash flow findings reveal a significant gap between reported earnings and actual "
                "cash generation, with FCF negative and capital investment below replacement levels — "
                "signaling both immediate liquidity pressure and medium-term productive capacity erosion. "
                "The debt dependency and dividend sustainability signals suggest the company may have "
                "funded shareholder returns with new borrowings during the downcycle."
            ),
            "finding_groups": [
                {
                    "group_label": "Earnings Quality and FCF Erosion",
                    "finding_ids": ["F014", "F015"],
                    "top_hypothesis": {
                        "title": "Interest cost crowding out operating cash due to leverage escalation",
                        "confidence": "HIGH",
                        "explanation": (
                            "As net debt expanded, interest payments consume an increasing share of "
                            "operating cash flow — even if EBITDA is stable, FCF can turn negative "
                            "purely from debt service growth. "
                            "With ~R$41bn net debt, interest payments are material enough to explain "
                            "the FCF gap even if operations are marginally cash-generative. "
                            "A debt service coverage analysis would quantify this channel precisely."
                        ),
                        "confirmation_data": [
                            "Interest expense paid (cash) vs. EBIT — interest coverage ratio trend",
                            "Debt maturity profile and upcoming refinancing requirements",
                            "OCF bridge: EBITDA to working capital changes to interest to FCF",
                        ],
                    },
                    "additional_hypotheses": [
                        {
                            "title": "Working capital movements consuming operating cash despite positive EBITDA",
                            "confidence": "HIGH",
                            "explanation": (
                                "If Braskem is building inventory or extending customer credit while "
                                "EBITDA is reported positively, OCF will lag EBITDA by the full "
                                "working capital investment amount. "
                                "This mechanism compounds the interest cost channel, making FCF doubly negative. "
                                "A detailed OCF bridge would isolate the exact working capital contribution."
                            ),
                            "confirmation_data": [
                                "OCF bridge by component: inventory, receivables, payables",
                                "Non-cash item register: provisions booked vs. cash settlements",
                            ],
                        },
                    ],
                },
            ],
        },
        "cross_module": {
            "summary": (
                "The convergence of profitability deterioration, leverage escalation, and negative FCF "
                "creates a reinforcing feedback loop: compressed margins reduce EBITDA, increasing "
                "leverage ratios; higher debt service reduces FCF; external financing required to "
                "bridge the gap further increases leverage. "
                "The Alagoas contingency adds an exogenous liability that compounds this structural "
                "pressure, making it difficult to separate operational from financial causes in "
                "public data alone."
            ),
            "what_would_change_this": (
                "The cross-module diagnosis would be materially revised if internal data reveals: "
                "(1) the COGS deterioration is primarily FX-translation rather than physical cost "
                "increase — if USD-denominated spreads have stabilized; "
                "(2) the Alagoas liability is fully provisioned and capped; "
                "or (3) cracker utilization data shows deliberate curtailments with a clear restart "
                "timeline, indicating the company is managing through a trough rather than in "
                "structural decline."
            ),
            "diagnoses": [
                {
                    "id": "DX001",
                    "label": "Structural Margin-Leverage Compression Loop",
                    "interpretation": (
                        "The simultaneous deterioration across all three modules is characteristic of a "
                        "commodity producer caught in a negative cycle where falling spreads reduce "
                        "debt-service capacity, forcing reliance on external financing that further "
                        "increases financial risk. "
                        "Breaking this loop requires either a commodity price recovery or a structural "
                        "cost reduction."
                    ),
                },
                {
                    "id": "DX002",
                    "label": "Feedstock Cost Disadvantage Amplified by Financial Leverage",
                    "interpretation": (
                        "The underlying feedstock cost disadvantage (naphtha vs. ethane) is being "
                        "amplified by Braskem's current leverage position — a competitor with the same "
                        "feedstock disadvantage but lower debt would have more flexibility to absorb "
                        "the cycle. "
                        "The financial structure is converting an industry-wide challenge into a "
                        "company-specific crisis."
                    ),
                },
            ],
        },
    },
}

MOCK_RESPONSE = json.dumps(_MOCK_DATA, ensure_ascii=False)


# ── JSON fragment helpers ─────────────────────────────────────────────────────

def _fix_literal_newlines(s: str) -> str:
    """Replace bare newlines/tabs inside JSON string values with escape sequences."""
    out: list[str] = []
    in_string = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and in_string:
            out.append(ch)
            if i + 1 < len(s):
                out.append(s[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            i += 1
            continue
        if in_string:
            if ch == "\n": out.append("\\n"); i += 1; continue
            if ch == "\r": out.append("\\r"); i += 1; continue
            if ch == "\t": out.append("\\t"); i += 1; continue
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_fragment(text: str) -> dict | None:
    """Parse a JSON fragment from an LLM section response."""
    if not text:
        return None
    cleaned = re.sub(r"^```json\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    cleaned = re.sub(r"^```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last > first:
        cleaned = cleaned[first : last + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_fix_literal_newlines(cleaned))
    except json.JSONDecodeError as e:
        logger.warning("Fragment parse failed: %s | first 200: %s", e, cleaned[:200])
        return None


# ── Section schemas (each call sees only its own schema) ──────────────────────

_MACRO_SCHEMA = """\
{
  "summary": "<MAX 60 WORDS: macro/industry backdrop explaining the key findings — lead with the dominant force, specific to the company's sector>",
  "full_narrative": "<3-4 paragraphs total: (1) 2020-2021 backdrop, (2) 2022 inflection and exact mechanism, (3) 2023-2024 structural dynamics, (4) sector-specific amplifier. Each paragraph MAX 60 words. Include specific numbers where available.>"
}"""

_MODULE_SCHEMA = """\
{
  "summary": "<MAX 40 WORDS: what this module's findings reveal as a whole — one clear thesis>",
  "finding_groups": [
    {
      "group_label": "<descriptive label for this cluster>",
      "finding_ids": ["F001", "F002"],
      "top_hypothesis": {
        "title": "<concise, specific hypothesis — the title carries the main insight>",
        "confidence": "HIGH|MEDIUM|LOW",
        "explanation": "<MAX 80 WORDS: specific mechanism + one key number. Do NOT restate the title. Add only what the title cannot convey.>",
        "confirmation_data": ["<internal data source 1>", "<source 2>", "<source 3>"]
      },
      "additional_hypotheses": [
        {
          "title": "<hypothesis title>",
          "confidence": "HIGH|MEDIUM|LOW",
          "explanation": "<MAX 50 WORDS: mechanism + key number only>",
          "confirmation_data": ["<source 1>", "<source 2>"]
        }
      ]
    }
  ]
}"""

_CROSS_SCHEMA = """\
{
  "summary": "<MAX 40 WORDS: cross-module synthesis in one clear thesis>",
  "what_would_change_this": "<MAX 30 WORDS: the one or two specific internal data points that would materially change the diagnosis>",
  "diagnoses": [
    {
      "id": "DX001",
      "label": "<diagnosis label>",
      "interpretation": "<MAX 60 WORDS: what this composite signal means and why it matters>"
    }
  ]
}"""

_DEFAULTS = {
    "macro":    {"summary": "", "full_narrative": ""},
    "module":   {"summary": "", "finding_groups": []},
    "cross":    {"summary": "", "what_would_change_this": "", "diagnoses": []},
}


# ── Main stream function ──────────────────────────────────────────────────────

async def stream(payload: dict, config) -> AsyncIterator[str]:
    """Yield a single valid JSON string (all sections assembled). Uses 5 focused API calls."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        yield MOCK_RESPONSE
        return

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)

    findings       = payload.get("findings", [])
    composite_sigs = payload.get("composite_signals", [])
    risk_score     = payload.get("risk_score", 0)
    risk_level     = payload.get("risk_level", "UNKNOWN")
    company_name   = payload.get("company_name", "Unknown Company")
    date_range     = payload.get("date_range", "2020-2025")
    language       = payload.get("language", "en")

    lang_str    = "Portuguese (Brazilian)" if language == "pt-br" else "English"
    company_key = company_name.split()[0].upper()
    sector      = SECTOR_MAP.get(company_key, "Unknown")
    sector_str  = sector if sector != "Unknown" else "Unknown (infer from company name and findings)"
    cs_types    = ", ".join(s.get("composite_signal_type", "") for s in composite_sigs) or "None"

    # ── Shared base system ────────────────────────────────────────────────────

    base_system = (
        "CRITICAL: You MUST respect the word limits specified for each field. "
        "Shorter is better. A CFO will scan this in 30 seconds — every sentence must earn its place. "
        "If you can say it in 10 words, do not use 30.\n\n"
        "You are a senior industry specialist and financial analyst with deep expertise in "
        "Brazilian capital markets, commodity-driven industries, and corporate financial analysis.\n\n"
        "CRITICAL: Output ONLY valid JSON. No markdown fences, no ```json, no preamble, "
        "no explanation outside the JSON. The output must be directly parseable by JSON.parse().\n\n"
        f"Write all text in {lang_str}. "
        "Keep confidence values as HIGH, MEDIUM, or LOW (always in English). "
        "Maximum 3 items in additional_hypotheses. "
        "Group ALL findings of the same pattern type into ONE finding_group — never create one group per finding. Target 2-3 groups total per module. "
        "Be specific to the company's sector — not generic financial theory. "
        "The hypothesis TITLE is the primary carrier of meaning. "
        "The explanation adds only the specific mechanism and one key number — nothing else.\n\n"
        "Before returning your response, verify that EVERY field respects its word limit. "
        "Cut ruthlessly. The hypothesis title should do most of the work — "
        "the explanation adds only what the title cannot convey."
    )

    # ── Shared context ────────────────────────────────────────────────────────

    ctx = (
        f"Company: {company_name} — {sector_str}\n"
        f"Period: {date_range}  |  Risk: {risk_score}/100 ({risk_level})  |  Signals: {cs_types}\n"
    )

    def _fmt_findings(module_key: str) -> str:
        relevant = [f for f in findings if f.get("module", "profitability") == module_key]
        if not relevant:
            return "  (none)"
        groups: dict[str, list] = {}
        for f in relevant:
            groups.setdefault(f.get("pattern", "other"), []).append(f)
        lines = []
        for pattern, flist in groups.items():
            ids = ", ".join(f.get("id", "") for f in flist)
            lines.append(f"  Group '{pattern}' [{ids}]:")
            for f in flist:
                dp = f.get("data_points", {})
                dp_s = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:3]) if dp else ""
                row = f"    {f.get('id','')}: {f.get('description','')[:90]}"
                if dp_s:
                    row += f" [{dp_s}]"
                lines.append(row)
        return "\n".join(lines)

    def _fmt_stacked() -> str:
        stacked = [f for f in findings if f.get("module") == "stacked"]
        if not stacked:
            return "  (none)"
        return "\n".join(
            f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {f.get('description','')[:100]}"
            for f in stacked
        )

    def _all_findings_brief() -> str:
        rows = []
        for f in findings:
            if f.get("module") == "stacked":
                continue
            rows.append(f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {f.get('description','')[:70]}")
        return "\n".join(rows) if rows else "  (none)"

    # ── Single-section call ───────────────────────────────────────────────────

    async def _call(section_name: str, schema: str, user_prompt: str, max_tok: int) -> dict | None:
        system = (
            base_system
            + f"\n\nGenerate ONLY the `{section_name}` JSON object using this exact schema:\n{schema}"
        )
        try:
            resp = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tok,
                temperature=0.7,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = resp.content[0].text
            stop_reason = resp.stop_reason
            logger.info(
                "Step 7 section '%s': stop_reason=%s, output_tokens=%d, raw_len=%d",
                section_name, stop_reason, resp.usage.output_tokens, len(raw),
            )
            if stop_reason == "max_tokens":
                logger.warning(
                    "Step 7 section '%s' hit max_tokens=%d — response truncated. Last 200 chars: %s",
                    section_name, max_tok, raw[-200:],
                )
            result = _parse_fragment(raw)
            if result is None:
                logger.warning("Step 7 section '%s' produced unparseable output: %s", section_name, raw[:200])
            return result
        except Exception as e:
            logger.error("Step 7 section '%s' API call failed: %s", section_name, e)
            return None

    # ── Five focused calls ────────────────────────────────────────────────────

    macro_data = await _call(
        "macro_context", _MACRO_SCHEMA,
        ctx + "\nAll findings:\n" + _all_findings_brief()
        + "\n\nGenerate the macro_context section: macro/industry events that explain these findings.",
        max_tok=1500,
    ) or dict(_DEFAULTS["macro"])

    prof_data = await _call(
        "profitability", _MODULE_SCHEMA,
        ctx + "\nProfitability findings:\n" + _fmt_findings("profitability")
        + "\n\nGenerate the profitability module section. Group related findings (same pattern type) into one finding_group — aim for 2-3 groups max.",
        max_tok=3000,
    ) or dict(_DEFAULTS["module"])

    bs_data = await _call(
        "balance_sheet", _MODULE_SCHEMA,
        ctx + "\nBalance sheet health findings:\n" + _fmt_findings("balance_sheet_health")
        + "\n\nGenerate the balance_sheet module section. Group related findings into 2-3 groups max.",
        max_tok=2500,
    ) or dict(_DEFAULTS["module"])

    cf_data = await _call(
        "cash_flow", _MODULE_SCHEMA,
        ctx + "\nCash flow quality findings:\n" + _fmt_findings("cash_flow_quality")
        + "\n\nGenerate the cash_flow module section. Group related findings into 2-3 groups max.",
        max_tok=2500,
    ) or dict(_DEFAULTS["module"])

    cross_data = await _call(
        "cross_module", _CROSS_SCHEMA,
        ctx + "\nCross-module diagnoses:\n" + _fmt_stacked()
        + "\n\nGenerate the cross_module section: synthesis and what-would-change-this.",
        max_tok=1000,
    ) or dict(_DEFAULTS["cross"])

    # ── Assemble and yield ────────────────────────────────────────────────────

    result = {
        "macro_context": macro_data,
        "modules": {
            "profitability": prof_data,
            "balance_sheet": bs_data,
            "cash_flow": cf_data,
            "cross_module": cross_data,
        },
    }
    yield json.dumps(result, ensure_ascii=False)


def run(config, pipeline_state: dict) -> dict:
    """REST endpoint handler — returns cached/pipeline_state data or pending status."""
    STEP = 7

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            return cached

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
