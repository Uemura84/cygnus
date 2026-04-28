"""Step 8: Executive Summary — structured JSON via single batch API call.

Returns one JSON object with narrative per section, key findings, and data gaps.
The frontend renders bilingual section headers and embeds visual elements from
Step 4/6 data already in memory — the LLM only generates narrative text.
"""

import asyncio
import json
import logging
import os
import re
from typing import AsyncIterator

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline.enrichment import SECTOR_MAP
from steps.step7_ai_agent import build_base_system

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _fix_literal_newlines(s: str) -> str:
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
    if not text:
        return None
    cleaned = re.sub(r"^```json\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    cleaned = re.sub(r"^```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    first = cleaned.find("{")
    last  = cleaned.rfind("}")
    if first != -1 and last > first:
        cleaned = cleaned[first : last + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_fix_literal_newlines(cleaned))
    except json.JSONDecodeError as e:
        logger.warning("Step 8 fragment parse failed: %s | first 200: %s", e, cleaned[:200])
        return None


# ── Mock response ─────────────────────────────────────────────────────────────

_MOCK_DATA = {
    "executive_summary": (
        "Braskem S.A. reached a risk score of 100/100 (CRITICAL): structural COGS deterioration "
        "(81% → 95% of revenue), negative equity of −R$16.5B, Debt/EBITDA of 14.4×, and six "
        "consecutive periods of negative free cash flow."
    ),
    "featured_chart": {
        "primary_metric": "revenue_abs",
        "secondary_metric": "cogs_abs",
        "chart_title": "Revenue vs COGS Trajectory",
        "reason": "Shows cost absorption eroding revenue as spreads collapsed",
    },
    "what_happened": (
        "Gross margin collapsed from 30.4% in 2021 to 2.2% by 2024 — a 4.6pp/year compression "
        "driven by COGS rising 11pp as a share of revenue. "
        "Revenue recovered in nominal terms from 2020 lows while COGS remained structurally "
        "elevated, confirming a permanent shift rather than a cyclical dip. "
        "The 2022 inflection — Revenue −8.6%, COGS +15.8% — was the structural break point."
    ),
    "how_serious": (
        "At 4.6pp/year compression, gross margin turns negative within one year without intervention. "
        "EBIT is already negative at −2.5%. Three modules simultaneously critical: profitability "
        "deterioration, negative equity, and persistent cash burn — a reinforcing feedback loop."
    ),
    "when_things_turned": (
        "Q2 2022: Brent above $100/bbl transmitted directly into naphtha costs while simultaneous "
        "Chinese PE/PP capacity additions suppressed selling prices. Unlike US ethane-based crackers, "
        "Braskem has no lower-cost feedstock alternative. "
        "When energy prices partially normalized in 2023–2024, COGS/Revenue did not recover — "
        "confirming the shift is structural, not energy-cycle-driven."
    ),
    "what_comes_next": (
        "Without COGS decomposition data, the right intervention is unknown. "
        "Feedstock cost as driver → hedging or diversification. "
        "Fixed-cost deleverage → utilization optimization. "
        "China spread compression → product mix differentiation. "
        "All three require different capital allocation decisions — all invisible in public filings."
    ),
    "what_we_cant_answer": (
        "The critical open question is the composition of the COGS line. "
        "Public CVM filings aggregate all production costs into a single account (3.02). "
        "Three specific data sources would materially change the diagnosis."
    ),
    "data_gaps": [
        "Feedstock cost per tonne by quarter (naphtha vs. ethane equivalent) — isolates whether feedstock or spread is the dominant driver",
        "Product realization prices by polymer grade (PE, PP, PVC) — reveals whether margin erosion is pricing or cost driven",
        "Debt maturity schedule 2025–2027 with covenant terms — quantifies refinancing risk given negative equity and 14.4× leverage",
    ],
    "key_findings": [
        {"module": "Profitability", "finding": "COGS composition drift +11pp",    "severity": "HIGH",     "evidence": "COGS/Rev: 80.9% → 95.3% over 5 years"},
        {"module": "Profitability", "finding": "Gross margin compression",         "severity": "HIGH",     "evidence": "−4.6pp/year, now 2.2%"},
        {"module": "Balance Sheet", "finding": "Negative equity −R$16.5B",        "severity": "CRITICAL", "evidence": "Technical insolvency; USD debt amplifies FX erosion"},
        {"module": "Balance Sheet", "finding": "Debt/EBITDA 14.4×",               "severity": "CRITICAL", "evidence": "3.5× above 4× warning threshold"},
        {"module": "Cash Flow",     "finding": "Negative FCF — 6 periods",        "severity": "HIGH",     "evidence": "Structural cash burn, interest crowding out OCF"},
    ],
    "next_step": (
        "Access to internal management accounts — specifically the sub-line COGS decomposition "
        "and debt maturity schedule — is the prerequisite for building a credible recovery scenario."
    ),
    "suggested_questions": [
        "What are the terms of Braskem's naphtha supply contract with Petrobras — is the price formula cost-plus or market-linked?",
        "How much of the −R$16.5B negative equity is attributable to Alagoas geological provisions vs. cumulative FX losses on USD debt?",
        "What is the debt maturity schedule for 2025–2027, and which tranches carry financial maintenance covenants?",
        "Has Braskem quantified the spread between naphtha-based and ethane-based cracking economics at current Brent prices?",
        "What product-mix shift toward higher-margin specialty polymers is operationally feasible within the existing asset base?",
    ],
}

MOCK_RESPONSE = json.dumps(_MOCK_DATA, ensure_ascii=False)


# ── Section schemas ───────────────────────────────────────────────────────────

_DIAGNOSIS_SCHEMA = """\
{
  "executive_summary": "<MAX 50 WORDS: one tight sentence with specific numbers — risk score, key metric, the central finding>",
  "featured_chart": {
    "primary_metric": "<exactly one of: revenue_abs | cogs_abs | gross_profit_abs | ebit_abs | ebitda_abs>",
    "secondary_metric": "<one of the same options, or null if a single line is cleaner>",
    "chart_title": "<4-6 word label for the chart>",
    "reason": "<MAX 15 WORDS: why this metric best illustrates the central finding>"
  },
  "key_findings": [
    {
      "module": "<Profitability | Balance Sheet | Cash Flow | Diagnosis>",
      "finding": "<concise finding label>",
      "severity": "<HIGH | MEDIUM | CRITICAL>",
      "evidence": "<key number(s) in 10 words max>"
    }
  ],
  "next_step": "<MAX 30 WORDS: one sentence framing the value of internal data access>"
}"""

_TIMELINE_SCHEMA = """\
{
  "what_happened": "<MAX 80 WORDS: 2-3 sentences, data-driven, specific % and periods. What changed, when, how much>",
  "when_things_turned": "<MAX 80 WORDS: the critical inflection — exact period, mechanism, why it is structural not cyclical>"
}"""

_SEVERITY_SCHEMA = """\
{
  "how_serious": "<MAX 80 WORDS: 2-3 sentences on magnitude and trajectory. Reference the cross-module convergence>",
  "what_comes_next": "<MAX 80 WORDS: forward implications integrating specialist hypotheses and data trajectory>"
}"""

_GAPS_SCHEMA = """\
{
  "what_we_cant_answer": "<MAX 60 WORDS: 2-3 sentences framing the data gap — what question remains and why it matters>",
  "data_gaps": [
    "<specific internal data source 1 — one sentence each, name the data and why it matters>",
    "<source 2>",
    "<source 3>"
  ],
  "suggested_questions": [
    "<company-specific follow-up question a CFO would ask — reference a specific finding, number, or data gap>",
    "<question 2>",
    "<question 3>",
    "<question 4>",
    "<question 5>"
  ]
}"""

_SEVERITY_VOCAB_GATE = (
    "SEVERITY VOCABULARY GATE: If the cross-module summary above does not use the word "
    "\"distress\", this section must not use \"distress\", \"crisis\", \"collapse\", "
    "\"insolvency\", \"critical condition\", \"financial distress\", \"distress risk\", "
    "\"no financial cushion\", or equivalent distress-implying phrases. Use approved "
    "vocabulary (pressure / compression / deterioration / erosion / multi-signal "
    "deterioration / elevated risk signals / material pressure signals) only."
)


_SECTION_DEFAULTS: dict[str, dict] = {
    "diagnosis": {"executive_summary": "", "featured_chart": None, "key_findings": [], "next_step": ""},
    "timeline":  {"what_happened": "", "when_things_turned": ""},
    "severity":  {"how_serious": "", "what_comes_next": ""},
    "gaps":      {"what_we_cant_answer": "", "data_gaps": [], "suggested_questions": []},
}


# ── Stream function ───────────────────────────────────────────────────────────

async def stream(payload: dict, config) -> AsyncIterator[str]:
    """Yield one section message per completed parallel call. Uses 4 focused API calls."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        # Emit mock data as section messages
        mock = json.loads(MOCK_RESPONSE)
        for section_key, fields in [
            ("diagnosis", ["executive_summary", "featured_chart", "key_findings", "next_step"]),
            ("timeline",  ["what_happened", "when_things_turned"]),
            ("severity",  ["how_serious", "what_comes_next"]),
            ("gaps",      ["what_we_cant_answer", "data_gaps", "suggested_questions"]),
        ]:
            yield json.dumps({"__section": section_key, "data": {k: mock.get(k) for k in fields}})
        return

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)

    step6_data        = payload.get("step6_data", {})
    step7_response    = payload.get("step7_response", "")
    company_name      = payload.get("company_name", "the company")
    language          = payload.get("language", "en")
    fre_available     = payload.get("fre_available", False)
    fre_debt_maturity = payload.get("fre_debt_maturity") or {}
    fre_debt_currency = payload.get("fre_debt_currency") or {}
    lang_str       = "Portuguese (Brazilian)" if language == "pt-br" else "English"

    company_key = company_name.split()[0].upper()
    sector      = SECTOR_MAP.get(company_key, "Unknown")

    # ── Build shared context blocks ───────────────────────────────────────────

    risk_score = step6_data.get("risk_score", "N/A")
    risk_level = step6_data.get("risk_level", "N/A")
    findings   = step6_data.get("findings", [])
    comp_sigs  = step6_data.get("composite_signals", [])
    cs_types   = ", ".join(s.get("composite_signal_type", "") for s in comp_sigs) or "None"

    def _finding_line(f: dict) -> str:
        dp     = f.get("data_points", {})
        key_dp = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:3]) if dp else ""
        line   = (
            f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — "
            f"{f.get('description','')}"
        )
        if key_dp:
            line += f" [{key_dp}]"
        return line

    def _module_block(module: str, label: str) -> str:
        items = [f for f in findings if f.get("module", "profitability") == module]
        if not items:
            return ""
        return label + ":\n" + "\n".join(_finding_line(f) for f in items)

    def _stacked_block() -> str:
        items = [f for f in findings if f.get("module") == "stacked"]
        if not items:
            return ""
        lines = ["Cross-Module Diagnoses:"]
        for f in items:
            lines.append(f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {f.get('description','')}")
        return "\n".join(lines)

    finding_blocks = [
        s for s in [
            _module_block("profitability",        "Profitability"),
            _module_block("balance_sheet_health", "Balance Sheet Health"),
            _module_block("cash_flow_quality",    "Cash Flow Quality"),
            _module_block("value_distribution",   "Value Distribution (DVA)"),
            _module_block("equity",               "Equity Movements (DMPL)"),
            _module_block("auditor",              "Auditor Findings"),
            _stacked_block(),
        ] if s
    ]

    step6_block = (
        f"Company: {company_name} — {sector}\n"
        f"Distress Score: {risk_score}/100 ({risk_level})\n"
        f"Composite Signals: {cs_types}\n\n"
        + "\n\n".join(finding_blocks)
    )

    step7_block = "(Step 7 not yet run)"
    if step7_response:
        try:
            s7   = json.loads(step7_response) if isinstance(step7_response, str) else step7_response
            mods = s7.get("modules", {})
            step7_block = (
                f"Macro context: {s7.get('macro_context', {}).get('summary', '')}\n"
                f"Profitability: {mods.get('profitability', {}).get('summary', '')}\n"
                f"Balance sheet: {mods.get('balance_sheet', {}).get('summary', '')}\n"
                f"Cash flow: {mods.get('cash_flow', {}).get('summary', '')}\n"
                f"Cross-module: {mods.get('cross_module', {}).get('summary', '')}\n"
                f"What would change diagnosis: {mods.get('cross_module', {}).get('what_would_change_this', '')}\n"
                f"CFO decision lens: {mods.get('cross_module', {}).get('cfo_lens', '')}"
            )
        except Exception:
            step7_block = str(step7_response)[:600]

    # ── FRE debt context block ────────────────────────────────────────────────
    fre_block = ""
    if fre_debt_maturity:
        near_pct  = fre_debt_maturity.get("near_term_pct")
        total_d   = fre_debt_maturity.get("total_debt")
        lg_year   = fre_debt_maturity.get("largest_single_year")
        lg_pct    = fre_debt_maturity.get("largest_single_year_pct")
        fx_pct    = fre_debt_currency.get("fx_pct")
        currencies = fre_debt_currency.get("currencies", {})
        cur_str   = ", ".join(
            f"{cur} {v['pct']:.0f}%" for cur, v in list(currencies.items())[:3]
        ) if currencies else None

        lines = ["## FRE Debt Structure"]
        if total_d is not None:
            lines.append(f"Total bond debt (FRE): BRL {total_d/1_000_000:,.1f}B")
        if near_pct is not None:
            lines.append(f"Near-term maturities (≤2 years): {near_pct:.0f}% of total")
        if lg_year and lg_pct is not None:
            lines.append(f"Largest single-year maturity: {lg_year} ({lg_pct:.0f}% of total)")
        if fx_pct is not None:
            lines.append(f"FX-denominated debt: {fx_pct:.0f}% of total")
        if cur_str:
            lines.append(f"Currency breakdown: {cur_str}")
        fre_block = "\n".join(lines) + "\n\n"

    ctx = (
        f"## Quantitative Analysis\n\n{step6_block}\n\n"
        + fre_block
        + f"## AI Industry Specialist Context\n\n{step7_block}\n\n"
    )

    # Shared Phase 1 v2 base_system (defined in step7_ai_agent.py) — keeps
    # severity calibration and mechanism vocabulary consistent across steps 7 & 8.
    base_system = build_base_system(lang_str)

    # ── Single-section call ───────────────────────────────────────────────────

    async def _call(section_key: str, schema: str, instruction: str, max_tok: int) -> dict | None:
        system = base_system + f"\n\nGenerate ONLY this JSON object:\n{schema}"
        try:
            resp = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tok,
                temperature=0.5,
                system=system,
                messages=[{"role": "user", "content": ctx + instruction}],
            )
            raw = resp.content[0].text
            logger.info("Step 8 section '%s': stop_reason=%s, output_tokens=%d",
                        section_key, resp.stop_reason, resp.usage.output_tokens)
            if resp.stop_reason == "max_tokens":
                logger.warning("Step 8 section '%s' hit max_tokens", section_key)
            result = _parse_fragment(raw)
            if result is None:
                logger.warning("Step 8 section '%s' unparseable: %s", section_key, raw[:200])
            return result
        except Exception as exc:
            logger.error("Step 8 section '%s' failed: %s", section_key, exc)
            return None

    # ── Four concurrent calls — yield each section as it completes ────────────

    async def _run_section(section_key: str, schema: str, instruction: str, max_tok: int):
        result = await _call(section_key, schema, instruction, max_tok)
        return section_key, result

    tasks = [
        asyncio.ensure_future(_run_section(
            "diagnosis", _DIAGNOSIS_SCHEMA,
            (
                "Generate the diagnosis section with ALL four fields: "
                "executive_summary (max 50 words, specific numbers), "
                "featured_chart (choose the single BRL metric — revenue_abs, cogs_abs, gross_profit_abs, "
                "ebit_abs, or ebitda_abs — that best visualises the central finding; set secondary_metric "
                "to a complementary BRL metric or null), "
                "key_findings (top 4-5 findings as objects), "
                "and next_step (max 30 words). "
                "`executive_summary` and `next_step` must echo the decision tension from the CFO "
                "decision lens above — do not invent a new decision frame. `next_step` should be a "
                "concrete near-term decision or forced choice tied to one named lever. It should "
                "not be a generic recommendation, research task, or broad strategic reflection. "
                "RISK-SCORE REFRAMING (hard): if the supplied findings include a deterministic "
                "`risk_score` or severity tag of HIGH / CRITICAL, treat these as SIGNAL INTENSITY, "
                "PATTERN INTENSITY, or ANOMALY INTENSITY indicators only — never as company "
                "condition. Whenever you reference the risk score in `executive_summary`, "
                "`what_happened`, `how_serious`, `what_comes_next`, or `next_step`, use one of "
                "these framings explicitly: \"signal intensity\", \"pattern intensity\", \"anomaly "
                "intensity\", \"risk-signal intensity\", \"signal strength\". Do NOT echo the word "
                "\"CRITICAL\" as a condition descriptor; if you must reference a CRITICAL tag, "
                "always qualify it — \"CRITICAL-intensity signal\", \"high-intensity pattern\" — "
                "never \"critical risk\", \"critical condition\", or \"critical deterioration\". "
                "If the risk score is 100/100 but severity_posture is pressure or deterioration, "
                "the executive summary must explicitly state that the score reflects pattern "
                "convergence, not distress."
            ),
            1500,
        )),
        asyncio.ensure_future(_run_section(
            "timeline", _TIMELINE_SCHEMA,
            "Generate the timeline section: what_happened and when_things_turned. "
            + _SEVERITY_VOCAB_GATE,
            800,
        )),
        asyncio.ensure_future(_run_section(
            "severity", _SEVERITY_SCHEMA,
            "Generate the severity section: how_serious and what_comes_next."
            + (
                " Incorporate the FRE debt maturity concentration and FX exposure in how_serious."
                if fre_available else ""
            )
            + " " + _SEVERITY_VOCAB_GATE,
            800,
        )),
        asyncio.ensure_future(_run_section(
            "gaps", _GAPS_SCHEMA,
            "Generate the gaps section: what_we_cant_answer, data_gaps (3 items), "
            "and suggested_questions (4-5 CFO questions that reference specific findings, numbers, or data gaps)."
            + (
                (
                    " FRE debt structure is available (see above). Reference the specific maturity concentration, "
                    "FX exposure, and currency breakdown in your suggested questions and gaps analysis."
                ) if fre_available else (
                    " Note: FRE (Formulário de Referência) data was not available for this company. "
                    "Include 'Debt maturity profile and currency exposure unavailable — FRE data not loaded.' "
                    "as part of what_we_cant_answer."
                )
            )
            + " " + _SEVERITY_VOCAB_GATE,
            1000,
        )),
    ]

    for fut in asyncio.as_completed(tasks):
        section_key, result = await fut
        data = result or dict(_SECTION_DEFAULTS[section_key])
        yield json.dumps({"__section": section_key, "data": data}, ensure_ascii=False)


# ── REST run handler ──────────────────────────────────────────────────────────

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
