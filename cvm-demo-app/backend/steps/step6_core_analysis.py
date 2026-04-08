"""Step 6: Pattern Detection & Risk Assessment — merged detection + enrichment."""

import json

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import pattern_detector, enrichment, bs_detector, cf_detector, signal_stacker
from pipeline.enrichment import SECTOR_MAP
from pipeline.materiality import estimate_impact, estimate_bs_cf_impact
from pipeline import metrics_calculator
from models import determine_active_modules, CompanyFinancials, Company, Period, IncomeStatement


IMPLEMENTED_MODULES = ["profitability", "balance_sheet_health", "cash_flow_quality"]


def _normalize_df_columns(df: pd.DataFrame) -> None:
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


def _load_enriched_df(company_name: str, data_dir) -> pd.DataFrame:
    company_key = company_name.split()[0].lower()
    enriched_path = data_dir / "analysis" / f"enriched_{company_key}.csv"
    if enriched_path.exists():
        df = pd.read_csv(enriched_path, low_memory=False)
        _normalize_df_columns(df)
        return df

    metrics_path = data_dir / "analysis" / f"metrics_{company_key}.csv"
    pivot_path   = data_dir / "analysis" / f"pivot_{company_key}.csv"
    for path in (metrics_path, pivot_path):
        if path.exists():
            df = pd.read_csv(path, low_memory=False)
            _normalize_df_columns(df)
            df = pattern_detector.validate_metric_ranges(df)
            df = pattern_detector.assign_data_confidence(df)
            return df

    raise FileNotFoundError(
        f"No enriched/metrics/pivot CSV found for {company_name}. Run Steps 3-5 first."
    )


def _build_company_financials(company_name: str, balance_sheets: list, cash_flows: list) -> CompanyFinancials:
    """Build a minimal CompanyFinancials for determine_active_modules()."""
    company = Company(id=company_name, name=company_name, source="cvm", country="BR", currency="BRL")
    # Stub income_statements with enough periods to satisfy the ≥4 threshold
    stubs = [
        IncomeStatement(
            company_id=company_name,
            period=Period(date=__import__('datetime').date(2020 + i, 12, 31), granularity="annual", fiscal_year=2020 + i),
        )
        for i in range(5)
    ]
    return CompanyFinancials(
        company=company,
        income_statements=stubs,
        balance_sheets=balance_sheets if balance_sheets else None,
        cash_flows=cash_flows if cash_flows else None,
    )


def _shape_findings(findings: list, id_prefix: str = "F") -> list:
    shaped = []
    base_keys = {"company", "metric", "pattern", "severity", "confidence_score",
                 "anomaly_type", "confidence_reason", "insight", "estimated_impact",
                 "module", "code", "category", "description", "trend_direction",
                 "materiality_brl", "periods_affected", "metric_name", "metric_values",
                 "contributing_signals", "modules_involved", "description_pt"}
    for i, f in enumerate(findings, start=1):
        # Use 'code' if present (BS_/CF_/STACKED_), else fall back to 'pattern'
        code    = f.get("code") or f.get("pattern", "")
        pattern = f.get("pattern") or code
        module  = f.get("module", "profitability")
        record = {
            "id":               f"{id_prefix}{i:03d}",
            "code":             code,
            "module":           module,
            "company":          f.get("company", ""),
            "pattern":          pattern,
            "severity":         f.get("severity", "MEDIUM"),
            "metric":           f.get("metric_name") or f.get("metric", ""),
            "confidence":       f.get("confidence_score", "MEDIUM"),
            "anomaly_type":     f.get("anomaly_type", ""),
            "description":      f.get("description") or f.get("insight", ""),
            "period":           f.get("period", ""),
            "estimated_impact": f.get("estimated_impact"),
            "category":         f.get("category", ""),
            "trend_direction":  f.get("trend_direction", ""),
            "materiality_brl":  f.get("materiality_brl"),
            "contributing_signals": f.get("contributing_signals"),
            "modules_involved":     f.get("modules_involved"),
            "data_points":      {
                k: v for k, v in f.items()
                if k not in base_keys
                and k not in {"company", "metric", "pattern", "severity",
                              "confidence_score", "anomaly_type", "confidence_reason",
                              "insight", "estimated_impact"}
            },
        }
        shaped.append(record)
    return shaped


