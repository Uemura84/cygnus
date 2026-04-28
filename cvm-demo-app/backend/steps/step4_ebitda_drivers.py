"""Step 4: EBITDA Drivers Construction — live implementation with cache layer."""

import json
import os

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import metrics_calculator
from pipeline.dva_parser import parse_dva
from pipeline.dmpl_parser import parse_dmpl
from pipeline.dra_parser import parse_dra
from pipeline.fre_parser import parse_fre_foreign_bonds, parse_fre_auditor


# ── Interpretation sidecar cache helpers ─────────────────────────────────────

def _interp_cache_path(cache_dir: str, company_name: str, language: str) -> str:
    lang_key = language.replace("-", "_")        # "pt-br" → "pt_br"
    company_key = company_name.split()[0].upper()
    return os.path.join(cache_dir, company_key, f"step4_interp_{lang_key}.json")


def _load_interp_cache(cache_dir: str, company_name: str, language: str) -> dict | None:
    path = _interp_cache_path(cache_dir, company_name, language)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _save_interp_cache(data: dict, cache_dir: str, company_name: str, language: str) -> None:
    path = _interp_cache_path(cache_dir, company_name, language)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _format_bridge_summary(bridge: dict | None) -> str:
    """Format a bridge dict into a compact one-line string for the LLM prompt."""
    if not bridge:
        return "(not available)"
    start = f"{bridge['start_label']}={bridge['start_value']:.1f}"
    end   = f"{bridge['end_label']}={bridge['end_value']:.1f}"
    factors = ", ".join(
        f"{f['name']}={'+' if f['value'] >= 0 else ''}{f['value']:.1f}"
        for f in bridge.get("factors", [])
    )
    return f"{start} → {factors} → {end}" if factors else f"{start} → {end}"


def _generate_chart_interpretations(
    time_series: list,
    bs_annual: list,
    cf_annual: list,
    company_name: str,
    language: str,
    margin_bridge: dict | None = None,
    equity_bridge: dict | None = None,
    cashflow_bridge: dict | None = None,
    dva_bridge: dict | None = None,
) -> dict:
    """Call Claude Sonnet once to generate one-sentence chart interpretations.

    Returns a dict keyed by chart name.  Returns {} on any failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {}

    try:
        import anthropic
    except ImportError:
        return {}

    def _last_n(series, keys, n=4):
        rows = series[-n:] if len(series) >= n else series
        lines = []
        for r in rows:
            period = str(r.get("period", ""))[:4]
            vals = ", ".join(
                f"{k}={round(float(r[k]), 2)}" for k in keys if r.get(k) is not None
            )
            if vals:
                lines.append(f"  {period}: {vals}")
        return "\n".join(lines) if lines else "  (no data)"

    ts_summary = _last_n(time_series, [
        "Gross_Margin_pct", "EBIT_Margin_pct", "EBITDA_Margin_pct",
        "revenue_abs", "cogs_abs",
    ])
    bs_summary = _last_n(bs_annual, [
        "current_ratio", "quick_ratio", "net_debt", "working_capital",
        "return_on_assets", "return_on_equity", "debt_to_ebitda",
        "cash_conversion_cycle", "receivable_days", "inventory_days", "payable_days",
    ])
    cf_summary = _last_n(cf_annual, [
        "operating_cash_flow", "free_cash_flow", "ocf_to_net_income",
        "capex_to_revenue", "capex_to_depreciation",
    ])

    bridge_summary = f"""Margin Bridge (pp): {_format_bridge_summary(margin_bridge)}
Equity Bridge (BRL K): {_format_bridge_summary(equity_bridge)}
Cash Flow Bridge (BRL K): {_format_bridge_summary(cashflow_bridge)}
Value Distribution Bridge (BRL K): {_format_bridge_summary(dva_bridge)}"""

    lang_label = "English" if language == "en" else "Brazilian Portuguese"

    prompt = f"""You are a financial analyst reviewing {company_name}'s metrics (BRL thousands).

=== Income Statement Metrics ===
{ts_summary}

=== Balance Sheet Metrics ===
{bs_summary}

=== Cash Flow Metrics ===
{cf_summary}

=== Bridge Charts ===
{bridge_summary}

Generate exactly ONE sentence (max 30 words) interpreting each of these 15 charts.
For bridge charts, explain what the decomposition reveals — which factor drove the change.
For "revenue_cogs_growth": describe how the BRL gap between Revenue and COGS (gross profit) changed over time — use absolute amounts.
For "ccc": describe the trend in Cash Conversion Cycle (days) using receivable_days, inventory_days, and payable_days — do NOT mention liquidity ratios or current ratio.
For "liquidity": describe the current_ratio and quick_ratio trend — do NOT mention CCC or working capital days.
Mention specific numbers. Write in {lang_label}.

