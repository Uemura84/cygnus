"""Step 5: Data Quality Scan — live implementation with cache layer."""

import pandas as pd

from config import DATA_DIR, CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline import pattern_detector


def _normalize_df_columns(df: pd.DataFrame) -> None:
    """Rename legacy CVM column names to common model names (in-place).

    Handles pivot/metrics CSVs written before the common model refactor.
    """
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


def _load_metrics_df(company_name: str, data_dir) -> pd.DataFrame:
    """Load the metrics CSV written by Step 4."""
    company_key  = company_name.split()[0].lower()
    metrics_path = data_dir / "analysis" / f"metrics_{company_key}.csv"
    if metrics_path.exists():
        df = pd.read_csv(metrics_path, low_memory=False)
    else:
        # Fall back to pivot CSV if metrics not yet available
        pivot_path = data_dir / "analysis" / f"pivot_{company_key}.csv"
        if pivot_path.exists():
            df = pd.read_csv(pivot_path, low_memory=False)
        else:
            raise FileNotFoundError(
                f"No metrics or pivot CSV found for {company_name}. Run Steps 3 and 4 first."
            )
    # Normalize legacy CVM column names to common model names
    _normalize_df_columns(df)
    return df


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
