"""Materiality layer — converts percentage-point findings into BRL estimates.

Uses absolute revenue and COGS figures from the metrics pipeline to translate
relative findings (pp shifts, compression rates) into order-of-magnitude
economic impact estimates.

CVM data is stored in BRL thousands. All internal computations produce values
in BRL thousands; we multiply by 1,000 before calling _format_brl so that
the formatter receives actual BRL and produces correct "bn / mn" labels.

Public API
----------
estimate_impact(findings, metrics_df, language) -> list
    Adds estimated_impact dict to profitability findings in-place.

estimate_bs_cf_impact(findings, language) -> list
    Adds estimated_impact dict to BS / CF findings in-place,
    using the materiality_brl field already set by bs_detector / cf_detector.
"""

import pandas as pd


# ── Per-code basis text (EN, PT) ─────────────────────────────────────────────

_BS_CF_BASIS = {
    "BS_LEVERAGE_ESCALATION":          ("Net debt exposure (point-in-time balance)",                        "Exposição da dívida líquida (saldo pontual)"),
    "BS_EQUITY_EROSION":               ("Equity change over analysis period (cumulative)",                  "Variação do patrimônio no período (acumulado)"),
    "BS_LIQUIDITY_STRESS":             ("Working capital position (point-in-time)",                         "Posição do capital de giro (saldo pontual)"),
    "BS_WORKING_CAPITAL_DETERIORATION":("Working capital change over analysis period (cumulative)",          "Variação do capital de giro no período (acumulado)"),
    "BS_CCC_EXPANSION":                ("Cash tied up by CCC expansion (annual run-rate)",                  "Caixa imobilizado pela expansão do CCC (taxa anual)"),
    "BS_ASSET_EFFICIENCY_DECLINE":     ("Revenue gap from asset turnover decline (annual run-rate)",        "Gap de receita pela queda de giro do ativo (taxa anual)"),
    "BS_DEBT_MATURITY_CONCENTRATION":  ("Short-term debt at refinancing risk (point-in-time)",              "Dívida de curto prazo sob risco de refinanciamento (saldo pontual)"),
    "CF_EARNINGS_QUALITY_GAP":         ("OCF shortfall vs reported earnings (latest annual period)",        "Déficit de OCF frente ao lucro reportado (último período anual)"),
    "CF_FCF_EROSION":                  ("Free cash flow — negative = cash burn (latest annual period)",     "Fluxo de caixa livre — negativo = queima de caixa (último período anual)"),
    "CF_CAPEX_STARVATION":             ("D&A minus capex investment gap (latest annual period)",            "Gap de investimento: D&A menos capex (último período anual)"),
    "CF_DEBT_DEPENDENCY":              ("Cumulative net debt raised over analysis period",                   "Captações líquidas acumuladas no período de análise"),
    "CF_DIVIDEND_SUSTAINABILITY":      ("Dividend overshoot above free cash flow (latest annual period)",   "Excesso de dividendos sobre o FCL (último período anual)"),
    "CF_WORKING_CAPITAL_DRAIN":        ("Working capital cash drain (latest annual period)",                "Drenagem de caixa do capital de giro (último período anual)"),
}

_CAVEAT = {
    "en": "Order-of-magnitude estimate from balance sheet / cash flow data; may include non-operating items",
    "pt": "Estimativa de ordem de magnitude a partir de dados de balanço / fluxo de caixa; pode incluir itens não operacionais",
}