def categorize_findings(findings: list, composite_signals: list) -> dict:
    categories: dict = {
        "core": [], "supporting": [], "contextual": [], "anomalies": [],
        "balance_sheet": [], "cash_flow": [], "diagnoses": [],
    }

    for i, f in enumerate(findings, start=1):
        # Determine which section this finding belongs to based on its id prefix
        fid    = f.get("id", f"F{i:03d}")
        module = f.get("module", "profitability")
        cat    = f.get("category", "")

        if module == "stacked":
            categories["diagnoses"].append(fid)
        elif module == "balance_sheet_health":
            categories["balance_sheet"].append(fid)
        elif module == "cash_flow_quality":
            categories["cash_flow"].append(fid)
        else:
            # Module 1 profitability — existing categorization
            pattern      = f.get("pattern", "")
            anomaly_type = f.get("anomaly_type", "")

            if cat in ("Core",):
                categories["core"].append(fid)
            elif cat in ("Supporting",):
                categories["supporting"].append(fid)
            elif pattern in ("Cost composition drift", "Margin compression"):
                categories["core"].append(fid)
            elif pattern == "Revenue-cost decoupling":
                if (f.get("data_points", {}).get("divergence_pp") or 0) > 0:
                    categories["supporting"].append(fid)
                else:
                    categories["contextual"].append(fid)
            elif pattern == "Statistical anomaly":
                categories["anomalies"].append(fid)
            elif pattern == "YoY quarter comparison":
                if anomaly_type == "EVENT_DRIVEN_BUT_PLAUSIBLE":
                    categories["contextual"].append(fid)
                else:
                    categories["supporting"].append(fid)
            elif pattern == "Peer divergence":
                categories["supporting"].append(fid)
            else:
                categories["contextual"].append(fid)

    return categories


def _compute_risk_boost(bs_findings: list, cf_findings: list, stacked: list) -> float:
    """Compute additional risk points from BS, CF, and stacked findings."""
    boost = 0.0
    sev_pts = {"CRITICAL": 8.0, "HIGH": 5.0, "MEDIUM": 2.0, "LOW": 0.5}
    for f in bs_findings + cf_findings:
        boost += sev_pts.get(f.get("severity", ""), 0)
    for f in stacked:
        # Stacked diagnoses carry elevated weight
        base = sev_pts.get(f.get("severity", ""), 0)
        multiplier = 1.5 if f.get("severity") == "CRITICAL" else 1.3
        boost += base * multiplier
    return boost


