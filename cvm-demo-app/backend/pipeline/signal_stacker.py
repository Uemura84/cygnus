"""Cross-module signal stacking engine.

Looks for combinations of findings from Module 1 (profitability), Module 2
(balance_sheet_health), and Module 3 (cash_flow_quality) that together confirm
a diagnosis bigger than any single finding.

Public API
----------
stack_signals(all_findings) -> list[dict]
    Run all 4 stacking rules. Returns stacked diagnosis findings.
    Each stacked finding has module="stacked", category="Diagnosis".
"""

import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Signal map: abstract signal name → list of (finding code or pattern) values
# =============================================================================
# Module 1 findings use "pattern" field (not "code").
# Module 2/3 findings use "code" field.
# The _match() helper checks both.

SIGNAL_MAP: dict[str, list[str]] = {
    # Module 1 — profitability
    "margin_compression": ["Margin compression"],
    "margin_expansion":   ["Margin expansion"],
    "cost_drift":         ["Cost composition drift"],
    "revenue_growth":     ["Revenue-cost decoupling"],  # positive revenue_change_pct checked separately

    # Module 2 — balance sheet
    "leverage_escalation":      ["BS_LEVERAGE_ESCALATION"],
    "liquidity_stress":         ["BS_LIQUIDITY_STRESS", "BS_LIQUIDITY_STRESS_STREAK"],
    "equity_erosion":           ["BS_EQUITY_EROSION"],
    "inventory_build":          ["BS_WORKING_CAPITAL_DETERIORATION"],
    "receivable_days_growing":  ["BS_WORKING_CAPITAL_DETERIORATION", "BS_CCC_EXPANSION"],
    "leverage_reduction":       ["BS_LEVERAGE_ESCALATION"],  # polarity checked via trend_direction

    # Module 3 — cash flow
    "negative_fcf":         ["CF_FCF_EROSION"],
    "positive_fcf":         ["CF_FCF_EROSION"],   # polarity checked via trend_direction
    "capex_decline":        ["CF_CAPEX_STARVATION"],
    "debt_dependency":      ["CF_DEBT_DEPENDENCY"],
    "earnings_quality_gap": ["CF_EARNINGS_QUALITY_GAP"],

    # Module 4 — auditor
    "going_concern":     ["AUD001"],
    "qualified_opinion": ["AUD002"],
    "maturity_wall":     ["BS_MATURITY_WALL"],
    "fx_debt":           ["BS_FX_DEBT_CONCENTRATION"],

    # Module 5 — DVA value distribution
    "lender_share_escalating":   ["DVA_LENDER_SHARE_ESCALATION"],
    "shareholder_value_eroding": ["DVA_SHAREHOLDER_VALUE_EROSION"],

    # Module 6 — equity
    "distributing_while_insolvent": ["EQ_DIVIDEND_EXCEEDS_INCOME"],
}

# =============================================================================
# Stacking rules
# =============================================================================

