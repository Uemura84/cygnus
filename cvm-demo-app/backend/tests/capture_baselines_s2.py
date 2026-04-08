"""Capture Sprint 2 regression baselines before writing any Sprint 3 code.

Run:
    cd cvm-demo-app/backend
    .venv/bin/python tests/capture_baselines_s2.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AppConfig
import steps.step4_ebitda_drivers as step4_mod
import steps.step5_quality_scan as step5_mod

REGRESSION_DIR = Path(__file__).parent / "regression"
REGRESSION_DIR.mkdir(exist_ok=True)

COMPANIES = {
    "BRASKEM S.A.":            REGRESSION_DIR / "braskem_baseline_s2.json",
    "VALE S.A.":               REGRESSION_DIR / "vale_baseline_s2.json",
    "VOTORANTIM CIMENTOS S.A.": REGRESSION_DIR / "votorantim_baseline_s2.json",
}


def capture(company_name: str) -> dict:
    config = AppConfig(company_name=company_name, cache_mode=False)
    state: dict = {}

    r4 = step4_mod.run(config, state)
    assert r4["status"] == "complete", f"Step 4 failed: {r4.get('error')}"
    state["step4"] = r4["data"]

    r5 = step5_mod.run(config, state)
    assert r5["status"] == "complete", f"Step 5 failed: {r5.get('error')}"

    return {
        "company_name":      company_name,
        "snapshot_sprint":   "sprint2",
        "step4_balance_sheet_series": r4["data"].get("balance_sheet_series", []),
        "step4_cash_flow_series":     r4["data"].get("cash_flow_series", []),
        "step5_cross_statement_warnings": r5["data"].get("cross_statement_warnings", []),
    }


def main():
    print("Capturing Sprint 2 regression baselines...")
    for company, path in COMPANIES.items():
        print(f"  {company}...", end=" ", flush=True)
        baseline = capture(company)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2, default=str)
        bs_n  = len(baseline["step4_balance_sheet_series"])
        cf_n  = len(baseline["step4_cash_flow_series"])
        cs_n  = len(baseline["step5_cross_statement_warnings"])
        print(f"OK — BS periods={bs_n}, CF periods={cf_n}, cross-warnings={cs_n}")
    print("Done. Baselines written to tests/regression/")


if __name__ == "__main__":
    main()
