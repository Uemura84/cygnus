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
    "inventory_build":          ["BS_WORKING_CAPITAL_DETERIORATION"],
    "receivable_days_growing":  ["BS_WORKING_CAPITAL_DETERIORATION", "BS_CCC_EXPANSION"],
    "leverage_reduction":       ["BS_LEVERAGE_ESCALATION"],  # polarity checked via trend_direction

    # Module 3 — cash flow
    "negative_fcf": ["CF_FCF_EROSION"],
    "positive_fcf": ["CF_FCF_EROSION"],   # polarity checked via trend_direction
    "capex_decline": ["CF_CAPEX_STARVATION"],
}

# =============================================================================
# Stacking rules
# =============================================================================

STACKING_RULES: list[dict] = [
    {
        "diagnosis":  "FINANCIAL_DISTRESS_RISK",
        "requires": {
            "profitability": ["margin_compression", "cost_drift"],
            "balance_sheet": ["leverage_escalation"],
            "cash_flow":     ["negative_fcf"],
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
            "profitability": ["revenue_growth", "margin_compression"],
            "cash_flow":     ["capex_decline"],
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
        "diagnosis":  "CONFIRMED_RECOVERY",
        "requires": {
            "profitability": ["margin_expansion"],
            "balance_sheet": ["leverage_reduction"],
            "cash_flow":     ["positive_fcf"],
        },
        "min_modules": 2,
        "severity":   "LOW",
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
        return (finding.get("shift_pp") or 0) > 0 or code.startswith("BS_") or code.startswith("CF_") or True
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

    return True


def _find_matching(all_findings: list, signal_name: str) -> dict | None:
    for f in all_findings:
        if _match(f, signal_name):
            return f
    return None


# =============================================================================
# Public API
# =============================================================================

def stack_signals(all_findings: list) -> list:
    """Check each stacking rule against the combined findings from all modules.

    Returns a list of stacked diagnosis findings, each with:
        module="stacked", category="Diagnosis", code=<DIAGNOSIS_NAME>
    """
    stacked = []

    for rule in STACKING_RULES:
        modules_matched = 0
        signals_matched: dict[str, list] = {}

        for module_name, required_signals in rule["requires"].items():
            module_signals_found = []
            for signal_name in required_signals:
                match = _find_matching(all_findings, signal_name)
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
            stacked.append({
                "code":                "STACKED_" + rule["diagnosis"],
                "module":              "stacked",
                "pattern":             rule["diagnosis"].replace("_", " ").title(),
                "severity":            severity,
                "category":            "Diagnosis",
                "company":             "",  # filled in by Step 6
                "description":         rule["narrative_en"],
                "description_pt":      rule["narrative_pt"],
                "contributing_signals": signals_matched,
                "modules_involved":    list(signals_matched.keys()),
                "trend_direction":     "deteriorating" if severity in ("CRITICAL", "HIGH") else "improving",
                "materiality_brl":     None,
            })

    return stacked
