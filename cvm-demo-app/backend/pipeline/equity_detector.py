"""Module 6: Equity Movements Detection (DMPL).

Receives dmpl_series (list of dicts from step4 _build_dmpl_series) and produces
findings with code prefix EQ_.

Public API
----------
detect_equity_patterns(dmpl_series, company_name) -> list[dict]
    Returns findings with module="equity".
"""


def _safe(record: dict, key: str, default=None):
    v = record.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f  # NaN check
    except (TypeError, ValueError):
        return default


def _fmtbrl(v: float | None) -> str:
    if v is None:
        return "N/A"
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        return f"BRL {v/1_000_000:,.1f}B"
    if abs_v >= 1_000:
        return f"BRL {v/1_000:,.0f}M"
    return f"BRL {v:,.0f}K"


# =============================================================================
# EQ-1: DIVIDEND_EXCEEDS_INCOME
# Company declared/distributed more dividends than it earned in net income.
# Payout > 100% of net income (BRL basis) — erodes equity or requires debt.
# =============================================================================

def _check_dividend_exceeds_income(series: list, company: str) -> list:
    findings = []
    for rec in series:
        period = str(rec.get("period", ""))[:4]
        total_div = _safe(rec, "total_dividends")
        net_income = _safe(rec, "net_income")

        if total_div is None or net_income is None:
            continue

        # Dividends are typically negative in DMPL (outflows); normalise to abs
        div_abs = abs(total_div)
        ni_abs  = abs(net_income) if net_income > 0 else None  # skip loss years for ratio

        if ni_abs is None or ni_abs == 0:
            # If company had a loss AND declared dividends → always flag HIGH
            if div_abs > 0 and net_income <= 0:
                findings.append({
                    "code":        "EQ_DIVIDEND_EXCEEDS_INCOME",
                    "pattern":     "Dividend exceeds income",
                    "module":      "equity",
                    "company":     company,
                    "severity":    "HIGH",
                    "description": (
                        f"{period}: Dividends of {_fmtbrl(div_abs)} declared "
                        f"while net income was {_fmtbrl(net_income)} (loss). "
                        f"Distributing capital while in a loss position erodes equity."
                    ),
                    "description_pt": (
                        f"{period}: Dividendos de {_fmtbrl(div_abs)} declarados "
                        f"com prejuízo líquido de {_fmtbrl(net_income)}. "
                        f"Distribuição de capital durante prejuízo corrói o patrimônio."
                    ),
                    "metric_name":  "total_dividends",
                    "period":       period,
                    "total_dividends": round(div_abs, 0),
                    "net_income":      round(net_income, 0),
                    "payout_ratio":    None,
                    "trend_direction": "deteriorating",
                    "category":    "Core",
                })
            continue

        payout_ratio = div_abs / ni_abs
        if payout_ratio > 1.0:
            severity = "HIGH" if payout_ratio > 1.5 else "MEDIUM"
            findings.append({
                "code":        "EQ_DIVIDEND_EXCEEDS_INCOME",
                "module":      "equity",
                "company":     company,
                "severity":    severity,
                "description": (
                    f"{period}: Payout ratio {payout_ratio:.1f}× — dividends "
                    f"({_fmtbrl(div_abs)}) exceeded net income ({_fmtbrl(net_income)}). "
                    f"Excess distribution must come from existing equity or new debt."
                ),
                "description_pt": (
                    f"{period}: Payout de {payout_ratio:.1f}× — dividendos "
                    f"({_fmtbrl(div_abs)}) superaram o lucro líquido ({_fmtbrl(net_income)}). "
                    f"Excesso deve ser financiado pelo patrimônio existente ou nova dívida."
                ),
                "metric_name":  "total_dividends",
                "period":       period,
                "total_dividends": round(div_abs, 0),
                "net_income":      round(net_income, 0),
                "payout_ratio":    round(payout_ratio, 3),
                "trend_direction": "deteriorating",
                "category":    "Core",
            })
    return findings


# =============================================================================
# EQ-2: MATERIAL_OCI
# Other Comprehensive Income is material relative to net income (>20%).
# Significant OCI means reported NI gives an incomplete picture of economic P&L.
# =============================================================================

def _check_material_oci(series: list, company: str) -> list:
    findings = []
    oci_count = 0
    for rec in series:
        period = str(rec.get("period", ""))[:4]
        oci = _safe(rec, "oci_total")
        ni  = _safe(rec, "net_income")

        if oci is None or ni is None or ni == 0:
            continue

        oci_pct = abs(oci) / abs(ni) * 100
        if oci_pct > 20:
            oci_count += 1

    if oci_count >= 2:
        # Persistent material OCI — structural, not one-off
        # Collect the specific period data
        periods_data = []
        for rec in series:
            oci = _safe(rec, "oci_total")
            ni  = _safe(rec, "net_income")
            if oci is None or ni is None or ni == 0:
                continue
            oci_pct = abs(oci) / abs(ni) * 100
            if oci_pct > 20:
                periods_data.append({
                    "period": str(rec.get("period", ""))[:4],
                    "oci_total": round(oci, 0),
                    "oci_pct_net_income": round(oci_pct, 1),
                })

        findings.append({
            "code":        "EQ_MATERIAL_OCI",
            "pattern":     "Material OCI movement",
            "module":      "equity",
            "company":     company,
            "severity":    "MEDIUM",
            "description": (
                f"OCI exceeded 20% of net income in {oci_count} annual periods. "
                f"Comprehensive income diverges materially from reported net income, "
                f"driven by FX translation, hedge accounting, or actuarial adjustments."
            ),
            "description_pt": (
                f"ORA superou 20% do lucro líquido em {oci_count} períodos anuais. "
                f"O resultado abrangente diverge materialmente do lucro reportado, "
                f"impulsionado por conversão cambial, hedge contábil ou ajustes atuariais."
            ),
            "metric_name":    "oci_total",
            "oci_count":      oci_count,
            "periods_data":   periods_data,
            "trend_direction": "informational",
            "category":    "Contextual",
        })
    return findings


# =============================================================================
# Public API
# =============================================================================

def detect_equity_patterns(dmpl_series: list, company_name: str) -> list:
    """Run all equity detection algorithms.

    *dmpl_series* is the annual list from step4 _build_dmpl_series().
    Returns findings with module="equity".
    """
    if not dmpl_series:
        return []

    findings: list = []
    findings.extend(_check_dividend_exceeds_income(dmpl_series, company_name))
    findings.extend(_check_material_oci(dmpl_series, company_name))
    return findings
