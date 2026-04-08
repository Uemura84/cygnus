"""Step 5: Metric Validation — live implementation with cache layer."""

import json
import logging
import os

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache, _resolve_dir
from pipeline import pattern_detector, metrics_calculator

logger = logging.getLogger(__name__)

# ── Sector hints for LLM prompt ──────────────────────────────────────────────
COMPANY_SECTOR_HINTS = {
    "BRASKEM S.A.": "Petrochemical manufacturer (naphtha-based, commodity chemicals)",
    "VALE S.A.": "Mining (iron ore, nickel, base metals)",
    "VOTORANTIM CIMENTOS S.A.": "Building materials (cement, concrete, aggregates)",
}

# ── Default fallback bounds (no LLM required) ────────────────────────────────
DEFAULT_BOUNDS = {
    "label_en": "General Industrial",
    "label_pt": "Industrial Geral",
    "source": "default",
    "profitability": {
        "Gross Margin %":   {"min": -80,  "max": 95,   "rationale_en": "General range; values outside suggest data error.", "rationale_pt": "Faixa geral; valores fora sugerem erro de dados."},
        "EBIT Margin %":    {"min": -80,  "max": 80,   "rationale_en": "General range.", "rationale_pt": "Faixa geral."},
        "COGS / Revenue %": {"min": 5,    "max": 150,  "rationale_en": "Very low or very high COGS flags data error.", "rationale_pt": "COGS muito baixo ou alto indica erro de dados."},
        "SGA / Revenue %":  {"min": 0,    "max": 60,   "rationale_en": "SGA above 60% is unusual for any industrial.", "rationale_pt": "SGA acima de 60% é incomum para qualquer indústria."},
    },
    "balance_sheet": {
        "Current Ratio":            {"min": 0.05, "max": 20,  "rationale_en": "Extreme values suggest data error.", "rationale_pt": "Valores extremos sugerem erro de dados."},
        "Debt / EBITDA":            {"min": -10,  "max": 50,  "rationale_en": "Wide default range.", "rationale_pt": "Faixa padrão ampla."},
        "Working Capital Change %": {"min": -300, "max": 300, "rationale_en": "Swings exceeding ±300% suggest anomaly.", "rationale_pt": "Variações acima de ±300% sugerem anomalia."},
        "Asset Turnover":           {"min": 0,    "max": 10,  "rationale_en": "Above 10× is unusual.", "rationale_pt": "Acima de 10× é incomum."},
        "ROA %":                    {"min": -100, "max": 100, "rationale_en": "Values outside ±100% suggest scaling error.", "rationale_pt": "Valores fora de ±100% sugerem erro de escala."},
        "ROE %":                    {"min": -500, "max": 500, "rationale_en": "Extreme values flag for review.", "rationale_pt": "Valores extremos requerem revisão."},
    },
    "cash_flow": {
        "OCF / Net Income":  {"min": -15,  "max": 15,  "rationale_en": "Extreme values suggest data inconsistency.", "rationale_pt": "Valores extremos sugerem inconsistência de dados."},
        "Capex / Revenue %": {"min": 0,    "max": 60,  "rationale_en": "Capex above 60% of revenue is unusual.", "rationale_pt": "Capex acima de 60% da receita é incomum."},
        "Capex / D&A":       {"min": 0,    "max": 8,   "rationale_en": "Above 8× suggests major expansion or error.", "rationale_pt": "Acima de 8× sugere grande expansão ou erro."},
        "FCF / Revenue %":   {"min": -150, "max": 150, "rationale_en": "FCF exceeding 150% of revenue flags anomaly.", "rationale_pt": "FCL acima de 150% da receita indica anomalia."},
    },
}

# ── Expected metric keys per section (for LLM validation) ────────────────────
_EXPECTED_KEYS = {
    "profitability": {"Gross Margin %", "EBIT Margin %", "COGS / Revenue %", "SGA / Revenue %"},
    "balance_sheet": {"Current Ratio", "Debt / EBITDA", "Working Capital Change %", "Asset Turnover", "ROA %", "ROE %"},
    "cash_flow":     {"OCF / Net Income", "Capex / Revenue %", "Capex / D&A", "FCF / Revenue %"},
}


# ── Balance sheet plausibility bounds (industrial / capital-intensive) ────────
_BS_PLAUSIBILITY_BOUNDS = [
    # (metric_key, lo, hi)
    ("current_ratio",     0.1,   10.0),
    ("debt_to_ebitda",   -5.0,   30.0),
    ("asset_turnover",    0.0,    5.0),
    ("return_on_assets", -100.0, 100.0),
    ("return_on_equity", -500.0, 500.0),
]

