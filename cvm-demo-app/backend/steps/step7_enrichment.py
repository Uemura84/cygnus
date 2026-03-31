"""Step 7: Enrichment Layer — live implementation with cache layer."""

import json

import pandas as pd

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline import enrichment


def _load_findings(company_name: str, data_dir, pipeline_state: dict) -> list:
    """Load findings from disk or pipeline_state."""
    company_key   = company_name.split()[0].lower()
    findings_path = data_dir / "analysis" / f"findings_{company_key}.json"
    if findings_path.exists():
        with open(findings_path, encoding="utf-8") as jf:
            return json.load(jf)

    # Fallback: extract raw findings from pipeline_state step6
    step6 = pipeline_state.get("step6") or {}
    shaped = step6.get("findings", [])
    # shaped findings have 'description' not 'insight'; reconstruct minimally
    raw = []
    for f in shaped:
        raw.append({
            "company":        f.get("company", ""),
            "pattern":        f.get("pattern", ""),
            "severity":       f.get("severity", "MEDIUM"),
            "metric":         f.get("metric", ""),
            "confidence_score": f.get("confidence", "MEDIUM"),
            "insight":        f.get("description", ""),
            "period":         f.get("period", ""),
            "anomaly_type":   f.get("anomaly_type", ""),
            **f.get("data_points", {}),
        })
    return raw


def _load_enriched_df(company_name: str, data_dir) -> pd.DataFrame:
    """Load enriched DataFrame for risk scoring."""
    company_key = company_name.split()[0].lower()
    for suffix in ("enriched", "metrics", "pivot"):
        path = data_dir / "analysis" / f"{suffix}_{company_key}.csv"
        if path.exists():
            return pd.read_csv(path, low_memory=False)
    return pd.DataFrame()


def run(config, pipeline_state: dict) -> dict:
    """Build composite signals and score company risk.

    Reads findings from data/analysis/findings_{key}.json (written by Step 6)
    and enriched DataFrame from data/analysis/enriched_{key}.csv (Step 5).
    """
    STEP = 7

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached

    try:
        findings = _load_findings(config.company_name, DATA_DIR, pipeline_state)
        df       = _load_enriched_df(config.company_name, DATA_DIR)

        enriched = enrichment.enrich(findings, df)

        # Build macro timeline in a simpler shape for the frontend
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
                "findings_enriched":     enriched["findings_enriched"],
                "macro_annotations_added": enriched["macro_annotations_added"],
                "composite_signals":     enriched["composite_signals"],
                "risk_scores":           enriched["risk_scores"],
                "macro_timeline":        macro_timeline,
                "risk_score":            enriched["risk_score"],
                "risk_level":            enriched["risk_level"],
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
