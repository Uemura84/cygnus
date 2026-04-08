"""Step 3: DRE Transformation — live implementation with cache layer."""

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import metrics_calculator

# Ordered BS fields for the annual values table (matches spec Section 1.2)
_BS_TABLE_FIELDS = [
    "current_assets", "cash_and_equivalents", "accounts_receivable", "inventories",
    "non_current_assets", "property_plant_equipment", "intangible_assets",
    "total_assets",
    "current_liabilities", "accounts_payable", "short_term_debt",
    "non_current_liabilities", "long_term_debt",
    "total_liabilities",
    "total_equity", "retained_earnings",
]

# Ordered CF fields for the annual values table (matches spec Section 2.1)
# free_cash_flow is derived by _build_cf_table; not a CashFlow model field yet.
_CF_TABLE_FIELDS = [
    "operating_cash_flow", "depreciation_amortization",
    "investing_cash_flow", "capex", "acquisitions",
    "financing_cash_flow", "debt_issuance", "debt_repayment", "dividends_paid",
]

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


def _build_bs_table(balance_sheets: list) -> dict | None:
    """Extract annual (DFP) balance sheet values for the Step 3 summary table."""
    annual = [bs for bs in balance_sheets if bs.period.filing_type == "DFP"]
    if not annual:
        return None
    years = [str(bs.period.date)[:4] for bs in annual]
    rows = {}
    for field in _BS_TABLE_FIELDS:
        values = []
        for bs in annual:
            val = getattr(bs, field, None)
            values.append(round(float(val)) if val is not None else None)
        rows[field] = values
    return {"years": years, "rows": rows}


def _build_cf_table(cash_flows: list) -> dict | None:
    """Extract annual (DFP) cash flow values for the Step 3 summary table.

    FCF is derived as operating_cash_flow + capex (capex is typically negative).
    """
    annual = [cf for cf in cash_flows if cf.period.filing_type == "DFP"]
    if not annual:
        return None
    years = [str(cf.period.date)[:4] for cf in annual]
    rows = {}
    for field in _CF_TABLE_FIELDS:
        values = []
        for cf in annual:
            val = getattr(cf, field, None)
            values.append(round(float(val)) if val is not None else None)
        rows[field] = values
    # Derive FCF = OCF + capex (capex is already signed negative for outflows)
    fcf_values = []
    for cf in annual:
        ocf   = getattr(cf, "operating_cash_flow", None)
        capex = getattr(cf, "capex", None)
        if ocf is not None and capex is not None:
            fcf_values.append(round(float(ocf) + float(capex)))
        elif ocf is not None:
            fcf_values.append(round(float(ocf)))
        else:
            fcf_values.append(None)
    rows["free_cash_flow"] = fcf_values
    return {"years": years, "rows": rows}


def _build_income_statement(pivot: pd.DataFrame, company_name: str) -> list:
    """Extract annual (DFP) income statement amounts from the pivot (2021–2025)."""
    company_key = company_name.split()[0].upper()

    # Support both common model column names and legacy CVM names
    id_col   = "company_id" if "company_id" in pivot.columns else "DENOM_CIA"
    date_col = "period_date" if "period_date" in pivot.columns else "DT_REFER"

    comp = pivot[
        pivot[id_col].str.upper().str.contains(company_key, na=False) &
        (pivot["_doc_type"] == "DFP") &
        (pd.to_datetime(pivot[date_col], errors="coerce").dt.year >= 2021)
    ].sort_values(date_col)

    rows = []
    for desc in _IS_ACCOUNTS:
        if desc not in comp.columns:
            continue
        values = {}
        for _, row in comp.iterrows():
            year = str(row[date_col])[:4]
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

        # Collect BS/CF loading stats + annual values for Step 3 display.
        # Parsing failures are non-fatal — stats will be None and the UI
        # falls back to "Not available".
        bs_stats = None
        cf_stats = None
        bs_table = None
        cf_table = None
        try:
            balance_sheets, bs_stats = metrics_calculator.parse_balance_sheets(
                company_name=config.company_name,
                data_dir=DATA_DIR,
                years=YEARS,
            )
            bs_table = _build_bs_table(balance_sheets)
        except Exception:
            pass
        try:
            cash_flows, cf_stats = metrics_calculator.parse_cash_flows(
                company_name=config.company_name,
                data_dir=DATA_DIR,
                years=YEARS,
            )
            cf_table = _build_cf_table(cash_flows)
        except Exception:
            pass

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
                "bs_stats":            bs_stats,
                "cf_stats":            cf_stats,
                "bs_table":            bs_table,
                "cf_table":            cf_table,
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