# ── Cash flow plausibility bounds (industrial / capital-intensive) ────────────
_CF_PLAUSIBILITY_BOUNDS = [
    # (metric_key, lo, hi)
    ("ocf_to_net_income",      -10.0, 10.0),
    ("capex_to_revenue",         0.0, 50.0),
    ("capex_to_depreciation",    0.0,  5.0),
]


def _bs_plausibility_checks(bs_series: list) -> dict:
    """Run 7 balance sheet plausibility checks on annual BS data from Step 4.

    INFORMATIONAL flags (net_debt sign) are included in the flags list but
    NOT counted in flagged / quality-score.
    """
    annual = [r for r in bs_series if r.get("granularity") == "annual"]
    flags  = []
    total  = 0

    for record in annual:
        period = str(record.get("period", ""))[:4]

        # 5 range checks
        for metric, lo, hi in _BS_PLAUSIBILITY_BOUNDS:
            raw = record.get(metric)
            if raw is None:
                continue
            total += 1
            try:
                v = float(raw)
            except (TypeError, ValueError):
                continue
            if v < lo or v > hi:
                flags.append({
                    "period":     period,
                    "metric":     metric,
                    "value":      f"{v:.2f}",
                    "flag":       "DATA_ISSUE",
                    "reason":     f"outside [{lo}, {hi}]",
                    "confidence": "MEDIUM",
                    "severity":   "MEDIUM",
                })

        # Net debt sign — informational only, not counted in quality score
        nd = record.get("net_debt")
        if nd is not None:
            try:
                nd_v = float(nd)
                if nd_v < 0:
                    flags.append({
                        "period":     period,
                        "metric":     "net_debt",
                        "value":      f"{nd_v:,.0f}",
                        "flag":       "INFORMATIONAL",
                        "reason":     "Net cash position (net_debt < 0)",
                        "confidence": "HIGH",
                        "severity":   "LOW",
                    })
            except (TypeError, ValueError):
                pass

    # Working capital YoY change > 200% (one check per consecutive annual pair)
    for i in range(1, len(annual)):
        prev_wc = annual[i - 1].get("working_capital")
        curr_wc = annual[i].get("working_capital")
        period  = str(annual[i].get("period", ""))[:4]
        if prev_wc is None or curr_wc is None:
            continue
        try:
            prev_f = float(prev_wc)
            curr_f = float(curr_wc)
        except (TypeError, ValueError):
            continue
        if prev_f == 0:
            continue
        total += 1
        change_pct = abs((curr_f - prev_f) / abs(prev_f) * 100)
        if change_pct > 200:
            flags.append({
                "period":     period,
                "metric":     "working_capital_yoy",
                "value":      f"{change_pct:.1f}%",
                "flag":       "DATA_ISSUE",
                "reason":     f"YoY change {change_pct:.0f}% exceeds 200% threshold",
                "confidence": "MEDIUM",
                "severity":   "MEDIUM",
            })

    n_flagged = sum(1 for f in flags if f.get("severity") in ("HIGH", "MEDIUM"))
    n_clean   = max(0, total - n_flagged)
    return {
        "flags":             flags,
        "total_data_points": total,
        "clean":             n_clean,
        "flagged":           n_flagged,
    }