STACKING_RULES: list[dict] = [
    {
        "diagnosis":  "FINANCIAL_DISTRESS_RISK",
        "requires": {
            "profitability":       ["margin_compression", "cost_drift"],
            "balance_sheet":       ["leverage_escalation", "liquidity_stress", "equity_erosion"],
            "cash_flow":           ["negative_fcf"],
            "value_distribution":  ["lender_share_escalating"],
        },
        "amplifiers": {
            "auditor": ["going_concern", "qualified_opinion"],
            "equity":  ["distributing_while_insolvent"],
        },
        "min_modules": 2,
        "severity":   "CRITICAL",
        "narrative_en": (
            "The company is deteriorating operationally and has no financial cushion. "
            "Multiple signals confirm distress risk."
        ),
        "narrative_pt": (
            "A empresa está se deteriorando operacionalmente e não possui colchão financeiro. "
            "Múltiplos sinais confirmam risco de estresse financeiro."
        ),
        "narrative_amplified_en": (
            "The company is deteriorating operationally and has no financial cushion. "
            "Multiple signals confirm distress risk. "
            "Independently confirmed by auditor going concern emphasis "
            "and/or dividend distribution during a loss year."
        ),
        "narrative_amplified_pt": (
            "A empresa está se deteriorando operacionalmente e não possui colchão financeiro. "
            "Múltiplos sinais confirmam risco de estresse financeiro. "
            "Confirmado independentemente pela ênfase em continuidade operacional do auditor "
            "e/ou distribuição de dividendos durante ano de prejuízo."
        ),
    },
    {
        "diagnosis":  "WORKING_CAPITAL_TRAP",
        "requires": {
            "profitability": ["cost_drift"],
            "balance_sheet": ["inventory_build", "receivable_days_growing"],
        },
        "min_modules": 2,
        "severity":   "HIGH",
        "narrative_en": (
            "Cost pressure is compounded by working capital accumulation. "
            "The company is not just facing margin squeeze — it is also tying up "
            "cash in receivables and inventory."
        ),
        "narrative_pt": (
            "A pressão de custos é agravada pelo acúmulo de capital de giro. "
            "A empresa não enfrenta apenas compressão de margens — também está "
            "imobilizando caixa em recebíveis e estoques."
        ),
    },
    {
        "diagnosis":  "LOW_QUALITY_GROWTH",
        "requires": {
            "profitability":      ["revenue_growth", "margin_compression"],
            "cash_flow":          ["capex_decline", "earnings_quality_gap"],
            "value_distribution": ["shareholder_value_eroding"],
        },
        "min_modules": 2,
        "severity":   "HIGH",
        "narrative_en": (
            "Revenue is growing but profitability is declining and the company has "
            "stopped investing. Growth may be low-quality — buying revenue at the "
            "expense of margin and future capacity."
        ),
        "narrative_pt": (
            "A receita está crescendo mas a rentabilidade está caindo e a empresa "
            "parou de investir. O crescimento pode ser de baixa qualidade — "
            "comprando receita às custas de margem e capacidade futura."
        ),
    },
    {
        "diagnosis":  "REFINANCING_CLIFF_RISK",
        "requires": {
            "balance_sheet":  ["maturity_wall", "leverage_escalation"],
            "cash_flow":      ["negative_fcf"],
        },
        "amplifiers": {
            "auditor":        ["going_concern"],
            "balance_sheet_fx": ["fx_debt"],
            "cash_flow":      ["debt_dependency"],
        },
        "min_modules": 2,
        "severity":   "CRITICAL",
        "narrative_en": (
            "Near-term debt maturities are concentrated while the company cannot generate "
            "sufficient cash to repay. High leverage combined with cash burn creates acute "
            "refinancing risk."
        ),
        "narrative_pt": (
            "Os vencimentos de dívida de curto prazo estão concentrados enquanto a empresa "
            "não consegue gerar caixa suficiente para pagamento. Alta alavancagem combinada "
            "com queima de caixa cria risco agudo de refinanciamento."
        ),
        "narrative_amplified_en": (
            "Near-term debt maturities are concentrated while the company cannot generate "
            "sufficient cash to repay. High leverage combined with cash burn creates acute "
            "refinancing risk. "
            "The independent auditor has also flagged going concern risk "
            "and/or significant FX-denominated debt adds exchange rate risk to the refinancing challenge."
        ),
        "narrative_amplified_pt": (
            "Os vencimentos de dívida de curto prazo estão concentrados enquanto a empresa "
            "não consegue gerar caixa suficiente para pagamento. Alta alavancagem combinada "
            "com queima de caixa cria risco agudo de refinanciamento. "
            "O auditor independente também sinalizou risco de continuidade operacional "
            "e/ou a dívida significativa em moeda estrangeira adiciona risco cambial ao desafio de refinanciamento."
        ),
    },
    {
        "diagnosis":  "CONFIRMED_RECOVERY",
        "requires": {
            "profitability": ["margin_expansion"],
            "balance_sheet": ["leverage_reduction"],
            "cash_flow":     ["positive_fcf"],
        },
        "min_modules": 2,
        "severity":   "LOW",
        # Only evaluate recovery signals from the most recent 3 periods
        "recency_filter": 3,
        "narrative_en": (
            "Recovery is confirmed across profitability, leverage, and cash generation. "
            "The turnaround appears real."
        ),
        "narrative_pt": (
            "A recuperação é confirmada em rentabilidade, alavancagem e geração de caixa. "
            "A reversão parece ser real."
        ),
    },
]

# =============================================================================
# Matching helper
# =============================================================================

def _match(finding: dict, signal_name: str) -> bool:
    """Check if a finding matches an abstract signal name."""
    codes = SIGNAL_MAP.get(signal_name, [])
    code    = finding.get("code", "") or ""
    pattern = finding.get("pattern", "") or ""

    matched_code = (code in codes) or (pattern in codes)
    if not matched_code:
        return False

    # Polarity checks for bi-directional signal names
    if signal_name == "margin_expansion":
        return "expansion" in pattern.lower()
    if signal_name == "margin_compression":
        return "compression" in pattern.lower()
    if signal_name == "cost_drift":
        # Only positive COGS shift (deterioration)
        return (finding.get("shift_pp") or 0) > 0
    if signal_name == "revenue_growth":
        # Revenue-cost decoupling with positive revenue change
        if pattern == "Revenue-cost decoupling":
            return (finding.get("revenue_change_pct") or 0) > 0
        return True
    if signal_name == "leverage_reduction":
        # BS_LEVERAGE_ESCALATION with improving trend
        return finding.get("trend_direction") == "improving"
    if signal_name == "leverage_escalation":
        return finding.get("trend_direction") != "improving"
    if signal_name == "positive_fcf":
        # FCF erosion finding with improving trend
        return finding.get("trend_direction") == "improving"
    if signal_name == "negative_fcf":
        return finding.get("trend_direction") != "improving"
    if signal_name == "maturity_wall":
        return finding.get("severity") in ("HIGH", "CRITICAL")

    return True


