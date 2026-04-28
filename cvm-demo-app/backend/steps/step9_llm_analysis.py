"""Step 9: Q&A with AI Industry Specialist — conversational streaming over WebSocket."""

import asyncio
import os
from typing import AsyncIterator

MOCK_RESPONSE = """\
{
  "answer": "The 2022 COGS inflection reflects two simultaneous shocks: Brent crude surged above $100/bbl in February 2022, directly raising naphtha feedstock costs, while Fed tightening (400bps) destroyed global polymer demand. Unlike US ethane-based crackers, Braskem has no lower-cost feedstock alternative, so the cost impact was immediate and unhedgeable. When energy prices partially normalised in 2023–2024, COGS/Revenue did not recover — confirming structural damage beyond the energy cycle.",
  "evidence": [
    {"label": "COGS/Revenue at inflection", "value": "80.9% (2021) → 90.7% (2022)", "note": "Single-year jump of 9.8pp driven by naphtha cost spike"},
    {"label": "Revenue change 2022", "value": "−8.6% YoY", "note": "Demand destruction compressing realisation prices"},
    {"label": "COGS change 2022", "value": "+15.8% YoY", "note": "Feedstock cost rising while volumes fell — worst-case divergence"},
    {"label": "EBIT margin 2022", "value": "6.5% (vs 34% in mid-2021)", "note": "27.8pp collapse in two quarters confirms structural, not cyclical, break"}
  ],
  "implications": "The persistence of elevated COGS/Revenue through 2023–2024 — despite energy price normalisation — points to Chinese PE/PP capacity additions as a secondary structural suppressor of selling prices. Without feedstock diversification or product-mix differentiation, the margin floor is set by global commodity spreads, not internal efficiency.",
  "data_needed": "Naphtha purchase price per tonne by quarter vs. domestic polyethylene/polypropylene realisation price by quarter — this isolates the feedstock-spread effect from fixed-cost deleverage and would identify whether the 2023–2024 stagnation is cost-side or price-side.",
  "follow_up": "What share of Braskem's COGS is fixed vs. variable, and at what revenue level does the fixed-cost structure tip EBIT back to breakeven?"
}
"""


async def stream(payload: dict, config, pipeline_state: dict = None) -> AsyncIterator[str]:
    """Yield Q&A response tokens. Uses Claude API if key available, else streams mock."""
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

    message      = payload.get("message", "")
    conv_history = payload.get("conversation_history", [])
    language     = payload.get("language", "en")
    company_name = payload.get("company_name", "the company")

    ps         = pipeline_state or {}
    step6_data = ps.get("step6") or {}
    step7_data = ps.get("step7") or {}

    lang_str = "Portuguese (Brazilian)" if language == "pt-br" else "English"

    _ANSWER_SCHEMA = """\
{
  "answer": "<direct answer — 3-5 sentences, reference specific numbers, periods, and findings from the analysis>",
  "evidence": [
    {
      "label": "<metric or finding name>",
      "value": "<specific number or range>",
      "note": "<one-line interpretation>"
    }
  ],
  "implications": "<what this means for the company outlook — 2-3 sentences, forward-looking>",
  "data_needed": "<specific internal data source that would confirm, refute, or extend this answer — 1-2 sentences>",
  "follow_up": "<one natural follow-up question the analyst would ask next>"
}"""

    system_prompt = (
        "CRITICAL: Output ONLY valid JSON. No markdown fences, no preamble, no text outside the JSON.\n\n"
        "You are a senior industry specialist and financial analyst. You previously analyzed "
        "a Brazilian company's CVM financial data across three modules: profitability, "
        "balance sheet health, and cash flow quality — and synthesized cross-module diagnoses.\n\n"
        "You are now in a follow-up conversation. The user may ask about:\n"
        "- Specific findings or patterns from any module (profitability, balance sheet, cash flow)\n"
        "- Cross-module diagnoses and what they mean together\n"
        "- Industry dynamics or macro context\n"
        "- What internal data would be needed to investigate further\n"
        "- Leverage, liquidity, working capital, dividend sustainability, or cash generation\n"
        "- Comparisons with peers or industry benchmarks\n"
        "- Specific hypotheses and how to test them\n\n"
        "For every response, output ONLY this JSON object:\n"
        f"{_ANSWER_SCHEMA}\n\n"
        "Be specific — reference actual numbers from the analysis. "
        "Include 2-4 evidence items. "
        f"Write all text values in {lang_str}."
    )

    # Build base context from step 6 + step 7
    step6_summary  = _build_step6_summary(step6_data, company_name)
    step7_response = step7_data.get("response_text", "")

    if step6_summary or step7_response:
        context_content = f"Here is the financial analysis for {company_name}:\n\n{step6_summary}"
        if step7_response:
            context_content += f"\n\nAnd here is the industry specialist assessment:\n\n{step7_response}"
        base_context = [
            {"role": "user", "content": context_content},
            {"role": "assistant", "content": "I have the full analysis context. What would you like to explore further?"},
        ]
    else:
        base_context = []

    messages = base_context + list(conv_history) + [{"role": "user", "content": message}]

    resp = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.7,
        system=system_prompt,
        messages=messages,
    )
    yield resp.content[0].text


def _build_step6_summary(step6_data: dict, company_name: str) -> str:
    """Build a compact text summary of Step 6 findings for context injection."""
    if not step6_data:
        return ""

    lines = [
        f"Company: {company_name}",
        f"Risk Score: {step6_data.get('risk_score', 'N/A')}/100 ({step6_data.get('risk_level', 'N/A')})",
    ]

    cs = step6_data.get("composite_signals", [])
    if cs:
        lines.append("Composite Signals: " + ", ".join(s.get("composite_signal_type", "") for s in cs))

    findings = step6_data.get("findings", [])

    # Group by module for cleaner context
    for module, label in [
        ("profitability",        "Profitability Findings"),
        ("balance_sheet_health", "Balance Sheet Health Findings"),
        ("cash_flow_quality",    "Cash Flow Quality Findings"),
        ("stacked",              "Cross-Module Diagnoses"),
    ]:
        module_findings = [f for f in findings if f.get("module", "profitability") == module]
        if not module_findings:
            continue
        lines.append("")
        lines.append(f"{label}:")
        for f in module_findings:
            desc = f.get("description", "") or ""
            lines.append(f"  - {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {desc}")

    return "\n".join(lines)