def run(config, pipeline_state: dict) -> dict:
    STEP = 6

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            return cached

    try:
        df = _load_enriched_df(config.company_name, DATA_DIR)

        # Parse balance sheets and cash flows
        # Both functions return (list[obj], stats_dict) — unpack the list
        balance_sheets, cash_flows = [], []
        try:
            bs_result = metrics_calculator.parse_balance_sheets(
                company_name=config.company_name, data_dir=DATA_DIR, years=YEARS
            )
            balance_sheets = bs_result[0] if isinstance(bs_result, tuple) else bs_result
        except Exception:
            pass
        try:
            cf_result = metrics_calculator.parse_cash_flows(
                company_name=config.company_name, data_dir=DATA_DIR, years=YEARS
            )
            cash_flows = cf_result[0] if isinstance(cf_result, tuple) else cf_result
        except Exception:
            pass

        # Determine active + runnable modules
        company_financials = _build_company_financials(config.company_name, balance_sheets, cash_flows)
        active_modules  = determine_active_modules(company_financials)
        runnable_modules = [m for m in active_modules if m in IMPLEMENTED_MODULES]

        # ── Module 1: Profitability (existing) ──────────────────────────────
        if "_doc_type" in df.columns:
            df["period_type"] = df["_doc_type"].map({"DFP": "annual", "ITR": "quarterly"})
        df_annual    = df[df["_doc_type"] == "DFP"].copy() if "_doc_type" in df.columns else df.copy()
        df_quarterly = df[df["_doc_type"] == "ITR"].copy() if "_doc_type" in df.columns else pd.DataFrame()

        if "is_standalone" in df_quarterly.columns and not df_quarterly.empty:
            df_quarterly = df_quarterly[df_quarterly["is_standalone"] == True].copy()

        m1_findings = []
        if "profitability" in runnable_modules:
            m1_findings = pattern_detector.detect_patterns(
                df=df, df_annual=df_annual, df_quarterly=df_quarterly,
                sector_map=SECTOR_MAP,
            )
            # Tag with module field
            for f in m1_findings:
                f.setdefault("module", "profitability")
                f.setdefault("code", f.get("pattern", ""))

        # ── Module 2: Balance Sheet Health ──────────────────────────────────
        m2_findings = []
        if "balance_sheet_health" in runnable_modules:
            # Build BS series from parsed objects (mirrors step4 _build_bs_series output)
            bs_series = _bs_objects_to_series(balance_sheets, config.company_name)
            m2_findings = bs_detector.detect_bs_patterns(bs_series, config.company_name)

        # ── Module 3: Cash Flow Quality ──────────────────────────────────────
        m3_findings = []
        if "cash_flow_quality" in runnable_modules:
            cf_series = _cf_objects_to_series(cash_flows, config.company_name)
            m3_findings = cf_detector.detect_cf_patterns(cf_series, config.company_name)

        # ── Materiality for BS / CF findings ────────────────────────────────
        lang = getattr(config, "language", "en")
        estimate_bs_cf_impact(m2_findings + m3_findings, language=lang)

        # ── Signal stacking ─────────────────────────────────────────────────
        all_module_findings = m1_findings + m2_findings + m3_findings
        stacked_diagnoses = signal_stacker.stack_signals(all_module_findings)
        for sd in stacked_diagnoses:
            sd["company"] = config.company_name

        all_findings = all_module_findings + stacked_diagnoses

        # ── Materiality (Module 1 only, uses metrics df) ────────────────────
        # pipeline_state["step4"] starts as None, so use "or {}" instead of .get(..., {})
        step4_data_s6      = pipeline_state.get("step4") or {}
        step4_time_series  = step4_data_s6.get("time_series", [])
        if not step4_time_series:
            # Fall back to step4 cache
            from cache_utils import load_cache as _lc
            cached4_s6 = _lc(4, CACHE_DIR, company_name=config.company_name)
            step4_time_series = ((cached4_s6 or {}).get("data") or {}).get("time_series", [])
        metrics_df = pd.DataFrame(step4_time_series) if step4_time_series else pd.DataFrame()
        estimate_impact(m1_findings, metrics_df, language=getattr(config, "language", "en"))

        # Save raw profitability findings for downstream steps (Step 7-8 prompts)
        company_key   = config.company_name.split()[0].lower()
        findings_path = DATA_DIR / "analysis" / f"findings_{company_key}.json"
        with open(findings_path, "w", encoding="utf-8") as jf:
            json.dump(all_findings, jf, ensure_ascii=False, default=str, indent=2)

        # ── Shape findings with module-prefixed IDs ──────────────────────────
        shaped_m1     = _shape_findings(m1_findings,        id_prefix="F")
        shaped_m2     = _shape_findings(m2_findings,        id_prefix="BS")
        shaped_m3     = _shape_findings(m3_findings,        id_prefix="CF")
        shaped_stacked = _shape_findings(stacked_diagnoses, id_prefix="DX")
        all_shaped = shaped_m1 + shaped_m2 + shaped_m3 + shaped_stacked

        # ── Enrichment: composite signals from Module 1 findings ─────────────
        enriched = enrichment.enrich(m1_findings, df)

        # ── Categorize ALL shaped findings ────────────────────────────────────
        finding_categories = categorize_findings(all_shaped, enriched["composite_signals"])

        # ── Risk score: M1 base + BS/CF/stacked boost ────────────────────────
        m1_risk_score = enriched.get("risk_score", 0.0)
        boost         = _compute_risk_boost(m2_findings, m3_findings, stacked_diagnoses)
        final_score   = min(100.0, round(m1_risk_score + boost, 1))

        risk_level = "LOW"
        if final_score >= 75:
            risk_level = "CRITICAL"
        elif final_score >= 50:
            risk_level = "HIGH"
        elif final_score >= 25:
            risk_level = "MEDIUM"

        result = {
            "status": "complete",
            "data": {
                "algorithms_run": [
                    "margin_trends", "cost_composition_drift",
                    "revenue_cost_decoupling", "peer_comparison",
                    "statistical_anomaly", "yoy_quarter_comparison",
                    "bs_leverage_escalation", "bs_working_capital",
                    "bs_liquidity_stress", "bs_asset_efficiency",
                    "bs_ccc_expansion", "bs_debt_maturity", "bs_equity_erosion",
                    "cf_earnings_quality", "cf_capex_starvation",
                    "cf_fcf_erosion", "cf_debt_dependency",
                    "cf_dividend_sustainability", "cf_wc_drain",
                    "signal_stacking",
                ],
                "active_modules":    active_modules,
                "runnable_modules":  runnable_modules,
                "raw_findings":      len(all_shaped),
                "profitability_findings_count": len(shaped_m1),
                "bs_findings_count":            len(shaped_m2),
                "cf_findings_count":            len(shaped_m3),
                "stacked_diagnoses_count":      len(shaped_stacked),
                "findings":           all_shaped,
                "finding_categories": finding_categories,
                "composite_signals":  enriched["composite_signals"],
                "risk_score":         final_score,
                "risk_level":         risk_level,
                "risk_scores":        enriched["risk_scores"],
                "findings_enriched":  enriched["findings_enriched"],
                "source":             "live",
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


# =============================================================================
# Adapters: BalanceSheet/CashFlow objects → series dicts (mirrors step4)
# =============================================================================

def _bs_objects_to_series(balance_sheets: list, company_name: str) -> list:
    """Convert BalanceSheet objects to the same dict format as step4 bs_series."""
    from steps.step4_ebitda_drivers import _build_is_lookup, _build_bs_series
    try:
        pivot = metrics_calculator.compute_metrics(
            company_name=company_name, data_dir=DATA_DIR, years=YEARS
        )
        is_lookup = _build_is_lookup(pivot, company_name)
    except Exception:
        is_lookup = {}
    try:
        return _build_bs_series(balance_sheets, is_lookup)
    except Exception:
        return []


def _cf_objects_to_series(cash_flows: list, company_name: str) -> list:
    """Convert CashFlow objects to the same dict format as step4 cf_series."""
    from steps.step4_ebitda_drivers import _build_is_lookup, _build_cf_series
    try:
        pivot = metrics_calculator.compute_metrics(
            company_name=company_name, data_dir=DATA_DIR, years=YEARS
        )
        is_lookup = _build_is_lookup(pivot, company_name)
    except Exception:
        is_lookup = {}
    try:
        return _build_cf_series(cash_flows, is_lookup)
    except Exception:
        return []
