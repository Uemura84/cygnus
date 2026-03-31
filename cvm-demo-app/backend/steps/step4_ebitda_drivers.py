"""Step 4: EBITDA Drivers Construction — live implementation with cache layer."""

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import metrics_calculator


def _build_time_series(pivot: pd.DataFrame, company_name: str) -> list:
    """Extract annual (DFP) time series records for the target company."""
    company_key = company_name.split()[0].upper()

    # Filter to target company, DFP rows only, sorted by date
    comp = pivot[
        pivot["DENOM_CIA"].str.upper().str.contains(company_key, na=False) &
        (pivot["_doc_type"] == "DFP")
    ].sort_values("DT_REFER").copy()

    if comp.empty:
        # Fall back to all doc types if no DFP rows
        comp = pivot[
            pivot["DENOM_CIA"].str.upper().str.contains(company_key, na=False)
        ].sort_values("DT_REFER").copy()

    metric_cols = [
        "Gross_Margin_pct",
        "EBIT_Margin_pct",
        "EBITDA_Margin_pct",
        "COGS_pct_Revenue",
        "SGA_pct_Revenue",
    ]
    available = [c for c in metric_cols if c in comp.columns]

    revenue_col = "Receita de Venda de Bens e/ou Serviços"

    records = []
    prev_revenue = None
    prev_cogs    = None

    for _, row in comp.iterrows():
        record = {"period": str(row["DT_REFER"])}

        for col in available:
            val = row.get(col)
            record[col] = round(float(val), 2) if pd.notna(val) else None

        # YoY revenue and COGS growth
        cogs_col = "Custo dos Bens e/ou Serviços Vendidos"
        rev_val  = row.get(revenue_col)
        cogs_val = row.get(cogs_col)

        if prev_revenue is not None and pd.notna(rev_val) and prev_revenue != 0:
            record["Revenue_YoY_pct"] = round((float(rev_val) - prev_revenue) / abs(prev_revenue) * 100, 1)
        else:
            record["Revenue_YoY_pct"] = None

        if prev_cogs is not None and pd.notna(cogs_val) and prev_cogs != 0:
            record["COGS_YoY_pct"] = round((abs(float(cogs_val)) - abs(prev_cogs)) / abs(prev_cogs) * 100, 1)
        else:
            record["COGS_YoY_pct"] = None

        if pd.notna(rev_val):
            prev_revenue = float(rev_val)
        if pd.notna(cogs_val):
            prev_cogs = float(cogs_val)

        records.append(record)

    return records


def run(config, pipeline_state: dict) -> dict:
    """Add D&A from DFC, compute EBITDA metrics, return time series.

    Requires Step 3 to have saved data/analysis/pivot_{key}.csv.
    """
    STEP = 4

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached

    try:
        pivot = metrics_calculator.compute_metrics(
            company_name=config.company_name,
            data_dir=DATA_DIR,
            years=YEARS,
        )

        time_series  = _build_time_series(pivot, config.company_name)
        metrics_computed = [
            "Gross_Margin_pct",
            "EBIT_Margin_pct",
            "COGS_pct_Revenue",
            "Revenue_YoY_pct",
            "COGS_YoY_pct",
        ]
        if "EBITDA_Margin_pct" in pivot.columns:
            metrics_computed.append("EBITDA_Margin_pct")

        result = {
            "status": "complete",
            "data": {
                "metrics_computed": metrics_computed,
                "periods":          len(time_series),
                "time_series":      time_series,
                "source":           "live",
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
