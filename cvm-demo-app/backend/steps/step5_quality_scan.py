"""Step 5: Data Quality Scan — live implementation with cache layer."""

import pandas as pd

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline import pattern_detector


def _load_metrics_df(company_name: str, data_dir) -> pd.DataFrame:
    """Load the metrics CSV written by Step 4."""
    company_key  = company_name.split()[0].lower()
    metrics_path = data_dir / "analysis" / f"metrics_{company_key}.csv"
    if metrics_path.exists():
        return pd.read_csv(metrics_path, low_memory=False)
    # Fall back to pivot CSV if metrics not yet available
    pivot_path = data_dir / "analysis" / f"pivot_{company_key}.csv"
    if pivot_path.exists():
        return pd.read_csv(pivot_path, low_memory=False)
    raise FileNotFoundError(
        f"No metrics or pivot CSV found for {company_name}. Run Steps 3 and 4 first."
    )


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
        df = _load_metrics_df(config.company_name, DATA_DIR)

        quality = pattern_detector.quality_scan(df)

        # Save enriched df for downstream steps
        enriched_df  = quality.pop("_enriched_df")  # extract before caching
        company_key  = config.company_name.split()[0].lower()
        enriched_path = DATA_DIR / "analysis" / f"enriched_{company_key}.csv"
        enriched_df.to_csv(enriched_path, index=False, encoding="utf-8-sig")

        result = {
            "status": "complete",
            "data": {
                **quality,
                "source": "live",
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