def estimate_impact(findings: list, metrics_df: pd.DataFrame, language: str = "pt") -> list:
    """Add estimated_impact to each profitability finding.

    Args:
        findings:   List of findings from detect_patterns (Step 6, module 1).
        metrics_df: Annual metrics DataFrame from Step 4. Must include
                    revenue_abs and cogs_abs columns (values in BRL thousands).
        language:   "en" or "pt-br".

    Each finding gets estimated_impact = {value_brl, formatted, basis, caveat}
    or None when the finding cannot be quantified.
    """
    if metrics_df is None or metrics_df.empty:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    if "revenue_abs" not in metrics_df.columns or "cogs_abs" not in metrics_df.columns:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    # Most-recent annual revenue — stored in BRL thousands; multiply to get BRL
    metrics_sorted = metrics_df.sort_values("period", ascending=False)
    latest = metrics_sorted.iloc[0] if len(metrics_sorted) > 0 else None

    if latest is None:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    # CVM data is in BRL thousands → multiply by 1 000 to get actual BRL
    latest_revenue = abs(float(latest.get("revenue_abs", 0) or 0)) * 1_000

    if latest_revenue == 0:
        for f in findings:
            f["estimated_impact"] = None
        return findings

    lang = "en" if language == "en" else "pt"

    for f in findings:
        pattern = f.get("pattern", "")
        impact = None

        if pattern == "Cost composition drift":
            shift_pp = abs(f.get("shift_pp", 0) or 0)
            if shift_pp > 0:
                value = (shift_pp / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{shift_pp:.1f}pp COGS drift × current annual revenue (annual run-rate)",
                    "caveat": "Order of magnitude estimate — does not isolate volume, mix, or price effects",
                }

        elif pattern == "Margin compression":
            annual_pp = abs(f.get("annual_change_pp", 0) or 0)
            if annual_pp > 0:
                value = (annual_pp / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{annual_pp:.1f}pp/year compression × current annual revenue (annual run-rate)",
                    "caveat": "Annual run-rate estimate — actual impact depends on revenue trajectory",
                }

        elif pattern == "Revenue-cost decoupling":
            divergence = f.get("divergence_pp", 0) or 0
            if divergence > 0:  # COGS outpaced revenue (margin pressure)
                value = (divergence / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{divergence:.1f}pp cost-revenue divergence × annual revenue (latest annual period)",
                    "caveat": "Single-period estimate — may include one-time items",
                }

        elif pattern == "Peer divergence":
            gap_pp = abs(f.get("gap_pp", 0) or 0)
            if gap_pp > 0:
                # Conservative: assume half the gap is closable
                value = (gap_pp / 2 / 100) * latest_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"Half of {gap_pp:.1f}pp peer gap × current annual revenue (annual run-rate)",
                    "caveat": "Assumes half the peer gap is closable — different business models may explain part of the gap",
                }

        elif pattern == "YoY quarter comparison":
            yoy_pp = abs(f.get("yoy_change_pp", 0) or 0)
            if yoy_pp > 0:
                quarterly_revenue = latest_revenue / 4
                value = (yoy_pp / 100) * quarterly_revenue
                impact = {
                    "value_brl": value,
                    "formatted": _format_brl(value, lang),
                    "basis": f"{yoy_pp:.1f}pp YoY change × estimated quarterly revenue (single quarter)",
                    "caveat": "Quarterly estimate — annualize with caution",
                }

        # Statistical anomaly and High margin volatility are not quantifiable in BRL

        f["estimated_impact"] = impact

    return findings


def estimate_bs_cf_impact(findings: list, language: str = "en") -> list:
    """Add estimated_impact to BS / CF findings using their materiality_brl field.

    materiality_brl is set by bs_detector / cf_detector and is in BRL thousands
    (matching CVM data units). We multiply by 1 000 to get actual BRL for the
    formatter, so display labels ("bn", "mn") are correct.

    Findings with materiality_brl = None or 0 get estimated_impact = None.
    """
    lang = "en" if language == "en" else "pt"
    caveat = _CAVEAT[lang]

    for f in findings:
        mat_thousands = f.get("materiality_brl")
        if mat_thousands is None or mat_thousands == 0:
            f["estimated_impact"] = None
            continue

        # Convert BRL thousands → actual BRL
        value_brl = mat_thousands * 1_000
        code = f.get("code", "")
        basis_en, basis_pt = _BS_CF_BASIS.get(code, ("Financial impact", "Impacto financeiro"))
        basis = basis_en if lang == "en" else basis_pt

        f["estimated_impact"] = {
            "value_brl": value_brl,
            "formatted": _format_brl(value_brl, lang),
            "basis":     basis,
            "caveat":    caveat,
        }

    return findings


def _format_brl(value: float, language: str = "pt") -> str:
    """Format a BRL value (in actual BRL, not thousands) as a human-readable string.

    Examples (en):  70_000_000_000 → "~R$ 70.0 bn",  350_000_000 → "~R$ 350 mn"
    Examples (pt):  70_000_000_000 → "~R$ 70.0 bi",  350_000_000 → "~R$ 350 mi"
    """
    abs_val = abs(value)
    if language == "en":
        if abs_val >= 1_000_000_000:
            return f"~R$ {abs_val / 1_000_000_000:.1f} bn"
        elif abs_val >= 1_000_000:
            return f"~R$ {abs_val / 1_000_000:.0f} mn"
        elif abs_val >= 1_000:
            return f"~R$ {abs_val / 1_000:.0f} k"
        else:
            return f"~R$ {abs_val:.0f}"
    else:
        if abs_val >= 1_000_000_000:
            return f"~R$ {abs_val / 1_000_000_000:.1f} bi"
        elif abs_val >= 1_000_000:
            return f"~R$ {abs_val / 1_000_000:.0f} mi"
        elif abs_val >= 1_000:
            return f"~R$ {abs_val / 1_000:.0f} mil"
        else:
            return f"~R$ {abs_val:.0f}"