Reply ONLY with a valid JSON object, no other text:
{{
  "margin_trend": "...",
  "revenue_cogs_growth": "...",
  "margin_bridge": "...",
  "liquidity": "...",
  "net_debt": "...",
  "working_capital": "...",
  "roa": "...",
  "equity_bridge": "...",
  "cf_bridge": "...",
  "fcf": "...",
  "ccc": "...",
  "capex": "...",
  "dva_dist": "...",
  "dva_bridge": "...",
  "dva_va_margin": "..."
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1800,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Strip markdown fencing if present
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()
        return json.loads(text)
    except Exception:
        return {}


def _safe(val, default=None):
    """Return float(val) if not None/NaN, else default."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return default


def _build_time_series(pivot: pd.DataFrame, company_name: str) -> list:
    """Extract annual (DFP) time series records for the target company."""
    company_key = company_name.split()[0].upper()

    # Support both common model column names and legacy CVM names
    id_col   = "company_id" if "company_id" in pivot.columns else "DENOM_CIA"
    date_col = "period_date" if "period_date" in pivot.columns else "DT_REFER"

    # Filter to target company, DFP rows only, sorted by date
    comp = pivot[
        pivot[id_col].str.upper().str.contains(company_key, na=False) &
        (pivot["_doc_type"] == "DFP")
    ].sort_values(date_col).copy()

    if comp.empty:
        comp = pivot[
            pivot[id_col].str.upper().str.contains(company_key, na=False)
        ].sort_values(date_col).copy()

    metric_cols = [
        "Gross_Margin_pct",
        "EBIT_Margin_pct",
        "EBITDA_Margin_pct",
        "COGS_pct_Revenue",
        "SGA_pct_Revenue",
    ]
    available = [c for c in metric_cols if c in comp.columns]

    revenue_col      = "revenue" if "revenue" in comp.columns else "Receita de Venda de Bens e/ou Serviços"
    cogs_col         = "cogs"    if "cogs"    in comp.columns else "Custo dos Bens e/ou Serviços Vendidos"
    gross_profit_col = "gross_profit" if "gross_profit" in comp.columns else "Resultado Bruto"
    ebit_col         = "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)"
    ebitda_col       = "EBITDA"
    cogs_is_abs      = (cogs_col == "cogs")

    records = []
    prev_revenue = None
    prev_cogs    = None

    for _, row in comp.iterrows():
        record = {"period": str(row[date_col])}

        for col in available:
            val = row.get(col)
            record[col] = round(float(val), 2) if pd.notna(val) else None

        rev_val  = row.get(revenue_col)
        cogs_val = row.get(cogs_col)

        if prev_revenue is not None and pd.notna(rev_val) and prev_revenue != 0:
            record["Revenue_YoY_pct"] = round(
                (float(rev_val) - prev_revenue) / abs(prev_revenue) * 100, 1)
        else:
            record["Revenue_YoY_pct"] = None

        if prev_cogs is not None and pd.notna(cogs_val) and prev_cogs != 0:
            cogs_abs_val = float(cogs_val) if cogs_is_abs else abs(float(cogs_val))
            record["COGS_YoY_pct"] = round(
                (cogs_abs_val - abs(prev_cogs)) / abs(prev_cogs) * 100, 1)
        else:
            record["COGS_YoY_pct"] = None

        record["revenue_abs"] = float(rev_val) if pd.notna(rev_val) else 0.0
        record["cogs_abs"]    = (float(cogs_val) if cogs_is_abs
                                 else abs(float(cogs_val))) if pd.notna(cogs_val) else 0.0

        gp_val = row.get(gross_profit_col)
        record["gross_profit_abs"] = float(gp_val) if pd.notna(gp_val) else None

        eb_val = row.get(ebit_col)
        record["ebit_abs"] = float(eb_val) if pd.notna(eb_val) else None

        ebitda_val = row.get(ebitda_col)
        record["ebitda_abs"] = float(ebitda_val) if pd.notna(ebitda_val) else None

        if pd.notna(rev_val):
            prev_revenue = float(rev_val)
        if pd.notna(cogs_val):
            prev_cogs = float(cogs_val) if cogs_is_abs else abs(float(cogs_val))

        records.append(record)

    return records


def _build_bs_series(balance_sheets: list, is_lookup: dict) -> list:
    """Build balance sheet time series with derived metrics.

    *is_lookup* maps str(period_date) → IncomeStatement-style dict with
    keys: revenue, cogs, net_income, ebitda (all in BRL thousands).
    """
    records = []
    for bs in balance_sheets:
        period_key = str(bs.period.date)
        is_data = is_lookup.get(period_key, {})

        # Raw fields
        r: dict = {
            "period":      period_key,
            "granularity": bs.period.granularity,
            "total_assets":            _safe(bs.total_assets),
            "current_assets":          _safe(bs.current_assets),
            "cash_and_equivalents":    _safe(bs.cash_and_equivalents),
            "accounts_receivable":     _safe(bs.accounts_receivable),
            "inventories":             _safe(bs.inventories),
            "non_current_assets":      _safe(bs.non_current_assets),
            "property_plant_equipment": _safe(bs.property_plant_equipment),
            "intangible_assets":       _safe(bs.intangible_assets),
            "total_liabilities":       _safe(bs.total_liabilities),
            "current_liabilities":     _safe(bs.current_liabilities),
            "accounts_payable":        _safe(bs.accounts_payable),
            "short_term_debt":         _safe(bs.short_term_debt),
            "non_current_liabilities": _safe(bs.non_current_liabilities),
            "long_term_debt":          _safe(bs.long_term_debt),
            "total_equity":            _safe(bs.total_equity),
        }

        # Derived: net_debt = short_term_debt + long_term_debt - cash
        std = _safe(bs.short_term_debt, 0.0)
        ltd = _safe(bs.long_term_debt, 0.0)
        csh = _safe(bs.cash_and_equivalents, 0.0)
        if bs.short_term_debt is not None or bs.long_term_debt is not None:
            r["net_debt"] = round(std + ltd - csh, 2)
        else:
            r["net_debt"] = None

        # working_capital = current_assets - current_liabilities
        ca = _safe(bs.current_assets)
        cl = _safe(bs.current_liabilities)
        r["working_capital"] = round(ca - cl, 2) if (ca is not None and cl is not None) else None

        # current_ratio = current_assets / current_liabilities
        if ca is not None and cl is not None and cl != 0:
            r["current_ratio"] = round(ca / cl, 3)
        else:
            r["current_ratio"] = None

        # quick_ratio = (current_assets - inventories) / current_liabilities
        inv = _safe(bs.inventories, 0.0)
        if ca is not None and cl is not None and cl != 0:
            r["quick_ratio"] = round((ca - inv) / cl, 3)
        else:
            r["quick_ratio"] = None

        # Cross-statement metrics (require IS data for same period)
        rev     = is_data.get("revenue")
        cogs    = is_data.get("cogs")
        ni      = is_data.get("net_income")
        ebitda  = is_data.get("ebitda")
        ta      = _safe(bs.total_assets)
        te      = _safe(bs.total_equity)
        ar      = _safe(bs.accounts_receivable)
        ap      = _safe(bs.accounts_payable)
        inv_val = _safe(bs.inventories)

        # debt_to_ebitda = net_debt / ebitda
        nd = r.get("net_debt")
        if nd is not None and ebitda is not None and ebitda != 0:
            r["debt_to_ebitda"] = round(nd / ebitda, 2)
        else:
            r["debt_to_ebitda"] = None

        # receivable_days = (accounts_receivable / revenue) × 365
        if ar is not None and rev is not None and rev != 0:
            r["receivable_days"] = round(ar / rev * 365, 1)
        else:
            r["receivable_days"] = None

        # inventory_days = (inventories / cogs) × 365
        if inv_val is not None and cogs is not None and cogs != 0:
            r["inventory_days"] = round(inv_val / cogs * 365, 1)
        else:
            r["inventory_days"] = None

        # payable_days = (accounts_payable / cogs) × 365
        if ap is not None and cogs is not None and cogs != 0:
            r["payable_days"] = round(ap / cogs * 365, 1)
        else:
            r["payable_days"] = None

        # cash_conversion_cycle = receivable_days + inventory_days - payable_days
        rd = r.get("receivable_days")
        id_ = r.get("inventory_days")
        pd_ = r.get("payable_days")
        if rd is not None and id_ is not None and pd_ is not None:
            r["cash_conversion_cycle"] = round(rd + id_ - pd_, 1)
        else:
            r["cash_conversion_cycle"] = None

        # return_on_assets = net_income / total_assets
        if ni is not None and ta is not None and ta != 0:
            r["return_on_assets"] = round(ni / ta * 100, 2)
        else:
            r["return_on_assets"] = None

        # return_on_equity = net_income / total_equity
        if ni is not None and te is not None and te != 0:
            r["return_on_equity"] = round(ni / te * 100, 2)
        else:
            r["return_on_equity"] = None

        # asset_turnover = revenue / total_assets
        if rev is not None and ta is not None and ta != 0:
            r["asset_turnover"] = round(rev / ta, 3)
        else:
            r["asset_turnover"] = None

        records.append(r)

    return records


def _build_cf_series(cash_flows: list, is_lookup: dict) -> list:
    """Build cash flow time series with derived metrics."""
    records = []
    for cf in cash_flows:
        period_key = str(cf.period.date)
        is_data = is_lookup.get(period_key, {})

        r: dict = {
            "period":      period_key,
            "granularity": cf.period.granularity,
            "operating_cash_flow":      _safe(cf.operating_cash_flow),
            "investing_cash_flow":      _safe(cf.investing_cash_flow),
            "financing_cash_flow":      _safe(cf.financing_cash_flow),
            "capex":                    _safe(cf.capex),
            "debt_issuance":            _safe(cf.debt_issuance),
            "debt_repayment":           _safe(cf.debt_repayment),
            "dividends_paid":           _safe(cf.dividends_paid),
            "depreciation_amortization": _safe(cf.depreciation_amortization),
        }

        # free_cash_flow = OCF + capex (capex is negative cash outflow)
        ocf  = _safe(cf.operating_cash_flow)
        capx = _safe(cf.capex, 0.0)
        if ocf is not None:
            r["free_cash_flow"] = round(ocf + capx, 2)
        else:
            r["free_cash_flow"] = None

        # Cross-statement metrics
        rev  = is_data.get("revenue")
        ni   = is_data.get("net_income")
        da   = _safe(cf.depreciation_amortization)

        # ocf_to_net_income = operating_cash_flow / net_income
        if ocf is not None and ni is not None and ni != 0:
            r["ocf_to_net_income"] = round(ocf / ni, 2)
        else:
            r["ocf_to_net_income"] = None

        # capex_to_revenue = abs(capex) / revenue
        if cf.capex is not None and rev is not None and rev != 0:
            r["capex_to_revenue"] = round(abs(cf.capex) / rev * 100, 2)
        else:
            r["capex_to_revenue"] = None

        # capex_to_depreciation = abs(capex) / depreciation_amortization
        if cf.capex is not None and da is not None and da != 0:
            r["capex_to_depreciation"] = round(abs(cf.capex) / da, 2)
        else:
            r["capex_to_depreciation"] = None

        records.append(r)

    return records


def _build_is_lookup(pivot: pd.DataFrame, company_name: str) -> dict:
    """Build period_date → IS metrics dict for cross-statement computation."""
    company_key = company_name.split()[0].upper()
    id_col   = "company_id"   if "company_id"   in pivot.columns else "DENOM_CIA"
    date_col = "period_date"  if "period_date"  in pivot.columns else "DT_REFER"

    comp = pivot[
        pivot[id_col].str.upper().str.contains(company_key, na=False)
    ].copy()

    revenue_col = "revenue" if "revenue" in comp.columns else "Receita de Venda de Bens e/ou Serviços"
    cogs_col    = "cogs"    if "cogs"    in comp.columns else "Custo dos Bens e/ou Serviços Vendidos"
    ni_col      = "Lucro/Prejuízo Consolidado do Período"
    ebitda_col  = "EBITDA"

    lookup: dict = {}
    for _, row in comp.iterrows():
        period_key = str(row.get(date_col, ""))
        if not period_key:
            continue
        entry: dict = {}
        for field, col in [("revenue", revenue_col), ("cogs", cogs_col),
                           ("net_income", ni_col), ("ebitda", ebitda_col)]:
            val = row.get(col)
            if val is not None and pd.notna(val):
                v = float(val)
                # cogs is stored as abs value in common model
                if field == "cogs" and cogs_col == "cogs":
                    entry[field] = v
                elif field == "cogs":
                    entry[field] = abs(v)
                else:
                    entry[field] = v
        lookup[period_key] = entry

    return lookup


def _build_dva_series(company_name: str) -> list:
    """Parse DVA and return annual records for Step 4 Value Distribution chart."""
    try:
        records, _ = parse_dva(company_name, DATA_DIR, YEARS)
    except Exception:
        return []
    # Return annual records only, keeping fields relevant for the chart
    result = []
    for r in records:
        if r.get("doc_type") != "DFP":
            continue
        entry: dict = {"period": r["period"]}
        for field in ("employees", "government", "lenders", "shareholders",
                      "total_to_distribute", "net_value_added", "revenues",
                      "employees_share_pct", "government_share_pct",
                      "lenders_share_pct", "shareholders_share_pct",
                      "va_margin_pct", "input_intensity_pct"):
            entry[field] = r.get(field)
        result.append(entry)
    return result


def _build_dmpl_series(company_name: str) -> list:
    """Parse DMPL and return annual records for Step 4 Equity Movements table."""
    try:
        records, _ = parse_dmpl(company_name, DATA_DIR, YEARS)
    except Exception:
        return []
    result = []
    for r in records:
        if r.get("doc_type") != "DFP":
            continue
        entry: dict = {"period": r["period"]}
        for field in ("opening_equity", "closing_equity", "net_income",
                      "total_dividends", "dividends_declared", "jcp_declared",
                      "dividends_additional", "dividends_proposed",
                      "treasury_shares_net", "capital_increase", "oci_total",
                      "equity_erosion_pct"):
            entry[field] = r.get(field)
        result.append(entry)
    return result


def _build_dra_series(company_name: str) -> list:
    """Parse DRA and return annual records for Step 4 profitability enhancements."""
    try:
        records, _ = parse_dra(company_name, DATA_DIR, YEARS)
    except Exception:
        return []
    result = []
    for r in records:
        if r.get("doc_type") != "DFP":
            continue
        entry: dict = {"period": r["period"]}
        for field in ("net_income", "oci_total", "total_comprehensive_income",
                      "oci_fx", "oci_hedge", "oci_actuarial",
                      "comprehensive_income_ratio", "oci_pct_net_income"):
            entry[field] = r.get(field)
        result.append(entry)
    return result


def _headline_cache_path(cache_dir: str, company_name: str, language: str) -> str:
    lang_key = language.replace("-", "_")
    company_key = company_name.split()[0].upper()
    return os.path.join(cache_dir, company_key, f"step4_headlines_{lang_key}.json")


def _load_headline_cache(cache_dir: str, company_name: str, language: str) -> dict | None:
    path = _headline_cache_path(cache_dir, company_name, language)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _save_headline_cache(data: dict, cache_dir: str, company_name: str, language: str) -> None:
    path = _headline_cache_path(cache_dir, company_name, language)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _build_fre_debt_maturity(bonds: list) -> dict | None:
    """Bucket FRE foreign bonds by time-to-maturity from today.

    Returns a dict with bucket amounts/percentages and summary metrics,
    or None if bonds is empty.
    """
    if not bonds:
        return None
    from datetime import date as _date
    today = _date.today()

    buckets: dict[str, float] = {
        "lt_1yr": 0.0, "yr_1_2": 0.0, "yr_2_3": 0.0,
        "yr_3_5": 0.0, "gt_5yr": 0.0, "undetermined": 0.0,
    }
    by_year: dict[str, float] = {}

    for bond in bonds:
        amt = bond.get("outstanding_amount") or 0.0
        maturity = bond.get("maturity_date", "Indeterminado")
        try:
            if maturity and maturity.lower() not in ("indeterminado", "", "nan"):
                mat_date = _date.fromisoformat(maturity[:10])
                days = (mat_date - today).days
                year_str = maturity[:4]
                by_year[year_str] = by_year.get(year_str, 0.0) + amt
                if days < 365:
                    buckets["lt_1yr"] += amt
                elif days < 365 * 2:
                    buckets["yr_1_2"] += amt
                elif days < 365 * 3:
                    buckets["yr_2_3"] += amt
                elif days < 365 * 5:
                    buckets["yr_3_5"] += amt
                else:
                    buckets["gt_5yr"] += amt
            else:
                buckets["undetermined"] += amt
        except Exception:
            buckets["undetermined"] += amt

    total = sum(buckets.values())
    if total == 0:
        return None

    near_term_pct = round((buckets["lt_1yr"] + buckets["yr_1_2"]) / total * 100, 1)
    largest_year = max(by_year, key=by_year.get) if by_year else None
    largest_pct = round(by_year[largest_year] / total * 100, 1) if largest_year else 0.0
    reference_period = bonds[0].get("period", "")[:4] if bonds else ""

    return {
        "total_debt":              round(total),
        "near_term_pct":           near_term_pct,
        "largest_single_year":     largest_year,
        "largest_single_year_pct": largest_pct,
        "reference_period":        reference_period,
        "buckets": {
            k: {"amount": round(v), "pct": round(v / total * 100, 1)}
            for k, v in buckets.items()
        },
    }


def _build_fre_debt_currency(bonds: list) -> dict | None:
    """Compute currency breakdown of FRE foreign bonds.

    Returns a dict with per-currency amounts/pct and total fx_pct, or None.
    """
    if not bonds:
        return None

    by_currency: dict[str, float] = {}
    for bond in bonds:
        amt = bond.get("outstanding_amount") or 0.0
        cur = bond.get("currency") or "Unknown"
        by_currency[cur] = by_currency.get(cur, 0.0) + amt

    total = sum(by_currency.values())
    if total == 0:
        return None

    brl = by_currency.get("BRL", 0.0)
    fx_pct = round((total - brl) / total * 100, 1)
    reference_period = bonds[0].get("period", "")[:4] if bonds else ""

    return {
        "total_debt":       round(total),
        "fx_pct":           fx_pct,
        "reference_period": reference_period,
        "currencies": {
            cur: {"amount": round(amt), "pct": round(amt / total * 100, 1)}
            for cur, amt in sorted(by_currency.items(), key=lambda x: -x[1])
        },
    }


def _build_fre_auditor_card(profiles: list) -> dict | None:
    """Return the latest auditor profile shaped for the Step 4 info card."""
    if not profiles:
        return None
    latest = sorted(profiles, key=lambda p: p["period"])[-1]
    return {
        "firm_name":       latest.get("firm_name"),
        "tenure_years":    latest.get("tenure_years"),
        "audit_fees":      round(latest["audit_fees"])     if latest.get("audit_fees")     else None,
        "non_audit_fees":  round(latest["non_audit_fees"]) if latest.get("non_audit_fees") else None,
        "non_audit_ratio": latest.get("non_audit_ratio"),
        "period":          latest.get("period", "")[:4],
    }


def _generate_section_headlines(
    time_series: list,
    bs_annual: list,
    cf_annual: list,
    dva_series: list,
    company_name: str,
    language: str,
) -> dict:
    """Call Claude Sonnet once to generate 4 section headline sentences.

    Returns a dict with keys section1–section4.  Returns {} on any failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {}
    try:
        import anthropic
    except ImportError:
        return {}

    def _snap(series, keys, n=3):
        rows = series[-n:] if len(series) >= n else series
        parts = []
        for r in rows:
            yr = str(r.get("period", ""))[:4]
            vals = ", ".join(
                f"{k}={round(float(r[k]), 1)}" for k in keys
                if r.get(k) is not None
            )
            if vals:
                parts.append(f"  {yr}: {vals}")
        return "\n".join(parts) if parts else "  (no data)"

    prof = _snap(time_series, ["Gross_Margin_pct", "EBIT_Margin_pct", "EBITDA_Margin_pct"])
    solv = _snap(bs_annual, ["current_ratio", "net_debt", "return_on_assets", "debt_to_ebitda"])
    cash = _snap(cf_annual, ["operating_cash_flow", "free_cash_flow", "capex_to_revenue"])
    dvap = _snap(dva_series, ["total_to_distribute", "employees", "government", "lenders", "shareholders"])

    lang_label = "English" if language == "en" else "Brazilian Portuguese"

    prompt = f"""You are a financial analyst reviewing {company_name} (all monetary values in BRL thousands).

=== Section 1: Profitability ===
{prof}

=== Section 2: Solvency ===
{solv}

=== Section 3: Cash Flow ===
{cash}

=== Section 4: Value Distribution ===
{dvap}

Write ONE headline sentence for each section (max 40 words, must include 2+ specific numbers).
Be direct and analytical — no "the company" preamble, start with the finding.
Write in {lang_label}.

Reply ONLY with valid JSON, no other text:
{{
  "section1": "...",
  "section2": "...",
  "section3": "...",
  "section4": "..."
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()
        return json.loads(text)
    except Exception:
        return {}


def compute_margin_bridge(time_series: list) -> dict | None:
    """Decompose gross margin shift from peak year to latest year."""
    annual = [r for r in time_series if r.get("Gross_Margin_pct") is not None]
    if len(annual) < 2:
        return None
    peak   = max(annual, key=lambda r: r["Gross_Margin_pct"])
    latest = annual[-1]
    if peak["period"] == latest["period"]:
        return None

    peak_year   = peak["period"][:4]
    latest_year = latest["period"][:4]

    factors = []
    peak_cogs   = peak.get("COGS_pct_Revenue")
    latest_cogs = latest.get("COGS_pct_Revenue")
    if peak_cogs is not None and latest_cogs is not None:
        factors.append({"name": "cogs_impact", "value": round(-(latest_cogs - peak_cogs), 2)})

    peak_sga   = peak.get("SGA_pct_Revenue")
    latest_sga = latest.get("SGA_pct_Revenue")
    if peak_sga is not None and latest_sga is not None:
        factors.append({"name": "sga_impact", "value": round(-(latest_sga - peak_sga), 2)})

    accounted = sum(f["value"] for f in factors)
    other = round((latest["Gross_Margin_pct"] - peak["Gross_Margin_pct"]) - accounted, 2)
    if abs(other) > 0.1:
        factors.append({"name": "other", "value": other})

    return {
        "start_label": f"peak_{peak_year}",
        "start_value": round(peak["Gross_Margin_pct"], 2),
        "end_label":   f"current_{latest_year}",
        "end_value":   round(latest["Gross_Margin_pct"], 2),
        "factors":     factors,
    }


def compute_equity_bridge(dmpl_series: list) -> dict | None:
    """Build equity bridge from the most recent DMPL annual record."""
    annual = [r for r in dmpl_series
              if r.get("opening_equity") is not None and r.get("closing_equity") is not None]
    if not annual:
        return None
    latest = annual[-1]
    year   = latest["period"][:4]

    factors = []
    for field, name_key in [
        ("net_income",          "net_income"),
        ("total_dividends",     "dividends"),
        ("oci_total",           "oci"),
        ("capital_increase",    "capital"),
        ("treasury_shares_net", "treasury"),
    ]:
        val = latest.get(field)
        if val is not None and abs(val) > 0.01:
            factors.append({"name": name_key, "value": round(val, 2)})

    return {
        "start_label": "opening_equity",
        "start_value": round(latest["opening_equity"], 2),
        "end_label":   "closing_equity",
        "end_value":   round(latest["closing_equity"], 2),
        "year":        year,
        "factors":     factors,
    }


def compute_cashflow_bridge(cf_series: list, bs_series: list) -> dict | None:
    """Build cash flow bridge for the most recent annual period."""
    annual_cf = [r for r in cf_series if r.get("granularity") == "annual"]
    annual_bs = [r for r in bs_series if r.get("granularity") == "annual"]
    if not annual_cf:
        return None
    latest_cf = annual_cf[-1]
    year = latest_cf["period"][:4]

    opening_cash = None
    closing_cash = None
    if len(annual_bs) >= 2:
        opening_cash = annual_bs[-2].get("cash_and_equivalents")
        closing_cash = annual_bs[-1].get("cash_and_equivalents")
    elif len(annual_bs) == 1:
        closing_cash = annual_bs[-1].get("cash_and_equivalents")

    factors = []
    for field, name_key in [
        ("operating_cash_flow",  "operating"),
        ("investing_cash_flow",  "investing"),
        ("financing_cash_flow",  "financing"),
    ]:
        val = latest_cf.get(field)
        if val is not None:
            factors.append({"name": name_key, "value": round(val, 2)})

    return {
        "start_label":  "opening_cash",
        "start_value":  round(opening_cash, 2) if opening_cash is not None else None,
        "end_label":    "closing_cash",
        "end_value":    round(closing_cash, 2) if closing_cash is not None else None,
        "year":         year,
        "factors":      factors,
    }


def compute_dva_bridge(dva_series: list) -> dict | None:
    """Decompose total value added shift from peak year to latest year."""
    valid = [r for r in dva_series if r.get("total_to_distribute") is not None]
    if len(valid) < 2:
        return None
    peak   = max(valid, key=lambda r: r["total_to_distribute"])
    latest = valid[-1]
    if peak["period"] == latest["period"]:
        return None

    peak_year   = peak["period"][:4]
    latest_year = latest["period"][:4]

    factors = []
    for field, name_key in [
        ("employees",    "employees_delta"),
        ("government",   "government_delta"),
        ("lenders",      "lenders_delta"),
        ("shareholders", "shareholders_delta"),
    ]:
        pv = peak.get(field)
        lv = latest.get(field)
        if pv is not None and lv is not None:
            delta = round(lv - pv, 2)
            if abs(delta) > 0.01:
                factors.append({"name": name_key, "value": delta})

    return {
        "start_label": f"total_va_{peak_year}",
        "start_value": round(peak["total_to_distribute"], 2),
        "end_label":   f"total_va_{latest_year}",
        "end_value":   round(latest["total_to_distribute"], 2),
        "factors":     factors,
    }


def run(config, pipeline_state: dict) -> dict:
    """Add D&A from DFC, compute EBITDA metrics, parse BS/CF, return time series."""
    STEP = 4
    language = getattr(config, "language", "en") or "en"

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            # Always overlay language-specific LLM content regardless of what's in the
            # main cache (which was saved in whichever language was active at write time).
            interp = _load_interp_cache(CACHE_DIR, config.company_name, language)
            if interp:
                cached["data"]["chart_interpretations"] = interp
            headlines = _load_headline_cache(CACHE_DIR, config.company_name, language)
            if headlines:
                cached["data"]["section_headlines"] = headlines
            return cached

    try:
        pivot = metrics_calculator.compute_metrics(
            company_name=config.company_name,
            data_dir=DATA_DIR,
            years=YEARS,
        )

        time_series  = _build_time_series(pivot, config.company_name)
        metrics_computed = [
            "Gross_Margin_pct", "EBIT_Margin_pct", "COGS_pct_Revenue",
            "Revenue_YoY_pct", "COGS_YoY_pct",
        ]
        if "EBITDA_Margin_pct" in pivot.columns:
            metrics_computed.append("EBITDA_Margin_pct")

        # Build IS lookup for cross-statement metrics
        is_lookup = _build_is_lookup(pivot, config.company_name)

        # Parse balance sheets and cash flows
        balance_sheet_series: list = []
        cash_flow_series: list = []

        try:
            balance_sheets, _bs_stats = metrics_calculator.parse_balance_sheets(
                company_name=config.company_name,
                data_dir=DATA_DIR,
                years=YEARS,
            )
            if balance_sheets:
                balance_sheet_series = _build_bs_series(balance_sheets, is_lookup)
        except Exception:
            pass  # BS parsing failure does not break profitability output

        try:
            cash_flows, _cf_stats = metrics_calculator.parse_cash_flows(
                company_name=config.company_name,
                data_dir=DATA_DIR,
                years=YEARS,
            )
            if cash_flows:
                cash_flow_series = _build_cf_series(cash_flows, is_lookup)
        except Exception:
            pass  # CF parsing failure does not break profitability output

        # Parse DVA / DMPL / DRA series
        dva_series  = _build_dva_series(config.company_name)
        dmpl_series = _build_dmpl_series(config.company_name)
        dra_series  = _build_dra_series(config.company_name)

        # Compute bridge data for waterfall charts
        margin_bridge   = compute_margin_bridge(time_series)
        equity_bridge   = compute_equity_bridge(dmpl_series)
        cashflow_bridge = compute_cashflow_bridge(cash_flow_series, balance_sheet_series)
        dva_bridge      = compute_dva_bridge(dva_series)

        # Generate LLM chart interpretations (language-specific sidecar cache)
        bs_annual = [r for r in balance_sheet_series if r.get("granularity") == "annual"]
        cf_annual = [r for r in cash_flow_series if r.get("granularity") == "annual"]
        interp = _load_interp_cache(CACHE_DIR, config.company_name, language)
        # Invalidate cache if it pre-dates the bridge chart captions
        if interp is not None and "margin_trend" not in interp:
            interp = None
        if interp is None:
            interp = _generate_chart_interpretations(
                time_series, bs_annual, cf_annual, config.company_name, language,
                margin_bridge=margin_bridge,
                equity_bridge=equity_bridge,
                cashflow_bridge=cashflow_bridge,
                dva_bridge=dva_bridge,
            )
            if interp:
                _save_interp_cache(interp, CACHE_DIR, config.company_name, language)

        # FRE enrichment — debt maturity, currency exposure, auditor card
        fre_debt_maturity = None
        fre_debt_currency = None
        fre_auditor_card  = None
        try:
            _bonds = parse_fre_foreign_bonds(DATA_DIR, config.company_name, YEARS)
            fre_debt_maturity = _build_fre_debt_maturity(_bonds)
            fre_debt_currency = _build_fre_debt_currency(_bonds)
        except Exception:
            pass
        try:
            _aud_profiles = parse_fre_auditor(DATA_DIR, config.company_name, YEARS)
            fre_auditor_card = _build_fre_auditor_card(_aud_profiles)
        except Exception:
            pass

        # Generate section headlines (separate cache)
        headlines = _load_headline_cache(CACHE_DIR, config.company_name, language)
        if headlines is None:
            headlines = _generate_section_headlines(
                time_series, bs_annual, cf_annual, dva_series,
                config.company_name, language,
            )
            if headlines:
                _save_headline_cache(headlines, CACHE_DIR, config.company_name, language)

        result = {
            "status": "complete",
            "data": {
                "metrics_computed":      metrics_computed,
                "periods":               len(time_series),
                "time_series":           time_series,
                "balance_sheet_series":  balance_sheet_series,
                "cash_flow_series":      cash_flow_series,
                "dva_series":            dva_series,
                "dmpl_series":           dmpl_series,
                "dra_series":            dra_series,
                "margin_bridge":         margin_bridge,
                "equity_bridge":         equity_bridge,
                "cashflow_bridge":       cashflow_bridge,
                "dva_bridge":            dva_bridge,
                "chart_interpretations": interp or {},
                "section_headlines":     headlines or {},
                "fre_debt_maturity":     fre_debt_maturity,
                "fre_debt_currency":     fre_debt_currency,
                "fre_auditor_card":      fre_auditor_card,
                "source":                "live",
            },
            "metadata": {"cache_used": False, "source": "live"},
        }
        save_cache(STEP, result, CACHE_DIR, company_name=config.company_name)
        return result

    except Exception as exc:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            cached["metadata"]["source"] = "cache"
            cached["metadata"]["reason"] = str(exc)
            interp = _load_interp_cache(CACHE_DIR, config.company_name, language)
            if interp:
                cached["data"]["chart_interpretations"] = interp
            headlines = _load_headline_cache(CACHE_DIR, config.company_name, language)
            if headlines:
                cached["data"]["section_headlines"] = headlines
            return cached

        return {
            "status": "error",
            "data":   {},
            "metadata": {"cache_used": False, "source": "live"},
            "error":  str(exc),
        }
