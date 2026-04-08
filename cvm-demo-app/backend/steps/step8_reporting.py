"""Step 8: Executive Summary — structured JSON via single batch API call.

Returns one JSON object with narrative per section, key findings, and data gaps.
The frontend renders bilingual section headers and embeds visual elements from
Step 4/6 data already in memory — the LLM only generates narrative text.
"""

import json
import logging
import os
import re
from typing import AsyncIterator

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline.enrichment import SECTOR_MAP

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


# ── JSON schema shown to the LLM ─────────────────────────────────────────────

_JSON_SCHEMA = """\
{
  "executive_summary": "<MAX 50 WORDS: one tight sentence with specific numbers — risk score, key metric, the central finding>",
  "what_happened": "<MAX 80 WORDS: 2-3 sentences, data-driven, specific % and periods. What changed, when, how much>",
  "how_serious": "<MAX 80 WORDS: 2-3 sentences on magnitude and trajectory. Reference the cross-module convergence>",
  "when_things_turned": "<MAX 80 WORDS: the critical inflection — exact period, mechanism, why it is structural not cyclical>",
  "what_comes_next": "<MAX 80 WORDS: forward implications integrating specialist hypotheses and data trajectory>",
  "what_we_cant_answer": "<MAX 60 WORDS: 2-3 sentences framing the data gap — what question remains and why it matters>",
  "data_gaps": [
    "<specific internal data source 1 — one sentence each, name the data and why it matters>",
    "<source 2>",
    "<source 3>"
  ],
  "key_findings": [
    {
      "module": "<Profitability | Balance Sheet | Cash Flow | Diagnosis>",
      "finding": "<concise finding label>",
      "severity": "<HIGH | MEDIUM | CRITICAL>",
      "evidence": "<key number(s) in 10 words max>"
    }
  ],
  "next_step": "<MAX 30 WORDS: one sentence framing the value of internal data access>",
  "suggested_questions": [
    "<company-specific follow-up question a CFO would ask — reference a specific finding, number, or data gap from the analysis>",
    "<question 2>",
    "<question 3>",
    "<question 4>",
    "<question 5>"
  ]
}"""


# ── Stream function ───────────────────────────────────────────────────────────

async def stream(payload: dict, config) -> AsyncIterator[str]:
    """Yield a single valid JSON string. Uses one batch API call."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key:
        yield MOCK_RESPONSE
        return

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)

    step6_data     = payload.get("step6_data", {})
    step7_response = payload.get("step7_response", "")
    company_name   = payload.get("company_name", "the company")
    language       = payload.get("language", "en")
    lang_str       = "Portuguese (Brazilian)" if language == "pt-br" else "English"

    company_key = company_name.split()[0].upper()
    sector      = SECTOR_MAP.get(company_key, "Unknown")

    # ── Build Step 6 context block ────────────────────────────────────────────

    risk_score = step6_data.get("risk_score", "N/A")
    risk_level = step6_data.get("risk_level", "N/A")
    findings   = step6_data.get("findings", [])
    comp_sigs  = step6_data.get("composite_signals", [])
    cs_types   = ", ".join(s.get("composite_signal_type", "") for s in comp_sigs) or "None"

    def _finding_line(f: dict) -> str:
        dp      = f.get("data_points", {})
        key_dp  = ", ".join(f"{k}: {v}" for k, v in list(dp.items())[:3]) if dp else ""
        line    = (
            f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — "
            f"{f.get('description','')[:100]}"
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
            lines.append(f"  {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {f.get('description','')[:100]}")
        return "\n".join(lines)

    sections = [
        s for s in [
            _module_block("profitability",        "Profitability"),
            _module_block("balance_sheet_health", "Balance Sheet Health"),
            _module_block("cash_flow_quality",    "Cash Flow Quality"),
            _stacked_block(),
        ] if s
    ]

    step6_block = (
        f"Company: {company_name} — {sector}\n"
        f"Risk Score: {risk_score}/100 ({risk_level})\n"
        f"Composite Signals: {cs_types}\n\n"
        + "\n\n".join(sections)
    )

    # ── Condense Step 7 context ───────────────────────────────────────────────

    step7_block = "(Step 7 not yet run)"
    if step7_response:
        try:
            s7 = json.loads(step7_response) if isinstance(step7_response, str) else step7_response
            macro   = s7.get("macro_context", {}).get("summary", "")
            mods    = s7.get("modules", {})
            prof    = mods.get("profitability",  {}).get("summary", "")
            bs      = mods.get("balance_sheet",  {}).get("summary", "")
            cf      = mods.get("cash_flow",      {}).get("summary", "")
            cross   = mods.get("cross_module",   {}).get("summary", "")
            change  = mods.get("cross_module",   {}).get("what_would_change_this", "")
            step7_block = (
                f"Macro context: {macro}\n"
                f"Profitability: {prof}\n"
                f"Balance sheet: {bs}\n"
                f"Cash flow: {cf}\n"
                f"Cross-module: {cross}\n"
                f"What would change diagnosis: {change}"
            )
        except Exception:
            step7_block = str(step7_response)[:600]

    # ── Prompt ───────────────────────────────────────────────────────────────

    system_prompt = (
        "CRITICAL: Output ONLY valid JSON. No markdown fences, no preamble, no text outside the JSON.\n\n"
        "You are a senior financial analyst preparing a concise executive summary for C-suite. "
        "You integrate automated pattern detection findings with AI specialist context.\n\n"
        f"Write all text in {lang_str}. "
        "Respect ALL word limits — a CFO reads this in 30 seconds. "
        "Be specific and quantitative — include actual numbers, percentages, and periods. "
        "Do NOT use generic language; every sentence must reference the specific company data provided.\n\n"
        "For suggested_questions: generate 4-5 follow-up questions a CFO would ask after reading this summary. "
        "Each question must reference a specific finding, number, hypothesis, or data gap from the analysis — "
        "not generic questions. Bad: 'Tell me about the balance sheet.' "
        "Good: 'What portion of the −R$16.5B negative equity is from Alagoas provisions vs. FX losses on USD debt?' "
        f"Generate questions in {lang_str}.\n\n"
        f"Generate this exact JSON:\n{_JSON_SCHEMA}"
    )

    user_prompt = (
        f"## Quantitative Analysis\n\n{step6_block}\n\n"
        f"## AI Industry Specialist Context\n\n{step7_block}\n\n"
        "Generate the executive summary JSON."
    )

    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            temperature=0.5,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = resp.content[0].text
        logger.info(
            "Step 8: stop_reason=%s, output_tokens=%d",
            resp.stop_reason, resp.usage.output_tokens,
        )
        if resp.stop_reason == "max_tokens":
            logger.warning("Step 8 hit max_tokens — response may be truncated")

        parsed = _parse_fragment(raw)
        if parsed:
            yield json.dumps(parsed, ensure_ascii=False)
        else:
            logger.error("Step 8 JSON parse failed, yielding raw for main.py fallback")
            yield raw
    except Exception as exc:
        logger.error("Step 8 API call failed: %s", exc)
        yield MOCK_RESPONSE


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
