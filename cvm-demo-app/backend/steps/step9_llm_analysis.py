"""Step 9: Q&A with AI Industry Specialist — conversational streaming over WebSocket."""

import asyncio
import os
from typing import AsyncIterator

MOCK_RESPONSE = """\
That's a great question. The 2022 COGS inflection reflects the confluence of two major external shocks:

**1. Ukraine War Energy Spike (February 2022)**
Brent crude surged above $100/bbl in February 2022 and remained elevated for most of H1 2022. Since Braskem's primary feedstock is naphtha (a crude oil derivative), the cost impact was direct and immediate. Unlike US cracker operators who use cheap shale ethane, Brazilian crackers have no affordable alternative feedstock, making them structurally exposed to crude oil price spikes.

**2. Demand Destruction Without Cost Relief**
The Fed's aggressive tightening cycle in H2 2022 (400bps of rate hikes) destroyed global polymer demand. This meant the company faced the worst of both worlds: high input costs AND declining selling prices. The revenue contraction visible in 2022 reflects this demand destruction, while COGS remained elevated because feedstock procurement cannot adjust quickly.

The structural nature of the deterioration — COGS ratio remained high even as energy prices normalized in 2023-2024 — suggests additional factors (China overcapacity, BRL weakness) compounded the initial energy shock.

**Key data that would confirm this:** Naphtha purchase price by quarter vs. PE/PP selling price by quarter — this would isolate the feedstock spread effect from other cost factors.
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

    system_prompt = (
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
        "Be concise and specific. Reference the actual numbers from the analysis when relevant. "
        "If asked about something outside the scope of the financial analysis, acknowledge the "
        "limitation and redirect to what the data shows.\n\n"
        f"Write in {lang_str}."
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

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.7,
        system=system_prompt,
        messages=messages,
    ) as stream_obj:
        async for text in stream_obj.text_stream:
            yield text


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
            desc = (f.get("description", "") or "")[:120]
            lines.append(f"  - {f.get('id','')}: {f.get('pattern','')} ({f.get('severity','')}) — {desc}")

    return "\n".join(lines)