def _cf_plausibility_checks(cf_series: list, ts_series: list) -> dict:
    """Run 4 cash flow plausibility checks on annual CF data from Step 4.

    ts_series is the IS time_series from Step 4, used to get revenue_abs
    for the FCF/Revenue check.
    """
    annual = [r for r in cf_series if r.get("granularity") == "annual"]
    flags  = []
    total  = 0

    # Revenue lookup from IS time_series: period_year → revenue_abs
    rev_lookup: dict = {}
    for r in ts_series:
        key = str(r.get("period", ""))[:4]
        rev = r.get("revenue_abs")
        if rev is not None:
            try:
                rev_lookup[key] = float(rev)
            except (TypeError, ValueError):
                pass

    for record in annual:
        period = str(record.get("period", ""))[:4]

        # 3 standard range checks
        for metric, lo, hi in _CF_PLAUSIBILITY_BOUNDS:
            raw = record.get(metric)
            if raw is None:
                continue
            total += 1
            try:
                v = float(raw)
            except (TypeError, ValueError):
                continue
            if v < lo or v > hi:
                flags.append({
                    "period":     period,
                    "metric":     metric,
                    "value":      f"{v:.2f}",
                    "flag":       "DATA_ISSUE",
                    "reason":     f"outside [{lo}, {hi}]",
                    "confidence": "MEDIUM",
                    "severity":   "MEDIUM",
                })

        # FCF / Revenue % (computed on the fly)
        fcf = record.get("free_cash_flow")
        rev = rev_lookup.get(period)
        if fcf is not None and rev is not None and rev != 0:
            total += 1
            try:
                fcf_rev_pct = float(fcf) / rev * 100
                if fcf_rev_pct < -100 or fcf_rev_pct > 100:
                    flags.append({
                        "period":     period,
                        "metric":     "fcf_revenue_pct",
                        "value":      f"{fcf_rev_pct:.1f}%",
                        "flag":       "DATA_ISSUE",
                        "reason":     f"FCF/Revenue {fcf_rev_pct:.1f}% outside [-100%, 100%]",
                        "confidence": "MEDIUM",
                        "severity":   "MEDIUM",
                    })
            except (TypeError, ValueError):
                pass

    n_flagged = sum(1 for f in flags if f.get("severity") in ("HIGH", "MEDIUM"))
    n_clean   = max(0, total - n_flagged)
    return {
        "flags":             flags,
        "total_data_points": total,
        "clean":             n_clean,
        "flagged":           n_flagged,
    }


def _bounds_cache_path(cache_dir, company_name: str):
    """Return the sidecar cache path for LLM-generated plausibility bounds."""
    company_key = company_name.split()[0].lower()
    return _resolve_dir(cache_dir, company_name) / f"step5_bounds_{company_key}.json"


