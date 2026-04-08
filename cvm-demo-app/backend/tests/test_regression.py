"""Regression tests for Sprint 1: Common Data Model Refactor.

Verifies that the refactored pipeline produces output identical to the
pre-refactor baselines captured in tests/regression/*.json.

Run:
    cd cvm-demo-app/backend
    .venv/bin/python3 -m pytest tests/test_regression.py -v
    # or without pytest:
    .venv/bin/python3 tests/test_regression.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AppConfig
import steps.step4_ebitda_drivers as step4_mod
import steps.step5_quality_scan as step5_mod
import steps.step6_core_analysis as step6_mod

REGRESSION_DIR = Path(__file__).parent / "regression"

COMPANIES = {
    "BRASKEM S.A.":           REGRESSION_DIR / "braskem_baseline.json",
    "VALE S.A.":              REGRESSION_DIR / "vale_baseline.json",
    "VOTORANTIM CIMENTOS S.A.": REGRESSION_DIR / "votorantim_baseline.json",
}

TOL = 1e-6      # numerical tolerance for metric values
RISK_TOL = 0.1  # tolerance for risk scores


def load_baseline(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(company_name: str) -> dict:
    config = AppConfig(company_name=company_name, cache_mode=False)
    pipeline_state: dict = {}

    result4 = step4_mod.run(config, pipeline_state)
    assert result4["status"] == "complete", f"Step 4 failed: {result4.get('error')}"
    pipeline_state["step4"] = result4["data"]

    result5 = step5_mod.run(config, pipeline_state)
    assert result5["status"] == "complete", f"Step 5 failed: {result5.get('error')}"
    pipeline_state["step5"] = result5["data"]

    result6 = step6_mod.run(config, pipeline_state)
    assert result6["status"] == "complete", f"Step 6 failed: {result6.get('error')}"

    return {
        "step4_data": result4["data"],
        "step5_data": result5["data"],
        "step6_data": result6["data"],
    }


def compare_step4(baseline: dict, current: dict, company: str) -> list[str]:
    errors = []
    b4 = baseline.get("step4_data", {})
    c4 = current["step4_data"]

    if b4.get("periods") != c4.get("periods"):
        errors.append(f"{company} Step4: periods mismatch {b4.get('periods')} vs {c4.get('periods')}")

    b_ts = b4.get("time_series", [])
    c_ts = c4.get("time_series", [])
    if len(b_ts) != len(c_ts):
        errors.append(f"{company} Step4: time_series length {len(b_ts)} vs {len(c_ts)}")
    else:
        for i, (br, cr) in enumerate(zip(b_ts, c_ts)):
            if br.get("period") != cr.get("period"):
                errors.append(f"{company} Step4 row {i}: period {br.get('period')} vs {cr.get('period')}")
            for metric in ["Gross_Margin_pct", "EBIT_Margin_pct", "COGS_pct_Revenue",
                           "Revenue_YoY_pct", "COGS_YoY_pct", "revenue_abs", "cogs_abs"]:
                bv = br.get(metric)
                cv = cr.get(metric)
                if bv is None and cv is None:
                    continue
                if bv is None or cv is None:
                    errors.append(f"{company} Step4 row {i} {metric}: None mismatch ({bv} vs {cv})")
                elif abs(bv - cv) > TOL:
                    errors.append(f"{company} Step4 row {i} {metric}: {bv} vs {cv}")
    return errors


def compare_step6(baseline: dict, current: dict, company: str) -> list[str]:
    """Verify profitability findings (F### prefix) are unchanged.

    Sprint 3 note: aggregate risk_score, risk_level, and raw_findings WILL change
    because BS/CF/stacked findings are now included. We only assert that the
    profitability findings themselves (codes, severities, patterns) are unchanged.
    """
    errors = []
    b6 = baseline.get("step6_data", {})
    c6 = current["step6_data"]

    # Only check profitability findings (F### prefix) — BS/CF/stacked are new in Sprint 3
    b_findings = {f["id"]: f for f in b6.get("findings", []) if f.get("id", "").startswith("F")}
    c_findings = {f["id"]: f for f in c6.get("findings", []) if f.get("id", "").startswith("F")}

    for fid in b_findings:
        if fid not in c_findings:
            errors.append(f"{company} Step6: profitability finding {fid} missing in current output")
            continue
        bf = b_findings[fid]
        cf = c_findings[fid]
        for field in ("pattern", "severity", "metric"):
            if bf.get(field) != cf.get(field):
                errors.append(f"{company} Step6 {fid} {field}: {bf.get(field)!r} vs {cf.get(field)!r}")

    return errors


def test_company(company_name: str, baseline_path: Path) -> bool:
    print(f"\n--- {company_name} ---")
    baseline = load_baseline(baseline_path)
    current  = run_pipeline(company_name)

    all_errors: list[str] = []
    all_errors.extend(compare_step4(baseline, current, company_name))
    all_errors.extend(compare_step6(baseline, current, company_name))

    if all_errors:
        print("  FAILED:")
        for e in all_errors:
            print(f"    ✗ {e}")
        return False
    else:
        step6 = current["step6_data"]
        print(f"  PASSED — {step6.get('raw_findings')} findings, risk_score={step6.get('risk_score')}")
        return True


def main():
    print("Sprint 1 Regression Tests")
    print("=" * 50)

    passed = 0
    failed = 0
    for company, path in COMPANIES.items():
        if not path.exists():
            print(f"\n{company}: baseline not found at {path}")
            failed += 1
            continue
        ok = test_company(company, path)
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")

    # Also validate structural requirements
    print("\n--- Structural checks ---")
    _check_structural()

    if failed > 0:
        sys.exit(1)


def _check_structural():
    """Validate structural requirements: CompanyFinancials, determine_active_modules."""
    from models import CompanyFinancials, Company, Period, IncomeStatement, determine_active_modules
    from datetime import date

    company = Company(id="test", name="TEST S.A.", source="cvm", country="BR", currency="BRL")
    period  = Period(date=date(2024, 12, 31), granularity="annual", fiscal_year=2024)
    is_stmt = IncomeStatement(company_id="test", period=period, revenue=1000.0)

    # With sufficient data
    cf_full = CompanyFinancials(company=company, income_statements=[is_stmt] * 5)
    modules = determine_active_modules(cf_full)
    assert "profitability" in modules, "determine_active_modules should return profitability"
    assert "balance_sheet_health" not in modules, "balance_sheet_health should not fire (balance_sheets=None)"
    assert "cash_flow_quality" not in modules, "cash_flow_quality should not fire (cash_flows=None)"
    print("  ✓ determine_active_modules returns ['profitability'] for current data")

    # With insufficient data
    cf_empty = CompanyFinancials(company=company, income_statements=[is_stmt] * 3)
    modules_empty = determine_active_modules(cf_empty)
    assert modules_empty == [], f"Expected [] with 3 statements, got {modules_empty}"
    print("  ✓ determine_active_modules returns [] for insufficient data")

    # balance_sheets is None
    assert cf_full.balance_sheets is None, "balance_sheets should be None"
    print("  ✓ balance_sheets is None in adapter output")

    # cash_flows is None
    assert cf_full.cash_flows is None, "cash_flows should be None"
    print("  ✓ cash_flows is None in adapter output")

    # dataframe_to_company_financials works
    from pipeline.metrics_calculator import dataframe_to_company_financials
    import pandas as pd
    dummy_df = pd.DataFrame({
        "company_id": ["TEST S.A."] * 2,
        "period_date": ["2023-12-31", "2024-12-31"],
        "_doc_type": ["DFP", "DFP"],
        "is_standalone": [True, True],
        "revenue": [1000.0, 1100.0],
        "cogs": [600.0, 650.0],
    })
    cf_from_df = dataframe_to_company_financials(dummy_df, "TEST S.A.")
    assert len(cf_from_df.income_statements) == 2, "Expected 2 income statements"
    assert cf_from_df.income_statements[0].revenue == 1000.0, "Revenue should be 1000.0"
    assert cf_from_df.income_statements[0].cost_of_goods_sold == 600.0, "COGS should be 600.0"
    print("  ✓ dataframe_to_company_financials converts correctly")


if __name__ == "__main__":
    main()
