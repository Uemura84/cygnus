"""Capture regression baselines for Sprint 1 common model refactor.

Run this script BEFORE making any code changes:
    cd cvm-demo-app/backend
    python tests/capture_baselines.py

Outputs:
    tests/regression/braskem_baseline.json
    tests/regression/vale_baseline.json
    tests/regression/votorantim_baseline.json
"""

import json
import sys
from pathlib import Path
from datetime import date

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AppConfig, DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache
import steps.step4_ebitda_drivers as step4_mod
import steps.step5_quality_scan as step5_mod
import steps.step6_core_analysis as step6_mod

COMPANIES = [
    "BRASKEM S.A.",
    "VALE S.A.",
    "VOTORANTIM CIMENTOS S.A.",
]

FILENAMES = {
    "BRASKEM S.A.":           "braskem_baseline.json",
    "VALE S.A.":              "vale_baseline.json",
    "VOTORANTIM CIMENTOS S.A.": "votorantim_baseline.json",
}

OUTPUT_DIR = Path(__file__).parent / "regression"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_company(company_name: str) -> dict:
    config = AppConfig(company_name=company_name, cache_mode=False)
    pipeline_state: dict = {}

    print(f"  Running step 4...")
    result4 = step4_mod.run(config, pipeline_state)
    if result4.get("status") != "complete":
        raise RuntimeError(f"Step 4 failed for {company_name}: {result4.get('error')}")
    pipeline_state["step4"] = result4.get("data", {})

    print(f"  Running step 5...")
    result5 = step5_mod.run(config, pipeline_state)
    if result5.get("status") != "complete":
        raise RuntimeError(f"Step 5 failed for {company_name}: {result5.get('error')}")
    pipeline_state["step5"] = result5.get("data", {})

    print(f"  Running step 6...")
    result6 = step6_mod.run(config, pipeline_state)
    if result6.get("status") != "complete":
        raise RuntimeError(f"Step 6 failed for {company_name}: {result6.get('error')}")

    return {
        "company_name":    company_name,
        "snapshot_date":   str(date.today()),
        "snapshot_branch": "master (pre-sprint1-refactor)",
        "step4_data":      result4.get("data", {}),
        "step5_data":      result5.get("data", {}),
        "step6_data":      result6.get("data", {}),
    }


def main():
    for company in COMPANIES:
        print(f"\n=== {company} ===")
        try:
            baseline = run_company(company)
            out_path = OUTPUT_DIR / FILENAMES[company]
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(baseline, f, indent=2, ensure_ascii=False, default=str)
            step6_data = baseline["step6_data"]
            print(f"  Saved → {out_path}")
            print(f"  Step 6: {step6_data.get('raw_findings', '?')} findings, "
                  f"risk_score={step6_data.get('risk_score', '?')}")
        except Exception as e:
            print(f"  ERROR: {e}")
            raise


if __name__ == "__main__":
    main()