def _load_bounds_cache(cache_dir, company_name: str) -> dict | None:
    path = _bounds_cache_path(cache_dir, company_name)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_bounds_cache(data: dict, cache_dir, company_name: str) -> None:
    path = _bounds_cache_path(cache_dir, company_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _validate_bounds(bounds: dict) -> bool:
    """Return True if bounds dict has all expected keys with valid min < max."""
    for section, keys in _EXPECTED_KEYS.items():
        section_data = bounds.get(section, {})
        for key in keys:
            entry = section_data.get(key)
            if not isinstance(entry, dict):
                return False
            mn = entry.get("min")
            mx = entry.get("max")
            if not isinstance(mn, (int, float)) or not isinstance(mx, (int, float)):
                return False
            if mn >= mx:
                return False
    return True


def _generate_llm_bounds(company_name: str) -> dict:
    """Call Claude Sonnet to generate sector-specific plausibility bounds.

    Returns a validated bounds dict (same structure as DEFAULT_BOUNDS),
    or DEFAULT_BOUNDS on any error.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return DEFAULT_BOUNDS

    sector = COMPANY_SECTOR_HINTS.get(company_name, "Unknown (infer from company name)")

    prompt = f"""You are a senior financial analyst specializing in industry-specific financial analysis.

Company: {company_name}
Sector: {sector}
Country: Brazil
Data source: CVM (Brazilian Securities Commission) public filings

For the metrics listed below, provide plausibility bounds (min and max) that are appropriate for this specific industry sector. These bounds are used to flag potential DATA ERRORS — not to detect business problems. Values inside the bounds are considered plausible; values outside suggest a data quality issue that needs investigation.

Be specific to this industry. For example:
- A petrochemical company has COGS/Revenue typically 70-95%, so a plausible range might be 20-130%
- A mining company has very low asset turnover (heavy fixed assets), so a plausible range might be 0-2×
- A software company has very low COGS, so a plausible range might be 5-60%

Metrics to define bounds for:

PROFITABILITY:
- Gross Margin % (revenue minus COGS, as percentage of revenue)
- EBIT Margin % (operating profit as percentage of revenue)
- COGS / Revenue % (cost of goods sold as percentage of revenue)
- SGA / Revenue % (selling, general & admin as percentage of revenue)

BALANCE SHEET:
- Current Ratio (current assets / current liabilities)
- Debt / EBITDA (net debt / EBITDA, times)
- Working Capital Change % (year-over-year percentage change)
- Asset Turnover (revenue / total assets)
- ROA % (net income / total assets)
- ROE % (net income / total equity)

CASH FLOW:
- OCF / Net Income (operating cash flow / net income)
- Capex / Revenue % (capital expenditure as percentage of revenue)
- Capex / D&A (capital expenditure / depreciation & amortization)
- FCF / Revenue % (free cash flow as percentage of revenue)

Respond ONLY with a JSON object in this exact format, no other text:

{{
  "sector_label_en": "Petrochemical",
  "sector_label_pt": "Petroquímico",
  "profitability": {{
    "Gross Margin %": {{"min": -50, "max": 80, "rationale_en": "...", "rationale_pt": "..."}},
    "EBIT Margin %": {{"min": -50, "max": 60, "rationale_en": "...", "rationale_pt": "..."}},
    "COGS / Revenue %": {{"min": 20, "max": 130, "rationale_en": "...", "rationale_pt": "..."}},
    "SGA / Revenue %": {{"min": 0, "max": 40, "rationale_en": "...", "rationale_pt": "..."}}
  }},
  "balance_sheet": {{
    "Current Ratio": {{"min": 0.1, "max": 10, "rationale_en": "...", "rationale_pt": "..."}},
    "Debt / EBITDA": {{"min": -5, "max": 30, "rationale_en": "...", "rationale_pt": "..."}},
    "Working Capital Change %": {{"min": -200, "max": 200, "rationale_en": "...", "rationale_pt": "..."}},
    "Asset Turnover": {{"min": 0, "max": 5, "rationale_en": "...", "rationale_pt": "..."}},
    "ROA %": {{"min": -100, "max": 100, "rationale_en": "...", "rationale_pt": "..."}},
    "ROE %": {{"min": -500, "max": 500, "rationale_en": "...", "rationale_pt": "..."}}
  }},
  "cash_flow": {{
    "OCF / Net Income": {{"min": -10, "max": 10, "rationale_en": "...", "rationale_pt": "..."}},
    "Capex / Revenue %": {{"min": 0, "max": 50, "rationale_en": "...", "rationale_pt": "..."}},
    "Capex / D&A": {{"min": 0, "max": 5, "rationale_en": "...", "rationale_pt": "..."}},
    "FCF / Revenue %": {{"min": -100, "max": 100, "rationale_en": "...", "rationale_pt": "..."}}
  }}
}}"""

    try:
        import anthropic
        client  = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)

        # Build normalised bounds dict
        bounds = {
            "label_en": parsed.get("sector_label_en", "Unknown"),
            "label_pt": parsed.get("sector_label_pt", "Desconhecido"),
            "source": "llm",
            "profitability": parsed.get("profitability", {}),
            "balance_sheet": parsed.get("balance_sheet", {}),
            "cash_flow":     parsed.get("cash_flow", {}),
        }
        if _validate_bounds(bounds):
            return bounds
        logger.warning("Step5 LLM bounds failed validation — using DEFAULT")
        return DEFAULT_BOUNDS
    except Exception as exc:
        logger.warning("Step5 LLM bounds call failed (%s) — using DEFAULT", exc)
        return DEFAULT_BOUNDS


def _normalize_df_columns(df: pd.DataFrame) -> None:
    """Rename legacy CVM column names to common model names (in-place).

    Handles pivot/metrics CSVs written before the common model refactor.
    """
    renames = {}
    if "DENOM_CIA" in df.columns:
        renames["DENOM_CIA"] = "company_id"
    if "DT_REFER" in df.columns:
        renames["DT_REFER"] = "period_date"
    if renames:
        df.rename(columns=renames, inplace=True)
    revenue_pt = "Receita de Venda de Bens e/ou Serviços"
    cogs_pt    = "Custo dos Bens e/ou Serviços Vendidos"
    if revenue_pt in df.columns and "revenue" not in df.columns:
        df["revenue"] = df[revenue_pt]
    if cogs_pt in df.columns and "cogs" not in df.columns:
        df["cogs"] = df[cogs_pt].abs()


def _load_metrics_df(company_name: str, data_dir) -> pd.DataFrame:
    """Load the metrics CSV written by Step 4."""
    company_key  = company_name.split()[0].lower()
    metrics_path = data_dir / "analysis" / f"metrics_{company_key}.csv"
    if metrics_path.exists():
        df = pd.read_csv(metrics_path, low_memory=False)
    else:
        # Fall back to pivot CSV if metrics not yet available
        pivot_path = data_dir / "analysis" / f"pivot_{company_key}.csv"
        if pivot_path.exists():
            df = pd.read_csv(pivot_path, low_memory=False)
        else:
            raise FileNotFoundError(
                f"No metrics or pivot CSV found for {company_name}. Run Steps 3 and 4 first."
            )
    # Normalize legacy CVM column names to common model names
    _normalize_df_columns(df)
    return df


def _cross_statement_validations(company_name: str) -> list:
    """Run 3 cross-statement consistency checks. Returns list of warning dicts."""
    warnings = []

    try:
        bs_result  = metrics_calculator.parse_balance_sheets(
            company_name=company_name, data_dir=DATA_DIR, years=YEARS
        )
        # parse_balance_sheets returns (list[BalanceSheet], stats_dict)
        balance_sheets = bs_result[0] if isinstance(bs_result, tuple) else bs_result
    except Exception:
        balance_sheets = []

    try:
        cf_result  = metrics_calculator.parse_cash_flows(
            company_name=company_name, data_dir=DATA_DIR, years=YEARS
        )
        # parse_cash_flows returns (list[CashFlow], stats_dict)
        cash_flows = cf_result[0] if isinstance(cf_result, tuple) else cf_result
    except Exception:
        cash_flows = []

    # Validation 1: Assets ≈ Liabilities + Equity (0.1% tolerance)
    for bs in balance_sheets:
        ta = bs.total_assets
        tl = bs.total_liabilities
        te = bs.total_equity
        if ta is None or tl is None or te is None:
            continue
        expected = tl + te
        if abs(ta) < 1:
            continue
        gap_pct = abs(ta - expected) / abs(ta) * 100
        if gap_pct > 0.1:
            warnings.append({
                "type": "cross_statement",
                "check": "balance_sheet_equation",
                "severity": "HIGH",
                "period": str(bs.period.date),
                "message": (
                    f"Assets ({ta:,.0f}) ≠ Liabilities + Equity ({expected:,.0f}); "
                    f"gap {gap_pct:.2f}%"
                ),
                "gap_pct": round(gap_pct, 4),
            })

    # Validation 2: D&A on IS ≈ D&A on CF (0.1% tolerance or BRL 1K)
    # Build a lookup from CF: period_date → depreciation_amortization
    cf_da_lookup: dict = {}
    for cf in cash_flows:
        da = cf.depreciation_amortization
        if da is not None:
            cf_da_lookup[str(cf.period.date)] = abs(float(da))

    # Get IS D&A from pivot via metrics_calculator
    try:
        pivot = metrics_calculator.compute_metrics(
            company_name=company_name, data_dir=DATA_DIR, years=YEARS
        )
        company_key = company_name.split()[0].upper()
        id_col   = "company_id"  if "company_id"  in pivot.columns else "DENOM_CIA"
        date_col = "period_date" if "period_date" in pivot.columns else "DT_REFER"

        comp = pivot[
            pivot[id_col].str.upper().str.contains(company_key, na=False)
        ].copy()

        da_col = "DA_from_DFC"
        if da_col in comp.columns:
            for _, row in comp.iterrows():
                period_key = str(row.get(date_col, ""))
                is_da_val  = row.get(da_col)
                cf_da_val  = cf_da_lookup.get(period_key)
                if is_da_val is None or pd.isna(is_da_val) or cf_da_val is None:
                    continue
                is_da = abs(float(is_da_val))
                diff  = abs(is_da - cf_da_val)
                if diff > 1 and (max(is_da, cf_da_val) < 1 or diff / max(is_da, cf_da_val) > 0.001):
                    warnings.append({
                        "type": "cross_statement",
                        "check": "da_consistency",
                        "severity": "MEDIUM",
                        "period": period_key,
                        "message": (
                            f"D&A on IS ({is_da:,.0f}) ≠ D&A on CF ({cf_da_val:,.0f}); "
                            f"diff {diff:,.0f}"
                        ),
                        "diff_abs": round(diff, 2),
                    })
    except Exception:
        pass

    # Validation 3: Opening Cash + Net Cash Flow ≈ Closing Cash (2% or BRL 1M tolerance)
    # Check consecutive CF periods where we have all 3 flow lines
    sorted_cfs = sorted(cash_flows, key=lambda x: x.period.date)
    for i in range(1, len(sorted_cfs)):
        prev_cf = sorted_cfs[i - 1]
        curr_cf = sorted_cfs[i]

        ocf = curr_cf.operating_cash_flow
        icf = curr_cf.investing_cash_flow
        fcf_fin = curr_cf.financing_cash_flow
        if ocf is None or icf is None or fcf_fin is None:
            continue

        net_flow = float(ocf) + float(icf) + float(fcf_fin)

        # Find balance sheet cash for the two periods
        prev_bs = next(
            (bs for bs in balance_sheets if str(bs.period.date) == str(prev_cf.period.date)),
            None,
        )
        curr_bs = next(
            (bs for bs in balance_sheets if str(bs.period.date) == str(curr_cf.period.date)),
            None,
        )
        if prev_bs is None or curr_bs is None:
            continue
        opening = prev_bs.cash_and_equivalents
        closing = curr_bs.cash_and_equivalents
        if opening is None or closing is None:
            continue

        expected_closing = float(opening) + net_flow
        diff = abs(float(closing) - expected_closing)
        tolerance = max(abs(float(closing)) * 0.02, 1_000)  # 2% or BRL 1M (in thousands)
        if diff > tolerance:
            warnings.append({
                "type": "cross_statement",
                "check": "cash_reconciliation",
                "severity": "MEDIUM",
                "period": str(curr_cf.period.date),
                "message": (
                    f"Cash reconciliation gap {diff:,.0f} "
                    f"(opening {float(opening):,.0f} + net flow {net_flow:,.0f} "
                    f"≠ closing {float(closing):,.0f})"
                ),
                "diff_abs": round(diff, 2),
            })

    return warnings


def run(config, pipeline_state: dict) -> dict:
    """Validate metric ranges and assign row-level confidence.

    Saves enriched DataFrame to data/analysis/enriched_{key}.csv
    for use by Steps 6-8.
    """
    STEP = 5

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            return cached

    try:
        logger.info("Step5: starting live run for %s", config.company_name)
        df = _load_metrics_df(config.company_name, DATA_DIR)
        logger.info("Step5: metrics df loaded — %d rows, columns: %s", len(df), list(df.columns)[:6])

        quality = pattern_detector.quality_scan(df)
        logger.info("Step5: quality_scan → total=%s flagged=%s", quality.get("total_data_points"), quality.get("flagged"))

        # Save enriched df for downstream steps
        enriched_df  = quality.pop("_enriched_df")  # extract before caching
        company_key  = config.company_name.split()[0].lower()
        enriched_path = DATA_DIR / "analysis" / f"enriched_{company_key}.csv"
        enriched_df.to_csv(enriched_path, index=False, encoding="utf-8-sig")

        # Cross-statement validations (parsing errors are silently ignored)
        cross_warnings = _cross_statement_validations(config.company_name)
        logger.info("Step5: cross_statement_validations → %d warnings", len(cross_warnings))

        # BS / CF plausibility from Step 4 series (via pipeline_state)
        # Fall back to step4 cache when pipeline_state is empty (cache_mode, fresh session)
        step4_data = pipeline_state.get("step4") or {}
        if not step4_data:
            logger.info("Step5: pipeline_state missing step4 — loading from cache")
            cached4    = load_cache(4, CACHE_DIR, company_name=config.company_name)
            step4_data = (cached4 or {}).get("data", {})
        bs_series    = step4_data.get("balance_sheet_series", [])
        cf_series    = step4_data.get("cash_flow_series", [])
        ts_series    = step4_data.get("time_series", [])
        logger.info("Step5: step4 data → bs_series=%d cf_series=%d ts_series=%d",
                    len(bs_series), len(cf_series), len(ts_series))
        bs_plausibility = _bs_plausibility_checks(bs_series)
        cf_plausibility = _cf_plausibility_checks(cf_series, ts_series)
        logger.info("Step5: bs_plausibility → total=%s flagged=%s", bs_plausibility.get("total_data_points"), bs_plausibility.get("flagged"))
        logger.info("Step5: cf_plausibility → total=%s flagged=%s", cf_plausibility.get("total_data_points"), cf_plausibility.get("flagged"))

        # LLM-generated sector-aware plausibility bounds (cached per company)
        plausibility_bounds = _load_bounds_cache(CACHE_DIR, config.company_name)
        if plausibility_bounds is None:
            plausibility_bounds = _generate_llm_bounds(config.company_name)
            if plausibility_bounds.get("source") == "llm":
                _save_bounds_cache(plausibility_bounds, CACHE_DIR, config.company_name)

        result = {
            "status": "complete",
            "data": {
                **quality,
                "cross_statement_warnings": cross_warnings,
                "bs_plausibility":          bs_plausibility,
                "cf_plausibility":          cf_plausibility,
                "plausibility_bounds":      plausibility_bounds,
                "source": "live",
            },
            "metadata": {"cache_used": False, "source": "live"},
        }
        save_cache(STEP, result, CACHE_DIR, company_name=config.company_name)
        return result

    except Exception as exc:
        logger.error("Step5: exception in run() — %s: %s", type(exc).__name__, exc, exc_info=True)
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
