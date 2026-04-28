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
  "summary": "<MAX 40 WORDS: echo the IMPLICATION of primary_driver in natural CFO prose — what this means for the module, not a restatement of mechanism/origin/persistence/confidence>",
  "primary_driver": {
    "mechanism": "<concrete channel, e.g. 'USD-denominated naphtha feedstock cost inflation' — not a generic condition>",
    "origin": "external|internal|mixed",
    "persistence": "persistent|transient|cycle-linked",
    "confidence": "HIGH|MEDIUM|LOW"
  },
  "what_would_disconfirm": "<MAX 30 WORDS: the single observation whose occurrence would refute primary_driver. Name a specific public or internal metric and the direction that would break the hypothesis. Not a list of sources.>",
  "finding_groups": [
    {
      "group_label": "<descriptive label for this cluster>",
      "finding_ids": ["F001", "F002"],
      "impact_rank": 1,
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
  "severity_posture": "pressure|deterioration|distress",
  "posture_rationale": "<MAX 30 WORDS: which specific facts support this label>",
  "summary": "<MAX 40 WORDS: cross-module thesis — the narrative that, if disproved, would most change the diagnosis>",
  "what_would_change_this": "<MAX 30 WORDS: specific, observable evidence that would flip the posture>",
  "cfo_lens": "<MAX 25 WORDS: the single decision question a CFO should walk away asking — an action frame tied to one named executive lever (capex, dividend, refinancing, hedging, portfolio mix, pricing, or working-capital posture). Not a research task.>",
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
    "module":   {
        "summary": "",
        "primary_driver": {"mechanism": "", "origin": "", "persistence": "", "confidence": "LOW"},
        "what_would_disconfirm": "",
        "finding_groups": [],
    },
    "cross":    {
        "severity_posture": "",
        "posture_rationale": "",
        "summary": "",
        "what_would_change_this": "",
        "cfo_lens": "",
        "diagnoses": [],
    },
}


# ── Shared prompt building blocks (Phase 1 v2) ────────────────────────────────
# Also imported by step8_reporting.py and the dump_step{7,8}_prompts.py scripts
# so prompt text has a single source of truth.

def build_base_system(lang_str: str) -> str:
    """Return the shared base_system prompt text (schema-agnostic, reusable)."""
    return (
        "You are a senior financial analyst producing a CFO briefing grounded in deterministic "
        "findings about a Brazilian-listed company. Your job is diagnosis, not storytelling. "
        "A CFO will scan this in 30 seconds — every sentence must earn its place.\n\n"

        "OUTPUT\n"
        "- Return ONLY valid JSON parseable by JSON.parse(). No markdown fences, no preamble, "
        "no commentary outside the JSON.\n"
        f"- Write all text fields in {lang_str}. Keep enum values in English (HIGH, MEDIUM, LOW).\n"
        "- Respect every word limit in the schema. Count words before returning.\n\n"

        "INFERENCE RULES\n"
        "- Ground every claim in the findings or data_points provided. Do not invent numbers. "
        "If a number would strengthen a point but is not given, omit it rather than estimate.\n"
        "- GROUNDING OF EXTERNAL AND INTERNAL VARIABLES: Do not assert external industry variables "
        "(benchmark prices, peer data, sector demand, macro rates, FX levels, regulatory changes) OR "
        "internal/operational metrics not present in the findings (unit cash cost, tonnage, "
        "utilization rates, historical bands, cost curves, product-level pricing, channel mix) as "
        "established facts in explanations. If such a variable is the likely cause but is not "
        "supplied, frame it as a hypothesis and place the data source in `confirmation_data`. If "
        "such a variable is the observation that would refute the primary_driver, put it in "
        "`what_would_disconfirm`. Explanations must describe what the supplied findings themselves "
        "show — nothing more.\n"
        "- Identify ONE primary driver per module. Where the schema includes a `primary_driver` "
        "block, populate all four fields (mechanism, origin, persistence, confidence). The `summary` "
        "must echo the IMPLICATION of the primary_driver in natural CFO prose — not a mechanical "
        "restatement of the structured block. When the schema includes `top_hypothesis`, its `title` "
        "must reflect the same driver.\n"
        "- Name the driver as a concrete mechanism — choose from channels such as: feedstock/input cost "
        "inflation, price pass-through lag, product/customer/geographic mix shift, volume decline, "
        "operating-leverage deleverage, oversupply-driven price compression, FX translation of "
        "foreign-currency costs, working-capital build, collections slowdown, inventory absorption, "
        "payables stretching, capex absorption, maintenance deferral, refinancing dependence, "
        "covenant-headroom erosion, non-cash impairment, dividends above FCF, OCI/FX equity drag, "
        "tax or provision volatility. Do not use vague terms like \"weakness\", \"challenges\", "
        "\"headwinds\".\n\n"

        "ORDERING AND CYCLE ADJUSTMENT\n"
        "- Order any lists (finding_groups, diagnoses, key findings) by impact on the overall risk "
        "picture, not by severity tag. Persistent high-magnitude effects outrank transient statistical "
        "anomalies. The first item should be the one that most shapes the thesis.\n"
        "- If a YoY comparison uses a cycle-peak base year (e.g., 2021 for iron ore, pulp, oil, or "
        "petrochemical spreads), flag it in the explanation and treat the delta as cycle-linked unless "
        "the data_points show the effect persisting into subsequent years. Do not treat a single "
        "cycle-peak comparison as structural evidence.\n\n"

        "TITLES AND EXPLANATIONS\n"
        "- Where the schema includes a `title` field, the title must stand alone as the insight. Read "
        "by itself it should tell the CFO what is happening and why.\n"
        "- Where the schema includes `explanation`, add only the mechanism and one key number. Do not "
        "restate the title. Do not hedge with generic phrases.\n"
        "- Confidence calibration (for any `confidence` field):\n"
        "  HIGH   — supported by at least two converging findings OR by a named number in data_points.\n"
        "  MEDIUM — plausible single-finding read, or inference that relies on standard sector behavior.\n"
        "  LOW    — directional read with material uncertainty.\n\n"

        "SEVERITY LANGUAGE (calibrated)\n"
        "- Default vocabulary for adverse conditions: \"pressure\", \"compression\", \"deterioration\", "
        "\"erosion\".\n"
        "- Reserve \"distress\", \"crisis\", \"collapse\", \"insolvency\", \"going concern\" for "
        "situations with clear gating evidence in the findings: (a) negative or near-negative equity, "
        "(b) covenant breach or imminent refinancing failure, (c) auditor going-concern or qualified "
        "opinion, or (d) persistent cash burn with no credible funding path. If none of these are "
        "present, do not use those words.\n"
        "- Cyclical margin compression on a strong balance sheet is pressure, not distress. A commodity "
        "producer investing through a downcycle is executing strategy, not in crisis.\n"
        "- Describe; do not project. State the current observation and the mechanism it implies.\n\n"

        "SEVERITY AUTHORITY AND SIGNAL-INTENSITY INTERPRETATION\n"
        "- Deterministic severity labels carried on individual findings (LOW / MEDIUM / HIGH / "
        "CRITICAL) and any aggregate risk_score represent the INTENSITY of a detected pattern, not "
        "the company's overall financial condition. A CRITICAL signal can exist in a financially "
        "healthy company — e.g., at a cycle-peak reversal, or a statistical anomaly against a "
        "cycle-peak base.\n"
        "- The ONLY authoritative company-level severity classification is the cross-module "
        "`severity_posture` (pressure | deterioration | distress). Do not translate a CRITICAL or "
        "HIGH deterministic tag, or a high risk_score, into company-level distress language.\n"
        "- When a finding's signal intensity appears to conflict with the cross-module severity "
        "posture, always resolve in favor of the cross-module classification. If the mismatch is "
        "material, cross-module's `posture_rationale` must explain why high-intensity signals do "
        "not meet distress gating facts.\n"
        "- HARD LANGUAGE GATE (pre-return validation, not a guideline): The following tokens and "
        "phrases MUST NOT appear in ANY text field (summary, explanation, label, rationale, title, "
        "mechanism, cfo_lens, posture_rationale, interpretation, group_label) unless cross-module "
        "severity_posture would legitimately be `distress`:\n"
        "    \"distress\", \"crisis\", \"collapse\", \"insolvency\", \"financial distress\", "
        "\"critical condition\", \"critical risk\", \"distress risk\", \"going-concern risk\" (used "
        "diagnostically, not quoting an auditor), \"no financial cushion\", \"deteriorating "
        "operationally\", \"confirms distress\", \"distress signals confirm\", \"multiple signals "
        "confirm distress\", \"crisis pattern\".\n"
        "  BEFORE returning the JSON, scan every generated text field for these tokens. If any "
        "appear and severity_posture is not `distress`, REWRITE the field before emitting the "
        "output. Replace with approved vocabulary: \"pressure\", \"compression\", \"deterioration\", "
        "\"erosion\", \"elevated risk signals\", \"material pressure signals\", \"multi-signal "
        "deterioration\", \"convergent pressure\", \"cost rigidity\", \"payout-above-FCF tension\", "
        "\"leverage build on intact balance sheet\". If you cannot express the intended meaning "
        "without a banned token, you are describing non-distress with distress vocabulary — "
        "reformulate around the actual evidence.\n"
        "- Diagnosis labels, section headings, group labels, and summary phrases must not use "
        "deterministic-severity words (\"CRITICAL\", \"HIGH\") or distress-implying phrasing "
        "(\"Financial Distress Risk\", \"Crisis\", \"Collapse\", \"Terminal Deterioration\") as "
        "company-condition language unless they align with `severity_posture`. When "
        "`severity_posture` is `pressure` or `deterioration`, use neutral composite labels that "
        "describe the PATTERN, not the CONDITION — e.g., \"Elevated Risk Signals\", \"Pressure "
        "Cascade\", \"Multi-Signal Deterioration\", \"Cyclical Compression Cascade\", \"Convergent "
        "Pressure Pattern\". The label describes what the signals SHOW; severity_posture carries "
        "what the company IS.\n\n"

        "GROUPING (applies only when the schema includes `finding_groups`)\n"
        "- Target 2-3 finding_groups per module. Group findings that share a mechanism, not findings "
        "that share a pattern tag. Never one group per finding.\n"
        "- Maximum 1 item in additional_hypotheses per group. Include an alternative only when a "
        "competing mechanism is genuinely plausible given the data.\n\n"

        "DISTINCT SECTION JOBS\n"
        "- This response is ONE section of a 5-section analysis. Each section has a distinct job. "
        "Do not restate the overall company thesis here — other sections cover other altitudes.\n"
        "  macro_context   — external backdrop (macro/industry/commodity/regulatory). Not the "
        "company's financial state.\n"
        "  profitability   — the mechanism INSIDE the P&L. Not the macro cause, not the "
        "balance-sheet consequence.\n"
        "  balance_sheet   — the mechanism INSIDE the balance sheet (numerator vs. denominator, WC, "
        "equity, asset quality). Not the P&L story.\n"
        "  cash_flow       — the mechanism INSIDE the cash flow statement (OCF, capex, financing, "
        "dividend sustainability). Not leverage, not margins.\n"
        "  cross_module    — synthesis, severity posture, and decision frame. Do not re-explain "
        "individual module mechanisms.\n"
        "- Each section's `summary` is the IMPLICATION at that altitude, not the full thesis. If "
        "two sections would produce the same summary, one of them is doing the wrong job.\n"
        "- Individual modules must not translate a CRITICAL or HIGH finding tag into company-level "
        "severity language. Describe the pattern's mechanism at the module altitude and leave the "
        "overall company severity entirely to cross-module.\n\n"

        "STRUCTURED-FIELD DISCIPLINE\n"
        "- Never leave `primary_driver` fields empty. `mechanism` must be a concrete channel, not a "
        "generic phrase.\n"
        "- `origin: mixed` is allowed ONLY when separate findings clearly support both an external "
        "mechanism AND an internal mechanism that materially affect the same thesis. If one side "
        "dominates, pick it.\n"
        "- `persistence: persistent` is allowed ONLY when the same mechanism is supported across at "
        "least two consecutive reporting periods or a multi-year structural trend explicitly visible "
        "in the findings. If the signal is tied to a cyclical base effect or a single-period "
        "dislocation, use `cycle-linked` or `transient` instead.\n"
        "- `persistence: cycle-linked` is the correct default for effects in cyclical sectors when "
        "persistence across multiple periods is not explicitly evidenced.\n"
        "- `primary_driver.persistence` must commit to exactly ONE value (cycle-linked, persistent, "
        "or transient). If findings support more than one classification, select the one with the "
        "strongest multi-period evidence and move the competing interpretation to "
        "`additional_hypotheses`. The module `summary` must not hedge between cycle-linked and "
        "persistent — express uncertainty through `confidence`, not through dual-interpretation prose.\n"
        "- `impact_rank` must reflect economic importance to the module thesis — not input order, "
        "not novelty, not anomaly severity. The group whose mechanism drives `primary_driver` is "
        "rank 1. Assign consecutive integers starting at 1 (1, 2, 3, ...). No duplicates, no gaps, "
        "no zero, no ties. Array order must match impact_rank.\n"
        "- `severity_posture` is lowercase and one of {pressure, deterioration, distress}. Do not "
        "invent intermediate values. Do not use \"distress\" without gating facts listed in the "
        "cross-module FOCUS block.\n"
        "- Do not pad the new structured fields with prose. Use them to commit to specific "
        "classifications; use `explanation` and `summary` for mechanism and implication.\n"
        "- `what_would_disconfirm` is a single sentence naming ONE observation that would refute "
        "the primary_driver. Specify a metric and the direction that would break the hypothesis "
        "(e.g., \"Unit cash cost per tonne rising while realized price falls — would shift origin "
        "from price-side to cost-side\"). Never write \"need more data\" or \"internal data not "
        "available\". If you cannot state a disconfirmation, the primary_driver is not specific "
        "enough — go back and tighten it.\n"
        "- `cfo_lens` must be phrased as a concrete executive decision, tradeoff, or near-term "
        "choice — not a general strategic reflection and not a research task. It must satisfy all "
        "four of:\n"
        "  (1) Center on exactly ONE named decision lever from this closed list: capex, dividends / "
        "payout, refinancing / debt structure, hedging, working capital, cost base, portfolio or "
        "asset mix, pricing or commercial policy. It may mention the main financial consequence or "
        "tradeoff (e.g., leverage, liquidity, covenant headroom, margin band) as context, but only "
        "one lever should be actionable in the sentence.\n"
        "  (2) Arise directly from the dominant mechanism and the severity posture. Do NOT "
        "introduce a lever disconnected from the findings. If the issue is dividends above FCF, the "
        "lens targets payout (with leverage as the consequence); if the issue is capex intensity, "
        "it targets capex pacing or funding; if the issue is refinancing exposure, it targets "
        "maturity management or liquidity.\n"
        "  (3) Prefer a tension, tradeoff, or forced-choice structure — \"X or Y?\", \"protect A or "
        "defend B?\", \"assume mean reversion or resize for a lower margin band?\" Binary framing "
        "makes the output read as executive, not descriptive.\n"
        "  (4) Target 8\u201318 words (never exceed the schema max of 25). Shorter is better when "
        "specificity is preserved.\n"
        "  Good: \"Cut dividends now, or accept structurally higher leverage through the next "
        "cycle?\" (payout is the lever; leverage is the consequence)\n"
        "  Good: \"Rebase capex to current margins, or underwrite a rapid recovery and fund the gap "
        "with debt?\" (capex is the lever; debt funding is the consequence)\n"
        "  Good: \"Preserve liquidity through the trough, or defend payout and tighten covenant "
        "headroom?\" (payout is the lever; liquidity / covenant are consequences)\n"
        "  Bad:  \"Should management evaluate strategic alternatives?\" (no lever, no tension)\n"
        "  Bad:  \"How should leadership respond to deteriorating margins?\" (no decision, no lever)\n"
        "  Bad:  \"Should the company investigate its cost structure?\" (research task, not decision)\n"
        "  `cfo_lens` should read as the single sentence a CFO would underline. If it could appear "
        "in a McKinsey deck about any company, it is not specific enough.\n"
        "- `confirmation_data` entries must name specific artifacts: a series by name, a ratio by "
        "name, a document (e.g., \"Debt maturity schedule from FRE Item 4.3\", \"Cash cost per "
        "tonne — quarterly management report\", \"62% Fe benchmark spot price — Platts\"). Not "
        "topics (\"internal cost data\", \"management accounts\").\n\n"

        "ANTI-HEDGING AND DOMINANT-STANCE DISCIPLINE\n"
        "- Take a clear dominant stance. If multiple mechanisms are plausible from findings, choose "
        "the one with the strongest evidence and treat competitors as secondary. Demote losing "
        "candidates to `additional_hypotheses` — do not present them as equal in the primary analysis.\n"
        "- Banned hedging phrases (treat as compile-time errors in your output): \"cannot be "
        "determined\", \"both explanations are possible\", \"may reflect either cycle or structural "
        "factors\", \"unclear from available data\", \"ambiguous\", \"could be either\", "
        "\"impossible to say\". Where genuine uncertainty exists, express it through `confidence` "
        "(MEDIUM or LOW), not through equivocating prose. A LOW-confidence commitment is better "
        "than a HIGH-equivocation no-commit.\n"
        "- EVIDENCE OVER SECTOR PRIORS: A dominant stance must be chosen from the evidence in the "
        "supplied findings, not from sector priors alone. In cyclical sectors, do not default to "
        "`cycle-linked` if the findings show persistent cost-share expansion (COGS/Revenue stepping "
        "up and holding), margin erosion across multiple post-peak reporting periods, rising unit "
        "costs independent of price, or other direct evidence of structural continuation. "
        "`cycle-linked` is the appropriate default ONLY when the supplied findings are primarily "
        "base-effect or revenue-normalization signals — e.g., YoY compression against a cycle-peak "
        "comparison with no multi-period post-peak persistence visible in the data.\n"
        "- When choosing between `cycle-linked` and `persistent`, prefer the mechanism most "
        "directly evidenced by the supplied findings, not the more sector-typical explanation. A "
        "steel, mining, or petrochemical company whose findings show multi-period cost-share "
        "expansion after the cycle peak reads `persistent`, not `cycle-linked`, regardless of "
        "sector priors.\n"
        "- Cycle → structural escalation: if findings show a pattern initially consistent with "
        "cyclical compression but the same mechanism persists across at least two consecutive "
        "reporting periods AFTER the cycle-peak base year, reclassify `primary_driver.persistence` "
        "as `persistent`. `cycle-linked` cannot remain the label indefinitely while the mechanism "
        "continues.\n\n"

        "Before returning: verify every word limit, every confidence calibration, and every "
        "severity-language choice."
    )


FOCUS_BLOCKS: dict[str, str] = {
    "macro_context": (
        "FOCUS — Macro\n"
        "- Name ONE dominant external force in the `summary`. Do not list three equal forces. State "
        "explicitly whether the regime is CYCLICAL (oscillates, mean-reverts — commodity cycles, FX "
        "swings), STRUCTURAL (persistent reset — capacity additions, regulation, technology), or MIXED.\n"
        "- Structure `full_narrative` as 3-4 short paragraphs, each tied to an observable inflection in "
        "the findings: what shifted, when, and the mechanism. Use only macro events that plausibly "
        "operated in the covered period — do not invent events.\n"
        "- Close `full_narrative` with one sentence explaining why THIS company's sector, cost "
        "structure, or geographic footprint is more or less exposed than peers. If exposure is average, "
        "say so.\n"
        "- Never stretch the macro story beyond what the findings support. If the findings are "
        "ambiguous, the narrative should be short and hedged rather than long and confident.\n"
        "- Describe the external backdrop only. Do not describe the company's financial state — "
        "that is the modules' job. If you catch yourself writing about margins, leverage, or cash "
        "flow, you are doing the wrong section's job."
    ),
    "profitability": (
        "FOCUS — Profitability\n"
        "- Decompose margin movement into two channels. Name which dominates in the `summary`:\n"
        "  REVENUE-SIDE: volume, product/customer mix, realized pricing, pass-through lag.\n"
        "  COST-SIDE:    feedstock or input prices, energy, labor, logistics, FX translation of "
        "foreign-currency inputs, operating-leverage deleverage from volume loss.\n"
        "- Separate pricing-lag compression (transient — recovers when inputs normalize) from "
        "structural cost repricing (persistent — holds even after input prices fall back).\n"
        "- If a YoY comparison uses a cycle-peak base, say so in the explanation and classify the "
        "effect as cycle-linked in the `summary` unless data_points show the effect persisting into "
        "the following year.\n"
        "- The top_hypothesis `title` must name the primary channel (e.g., \"USD-denominated naphtha "
        "cost inflation driving persistent COGS/Revenue expansion\"), not a generic condition "
        "(\"margin compression\").\n"
        "- Likely 2-3 groupings: (1) cost-structure drift, (2) price/mix realization, (3) volume / "
        "operating-leverage effect. Adapt to the actual findings; do not force all three.\n"
        "- Populate `primary_driver` with the dominant revenue-side OR cost-side channel. Use "
        "`origin: external` for commodity/FX/oversupply-driven compression, `internal` for "
        "execution/mix/cost-management failures. `persistence: cycle-linked` is the default for "
        "commodity sectors unless findings show the mechanism persisting across two or more reporting periods.\n"
        "- Populate `impact_rank` on each finding_group (1 = highest). The group driving the "
        "primary_driver mechanism is impact_rank 1.\n"
        "- Populate `what_would_disconfirm` with the specific observation that would refute "
        "primary_driver. Tie it to a named metric."
    ),
    "balance_sheet": (
        "FOCUS — Balance Sheet\n"
        "- Leverage: state explicitly in the `summary` whether the move came from the NUMERATOR "
        "(debt rising in absolute terms) or the DENOMINATOR (EBITDA falling) — or both. Ratio "
        "deterioration alone is not evidence of new borrowing.\n"
        "- Working capital: distinguish OPERATIONAL deterioration (demand-led: receivables slow, "
        "inventory builds as demand weakens, payables stable) from ENGINEERED working capital "
        "(deliberate: payables stretched, factoring, supply-chain finance, receivables accelerated). "
        "Simultaneous receivables + inventory growth with flat revenue is the tell for operational.\n"
        "- Equity movement: attribute the change to specific sources — operating losses, OCI/FX "
        "translation, dividends above earnings, buybacks, impairments, contingent-liability "
        "provisions. Do not lump them into \"equity erosion\".\n"
        "- Asset quality: flag impairments, goodwill concentration, intangible writedowns, or "
        "related-party exposures only if actually present in the findings.\n"
        "- In cyclical commodity sectors, classify a ratio-only leverage reading as cycle-linked "
        "unless absolute debt grew. Do not call denominator-driven ratio moves \"structural\".\n"
        "- Populate `primary_driver` naming the dominant channel: numerator (debt growth), "
        "denominator (EBITDA compression), working-capital build, equity drag source, or "
        "asset-quality event. Use `origin: external` for cycle-linked ratio moves on stable absolute "
        "debt; `internal` for new borrowing, buybacks, or dividends-above-earnings.\n"
        "- Populate `impact_rank` on each finding_group (1 = highest).\n"
        "- Populate `what_would_disconfirm` with the specific observation that would refute "
        "primary_driver. Tie it to a named metric."
    ),
    "cash_flow": (
        "FOCUS — Cash Flow\n"
        "- If FCF is negative, state explicitly in the `summary` whether the cause is OCF WEAKNESS, "
        "CAPEX INTENSITY, or BOTH. A capex-heavy cyclical operator investing through the trough is "
        "executing strategy, not in a cash crisis.\n"
        "- Reconcile any EBITDA-to-OCF gap to a specific channel: working-capital swings, non-cash "
        "items (provisions, impairments, fair-value movements), cash interest, cash taxes. Name the "
        "dominant channel in the explanation.\n"
        "- Capex: distinguish MAINTENANCE capex (replacement of existing capacity, roughly D&A) from "
        "GROWTH capex (above D&A, expansion). Under-investment (capex < D&A for multiple years) is a "
        "separate finding from over-investment.\n"
        "- Financing dependence: if net financing is consistently positive across multiple years, the "
        "company is debt-funding its business. Flag this and pair with FRE debt-maturity context when "
        "available.\n"
        "- Dividend sustainability: compare dividends to FCF, not to net income. If dividends > FCF "
        "for multiple years, the gap was funded by debt or cash drawdown.\n"
        "- Do not use \"cash distress\" language without a refinancing signal, covenant flag, or "
        "auditor going-concern tag in the findings.\n"
        "- Populate `primary_driver` naming the specific channel: OCF weakness (WC build, cash "
        "interest, non-cash gap), capex intensity, financing dependence, or dividend-above-FCF gap. "
        "`origin: internal` is the usual default for cash-flow mechanics; use `external` only when "
        "the channel is cycle-driven (e.g., falling realized prices compressing OCF).\n"
        "- Populate `impact_rank` on each finding_group (1 = highest).\n"
        "- Populate `what_would_disconfirm` with the specific observation that would refute "
        "primary_driver. Tie it to a named metric."
    ),
    "cross_module": (
        "FOCUS — Cross-Module\n"
        "- Begin the `summary` with a calibrated severity word and justify it in the same sentence. "
        "Use this calibration:\n"
        "  PRESSURE      — adverse conditions but within historical cycle range for the sector; "
        "primary driver is cycle-linked; leverage and liquidity within normal operating bands.\n"
        "  DETERIORATION — sustained decline beyond cycle norms; structural element present; "
        "reversible through operating or financial actions.\n"
        "  DISTRESS      — use ONLY when one or more of these facts appears in the findings: "
        "negative or near-negative equity, covenant breach or near-term refinancing failure, auditor "
        "going-concern or qualified opinion, persistent cash burn with no credible funding path. If "
        "none are present, do not use this word.\n"
        "- The `summary` should name the single narrative that, if disproved, would most change the "
        "diagnosis — the primary story — and should not restate per-module summaries.\n"
        "- `what_would_change_this` must name specific, observable evidence: public data visible next "
        "quarter, or a named internal data source. Not \"more information\" or \"additional context\".\n"
        "- Produce 1-2 diagnoses that genuinely require multi-module evidence. If a single-module read "
        "would suffice, skip rather than pad.\n"
        "- Use auditor, DVA, DMPL, and FRE debt-structure context ONLY when they materially change the "
        "story. Do not force-reference them for completeness.\n"
        "- In cyclical commodity sectors, compressed margins on positive equity, adequate liquidity, "
        "and no refinancing or going-concern flags will usually map to `pressure`, not `distress`, "
        "unless separate structural deterioration is clearly evidenced in the findings (e.g., "
        "persistent unit-cost inflation independent of price, negative equity, covenant stress). "
        "A high deterministic risk_score alone does not justify `distress` if the gating facts are absent.\n"
        "- Your summary synthesizes the CONVERGENCE across modules. Do not re-explain the "
        "profitability / balance-sheet / cash-flow mechanisms individually — that is the modules' "
        "job. Name the dominant mechanism at the cross-module altitude (e.g., \"cyclical revenue-"
        "side compression flowing through to denominator-driven leverage\").\n"
        "- Populate `cfo_lens` as a concrete executive decision or forced-choice tied to one named "
        "lever AND directly linked to the dominant mechanism and severity_posture. Prefer tension/"
        "tradeoff structure (\"X or Y?\", \"protect A or defend B?\"). Target 8\u201318 words. It "
        "must read as the single sentence a CFO would underline and must not be interchangeable "
        "with one written for a different company. Bad: \"Dividend policy may need recalibration.\" "
        "Good: \"Cut payout now, or let rising leverage compound through the next cycle?\" Do not "
        "duplicate `what_would_change_this`: that is an evidence frame; `cfo_lens` is an action "
        "frame.\n"
        "- Deterministic severity labels on findings (LOW / MEDIUM / HIGH / CRITICAL) and any "
        "aggregate risk_score are INPUT signals, not the final diagnosis. Assess distress gating "
        "facts directly. If the findings carry HIGH or CRITICAL severity tags but distress gating "
        "facts are absent (no negative or near-negative equity, no covenant breach or refinancing "
        "failure, no auditor going-concern, no persistent cash burn without a credible funding "
        "path), you MUST classify `severity_posture` as `pressure` or `deterioration`, not "
        "`distress`.\n"
        "- When you override intense signals down to `pressure` or `deterioration`, state the "
        "override explicitly in `posture_rationale` — e.g., \"Multiple CRITICAL pattern signals "
        "but no distress gating facts; classified as pressure due to cycle-peak base effects.\"\n"
        "- DIAGNOSIS LABEL HARD GATE: Every `diagnoses[].label` MUST match the vocabulary tier "
        "approved for the active severity_posture. This is a pre-return check, not a preference.\n"
        "    severity_posture = pressure       -> labels must come from or closely resemble: "
        "\"Elevated Risk Signals\", \"Pressure Cascade\", \"Cyclical Compression Cascade\", "
        "\"Margin-and-Payout Tension\", \"Cost Rigidity Under Cycle Pressure\", \"Convergent "
        "Pressure Pattern\", \"Denominator-Driven Leverage Build\". Distress / crisis / "
        "critical-risk vocabulary is forbidden.\n"
        "    severity_posture = deterioration  -> labels must come from or closely resemble: "
        "\"Multi-Signal Deterioration\", \"Sustained Margin Erosion\", \"Structural Cost Rigidity\", "
        "\"Structural Cost Rigidity with Cyclical Trigger\", \"Persistent Leverage Build\", "
        "\"Payout-Above-FCF Tension\", \"Cross-Module Deterioration\". Distress / crisis / "
        "critical-risk vocabulary is forbidden.\n"
        "    severity_posture = distress       -> distress / crisis / insolvency / going-concern "
        "vocabulary permitted ONLY when gating facts are explicit in findings.\n"
        "  Labels like \"Financial Distress Risk\", \"Financial Distress Risk CRITICAL\", "
        "\"Critical Risk Profile\", \"Distress Cascade\" are FORBIDDEN when severity_posture is "
        "pressure or deterioration. Before returning, verify every label fits the active tier; "
        "rewrite any that do not.\n"
        "- INTERPRETATION ALIGNMENT GATE: Each `diagnoses[].interpretation` must match "
        "severity_posture in both claims and vocabulary. When severity_posture is `pressure` or "
        "`deterioration`, interpretations MUST NOT claim \"no financial cushion\", \"distress risk "
        "confirmed\", \"operationally deteriorating with no cushion\", \"multiple signals confirm "
        "distress\", \"crisis-level condition\", or any phrase that asserts company-level "
        "distress. Instead, claim what the findings actually support — e.g., \"signals confirm "
        "sustained pressure\", \"pattern intensity is high but gating facts absent\", \"convergent "
        "deterioration without distress thresholds\", \"CRITICAL-tagged signals reflect intensity, "
        "not condition\". Interpretations must be consistent with — never stronger than — the "
        "posture.\n"
        "- The cross-module `summary` must take an explicit dominant stance on the convergent "
        "mechanism: state one of \"primarily cycle-linked\", \"primarily structural / persistent\", "
        "or (rare) \"mixed with [cycle-linked | structural] dominant\". Use \"mixed\" ONLY when "
        "separate findings clearly support both a cycle-linked mechanism AND a persistent "
        "structural mechanism AND both materially affect the same thesis. If one side dominates, "
        "commit to that side. Express remaining uncertainty through diagnosis confidence or "
        "through `what_would_change_this`, not through hedged summary prose.\n"
        "- Reconcile with module-level `primary_driver.persistence`. If modules diverge (e.g., "
        "profitability says cycle-linked, balance_sheet says persistent), choose the dominant "
        "cross-module classification and briefly explain the divergence in `posture_rationale` — "
        "e.g., \"Profitability reads cycle-linked; balance-sheet pattern reads persistent; "
        "cross-module stance is cycle-linked because balance-sheet moves are denominator-driven, "
        "downstream of the P&L mechanism.\"\n"
        "- DO NOT ECHO DETERMINISTIC DIAGNOSIS NAMES: The \"Cross-module deterministic diagnoses\" "
        "block in the input is a SIGNAL of what patterns the deterministic layer detected. Its "
        "pattern names (which may include legacy labels like \"Financial Distress Risk\", "
        "\"Distress Cascade\", \"Critical Risk Profile\") are INPUTS only — never label templates. "
        "You MUST NOT copy those names into your own `diagnoses[].label` output. Your output "
        "labels must come from the severity_posture-tier whitelist in the DIAGNOSIS LABEL HARD "
        "GATE and must describe the mechanism you identified at the cross-module altitude, not "
        "echo a deterministic pattern name.\n"
        "- DIAGNOSES ARE SUBORDINATE TO CROSS-MODULE TRUTH: `diagnoses[].label` and "
        "`diagnoses[].interpretation` do NOT create an independent severity classification. They "
        "are concise explanations of the cross-module story already expressed in "
        "`severity_posture`, `posture_rationale`, and `summary`. A diagnosis MUST NOT carry a "
        "severity implication stronger than the cross-module posture. If `summary` opens with "
        "\"Mixed, with structural dominant\" and `severity_posture` is `deterioration`, a "
        "diagnosis that claims \"confirms distress risk\" or \"no financial cushion\" is "
        "self-contradictory — such a diagnosis is a drafting error, not a legitimate finding.\n"
        "- PRE-RETURN CONSISTENCY CHECK: Before emitting the JSON, compare every "
        "`diagnoses[].label` and `diagnoses[].interpretation` against your own `severity_posture`, "
        "`posture_rationale`, and `summary`. If a label implies a severity tier stronger than "
        "severity_posture, or an interpretation contradicts the dominant-stance opener of the "
        "summary, REWRITE that diagnosis before returning. The cross-module output must be "
        "internally consistent: one severity, one stance, and diagnoses that explain that stance "
        "— never a different one. If the summary says \"pattern convergence, not distress\", "
        "every diagnosis must also frame CRITICAL-tagged signals as intensity, not condition."
    ),
}


# ── Reasoning-engine integration helpers ──────────────────────────────────────

_DX_LABELS = {
    "DX-1": "Financial Distress",
    "DX-2": "Working Capital Trap",
    "DX-3": "Low Quality Growth",
    "DX-4": "Confirmed Recovery",
    "DX-5": "Refinancing Cliff",
}


def _build_structural_analysis_block(reasoning, findings: list[dict]) -> str:
    """Format ReasoningOutput as the Section 8 structural-analysis context block.

    Returns a multi-section string that grounds the cross-module LLM call in
    the deterministic primary explanation, secondary explanation(s), evidence
    chain, chain instruction, and unmatched findings.
    """
    if reasoning is None or not reasoning.ranked_explanations:
        return ""

    findings_by_id = {f.get("id", ""): f for f in findings}

    # Group ranked explanations by diagnosis
    by_dx: dict[str, list] = {}
    for exp in reasoning.ranked_explanations:
        by_dx.setdefault(exp.diagnosis, []).append(exp)

    out: list[str] = ["## Structural Analysis (Deterministic — do not override)"]

    for dx_label in sorted(by_dx.keys()):
        exps = by_dx[dx_label]
        primary = next(
            (e for e in exps if e.rank in ("primary", "co-primary")),
            None,
        )
        if primary is None:
            # Ungrounded — surface but signal absence of structural matching
            ung = next((e for e in exps if e.rank == "ungrounded"), None)
            if ung:
                out.append(f"\n### {dx_label} ({_DX_LABELS.get(dx_label, '')}) — UNGROUNDED")
                out.append(f"No structural relationship matched the contributing findings.")
                out.append("Use judgment; flag as ungrounded.")
            continue

        out.append(f"\n### Primary Explanation for {dx_label} "
                   f"({_DX_LABELS.get(dx_label, '')})")
        out.append(f"Mechanism: {primary.mechanism}")
        if primary.specificity:
            out.append(f"Specificity: {primary.specificity}")
        secondary_count = sum(1 for e in exps if e.rank == "secondary")
        rank_descriptor = primary.rank.upper() if primary.rank == "co-primary" else "highest"
        out.append(
            f"Confidence: score {primary.score} "
            f"({rank_descriptor} of {len(exps)} candidates)"
        )
        if primary.primary_driver_concepts:
            out.append(f"Primary driver concepts: {', '.join(primary.primary_driver_concepts)}")
        if primary.affected_concepts:
            out.append(f"Affected concepts: {', '.join(primary.affected_concepts)}")
        if primary.supporting_concepts:
            out.append(f"Supporting concepts: {', '.join(primary.supporting_concepts)}")

        chain = primary.evidence_chain
        if chain:
            chain_links: list[str] = []
            for step in chain.steps:
                fids = step.supporting_findings
                bits = []
                for fid in fids:
                    f = findings_by_id.get(fid, {})
                    pat = f.get("pattern") or f.get("code") or fid
                    bits.append(f"{pat} [{fid}]")
                step_label = step.relationship.replace("_", " ")
                chain_links.append(f"{step_label}: {', '.join(bits)}")
            out.append("Evidence chain: " + " -> ".join(chain_links))
            if chain.concept_path:
                out.append(f"Concept path: {' -> '.join(chain.concept_path)}")

        # Secondary / co-primary explanations
        secondaries = [e for e in exps if e.rank in ("secondary", "co-primary") and e is not primary]
        for sec in secondaries:
            out.append(f"\n### Secondary Explanation for {dx_label}")
            out.append(f"Mechanism: {sec.mechanism}")
            top_score = primary.score or 1
            pct_below = max(0, round((top_score - sec.score) / top_score * 100, 1)) if top_score else 0
            out.append(f"Score: {sec.score} ({pct_below}% below primary)")
            if sec.primary_driver_concepts:
                out.append(f"Primary driver concepts: {', '.join(sec.primary_driver_concepts)}")
            if sec.affected_concepts:
                out.append(f"Affected concepts: {', '.join(sec.affected_concepts)}")
            if sec.supporting_findings:
                out.append(f"Evidence: [{', '.join(sec.supporting_findings)}]")

        if primary.chain_instruction:
            out.append(f"\n### Chain Instruction for {dx_label}")
            out.append(primary.chain_instruction.strip())

    if reasoning.unmatched_findings:
        out.append("\n### Unmatched Findings (no structural explanation — use judgment)")
        for fid in reasoning.unmatched_findings:
            f = findings_by_id.get(fid, {})
            pat = f.get("pattern") or f.get("code") or ""
            desc = (f.get("description") or "").split(".")[0]
            line = f"{fid}: {pat}"
            if desc:
                line += f" — {desc}"
            out.append(line)

    return "\n".join(out)


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

    # ── Reasoning engine (deterministic structural analysis) ──────────────────
    # Run before the LLM calls so the cross-module prompt is grounded in the
    # ranked explanation instead of letting the LLM invent its own causal story.
    structural_block = ""
    try:
        from pipeline.reasoning_engine import run_reasoning_engine
        reasoning_input = {
            "findings":          findings,
            "composite_signals": composite_sigs,
            "risk_score":        risk_score,
            "risk_level":        risk_level,
        }
        reasoning = run_reasoning_engine(reasoning_input)
        structural_block = _build_structural_analysis_block(reasoning, findings)
        logger.info(
            "Step 7 reasoning engine: %d chains, %d explanations, %d unmatched",
            len(reasoning.evidence_chains),
            len(reasoning.ranked_explanations),
            len(reasoning.unmatched_findings),
        )
    except Exception as exc:
        logger.warning("Step 7 reasoning engine failed (continuing without): %s", exc)

    # ── Shared base system (Phase 1 v2) ───────────────────────────────────────

    base_system = build_base_system(lang_str)

    # ── Shared context ────────────────────────────────────────────────────────

    ctx = (
        f"Company: {company_name} — {sector_str}\n"
        f"Period: {date_range}  |  Distress Score: {risk_score}/100 ({risk_level})  |  Signals: {cs_types}\n"
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
                row = f"    {f.get('id','')}: {f.get('description','')}"
                if dp_s:
                    row += f" [{dp_s}]"
                lines.append(row)
        return "\n".join(lines)

    def _fmt_stacked() -> str:
        stacked = [f for f in findings if f.get("module") == "stacked"]
        if not stacked:
            return "  (none)"
        return "\n".join(
            f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {f.get('description','')}"
            for f in stacked
        )

    def _fmt_auditor() -> str:
        auditor = [f for f in findings if f.get("module") == "auditor"]
        if not auditor:
            return "  (none)"
        lines = []
        for f in auditor:
            dp = f.get("data_points", {})
            line = f"  {f.get('id','')}: {f.get('description','')}"
            if dp:
                dp_s = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:3])
                line += f" [{dp_s}]"
            lines.append(line)
        return "\n".join(lines)

    def _fmt_dva_equity() -> str:
        """Format DVA + equity findings for the cross_module prompt."""
        dva_f  = [f for f in findings if f.get("module") == "value_distribution"]
        eq_f   = [f for f in findings if f.get("module") == "equity"]
        if not dva_f and not eq_f:
            return "  (none)"
        lines = []
        for f in dva_f + eq_f:
            dp = f.get("data_points", {})
            line = f"  {f.get('id','')}: [{f.get('module','')}] {f.get('description','')}"
            if dp:
                dp_s = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:2])
                line += f" [{dp_s}]"
            lines.append(line)
        return "\n".join(lines)

    def _fmt_dva_series_summary() -> str:
        """Compact DVA value distribution summary for the cross_module prompt."""
        dva_s = payload.get("dva_series", [])
        if not dva_s:
            return ""
        lines = ["DVA Value Distribution (annual, % of total distributed):"]
        for r in dva_s[-3:]:  # last 3 years max
            period = str(r.get("period", ""))[:4]
            emp  = r.get("employees_share_pct")
            gov  = r.get("government_share_pct")
            lend = r.get("lenders_share_pct")
            sh   = r.get("shareholders_share_pct")
            va_m = r.get("va_margin_pct")
            parts = []
            if emp  is not None: parts.append(f"Employees {emp:.0f}%")
            if gov  is not None: parts.append(f"Gov {gov:.0f}%")
            if lend is not None: parts.append(f"Lenders {lend:.0f}%")
            if sh   is not None: parts.append(f"Shareholders {sh:.0f}%")
            if va_m is not None: parts.append(f"VA Margin {va_m:.1f}%")
            if parts:
                lines.append(f"  {period}: {', '.join(parts)}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def _fmt_dmpl_summary() -> str:
        """Compact DMPL equity movements for the cross_module prompt."""
        dmpl_s = payload.get("dmpl_series", [])
        if not dmpl_s:
            return ""
        lines = ["DMPL Equity Movements (BRL thousands, annual):"]
        for r in dmpl_s[-3:]:
            period = str(r.get("period", ""))[:4]
            oe  = r.get("opening_equity")
            ce  = r.get("closing_equity")
            div = r.get("total_dividends")
            oci = r.get("oci_total")
            erp = r.get("equity_erosion_pct")
            parts = []
            if oe  is not None: parts.append(f"Open {oe/1000:,.0f}M")
            if ce  is not None: parts.append(f"Close {ce/1000:,.0f}M")
            if div is not None: parts.append(f"Div {div/1000:,.0f}M")
            if oci is not None: parts.append(f"OCI {oci/1000:,.0f}M")
            if erp is not None: parts.append(f"Erosion {erp:.1f}%")
            if parts:
                lines.append(f"  {period}: {', '.join(parts)}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def _fmt_fre_debt_structure() -> str:
        """Format FRE debt and auditor data for the cross_module prompt context."""
        fre_bonds   = payload.get("fre_foreign_bonds", [])
        fre_auditor = payload.get("fre_auditor_profiles", [])
        if not fre_bonds and not fre_auditor:
            return "Debt maturity and auditor detail not available (FRE data not loaded for this company)."

        lines = ["## Debt Structure (FRE — Formulário de Referência)"]

        if fre_bonds:
            from datetime import date as _date
            today = _date.today()
            total = sum(b.get("outstanding_amount", 0) or 0 for b in fre_bonds)
            near_2yr = sum(
                b.get("outstanding_amount", 0) or 0 for b in fre_bonds
                if b.get("maturity_date", "Indeterminado") != "Indeterminado"
                and (_date.fromisoformat(b["maturity_date"][:10]) - today).days / 365.25 < 2
            )
            near_5yr = sum(
                b.get("outstanding_amount", 0) or 0 for b in fre_bonds
                if b.get("maturity_date", "Indeterminado") != "Indeterminado"
                and (_date.fromisoformat(b["maturity_date"][:10]) - today).days / 365.25 < 5
            )
            period = fre_bonds[0].get("period", "")[:4]
            total_b = total / 1e9
            near_2yr_b = near_2yr / 1e9
            near_5yr_b = near_5yr / 1e9
            near_2yr_pct = near_2yr / total * 100 if total else 0
            near_5yr_pct = near_5yr / total * 100 if total else 0

            lines.append(f"\n### Foreign Bond Maturity Profile ({period})")
            lines.append(f"- Total foreign bonds (USD-denominated): R${total_b:.1f}B")
            lines.append(f"- Near-term (< 2 years): R${near_2yr_b:.1f}B ({near_2yr_pct:.0f}%)")
            lines.append(f"- Medium-term (2-5 years): R${(near_5yr_b-near_2yr_b):.1f}B ({(near_5yr_pct-near_2yr_pct):.0f}%)")
            lines.append(f"- Long-term (> 5 years): R${(total_b-near_5yr_b):.1f}B ({100-near_5yr_pct:.0f}%)")
            lines.append(f"\n### Currency Exposure")
            lines.append("- BRL-denominated: ~0% (these are USD foreign bonds)")
            lines.append(f"- USD-denominated: ~100% of R${total_b:.1f}B foreign bond portfolio")

        if fre_auditor:
            latest = max(fre_auditor, key=lambda p: p.get("period", ""))
            firm   = latest.get("firm_name", "Unknown")
            tenure = latest.get("tenure_years", 0)
            af     = latest.get("audit_fees", 0)
            naf    = latest.get("non_audit_fees", 0)
            ratio  = latest.get("non_audit_ratio", 0)
            af_m   = af / 1e6
            naf_m  = naf / 1e6
            lines.append(f"\n### Auditor Profile")
            lines.append(f"- Current auditor: {firm} ({tenure} years)")
            if af > 0:
                lines.append(f"- Audit fees: R${af_m:.1f}M | Non-audit fees: R${naf_m:.1f}M (ratio: {ratio:.2f})")

        return "\n".join(lines)

    def _all_findings_brief() -> str:
        rows = []
        for f in findings:
            if f.get("module") == "stacked":
                continue
            rows.append(f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {f.get('description','')}")
        return "\n".join(rows) if rows else "  (none)"

    # ── Transparency: capture prompts for each LLM call ─────────────────────
    captured_prompts: list[dict[str, str]] = []

    # ── Single-section call ───────────────────────────────────────────────────

    async def _call(section_name: str, schema: str, user_prompt: str, max_tok: int) -> dict | None:
        focus = FOCUS_BLOCKS.get(section_name, "")
        system = (
            base_system
            + f"\n\nGenerate ONLY the `{section_name}` JSON object using this exact schema:\n{schema}"
            + (f"\n\n{focus}" if focus else "")
        )
        captured_prompts.append({
            "name": section_name,
            "system_prompt": system,
            "user_message": user_prompt,
        })
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

    # ── Five concurrent calls — yield each section as it completes ───────────

    async def _run_section(section_key: str, default_key: str, schema: str, user_prompt: str, max_tok: int):
        result = await _call(section_key, schema, user_prompt, max_tok)
        return section_key, default_key, result

    tasks = [
        asyncio.ensure_future(_run_section(
            "macro_context", "macro", _MACRO_SCHEMA,
            ctx + "\nAll findings:\n" + _all_findings_brief()
            + "\n\nGenerate the macro_context section: macro/industry events that explain these findings.",
            1500,
        )),
        asyncio.ensure_future(_run_section(
            "profitability", "module", _MODULE_SCHEMA,
            ctx + "\nProfitability findings:\n" + _fmt_findings("profitability")
            + "\n\nGenerate the profitability module section. Group related findings (same pattern type) into one finding_group — aim for 2-3 groups max.",
            3000,
        )),
        asyncio.ensure_future(_run_section(
            "balance_sheet", "module", _MODULE_SCHEMA,
            ctx + "\nBalance sheet health findings:\n" + _fmt_findings("balance_sheet_health")
            + "\n\nGenerate the balance_sheet module section. Group related findings into 2-3 groups max.",
            2500,
        )),
        asyncio.ensure_future(_run_section(
            "cash_flow", "module", _MODULE_SCHEMA,
            ctx + "\nCash flow quality findings:\n" + _fmt_findings("cash_flow_quality")
            + "\n\nGenerate the cash_flow module section. Group related findings into 2-3 groups max.",
            2500,
        )),
        asyncio.ensure_future(_run_section(
            "cross_module", "cross", _CROSS_SCHEMA,
            ctx
            + (("\n\n" + structural_block) if structural_block else "")
            + "\n\nAuditor findings:\n" + _fmt_auditor()
            + "\nValue Distribution & Equity findings:\n" + _fmt_dva_equity()
            + (("\n" + _fmt_dva_series_summary()) if _fmt_dva_series_summary() else "")
            + (("\n" + _fmt_dmpl_summary()) if _fmt_dmpl_summary() else "")
            + "\nCross-module deterministic diagnoses:\n" + _fmt_stacked()
            + "\n\n" + _fmt_fre_debt_structure()
            + "\n\nGenerate the cross_module section: synthesis and what-would-change-this. "
            "Reference auditor going concern, value distribution to stakeholders, "
            "equity erosion/dividend sustainability, and debt structure/maturity risk if relevant. "
            + (
                "## Your Role (binding)\n"
                "Express the structural analysis above in clear financial language. "
                "Add sector context (commodity cycle, peer dynamics, feedstock exposure) and "
                "macro context (FX, regulatory environment) around the pre-determined causal "
                "story. Do NOT invent alternative primary causes. Do NOT override the evidence "
                "chain ranking. You may note the secondary explanation as a contributing factor. "
                "Flag any items in the unmatched-findings list that you believe deserve "
                "attention despite lacking a structural relationship."
                if structural_block else ""
            ),
            1400,
        )),
    ]

    for fut in asyncio.as_completed(tasks):
        section_key, default_key, result = await fut
        data = result or dict(_DEFAULTS[default_key])
        yield json.dumps({"__section": section_key, "data": data}, ensure_ascii=False)

    # ── Yield transparency section (prompts + reasoning engine output) ────
    transparency = {
        "reasoning_engine": _serialize_reasoning(reasoning if structural_block else None),
        "llm_calls": captured_prompts,
    }
    yield json.dumps({"__section": "transparency", "data": transparency}, ensure_ascii=False)


def _serialize_reasoning(reasoning) -> dict:
    """Convert ReasoningOutput dataclasses to JSON-serializable dicts."""
    if reasoning is None:
        return {"evidence_chains": [], "ranked_explanations": [], "unmatched_findings": []}

    chains = []
    for ch in reasoning.evidence_chains:
        chains.append({
            "diagnosis": ch.diagnosis,
            "chain_description": ch.chain_description,
            "concept_path": ch.concept_path,
            "total_evidence_count": ch.total_evidence_count,
            "steps": [
                {
                    "relationship": s.relationship,
                    "mechanism": s.mechanism,
                    "specificity": s.specificity,
                    "supporting_findings": s.supporting_findings,
                    "supporting_concepts": s.supporting_concepts,
                    "driver_concepts": s.driver_concepts,
                    "outcome_concepts": s.outcome_concepts,
                    "evidence_count": s.evidence_count,
                }
                for s in ch.steps
            ],
        })

    explanations = []
    for exp in reasoning.ranked_explanations:
        explanations.append({
            "diagnosis": exp.diagnosis,
            "rank": exp.rank,
            "relationship": exp.relationship,
            "label": exp.label,
            "mechanism": exp.mechanism,
            "specificity": exp.specificity,
            "score": exp.score,
            "supporting_findings": exp.supporting_findings,
            "supporting_concepts": exp.supporting_concepts,
            "primary_driver_concepts": exp.primary_driver_concepts,
            "affected_concepts": exp.affected_concepts,
        })

    return {
        "evidence_chains": chains,
        "ranked_explanations": explanations,
        "unmatched_findings": list(reasoning.unmatched_findings),
    }


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
