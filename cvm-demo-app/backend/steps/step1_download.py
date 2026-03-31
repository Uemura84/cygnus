"""Step 1: Download CVM Data — live implementation with cache layer."""

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import cvm_downloader


def run(config, pipeline_state: dict) -> dict:
    """Download DFP + ITR ZIPs from CVM; count rows for the configured company.

    Cache behaviour:
      - cache_mode ON  → load from cache/step1.json (fallback to live if missing)
      - cache_mode OFF → run live, then save result to cache/step1.json
      - live failure   → fall back to cache and set metadata.source = "cache"
    """
    STEP = 1

    # --- Cache read path ---
    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached
        # Cache not populated yet — fall through to live

    # --- Live path ---
    try:
        data = cvm_downloader.download(
            company_name=config.company_name,
            years=YEARS,
            data_dir=DATA_DIR,
        )
        result = {
            "status": "complete",
            "data": data,
            "metadata": {"cache_used": False, "source": "live"},
        }
        save_cache(STEP, result, CACHE_DIR)
        return result

    except Exception as exc:
        # Live failed — try cache as fallback
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            cached["metadata"]["source"] = "cache"
            cached["metadata"]["reason"] = str(exc)
            return cached

        # No cache available — return error
        return {
            "status": "error",
            "data": {},
            "metadata": {"cache_used": False, "source": "live"},
            "error": str(exc),
        }
