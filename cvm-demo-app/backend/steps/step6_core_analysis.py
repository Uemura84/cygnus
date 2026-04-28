"""Step 6: Pattern Detection & Risk Assessment — merged detection + enrichment."""

import json
from pathlib import Path as _Path

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import pattern_detector, enrichment, bs_detector, cf_detector, signal_stacker
from pipeline.materiality import estimate_impact, estimate_bs_cf_impact
from pipeline import metrics_calculator
from pipeline.parecer_classifier import parse_parecer, classify_parecer
from pipeline.auditor_detector import detect_auditor_patterns, detect_auditor_fre_patterns
from pipeline.bs_detector import detect_bs_fre_patterns
from pipeline.dva_detector import detect_dva_patterns
from pipeline.equity_detector import detect_equity_patterns
from pipeline.fre_parser import parse_fre_auditor, parse_fre_foreign_bonds
from models import determine_active_modules, CompanyFinancials, Company, Period, IncomeStatement


IMPLEMENTED_MODULES = ["profitability", "balance_sheet_health", "cash_flow_quality", "auditor",
                       "value_distribution", "equity"]


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


def _shape_findings(findings: list, id_prefix: str = "F", language: str = "en") -> list:
    shaped = []
    use_pt = (language or "en").startswith("pt")
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
        # Select description in the requested language
        if use_pt:
            desc = f.get("description_pt") or f.get("description") or f.get("insight", "")
        else:
            desc = f.get("description") or f.get("insight", "")
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
            "description":      desc,
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
        "balance_sheet": [], "cash_flow": [], "diagnoses": [], "auditor": [],
        "value_distribution": [], "equity": [],
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
        elif module == "auditor":
            categories["auditor"].append(fid)
        elif module == "value_distribution":
            categories["value_distribution"].append(fid)
        elif module == "equity":
            categories["equity"].append(fid)
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


def _finding_period(f: dict) -> str | None:
    """Best-effort extraction of the most recent period string from a finding."""
    if f.get("period"):
        return str(f["period"])
    pa = f.get("periods_affected")
    if isinstance(pa, list) and pa:
        return str(sorted(pa)[-1])
    return None


def recency_weight(finding: dict, sorted_periods: list) -> float:
    """Return a recency multiplier (0.5–1.5) based on how recent the finding's period is.

    sorted_periods is an ascending-sorted list of all unique period strings.
    Findings with no period or no matching period → 1.0 (neutral).
    """
    p = _finding_period(finding)
    if not p or not sorted_periods:
        return 1.0
    # rank from most recent (0) to oldest
    try:
        rank = len(sorted_periods) - 1 - sorted_periods.index(p)
    except ValueError:
        # Period not in list — try prefix match (e.g. "2024" in "2024-12-31")
        for i, sp in enumerate(reversed(sorted_periods)):
            if p[:4] == sp[:4]:
                rank = i
                break
        else:
            return 1.0
    weights = [1.5, 1.2, 1.0, 0.8]
    if rank < len(weights):
        return weights[rank]
    return 0.5


