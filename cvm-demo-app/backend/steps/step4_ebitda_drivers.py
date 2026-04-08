"""Step 4: EBITDA Drivers Construction — live implementation with cache layer."""

import json
import os

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import metrics_calculator


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


def _generate_chart_interpretations(
    time_series: list,
    bs_annual: list,
    cf_annual: list,
    company_name: str,
    language: str,
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
        "Revenue_YoY_pct", "COGS_YoY_pct",
    ])
    bs_summary = _last_n(bs_annual, [
        "current_ratio", "quick_ratio", "net_debt", "working_capital",
        "return_on_assets", "return_on_equity", "debt_to_ebitda",
    ])
    cf_summary = _last_n(cf_annual, [
        "operating_cash_flow", "free_cash_flow", "ocf_to_net_income",
        "capex_to_revenue", "capex_to_depreciation",
    ])

    lang_label = "English" if language == "en" else "Brazilian Portuguese"

    prompt = f"""You are a financial analyst reviewing {company_name}'s metrics (BRL thousands).

=== Income Statement Metrics ===
{ts_summary}

=== Balance Sheet Metrics ===
{bs_summary}

=== Cash Flow Metrics ===
{cf_summary}

Generate exactly ONE sentence (max 30 words) interpreting each of these 11 charts.
Mention specific numbers where useful. Write in {lang_label}.

Reply ONLY with a valid JSON object, no other text:
{{
  "margin_trajectory": "...",
  "revenue_cogs_growth": "...",
  "liquidity": "...",
  "net_debt": "...",
  "working_capital": "...",
  "roa": "...",
  "roe": "...",
  "cf_statement": "...",
  "fcf": "...",
  "ccc": "...",
  "capex": "..."
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
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

    revenue_col = "revenue" if "revenue" in comp.columns else "Receita de Venda de Bens e/ou Serviços"
    cogs_col    = "cogs"    if "cogs"    in comp.columns else "Custo dos Bens e/ou Serviços Vendidos"
    cogs_is_abs = (cogs_col == "cogs")

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


def run(config, pipeline_state: dict) -> dict:
    """Add D&A from DFC, compute EBITDA metrics, parse BS/CF, return time series."""
    STEP = 4
    language = getattr(config, "language", "en") or "en"

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            if "chart_interpretations" not in cached.get("data", {}):
                interp = _load_interp_cache(CACHE_DIR, config.company_name, language)
                cached["data"]["chart_interpretations"] = interp or {}
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

        # Generate LLM chart interpretations (language-specific sidecar cache)
        bs_annual = [r for r in balance_sheet_series if r.get("granularity") == "annual"]
        cf_annual = [r for r in cash_flow_series if r.get("granularity") == "annual"]
        interp = _load_interp_cache(CACHE_DIR, config.company_name, language)
        if interp is None:
            interp = _generate_chart_interpretations(
                time_series, bs_annual, cf_annual, config.company_name, language
            )
            if interp:
                _save_interp_cache(interp, CACHE_DIR, config.company_name, language)

        result = {
            "status": "complete",
            "data": {
                "metrics_computed":      metrics_computed,
                "periods":               len(time_series),
                "time_series":           time_series,
                "balance_sheet_series":  balance_sheet_series,
                "cash_flow_series":      cash_flow_series,
                "chart_interpretations": interp or {},
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
            return cached

        return {
            "status": "error",
            "data":   {},
            "metadata": {"cache_used": False, "source": "live"},
            "error":  str(exc),
        }
