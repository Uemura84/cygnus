"""Step 3: DRE Transformation — live implementation with cache layer."""

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import metrics_calculator

# Ordered subset of DRE accounts to include in income statement table
_IS_ACCOUNTS = [
    "Receita de Venda de Bens e/ou Serviços",
    "Custo dos Bens e/ou Serviços Vendidos",
    "Resultado Bruto",
    "Despesas com Vendas",
    "Despesas Gerais e Administrativas",
    "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)",
    "Resultado Financeiro",
    "Resultado Antes dos Tributos sobre o Lucro",
    "Imposto de Renda e Contribuição Social sobre o Lucro",
    "Lucro/Prejuízo Consolidado do Período",
]


def _build_income_statement(pivot: pd.DataFrame, company_name: str) -> list:
    """Extract annual (DFP) income statement amounts from the pivot."""
    company_key = company_name.split()[0].upper()
    comp = pivot[
        pivot["DENOM_CIA"].str.upper().str.contains(company_key, na=False) &
        (pivot["_doc_type"] == "DFP")
    ].sort_values("DT_REFER")

    rows = []
    for desc in _IS_ACCOUNTS:
        if desc not in comp.columns:
            continue
        values = {}
        for _, row in comp.iterrows():
            year = str(row["DT_REFER"])[:4]
            val = row.get(desc)
            values[year] = round(float(val), 0) if pd.notna(val) else None
        rows.append({"description": desc, "values": values})
    return rows


def run(config, pipeline_state: dict) -> dict:
    """Dedup DRE rows, pivot accounts, compute margin ratios.

    Requires Step 2 to have saved data/processed/dre_filtered_{key}.csv.
    """
    STEP = 3

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR, company_name=config.company_name)
        if cached:
            return cached

    try:
        pivot, quality_stats = metrics_calculator.build_pivot(
            company_name=config.company_name,
            data_dir=DATA_DIR,
            years=YEARS,
        )

        income_statement = _build_income_statement(pivot, config.company_name)

        result = {
            "status": "complete",
            "data": {
                "before_dedup":        quality_stats["rows_raw"],
                "after_dedup":         quality_stats["rows_after_dedup"],
                "duplicates_removed":  quality_stats["duplicates_removed"],
                "companies":           quality_stats["companies"],
                "date_range":          {
                    "start": quality_stats["date_range"][0],
                    "end":   quality_stats["date_range"][1],
                },
                "doc_types":           quality_stats["doc_types"],
                "missing_revenue_pct": quality_stats["missing_revenue_pct"],
                "itr_standalone_rows": quality_stats["itr_standalone_rows"],
                "pivot_rows":          len(pivot),
                "income_statement":    income_statement,
                "source":              "live",
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
