"""Step 6: Pattern Detection & Risk Assessment — merged detection + enrichment."""

import json

import pandas as pd

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline import pattern_detector, enrichment
from pipeline.enrichment import SECTOR_MAP


def _load_enriched_df(company_name: str, data_dir) -> pd.DataFrame:
    company_key = company_name.split()[0].lower()
    enriched_path = data_dir / "analysis" / f"enriched_{company_key}.csv"
    if enriched_path.exists():
        return pd.read_csv(enriched_path, low_memory=False)

    metrics_path = data_dir / "analysis" / f"metrics_{company_key}.csv"
    pivot_path   = data_dir / "analysis" / f"pivot_{company_key}.csv"
    for path in (metrics_path, pivot_path):
        if path.exists():
            df = pd.read_csv(path, low_memory=False)
            df = pattern_detector.validate_metric_ranges(df)
            df = pattern_detector.assign_data_confidence(df)
            return df

    raise FileNotFoundError(
        f"No enriched/metrics/pivot CSV found for {company_name}. Run Steps 3-5 first."
    )


def _shape_findings(findings: list) -> list:
    shaped = []
    base_keys = {"company", "metric", "pattern", "severity", "confidence_score",
                 "anomaly_type", "confidence_reason", "insight", "macro_context"}
    for i, f in enumerate(findings, start=1):
        record = {
            "id":           f"F{i:03d}",
            "company":      f.get("company", ""),
            "pattern":      f.get("pattern", ""),
            "severity":     f.get("severity", "MEDIUM"),
            "metric":       f.get("metric", ""),
            "confidence":   f.get("confidence_score", "MEDIUM"),
            "anomaly_type": f.get("anomaly_type", ""),
            "description":  f.get("insight", ""),
            "period":       f.get("period", ""),
            "macro_context": f.get("macro_context", ""),
            "data_points":  {k: v for k, v in f.items() if k not in base_keys},
        }
        shaped.append(record)
    return shaped


def categorize_findings(findings: list, composite_signals: list) -> dict:
    """Classify raw findings into narrative categories."""
    structural_types = {
        "STRUCTURAL_COMPETITIVENESS_ISSUE",
        "NEGATIVE_OPERATING_LEVERAGE",
        "COST_INFLATION_PRESSURE",
    }
    has_structural = any(
        cs.get("composite_signal_type") in structural_types
        for cs in composite_signals
    )  # noqa: F841 — reserved for future use

    categories: dict = {"core": [], "supporting": [], "contextual": [], "anomalies": []}

    for i, f in enumerate(findings, start=1):
        fid = f"F{i:03d}"
        pattern = f.get("pattern", "")
        anomaly_type = f.get("anomaly_type", "")

        if pattern in ("Cost composition drift", "Margin compression"):
            categories["core"].append(fid)
        elif pattern == "Revenue-cost decoupling":
            if (f.get("divergence_pp") or 0) > 0:
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


def run(config, pipeline_state: dict) -> dict:
    STEP = 6

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached

    try:
        df = _load_enriched_df(config.company_name, DATA_DIR)

        if "_doc_type" in df.columns:
            df["period_type"] = df["_doc_type"].map({"DFP": "annual", "ITR": "quarterly"})
        df_annual    = df[df["_doc_type"] == "DFP"].copy() if "_doc_type" in df.columns else df.copy()
        df_quarterly = df[df["_doc_type"] == "ITR"].copy() if "_doc_type" in df.columns else pd.DataFrame()

        if "is_standalone" in df_quarterly.columns and not df_quarterly.empty:
            df_quarterly = df_quarterly[df_quarterly["is_standalone"] == True].copy()

        findings = pattern_detector.detect_patterns(
            df=df,
            df_annual=df_annual,
            df_quarterly=df_quarterly,
            sector_map=SECTOR_MAP,
        )

        # Save raw findings for downstream steps
        company_key   = config.company_name.split()[0].lower()
        findings_path = DATA_DIR / "analysis" / f"findings_{company_key}.json"
        with open(findings_path, "w", encoding="utf-8") as jf:
            json.dump(findings, jf, ensure_ascii=False, default=str, indent=2)

        # Categorize before shaping (raw findings have all fields)
        finding_categories = categorize_findings(findings, [])

        shaped = _shape_findings(findings)

        # Run enrichment
        enriched = enrichment.enrich(findings, df)

        # Re-categorize now that we have composite signals
        finding_categories = categorize_findings(findings, enriched["composite_signals"])

        macro_timeline = [
            {
                "period": entry["period"],
                "year":   int(entry["period"].split("-")[0]),
                "half":   entry["period"].split("-")[1],
                "event":  entry["event"],
            }
            for entry in enriched["macro_timeline"]
        ]

        result = {
            "status": "complete",
            "data": {
                "algorithms_run": [
                    "margin_trends",
                    "cost_composition_drift",
                    "revenue_cost_decoupling",
                    "peer_comparison",
                    "statistical_anomaly",
                    "yoy_quarter_comparison",
                ],
                "raw_findings":          len(findings),
                "findings":              shaped,
                "finding_categories":    finding_categories,
                "composite_signals":     enriched["composite_signals"],
                "risk_score":            enriched["risk_score"],
                "risk_level":            enriched["risk_level"],
                "risk_scores":           enriched["risk_scores"],
                "macro_timeline":        macro_timeline,
                "findings_enriched":     enriched["findings_enriched"],
                "macro_annotations_added": enriched["macro_annotations_added"],
                "source":                "live",
            },
            "metadata": {"cache_used": False, "source": "live"},
        }
        save_cache(STEP, result, CACHE_DIR)
        return result

    except Exception as exc:
        cached = load_cache(STEP, CACHE_DIR)
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
