"""Step 2: Data Preparation — live implementation with cache layer."""

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import data_cleaner


def run(config, pipeline_state: dict) -> dict:
    """Read downloaded ZIPs and apply the three sequential filters.

    Requires Step 1 to have populated data_dir/raw/ first.

    Cache behaviour mirrors Step 1.
    """
    STEP = 2

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached

    try:
        data = data_cleaner.prepare(
            company_name=config.company_name,
            data_dir=DATA_DIR,
            years=YEARS,
        )

        # Propagate raw_rows from step1 if available, so the filter waterfall
        # starts from the real downloaded count rather than what we re-read here.
        step1_data = pipeline_state.get("step1") or {}
        if step1_data.get("total_rows") and data.get("raw_rows") == 0:
            data["raw_rows"] = step1_data["total_rows"]

        result = {
            "status": "complete",
            "data": data,
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
            "data": {},
            "metadata": {"cache_used": False, "source": "live"},
            "error": str(exc),
        }