def _compute_risk_boost(
    bs_findings: list, cf_findings: list, stacked: list, auditor_findings: list | None = None
) -> float:
    """Compute additional risk points from BS, CF, stacked, and auditor findings.

    Individual module findings (BS, CF, auditor, DVA, equity) receive temporal
    weighting based on recency. Stacked diagnoses always get 1.0× (neutral).
    """
    sev_pts = {"CRITICAL": 8.0, "HIGH": 5.0, "MEDIUM": 2.0, "LOW": 0.5}

    # Collect all periods from individual (non-stacked) findings to rank recency
    individual = bs_findings + cf_findings + (auditor_findings or [])
    all_periods = sorted({p for f in individual for p in ([_finding_period(f)] if _finding_period(f) else [])})

    boost = 0.0
    for f in individual:
        pts = sev_pts.get(f.get("severity", ""), 0)
        boost += pts * recency_weight(f, all_periods)

    for f in stacked:
        base = sev_pts.get(f.get("severity", ""), 0)
        multiplier = 1.5 if f.get("severity") == "CRITICAL" else 1.3
        boost += base * multiplier  # stacked findings: no temporal weighting

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

        # Load step4 time series early (needed for FRE AUD-5 fee trend context)
        _step4_data_early = pipeline_state.get("step4") or {}
        step4_time_series: list = _step4_data_early.get("time_series", [])
        if not step4_time_series:
            from cache_utils import load_cache as _lc_early
            _c4_early = _lc_early(4, CACHE_DIR, company_name=config.company_name)
            step4_time_series = ((_c4_early or {}).get("data") or {}).get("time_series", [])

        # Determine active + runnable modules
        company_financials = _build_company_financials(config.company_name, balance_sheets, cash_flows)
        active_modules  = determine_active_modules(company_financials)
        # Auditor module always active — gracefully handles missing Parecer data
        if "auditor" not in active_modules:
            active_modules = active_modules + ["auditor"]
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

        # ── Module 4: Auditor (Parecer classification) ───────────────────────
        import os as _os
        m4_findings = []
        auditor_classifications = []
        if "auditor" in runnable_modules:
            try:
                # Prefer Step 5's pre-computed classifications to ensure consistency.
                # Step 5 already called classify_parecer and cached the results;
                # re-calling independently can yield different LLM outputs when
                # the cache is cold or stale.
                step5_data = pipeline_state.get("step5", {})
                step5_opinions = (
                    step5_data.get("auditor_assessment", {}).get("opinions", [])
                )
                if step5_opinions:
                    auditor_classifications = step5_opinions
                else:
                    # Step 5 hasn't run yet — fall back to direct classification
                    api_key = _os.environ.get("ANTHROPIC_API_KEY", "")
                    parecer_reports = parse_parecer(DATA_DIR, config.company_name, YEARS)
                    if parecer_reports:
                        auditor_classifications = classify_parecer(
                            parecer_reports, config.company_name, CACHE_DIR, api_key, lang
                        )

                if auditor_classifications:
                    m4_findings = detect_auditor_patterns(
                        auditor_classifications, config.company_name
                    )
            except Exception as _exc:
                import logging as _log
                _log.getLogger(__name__).warning("Step6: auditor module failed: %s", _exc)

        # ── Module 5: DVA Value Distribution ────────────────────────────────
        m5_findings: list = []
        # Get dva_series from step4 pipeline_state or cache
        step4_data_dva = pipeline_state.get("step4") or {}
        if not step4_data_dva:
            from cache_utils import load_cache as _lc5
            _c4 = _lc5(4, CACHE_DIR, company_name=config.company_name)
            step4_data_dva = (_c4 or {}).get("data", {})
        dva_series_s6 = step4_data_dva.get("dva_series", [])
        if dva_series_s6:
            m5_findings = detect_dva_patterns(dva_series_s6, config.company_name)

        # ── Module 6: Equity Movements ──────────────────────────────────────
        m6_findings: list = []
        dmpl_series_s6 = step4_data_dva.get("dmpl_series", [])
        if dmpl_series_s6:
            m6_findings = detect_equity_patterns(dmpl_series_s6, config.company_name)

        # ── FRE-based enrichment (BS-8, BS-9, AUD-4, AUD-5) ─────────────────
        fre_auditor_profiles = []
        fre_foreign_bonds = []
        m_fre_bs_findings: list = []
        m_fre_aud_findings: list = []
        try:
            fre_auditor_profiles = parse_fre_auditor(DATA_DIR, config.company_name, YEARS)
            fre_foreign_bonds    = parse_fre_foreign_bonds(DATA_DIR, config.company_name, YEARS)
        except Exception as _fre_exc:
            import logging as _log
            _log.getLogger(__name__).warning("Step6: FRE parse failed: %s", _fre_exc)

        if fre_foreign_bonds:
            # Derive BS total debt for BS-9 fx_pct severity computation
            _bs_total_debt: float | None = None
            try:
                _bs_annual = [r for r in bs_series if r.get("granularity") == "annual"]
                if _bs_annual:
                    _latest_bs = sorted(_bs_annual, key=lambda r: r.get("period", ""))[-1]
                    _std = abs(_latest_bs.get("short_term_debt") or 0.0)
                    _ltd = abs(_latest_bs.get("long_term_debt")  or 0.0)
                    if _std or _ltd:
                        _bs_total_debt = _std + _ltd
            except Exception:
                pass
            m_fre_bs_findings = detect_bs_fre_patterns(
                fre_foreign_bonds, config.company_name, bs_total_debt=_bs_total_debt
            )
        if fre_auditor_profiles:
            m_fre_aud_findings = detect_auditor_fre_patterns(
                fre_auditor_profiles, config.company_name, step4_time_series or []
            )

        # ── Signal stacking ─────────────────────────────────────────────────
        all_module_findings = (
            m1_findings + m2_findings + m3_findings + m4_findings + m5_findings + m6_findings
            + m_fre_bs_findings + m_fre_aud_findings
        )
        stacked_diagnoses = signal_stacker.stack_signals(all_module_findings)
        for sd in stacked_diagnoses:
            sd["company"] = config.company_name

        all_findings = all_module_findings + stacked_diagnoses

        # ── Materiality (Module 1 only, uses metrics df) ────────────────────
        # step4_time_series was already loaded at the top of this try block
        metrics_df = pd.DataFrame(step4_time_series) if step4_time_series else pd.DataFrame()
        estimate_impact(m1_findings, metrics_df, language=getattr(config, "language", "en"))

        # Save raw profitability findings for downstream steps (Step 7-8 prompts)
        company_key   = config.company_name.split()[0].lower()
        findings_path = DATA_DIR / "analysis" / f"findings_{company_key}.json"
        with open(findings_path, "w", encoding="utf-8") as jf:
            json.dump(all_findings, jf, ensure_ascii=False, default=str, indent=2)

        # ── Shape findings with module-prefixed IDs ──────────────────────────
        shaped_m1      = _shape_findings(m1_findings,                       id_prefix="F",   language=lang)
        shaped_m2      = _shape_findings(m2_findings + m_fre_bs_findings,  id_prefix="BS",  language=lang)
        shaped_m3      = _shape_findings(m3_findings,                       id_prefix="CF",  language=lang)
        shaped_m4      = _shape_findings(m4_findings + m_fre_aud_findings, id_prefix="AUD", language=lang)
        shaped_m5      = _shape_findings(m5_findings,                       id_prefix="DVA", language=lang)
        shaped_m6      = _shape_findings(m6_findings,                       id_prefix="EQ",  language=lang)
        shaped_stacked = _shape_findings(stacked_diagnoses,                 id_prefix="DX",  language=lang)
        all_shaped = (shaped_m1 + shaped_m2 + shaped_m3 + shaped_m4 + shaped_m5 + shaped_m6
                      + shaped_stacked)

        # ── Enrichment: composite signals from Module 1 findings ─────────────
        enriched = enrichment.enrich(m1_findings, df)

        # ── Categorize ALL shaped findings ────────────────────────────────────
        finding_categories = categorize_findings(all_shaped, enriched["composite_signals"])

        # ── Distress scoring (v1.5 — replaces legacy signal-intensity score) ─
        from pipeline.distress.step6_adapter import extract_distress_inputs
        from pipeline.distress.distress_scorer import compute_distress_score
        from pipeline.enrichment import SECTOR_MAP

        company_key = config.company_name.split()[0].upper()
        sector_name = SECTOR_MAP.get(company_key, "Other")

        if sector_name in ("Unknown", "Other"):
            try:
                import yaml as _yaml
                _sectors_path = _Path(__file__).resolve().parent.parent / "knowledge" / "company_sectors.yaml"
                if _sectors_path.exists():
                    with open(_sectors_path) as _f:
                        _sector_map = _yaml.safe_load(_f) or {}
                    sector_name = _sector_map.get(config.company_name, "Other")
            except Exception:
                pass

        step4_data = pipeline_state.get("step4") or {}
        distress_inputs = extract_distress_inputs(
            step4_data, {"findings": all_shaped, "auditor_classifications": auditor_classifications},
            config.company_name, sector_name,
        )
        distress_result = compute_distress_score(**distress_inputs)
        final_score = distress_result["distress_score"]
        risk_level  = distress_result["band"]

        result = {
            "status": "complete",
            "data": {
                "algorithms_run": [
                    "margin_trends", "cost_composition_drift",
                    "revenue_cost_decoupling",
                    "statistical_anomaly", "yoy_quarter_comparison",
                    "bs_leverage_escalation", "bs_working_capital",
                    "bs_liquidity_stress", "bs_asset_efficiency",
                    "bs_ccc_expansion", "bs_debt_maturity", "bs_equity_erosion",
                    "cf_earnings_quality", "cf_capex_starvation",
                    "cf_fcf_erosion", "cf_debt_dependency",
                    "cf_dividend_sustainability", "cf_wc_drain",
                    *(["auditor_going_concern", "auditor_opinion_qualification"] if m4_findings else []),
                    "signal_stacking",
                    "distress_scoring",
                ],
                "active_modules":    active_modules,
                "runnable_modules":  runnable_modules,
                "raw_findings":      len(all_shaped),
                "profitability_findings_count": len(shaped_m1),
                "bs_findings_count":            len(shaped_m2),
                "cf_findings_count":            len(shaped_m3),
                "auditor_findings_count":       len(shaped_m4),
                "dva_findings_count":           len(shaped_m5),
                "equity_findings_count":        len(shaped_m6),
                "fre_bs_findings_count":        len(m_fre_bs_findings),
                "fre_aud_findings_count":       len(m_fre_aud_findings),
                "stacked_diagnoses_count":      len(shaped_stacked),
                "auditor_classifications":      auditor_classifications,
                "fre_auditor_profiles":         fre_auditor_profiles,
                "fre_foreign_bonds":            fre_foreign_bonds,
                "findings":           all_shaped,
                "finding_categories": finding_categories,
                "composite_signals":  enriched["composite_signals"],
                "risk_score":         final_score,
                "risk_level":         risk_level,
                "distress":           distress_result,
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