def _find_matching(all_findings: list, signal_name: str) -> dict | None:
    for f in all_findings:
        if _match(f, signal_name):
            return f
    return None


# =============================================================================
# Public API
# =============================================================================

def _extract_period(finding: dict) -> str | None:
    """Best-effort extraction of the most recent period from a finding."""
    if finding.get("period"):
        return str(finding["period"])
    if finding.get("periods_affected"):
        pa = finding["periods_affected"]
        if isinstance(pa, list) and pa:
            return str(sorted(pa)[-1])
    return None


def _recency_filtered(findings: list, n_periods: int) -> list:
    """Return only findings associated with the most recent n_periods.

    Findings with no period info are always included (conservative).
    """
    all_periods = sorted({
        p for f in findings
        for p in ([_extract_period(f)] if _extract_period(f) else [])
    })
    if len(all_periods) <= n_periods:
        return findings
    cutoff = all_periods[-n_periods]
    result = []
    for f in findings:
        p = _extract_period(f)
        if p is None or p >= cutoff:
            result.append(f)
    return result


def stack_signals(all_findings: list) -> list:
    """Check each stacking rule against the combined findings from all modules.

    Returns a list of stacked diagnosis findings, each with:
        module="stacked", category="Diagnosis", code=<DIAGNOSIS_NAME>

    Amplifiers (e.g. auditor going_concern) do NOT count toward min_modules
    but enrich the diagnosis narrative when present.

    DX-4 (CONFIRMED_RECOVERY) uses only the most recent 3 periods.
    DX-1 (FINANCIAL_DISTRESS_RISK) suppresses DX-4 if both would fire.
    """
    stacked = []
    company = next((f.get("company", "") for f in all_findings if f.get("company")), "")

    for rule in STACKING_RULES:
        modules_matched = 0
        signals_matched: dict[str, list] = {}

        # Apply recency filter for rules that require it (e.g., DX-4 recovery)
        recency_n = rule.get("recency_filter")
        findings_for_rule = (
            _recency_filtered(all_findings, recency_n) if recency_n else all_findings
        )

        for module_name, required_signals in rule["requires"].items():
            module_signals_found = []
            for signal_name in required_signals:
                match = _find_matching(findings_for_rule, signal_name)
                if match:
                    module_signals_found.append({
                        "signal":  signal_name,
                        "code":    match.get("code") or match.get("pattern", ""),
                        "module":  match.get("module", "profitability"),
                        "severity": match.get("severity", ""),
                    })
            if module_signals_found:
                modules_matched += 1
                signals_matched[module_name] = module_signals_found

        if modules_matched >= rule["min_modules"]:
            severity = rule["severity"]

            # Check amplifiers (don't count toward min_modules)
            amplifiers_matched: dict[str, list] = {}
            is_amplified = False
            for amp_module, amp_signals in rule.get("amplifiers", {}).items():
                amp_found = []
                for signal_name in amp_signals:
                    match = _find_matching(all_findings, signal_name)
                    if match:
                        amp_found.append({
                            "signal":  signal_name,
                            "code":    match.get("code") or match.get("pattern", ""),
                            "module":  match.get("module", "auditor"),
                            "severity": match.get("severity", ""),
                        })
                if amp_found:
                    amplifiers_matched[amp_module] = amp_found
                    is_amplified = True

            # Pick narrative — amplified version if available and amplifier triggered
            if is_amplified and rule.get("narrative_amplified_en"):
                narrative_en = rule["narrative_amplified_en"]
                narrative_pt = rule.get("narrative_amplified_pt", rule["narrative_pt"])
            else:
                narrative_en = rule["narrative_en"]
                narrative_pt = rule["narrative_pt"]

            all_contributing = {**signals_matched, **amplifiers_matched}
            stacked.append({
                "code":                "STACKED_" + rule["diagnosis"],
                "module":              "stacked",
                "pattern":             rule["diagnosis"].replace("_", " ").title(),
                "severity":            severity,
                "category":            "Diagnosis",
                "company":             "",  # filled in by Step 6
                "description":         narrative_en,
                "description_pt":      narrative_pt,
                "contributing_signals": all_contributing,
                "modules_involved":    list(all_contributing.keys()),
                "amplified_by_auditor": is_amplified,
                "trend_direction":     "deteriorating" if severity in ("CRITICAL", "HIGH") else "improving",
                "materiality_brl":     None,
            })

    # ── Conflict resolution: DX-1 (Financial Distress) beats DX-4 (Confirmed Recovery) ──
    dx1 = next((s for s in stacked if "FINANCIAL_DISTRESS" in s["code"]), None)
    dx4 = next((s for s in stacked if "CONFIRMED_RECOVERY" in s["code"]), None)
    if dx1 and dx4:
        logger.info(f"DX-4 suppressed: conflicts with active DX-1 for {company}")
        stacked.remove(dx4)
        dx1["note"] = (
            "Recovery signals from earlier periods were present but overridden "
            "by current distress indicators."
        )

    return stacked
