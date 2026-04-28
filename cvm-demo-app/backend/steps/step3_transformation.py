"""Step 3: DRE Transformation — live implementation with cache layer."""

import pandas as pd

from config import DATA_DIR, CACHE_DIR, YEARS
from cache_utils import load_cache, save_cache
from pipeline import metrics_calculator
from pipeline.parecer_classifier import parse_parecer
from pipeline.dva_parser import parse_dva
from pipeline.dmpl_parser import parse_dmpl
from pipeline.dra_parser import parse_dra
from pipeline.fre_parser import parse_fre_auditor, parse_fre_foreign_bonds

# Ordered DMPL fields for the annual values table
_DMPL_TABLE_FIELDS = [
    "opening_equity",
    "net_income",
    "total_dividends",
    "oci_total",
    "capital_increase",
    "treasury_shares_net",
    "closing_equity",
]

# Ordered DRA fields for the annual values table
_DRA_TABLE_FIELDS = [
    "net_income",
    "oci_total",
    "oci_fx",
    "oci_hedge",
    "oci_actuarial",
    "total_comprehensive_income",
]

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

# Ordered DVA fields for the annual values table
_DVA_TABLE_FIELDS = [
    "revenues",
    "third_party_inputs",
    "gross_value_added",
    "retentions",
    "net_value_added",
    "value_received",
    "total_to_distribute",
    "employees",
    "government",
    "lenders",
    "shareholders",
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


_FRE_AUDITOR_FIELDS = [
    {"field": "Nome_Companhia",          "status": "mapped",   "description": "Company name (filter key)"},
    {"field": "Versao",                  "status": "mapped",   "description": "Filing version (dedup — latest wins)"},
    {"field": "Data_Referencia",         "status": "mapped",   "description": "Reference date (period key)"},
    {"field": "Auditor",                 "status": "mapped",   "description": "Audit firm name → firm_name"},
    {"field": "CNPJ_Auditor",            "status": "mapped",   "description": "Audit firm CNPJ → firm_cnpj"},
    {"field": "Data_Inicio_Contratacao", "status": "mapped",   "description": "Contract start date → tenure_years"},
    {"field": "Remuneracao_Auditor",     "status": "mapped",   "description": "Free-text fee narrative → audit_fees + non_audit_fees via regex"},
]

_FRE_BONDS_FIELDS = [
    {"field": "Nome_Companhia",                 "status": "mapped",   "description": "Company name (filter key)"},
    {"field": "Versao",                         "status": "mapped",   "description": "Filing version (dedup — latest wins)"},
    {"field": "Data_Referencia",                "status": "mapped",   "description": "Reference date (period key)"},
    {"field": "Valor_Mobiliario",               "status": "mapped",   "description": "Instrument type → instrument_type"},
    {"field": "Identificacao_Valor_Mobiliario", "status": "mapped",   "description": "ISIN or description → identification"},
    {"field": "Data_Vencimento",                "status": "mapped",   "description": "Maturity date → maturity_date"},
    {"field": "Saldo_Devedor",                  "status": "mapped",   "description": "Outstanding balance (full BRL ÷ 1,000 → BRL thousands)"},
    {"field": "Moeda",                          "status": "not_used", "description": "Not present; all titulo_exterior assumed USD"},
]


def _build_fre_auditor_stats(profiles: list) -> dict | None:
    if not profiles:
        return None
    years = sorted(set(str(p["period"])[:4] for p in profiles))
    return {
        "records_loaded": len(profiles),
        "annual_periods": len(years),
        "periods":        years,
        "filing_type":    "FRE",
        "fields":         _FRE_AUDITOR_FIELDS,
    }


def _build_fre_auditor_table(profiles: list) -> dict | None:
    if not profiles:
        return None
    annual = sorted(profiles, key=lambda p: p["period"])
    years = [str(p["period"])[:4] for p in annual]
    return {
        "years": years,
        "rows": {
            "firm_name":       [p.get("firm_name") for p in annual],
            "tenure_years":    [p.get("tenure_years") for p in annual],
            "audit_fees":      [round(p["audit_fees"])       if p.get("audit_fees")      else None for p in annual],
            "non_audit_fees":  [round(p["non_audit_fees"])   if p.get("non_audit_fees")  else None for p in annual],
            "non_audit_ratio": [round(p["non_audit_ratio"], 3) if p.get("non_audit_ratio") is not None else None for p in annual],
        },
    }


def _build_fre_bonds_stats(bonds: list) -> dict | None:
    if not bonds:
        return None
    years = sorted(set(str(b["period"])[:4] for b in bonds))
    return {
        "records_loaded": len(bonds),
        "annual_periods": len(years),
        "periods":        years,
        "filing_type":    "FRE",
        "fields":         _FRE_BONDS_FIELDS,
    }


def _build_fre_bonds_table(bonds: list) -> list | None:
    if not bonds:
        return None
    return [
        {
            "period":             b.get("period"),
            "instrument_type":    b.get("instrument_type"),
            "identification":     b.get("identification"),
            "maturity_date":      b.get("maturity_date"),
            "outstanding_amount": round(b["outstanding_amount"]) if b.get("outstanding_amount") else None,
            "currency":           b.get("currency"),
        }
        for b in bonds
    ]


def _build_dva_table(dva_records: list) -> dict | None:
    """Extract annual (DFP) DVA values for the Step 3 summary table."""
    annual = [r for r in dva_records if r.get("period_type") == "annual"]
    if not annual:
        return None
    years = [str(r["period"])[:4] for r in annual]
    rows = {}
    for field in _DVA_TABLE_FIELDS:
        rows[field] = [
            round(float(r[field])) if r.get(field) is not None else None
            for r in annual
        ]
    return {"years": years, "rows": rows}


def _build_dmpl_table(dmpl_records: list) -> dict | None:
    """Extract annual (DFP) DMPL values for the Step 3 summary table."""
    annual = [r for r in dmpl_records if r.get("period_type") == "annual"]
    if not annual:
        return None
    years = [str(r["period"])[:4] for r in annual]
    rows = {}
    for field in _DMPL_TABLE_FIELDS:
        rows[field] = [
            round(float(r[field])) if r.get(field) is not None else None
            for r in annual
        ]
    return {"years": years, "rows": rows}


def _build_dra_table(dra_records: list) -> dict | None:
    """Extract annual (DFP) DRA values for the Step 3 summary table."""
    annual = [r for r in dra_records if r.get("period_type") == "annual"]
    if not annual:
        return None
    years = [str(r["period"])[:4] for r in annual]
    rows = {}
    for field in _DRA_TABLE_FIELDS:
        rows[field] = [
            round(float(r[field])) if r.get(field) is not None else None
            for r in annual
        ]
    return {"years": years, "rows": rows}


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

        # DVA parsing stats + annual values table
        dva_stats = None
        dva_table = None
        try:
            _dva_records, _dva_s = parse_dva(config.company_name, DATA_DIR, YEARS)
            if _dva_s.get("periods_available", 0) > 0:
                dva_stats = _dva_s
                dva_table = _build_dva_table(_dva_records)
        except Exception:
            pass

        # DMPL parsing stats + annual values table
        dmpl_stats = None
        dmpl_table = None
        try:
            _dmpl_records, _dmpl_s = parse_dmpl(config.company_name, DATA_DIR, YEARS)
            if _dmpl_s.get("periods_available", 0) > 0:
                dmpl_stats = _dmpl_s
                dmpl_table = _build_dmpl_table(_dmpl_records)
        except Exception:
            pass

        # DRA parsing stats + annual values table
        dra_stats = None
        dra_table = None
        try:
            _dra_records, _dra_s = parse_dra(config.company_name, DATA_DIR, YEARS)
            if _dra_s.get("periods_available", 0) > 0:
                dra_stats = _dra_s
                dra_table = _build_dra_table(_dra_records)
        except Exception:
            pass

        # FRE Auditor parsing stats + annual values table
        fre_auditor_stats = None
        fre_auditor_table = None
        try:
            _fre_aud = parse_fre_auditor(DATA_DIR, config.company_name, YEARS)
            if _fre_aud:
                fre_auditor_stats = _build_fre_auditor_stats(_fre_aud)
                fre_auditor_table = _build_fre_auditor_table(_fre_aud)
        except Exception:
            pass

        # FRE Foreign bonds parsing stats + flat obligation table
        fre_bonds_stats = None
        fre_bonds_table = None
        try:
            _fre_bonds = parse_fre_foreign_bonds(DATA_DIR, config.company_name, YEARS)
            if _fre_bonds:
                fre_bonds_stats = _build_fre_bonds_stats(_fre_bonds)
                fre_bonds_table = _build_fre_bonds_table(_fre_bonds)
        except Exception:
            pass

        # Parecer (auditor report) parsing stats — just counts, no LLM yet
        parecer_stats = None
        try:
            parecer_reports = parse_parecer(DATA_DIR, config.company_name, YEARS)
            if parecer_reports:
                periods = sorted(set(r["period"][:4] for r in parecer_reports))
                parecer_stats = {
                    "reports_found":  len(parecer_reports),
                    "annual_periods": len(parecer_reports),
                    "periods":        periods,
                    "filing_type":    "DFP",
                    "fields": [
                        {"field": "TXT_PARECER_DECL", "status": "mapped",    "description": "Auditor report text (items concatenated by NUM_ITEM_PARECER_DECL)"},
                        {"field": "TP_PARECER_DECL",  "status": "mapped",    "description": "Report type filter (keep 'Relatório do Auditor Independente')"},
                        {"field": "TP_RELAT_AUD",     "status": "mapped",    "description": "Structured opinion type (e.g. 'Sem Ressalva')"},
                        {"field": "NUM_ITEM_PARECER_DECL", "status": "mapped", "description": "Item order within report (sort key for concatenation)"},
                        {"field": "DT_REFER",         "status": "mapped",    "description": "Reference date (period key)"},
                        {"field": "DENOM_CIA",        "status": "mapped",    "description": "Company name (filter key)"},
                        {"field": "VERSAO",           "status": "mapped",    "description": "Filing version (dedup key — latest version wins)"},
                        {"field": "CNPJ_CIA",         "status": "not_used",  "description": "Not used (DENOM_CIA preferred for matching)"},
                    ],
                }
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
                "dva_stats":           dva_stats,
                "dva_table":           dva_table,
                "dmpl_stats":          dmpl_stats,
                "dmpl_table":          dmpl_table,
                "dra_stats":           dra_stats,
                "dra_table":           dra_table,
                "parecer_stats":       parecer_stats,
                "fre_auditor_stats":  fre_auditor_stats,
                "fre_auditor_table":  fre_auditor_table,
                "fre_bonds_stats":    fre_bonds_stats,
                "fre_bonds_table":    fre_bonds_table,
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
