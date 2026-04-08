"""Metrics calculator — builds DRE pivot and computes EBITDA driver metrics.

Public API
----------
build_pivot(company_name, data_dir, years) -> (pivot_df, quality_stats)
    Step 3: reads filtered DRE CSV, deduplicates, pivots, computes margin ratios.
    Saves data/analysis/pivot_{key}.csv and quality_stats_{key}.json.

compute_metrics(company_name, data_dir, years) -> pd.DataFrame
    Step 4: reads pivot CSV, adds D&A from DFC ZIPs, computes EBITDA metrics.
    Saves data/analysis/metrics_{key}.csv.

dataframe_to_company_financials(df, company_name, sector_map) -> CompanyFinancials
    Converts the enriched pivot DataFrame (output of compute_metrics / build_pivot)
    into the common CompanyFinancials data model. Called at the Step 3 boundary.
"""

import json
import sys
import zipfile
from datetime import date as date_type
from pathlib import Path

import pandas as pd

# Resolve models package regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import Company, Period, IncomeStatement, BalanceSheet, CashFlow, CompanyFinancials

# Matching the original 01_download_and_parse.py constant exactly
DRE_ACCOUNTS = {
    "3.01":    "Receita de Venda de Bens e/ou Serviços",
    "3.02":    "Custo dos Bens e/ou Serviços Vendidos",
    "3.03":    "Resultado Bruto",
    "3.04":    "Despesas/Receitas Operacionais",
    "3.04.01": "Despesas com Vendas",
    "3.04.02": "Despesas Gerais e Administrativas",
    "3.04.04": "Outras Receitas Operacionais",
    "3.04.05": "Outras Despesas Operacionais",
    "3.04.06": "Resultado de Equivalência Patrimonial",
    "3.05":    "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)",
    "3.06":    "Resultado Financeiro",
    "3.06.01": "Receitas Financeiras",
    "3.06.02": "Despesas Financeiras",
    "3.07":    "Resultado Antes dos Tributos sobre o Lucro",
    "3.08":    "Imposto de Renda e Contribuição Social sobre o Lucro",
    "3.09":    "Resultado Líquido das Operações Continuadas",
    "3.11":    "Lucro/Prejuízo Consolidado do Período",
}

ORDEM_EXERC_KEEP = "ÚLTIMO"


def _company_search_key(company_name: str) -> str:
    return company_name.split()[0].upper()


def _read_dfc_from_zip(zip_path: Path, company_key: str) -> pd.DataFrame:
    """Read DFC_MI_con CSV files from a ZIP, filtered to company_key."""
    frames = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_files = [
                name for name in zf.namelist()
                if "dfc_mi_con" in name.lower() and name.endswith(".csv")
            ]
            for csv_file in csv_files:
                try:
                    with zf.open(csv_file) as f:
                        df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
                    if "DENOM_CIA" not in df.columns:
                        continue
                    if "ORDEM_EXERC" in df.columns:
                        df = df[df["ORDEM_EXERC"] == ORDEM_EXERC_KEEP].copy()
                    mask = df["DENOM_CIA"].str.upper().str.contains(company_key, na=False)
                    df = df[mask]
                    if not df.empty:
                        frames.append(df)
                except Exception:
                    continue
    except (zipfile.BadZipFile, FileNotFoundError):
        pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_pivot(company_name: str, data_dir: Path, years: list) -> tuple:
    """Build deduped pivot table from filtered DRE CSV (Step 3).

    Reads data/processed/dre_filtered_{key}.csv written by data_cleaner.
    Applies DFP/ITR dedup logic (priority: DFP=0 > ITR standalone=1 > ITR YTD=2).
    Pivots to one row per (company, period, doc_type), computes margin ratios.
    Saves data/analysis/pivot_{key}.csv and quality_stats_{key}.json.

    Returns (pivot_df, quality_stats).
    """
    company_key  = _company_search_key(company_name)
    processed_dir = data_dir / "processed"
    analysis_dir  = data_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    dre_path = processed_dir / f"dre_filtered_{company_key.lower()}.csv"
    if not dre_path.exists():
        raise FileNotFoundError(
            f"Filtered DRE CSV not found: {dre_path}. Run Step 2 first."
        )

    dre = pd.read_csv(dre_path, low_memory=False)

    # Ensure VL_CONTA is numeric
    if "VL_CONTA" in dre.columns:
        dre["VL_CONTA"] = pd.to_numeric(dre["VL_CONTA"], errors="coerce")

    # Normalize monetary scale to thousands (UNIDADE ÷ 1000, MIL stays as-is)
    if "ESCALA_MOEDA" in dre.columns:
        dre.loc[dre["ESCALA_MOEDA"] == "UNIDADE", "VL_CONTA"] /= 1000

    rows_raw = len(dre)

    # Deduplicate: prefer DFP over ITR, and within ITR prefer standalone quarterly
    # rows over YTD cumulative rows (CVM ITR files include both formats for Q2/Q3).
    # Standalone ITR rows have DT_INI_EXERC != Jan 1 (e.g., Apr 1 for Q2, Jul 1 for Q3).
    # YTD rows start on Jan 1 of the reference year (e.g., Jan 1 for a Jun 30 period).
    if "DT_INI_EXERC" in dre.columns:
        ini_dt = pd.to_datetime(dre["DT_INI_EXERC"], errors="coerce")
        is_ytd_itr = (
            (dre["_doc_type"] == "ITR") &
            (ini_dt.dt.month == 1) & (ini_dt.dt.day == 1)
        )
        dre["_row_priority"] = 1   # ITR standalone (non-Jan-1 start)
        dre.loc[dre["_doc_type"] == "DFP", "_row_priority"] = 0
        dre.loc[is_ytd_itr, "_row_priority"] = 2  # ITR YTD (lowest priority)
    else:
        dre["_row_priority"] = dre["_doc_type"].map({"DFP": 0, "ITR": 1}).fillna(2)

    dre = (
        dre.sort_values("_row_priority")
           .drop_duplicates(subset=["DENOM_CIA", "DT_REFER", "CD_CONTA"], keep="first")
           .drop(columns="_row_priority")
    )
    rows_after_dedup = len(dre)

    # Compute standalone flag before pivoting so it survives the pivot_table aggregation.
    # After the dedup above, each ITR row is either:
    #   - standalone quarterly (DT_INI_EXERC != Jan 1 of reference year, e.g., Apr 1 for Q2)
    #   - Q1 / DFP annual (DT_INI_EXERC = Jan 1, but Jan–Mar = Q1 standalone = YTD identical)
    # Both cases are standalone; the YTD-only rows (Jan-1 start + Q2/Q3) were deprioritised
    # in the dedup and only survive if no standalone row existed.
    if "DT_INI_EXERC" in dre.columns:
        ini_dt = pd.to_datetime(dre["DT_INI_EXERC"], errors="coerce")
        ref_dt = pd.to_datetime(dre["DT_REFER"], errors="coerce")
        ytd_only = (
            (dre["_doc_type"] == "ITR") &
            (ini_dt.dt.month == 1) & (ini_dt.dt.day == 1) &
            (ini_dt.dt.year == ref_dt.dt.year) &
            (ref_dt.dt.month != 3)   # Q1 (March) is standalone even with Jan-1 start
        )
        dre["_is_standalone"] = ~ytd_only
    else:
        dre["_is_standalone"] = True

    # Filter to key EBITDA-relevant accounts and pivot
    key_accounts = list(DRE_ACCOUNTS.keys())
    dre_key = dre[dre["CD_CONTA"].isin(key_accounts)].copy()

    # Capture standalone flag per (company, period, doc_type) for merging into pivot
    standalone_map = (
        dre_key.groupby(["DENOM_CIA", "DT_REFER", "_doc_type"])["_is_standalone"]
        .first().reset_index()
        .rename(columns={"_is_standalone": "is_standalone"})
    )

    # Pivot: one row per company-period, one column per account
    pivot = dre_key.pivot_table(
        index=["DENOM_CIA", "DT_REFER", "_doc_type"],
        columns="CD_CONTA",
        values="VL_CONTA",
        aggfunc="first",
    ).reset_index()

    # Rename columns to readable names
    pivot.columns.name = None
    col_renames = {code: desc for code, desc in DRE_ACCOUNTS.items() if code in pivot.columns}
    pivot.rename(columns=col_renames, inplace=True)

    # Attach standalone flag to pivot
    pivot = pivot.merge(standalone_map, on=["DENOM_CIA", "DT_REFER", "_doc_type"], how="left")
    pivot["is_standalone"] = pivot["is_standalone"].fillna(True)

    # Compute derived metrics
    revenue_col = DRE_ACCOUNTS.get("3.01")
    cogs_col    = DRE_ACCOUNTS.get("3.02")
    gross_col   = DRE_ACCOUNTS.get("3.03")
    sga_col     = DRE_ACCOUNTS.get("3.04.02")
    selling_col = DRE_ACCOUNTS.get("3.04.01")
    ebit_col    = DRE_ACCOUNTS.get("3.05")

    if revenue_col in pivot.columns:
        revenue = pivot[revenue_col]

        if cogs_col in pivot.columns:
            pivot["COGS_pct_Revenue"] = (pivot[cogs_col].abs() / revenue * 100).round(2)

        if gross_col in pivot.columns:
            pivot["Gross_Margin_pct"] = (pivot[gross_col] / revenue * 100).round(2)

        if sga_col in pivot.columns:
            pivot["SGA_pct_Revenue"] = (pivot[sga_col].abs() / revenue * 100).round(2)

        if selling_col in pivot.columns:
            pivot["Selling_pct_Revenue"] = (pivot[selling_col].abs() / revenue * 100).round(2)

        if ebit_col in pivot.columns:
            pivot["EBIT_Margin_pct"] = (pivot[ebit_col] / revenue * 100).round(2)

    # Sort by company and date
    pivot.sort_values(["DENOM_CIA", "DT_REFER"], inplace=True)

    # Add CNPJ_CIA for reliable company identification
    if "CNPJ_CIA" in dre.columns:
        cnpj_map = dre.groupby("DENOM_CIA")["CNPJ_CIA"].first()
        pivot.insert(1, "CNPJ_CIA", pivot["DENOM_CIA"].map(cnpj_map))

    # Build quality stats
    missing_revenue_pct = 0.0
    if revenue_col in pivot.columns and len(pivot) > 0:
        missing_revenue_pct = round(pivot[revenue_col].isna().sum() / len(pivot) * 100, 1)

    itr_rows = pivot[pivot["_doc_type"] == "ITR"]
    itr_standalone_count = int(
        itr_rows["is_standalone"].sum() if "is_standalone" in itr_rows.columns else len(itr_rows)
    )

    quality_stats = {
        "rows_raw": rows_raw,
        "rows_after_dedup": rows_after_dedup,
        "duplicates_removed": rows_raw - rows_after_dedup,
        "companies": dre["DENOM_CIA"].unique().tolist(),
        "date_range": (str(dre["DT_REFER"].min()), str(dre["DT_REFER"].max())),
        "doc_types": dre["_doc_type"].value_counts().to_dict() if "_doc_type" in dre.columns else {},
        "missing_revenue_pct": missing_revenue_pct,
        "itr_standalone_rows": itr_standalone_count,
    }

    # ------------------------------------------------------------------
    # Normalize to common data model column names
    # ------------------------------------------------------------------
    # Rename identifier columns to common model names.
    # The Portuguese account columns are kept for backward-compat with Step 3's
    # income statement display; revenue/cogs are added as English aliases.
    pivot.rename(columns={"DENOM_CIA": "company_id", "DT_REFER": "period_date"}, inplace=True)
    if revenue_col in pivot.columns:
        pivot["revenue"] = pivot[revenue_col]
    if cogs_col in pivot.columns:
        pivot["cogs"] = pivot[cogs_col].abs()   # common model: positive absolute value

    # Save outputs
    pivot_path = analysis_dir / f"pivot_{company_key.lower()}.csv"
    pivot.to_csv(pivot_path, index=False, encoding="utf-8-sig")

    qs_path = analysis_dir / f"quality_stats_{company_key.lower()}.json"
    with open(qs_path, "w", encoding="utf-8") as qf:
        json.dump(quality_stats, qf, indent=2, default=str)

    return pivot, quality_stats


def compute_metrics(company_name: str, data_dir: Path, years: list) -> pd.DataFrame:
    """Add D&A from DFC ZIPs and compute EBITDA metrics (Step 4).

    Reads data/analysis/pivot_{key}.csv, enriches with D&A extracted from
    raw DFC_MI_con CSV files inside each year's DFP/ITR ZIP.
    Saves data/analysis/metrics_{key}.csv.

    Returns the enriched metrics DataFrame.
    """
    company_key  = _company_search_key(company_name)
    raw_dir      = data_dir / "raw"
    analysis_dir = data_dir / "analysis"

    pivot_path = analysis_dir / f"pivot_{company_key.lower()}.csv"
    if not pivot_path.exists():
        raise FileNotFoundError(
            f"Pivot CSV not found: {pivot_path}. Run Step 3 first."
        )

    pivot = pd.read_csv(pivot_path, low_memory=False)

    # Normalize legacy column names from old pivot CSVs (pre-common-model refactor)
    if "DENOM_CIA" in pivot.columns:
        pivot.rename(columns={"DENOM_CIA": "company_id", "DT_REFER": "period_date"}, inplace=True)
        revenue_pt = DRE_ACCOUNTS.get("3.01")
        cogs_pt    = DRE_ACCOUNTS.get("3.02")
        if revenue_pt in pivot.columns and "revenue" not in pivot.columns:
            pivot["revenue"] = pivot[revenue_pt]
        if cogs_pt in pivot.columns and "cogs" not in pivot.columns:
            pivot["cogs"] = pivot[cogs_pt].abs()

    ebit_col    = DRE_ACCOUNTS.get("3.05")
    revenue_col = "revenue"

    # D&A from DFC (indirect method cash flow)
    # Look for depreciation/amortization line items to compute true EBITDA.
    dfc_frames = []
    for year in years:
        for doc_type in ("dfp", "itr"):
            zip_path = raw_dir / f"{doc_type}_cia_aberta_{year}.zip"
            if not zip_path.exists():
                continue
            df_dfc = _read_dfc_from_zip(zip_path, company_key)
            if not df_dfc.empty:
                dfc_frames.append(df_dfc)

    if dfc_frames:
        try:
            dfc_all = pd.concat(dfc_frames, ignore_index=True)
            dfc_all["VL_CONTA"] = pd.to_numeric(dfc_all["VL_CONTA"], errors="coerce")
            da_mask = dfc_all["DS_CONTA"].str.lower().str.contains(
                "deprecia|amortiza", na=False
            )
            da = (
                dfc_all[da_mask]
                .groupby(["DENOM_CIA", "DT_REFER"])["VL_CONTA"]
                .sum().abs().reset_index()
                .rename(columns={"VL_CONTA": "DA_from_DFC",
                                 "DENOM_CIA": "company_id",
                                 "DT_REFER": "period_date"})
            )
            if not da.empty:
                pivot = pivot.merge(da, on=["company_id", "period_date"], how="left")
                if ebit_col in pivot.columns:
                    pivot["EBITDA"] = pivot[ebit_col] + pivot["DA_from_DFC"].fillna(0)
                    if revenue_col in pivot.columns:
                        pivot["EBITDA_Margin_pct"] = (
                            pivot["EBITDA"] / pivot[revenue_col] * 100
                        ).round(2)
        except Exception:
            pass

    metrics_path = analysis_dir / f"metrics_{company_key.lower()}.csv"
    pivot.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    return pivot


# =============================================================================
# Common Data Model Adapter
# =============================================================================

# Maps source column names → IncomeStatement field names.
# Includes both CVM Portuguese account names (legacy pivot CSVs) and
# common model column names (post-refactor pivot CSVs).
_CVM_TO_IS_FIELD = {
    DRE_ACCOUNTS["3.01"]: "revenue",
    DRE_ACCOUNTS["3.02"]: "cost_of_goods_sold",   # sign flip applied below
    DRE_ACCOUNTS["3.03"]: "gross_profit",
    DRE_ACCOUNTS["3.04.02"]: "sga_expenses",
    DRE_ACCOUNTS["3.04.01"]: "selling_expenses",
    DRE_ACCOUNTS["3.05"]: "ebit",
    DRE_ACCOUNTS["3.06"]: "financial_result",
    DRE_ACCOUNTS["3.07"]: "income_before_tax",
    DRE_ACCOUNTS["3.08"]: "income_tax",
    DRE_ACCOUNTS["3.11"]: "net_income",
    # Common model aliases (post-refactor pivot CSVs)
    "revenue": "revenue",
    "cogs":    "cost_of_goods_sold",  # already absolute in common model
}

# COGS is reported as negative by CVM — common model stores as positive absolute value.
_SIGN_FLIP_FIELDS = {"cost_of_goods_sold", "sga_expenses", "selling_expenses", "income_tax"}


def dataframe_to_company_financials(
    df: pd.DataFrame,
    company_name: str,
    sector_map: dict | None = None,
    balance_sheets: list | None = None,
    cash_flows: list | None = None,
) -> CompanyFinancials:
    """Convert the enriched metrics DataFrame into CompanyFinancials.

    Args:
        df:             Output of compute_metrics() — one row per (company, period, doc_type).
        company_name:   Display name (e.g. "BRASKEM S.A.").
        sector_map:     Optional SECTOR_MAP from enrichment.py for sector lookup.
        balance_sheets: Optional list of BalanceSheet objects (from parse_balance_sheets).
        cash_flows:     Optional list of CashFlow objects (from parse_cash_flows).

    Returns:
        CompanyFinancials with all available statements populated.
    """
    sector_map = sector_map or {}
    company_key = company_name.split()[0].upper()

    # Resolve sector
    sector = None
    sector_source = "unknown"
    for fragment, sec in sector_map.items():
        if fragment in company_key:
            sector = sec
            sector_source = "mapped"
            break

    # Determine company id — use CNPJ if available, else company_name
    company_id = company_name
    if "CNPJ_CIA" in df.columns:
        cnpj_vals = df["CNPJ_CIA"].dropna()
        if not cnpj_vals.empty:
            company_id = str(cnpj_vals.iloc[0])

    company_obj = Company(
        id=company_id,
        name=company_name,
        source="cvm",
        country="BR",
        currency="BRL",
        sector=sector,
        sector_source=sector_source,
    )

    income_statements: list[IncomeStatement] = []

    # Support both common model column names and legacy CVM column names
    date_col = "period_date" if "period_date" in df.columns else "DT_REFER"

    for _, row in df.iterrows():
        # Build Period
        dt_val = row.get(date_col)
        if not dt_val:
            continue
        try:
            period_date = pd.to_datetime(dt_val).date()
        except Exception:
            continue

        doc_type = str(row.get("_doc_type", "DFP")).upper()
        granularity = "annual" if doc_type == "DFP" else "quarterly"
        is_standalone = bool(row.get("is_standalone", True))
        fiscal_quarter = None
        if granularity == "quarterly":
            # Determine quarter from month of period_date
            month_to_q = {3: 1, 6: 2, 9: 3, 12: 4}
            fiscal_quarter = month_to_q.get(period_date.month)

        period = Period(
            date=period_date,
            granularity=granularity,
            fiscal_year=period_date.year,
            fiscal_quarter=fiscal_quarter,
            is_standalone=is_standalone,
            filing_type=doc_type,
        )

        # Build IncomeStatement kwargs
        kwargs: dict = {"company_id": company_id, "period": period}

        for cvm_col, field_name in _CVM_TO_IS_FIELD.items():
            val = row.get(cvm_col)
            if val is not None and pd.notna(val):
                fval = float(val)
                if field_name in _SIGN_FLIP_FIELDS:
                    fval = abs(fval)
                kwargs[field_name] = fval

        # D&A from DFC (stored in DA_from_DFC column by compute_metrics)
        da_val = row.get("DA_from_DFC")
        if da_val is not None and pd.notna(da_val):
            kwargs["depreciation_amortization"] = abs(float(da_val))

        # EBITDA
        ebitda_val = row.get("EBITDA")
        if ebitda_val is not None and pd.notna(ebitda_val):
            kwargs["ebitda"] = float(ebitda_val)

        income_statements.append(IncomeStatement(**kwargs))

    # Sort by period date
    income_statements.sort(key=lambda s: s.period.date)

    # Metadata
    granularities = sorted({s.period.granularity for s in income_statements})
    period_range = None
    if income_statements:
        dates = [s.period.date for s in income_statements]
        period_range = (min(dates), max(dates))

    bs_list = balance_sheets or []
    cf_list = cash_flows or []

    stmts_available = ["income_statement"]
    if bs_list:
        stmts_available.append("balance_sheet")
    if cf_list:
        stmts_available.append("cash_flow")

    data_completeness = {
        "income_statement": True,
        "balance_sheet": len(bs_list) > 0,
        "cash_flow": len(cf_list) > 0,
        "statements_available": stmts_available,
        "income_statement_periods": len(income_statements),
        "balance_sheet_periods": len(bs_list),
        "cash_flow_periods": len(cf_list),
        "has_da": any(s.depreciation_amortization is not None for s in income_statements),
        "has_ebitda": any(s.ebitda is not None for s in income_statements),
    }

    return CompanyFinancials(
        company=company_obj,
        income_statements=income_statements,
        balance_sheets=bs_list if bs_list else None,
        cash_flows=cf_list if cf_list else None,
        source="cvm",
        source_version="dfp_itr_v1",
        period_range=period_range,
        granularity=granularities,
        data_completeness=data_completeness,
    )


# =============================================================================
# Sprint 2 — Balance Sheet + Cash Flow Parsing
# =============================================================================

# Holding-entity exclusion (kept in sync with data_cleaner.py EXCLUDE_MAP)
_BS_EXCLUDE_MAP: dict[str, list[str]] = {
    "BRASKEM":    [],
    "SUZANO":     ["SUZANO HOLDING"],
    "GERDAU":     ["METALURGICA GERDAU"],
    "VOTORANTIM": [],
}

# BPA (assets) account codes → BalanceSheet field names
# Verified against Braskem, Vale, and Votorantim 2023 DFP filings.
_BPA_CODES: dict[str, str] = {
    "1":       "total_assets",
    "1.01":    "current_assets",
    "1.01.01": "cash_and_equivalents",
    "1.01.03": "accounts_receivable",
    "1.01.04": "inventories",
    "1.02":    "non_current_assets",
    "1.02.03": "property_plant_equipment",
    "1.02.04": "intangible_assets",
}

# BPP (liabilities + equity) account codes → BalanceSheet field names.
# Note: account "2" = Passivo Total = liabilities + equity (NOT stored).
# total_liabilities is computed as current_liabilities + non_current_liabilities.
_BPP_CODES: dict[str, str] = {
    "2.01":    "current_liabilities",
    "2.01.02": "accounts_payable",
    "2.01.04": "short_term_debt",
    "2.02":    "non_current_liabilities",
    "2.02.01": "long_term_debt",
    "2.03":    "total_equity",
}

# All directly-mapped BS fields (BPA + BPP); used for fields_mapped stats.
_BS_MAPPED_FIELDS: list[str] = list(_BPA_CODES.values()) + list(_BPP_CODES.values())

# Full BS field metadata for the mapping transparency panel (includes computed/unmapped fields).
_BS_ALL_FIELDS_META: list[dict] = (
    [{"field": v, "cvm_code": k} for k, v in _BPA_CODES.items()] +
    [{"field": v, "cvm_code": k} for k, v in _BPP_CODES.items()] +
    [{"field": "total_liabilities",  "cvm_code": "derived"}] +
    [{"field": "retained_earnings",  "cvm_code": "2.03.04"}]   # tracked but not mapped
)

# CF sub-account fields tracked in loading stats.
_CF_SUB_ACCOUNTS: list[str] = [
    "depreciation_amortization", "capex", "acquisitions",
    "debt_issuance", "debt_repayment", "dividends_paid",
]

# DFC top-level codes → CashFlow field names (standardised across companies)
_DFC_TOP_CODES: dict[str, str] = {
    "6.01": "operating_cash_flow",
    "6.02": "investing_cash_flow",
    "6.03": "financing_cash_flow",
}

# Keyword lists for DFC sub-account matching (case-insensitive partial match).
# Verified against Braskem, Vale, and Votorantim 2023 DFP/ITR filings.
_CAPEX_KEYWORDS    = ["imobilizado", "intangível"]
_CAPEX_EXCLUDE     = ["venda", "recebimento", "recursos recebidos", "alienação"]
_DA_KEYWORDS       = ["depreciação", "amortização", "exaustão"]
_DEBT_ISS_KEYWORDS = ["captações", "captação", "adições", "ingressos de empréstimos"]
_DEBT_REP_KEYWORDS = ["(pagamentos)", "baixas", "liquidação de empréstimos",
                      "pagamento de empréstimos", "amortização de empréstimos"]
_DEBT_REP_EXCLUDE  = ["arrendamento"]  # avoid matching lease repayments
_DIV_KEYWORDS      = ["dividendos", "jcp pagos", "juros sobre capital próprio pagos"]
_ACQUIS_KEYWORDS   = ["controladas", "subsidiária", "coligadas", "aquisição de invest"]
_ACQUIS_EXCLUDE    = ["imobilizado", "intangível"]


def _read_statement_from_zips(
    company_name: str,
    data_dir: Path,
    years: list,
    file_type: str,  # e.g. "bpa_con", "bpp_con", "dfc_mi_con"
) -> pd.DataFrame:
    """Read all *_file_type_*.csv files from DFP/ITR ZIPs, filtered to company."""
    company_key = _company_search_key(company_name)
    exclude     = _BS_EXCLUDE_MAP.get(company_key, [])
    raw_dir     = data_dir / "raw"
    frames: list[pd.DataFrame] = []

    for year in years:
        for doc_type in ("dfp", "itr"):
            zip_path = raw_dir / f"{doc_type}_cia_aberta_{year}.zip"
            if not zip_path.exists():
                continue
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    csv_files = [
                        n for n in zf.namelist()
                        if file_type.lower() in n.lower() and n.endswith(".csv")
                    ]
                    for csv_file in csv_files:
                        try:
                            with zf.open(csv_file) as f:
                                df = pd.read_csv(f, sep=";", encoding="latin-1",
                                                 low_memory=False)
                            if "DENOM_CIA" not in df.columns:
                                continue
                            # ORDEM_EXERC filter (drop prior-year restated rows)
                            if "ORDEM_EXERC" in df.columns:
                                df = df[df["ORDEM_EXERC"] == ORDEM_EXERC_KEEP].copy()
                            # Company + holding exclusion filter
                            mask = df["DENOM_CIA"].str.upper().str.contains(
                                company_key, na=False)
                            for excl in exclude:
                                mask &= ~df["DENOM_CIA"].str.upper().str.contains(
                                    excl, na=False)
                            df = df[mask].copy()
                            if not df.empty:
                                df["_doc_type"] = doc_type.upper()
                                frames.append(df)
                        except Exception:
                            continue
            except (zipfile.BadZipFile, FileNotFoundError):
                continue

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parse_balance_sheets(
    company_name: str,
    data_dir: Path,
    years: list,
) -> tuple:
    """Parse BPA_con + BPP_con into BalanceSheet objects.

    Balance sheets are point-in-time snapshots — no YTD conversion applied.
    DFP takes precedence over ITR for the same period + account code.
    Returns (list[BalanceSheet], bs_stats) sorted by period date.
    """
    bpa_raw = _read_statement_from_zips(company_name, data_dir, years, "bpa_con")
    bpp_raw = _read_statement_from_zips(company_name, data_dir, years, "bpp_con")
    bpa_records_loaded = len(bpa_raw)
    bpp_records_loaded = len(bpp_raw)

    _fields_total = len(_BS_MAPPED_FIELDS)

    def _empty_bs_stats() -> dict:
        return {
            "bpa_records_loaded": bpa_records_loaded,
            "bpp_records_loaded": bpp_records_loaded,
            "records_after_filter": 0,
            "periods_available": 0,
            "annual_periods": 0,
            "quarterly_periods": 0,
            "fields_mapped": 0,
            "fields_total": _fields_total,
        }

    if bpa_raw.empty and bpp_raw.empty:
        return [], _empty_bs_stats()

    def _pivot_bs(df: pd.DataFrame, code_map: dict) -> pd.DataFrame:
        """Dedup by (company, period, account) and pivot to one row per period."""
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        # Monetary scale normalisation (UNIDADE → thousands)
        df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
        if "ESCALA_MOEDA" in df.columns:
            df.loc[df["ESCALA_MOEDA"] == "UNIDADE", "VL_CONTA"] /= 1000
        # DFP/ITR dedup: prefer DFP (priority 0) over ITR (priority 1)
        df["_row_priority"] = df["_doc_type"].map({"DFP": 0, "ITR": 1}).fillna(1)
        df = (
            df.sort_values("_row_priority")
               .drop_duplicates(subset=["DENOM_CIA", "DT_REFER", "CD_CONTA"], keep="first")
        )
        # Filter to desired account codes
        df = df[df["CD_CONTA"].isin(code_map.keys())].copy()
        if df.empty:
            return pd.DataFrame()
        # Pivot: one row per (company, period)
        pivot = df.pivot_table(
            index=["DENOM_CIA", "DT_REFER", "_doc_type"],
            columns="CD_CONTA",
            values="VL_CONTA",
            aggfunc="first",
        ).reset_index()
        pivot.columns.name = None
        pivot.rename(columns=code_map, inplace=True)
        return pivot

    bpa_pivot = _pivot_bs(bpa_raw, _BPA_CODES)
    bpp_pivot = _pivot_bs(bpp_raw, _BPP_CODES)

    # Merge assets (BPA) + liabilities/equity (BPP) by period
    merge_on = ["DENOM_CIA", "DT_REFER", "_doc_type"]
    if not bpa_pivot.empty and not bpp_pivot.empty:
        merged = pd.merge(bpa_pivot, bpp_pivot, on=merge_on, how="outer")
    elif not bpa_pivot.empty:
        merged = bpa_pivot
    elif not bpp_pivot.empty:
        merged = bpp_pivot
    else:
        return [], _empty_bs_stats()
    records_after_filter = len(merged)

    # Compute total_liabilities = current + non_current (balance sheet "2" includes equity)
    cl  = merged.get("current_liabilities", pd.Series(dtype=float))
    ncl = merged.get("non_current_liabilities", pd.Series(dtype=float))
    if cl is not None or ncl is not None:
        merged["total_liabilities"] = cl.fillna(0) + ncl.fillna(0)
        # Reset to None when both components are missing
        if "current_liabilities" in merged.columns and "non_current_liabilities" in merged.columns:
            both_null = merged["current_liabilities"].isna() & merged["non_current_liabilities"].isna()
            merged.loc[both_null, "total_liabilities"] = None

    def _f(row, field: str) -> float | None:
        val = row.get(field)
        return float(val) if val is not None and pd.notna(val) else None

    balance_sheets: list = []
    for _, row in merged.iterrows():
        dt_val = row.get("DT_REFER")
        if not dt_val:
            continue
        try:
            period_date = pd.to_datetime(dt_val).date()
        except Exception:
            continue

        doc_type = str(row.get("_doc_type", "DFP")).upper()
        granularity = "annual" if doc_type == "DFP" else "quarterly"
        month_to_q = {3: 1, 6: 2, 9: 3, 12: 4}
        fiscal_quarter = month_to_q.get(period_date.month) if granularity == "quarterly" else None

        period = Period(
            date=period_date,
            granularity=granularity,
            fiscal_year=period_date.year,
            fiscal_quarter=fiscal_quarter,
            is_standalone=True,  # balance sheets are always point-in-time snapshots
            filing_type=doc_type,
        )
        bs = BalanceSheet(
            company_id=company_name,
            period=period,
            total_assets=_f(row, "total_assets"),
            current_assets=_f(row, "current_assets"),
            cash_and_equivalents=_f(row, "cash_and_equivalents"),
            accounts_receivable=_f(row, "accounts_receivable"),
            inventories=_f(row, "inventories"),
            non_current_assets=_f(row, "non_current_assets"),
            property_plant_equipment=_f(row, "property_plant_equipment"),
            intangible_assets=_f(row, "intangible_assets"),
            total_liabilities=_f(row, "total_liabilities"),
            current_liabilities=_f(row, "current_liabilities"),
            accounts_payable=_f(row, "accounts_payable"),
            short_term_debt=_f(row, "short_term_debt"),
            non_current_liabilities=_f(row, "non_current_liabilities"),
            long_term_debt=_f(row, "long_term_debt"),
            total_equity=_f(row, "total_equity"),
        )
        balance_sheets.append(bs)

    balance_sheets.sort(key=lambda x: x.period.date)

    # --- Loading stats (instrumentation only, no logic change) ---
    annual_periods   = sum(1 for bs in balance_sheets if bs.period.filing_type == "DFP")
    quarterly_periods = len(balance_sheets) - annual_periods

    # Per-field status for the mapping transparency panel
    fields_detail = []
    for fmeta in _BS_ALL_FIELDS_META:
        fname    = fmeta["field"]
        cvm_code = fmeta["cvm_code"]
        if cvm_code == "derived":
            status = "computed"
        elif fname not in _BS_MAPPED_FIELDS:
            status = "not_found"   # field defined in spec but not implemented
        elif balance_sheets and any(
            getattr(bs, fname, None) is not None for bs in balance_sheets
        ):
            status = "mapped"
        else:
            status = "not_found"
        fields_detail.append({"field": fname, "cvm_code": cvm_code, "status": status})

    # Derive fields_mapped/fields_total from fields_detail so card + table are consistent
    fields_mapped = sum(1 for fd in fields_detail if fd["status"] in ("mapped", "computed"))
    fields_total  = len(fields_detail)

    bs_stats = {
        "bpa_records_loaded":  bpa_records_loaded,
        "bpp_records_loaded":  bpp_records_loaded,
        "records_after_filter": records_after_filter,
        "periods_available":   len(balance_sheets),
        "annual_periods":      annual_periods,
        "quarterly_periods":   quarterly_periods,
        "fields_mapped":       fields_mapped,
        "fields_total":        fields_total,
        "fields":              fields_detail,
    }
    return balance_sheets, bs_stats


def _find_cf_descriptions(dfc_df: pd.DataFrame) -> dict[str, str | None]:
    """Return the first matching DS_CONTA text for each CF sub-account keyword set.

    Scans the full DFC DataFrame (after dedup) once to collect matched descriptions.
    No logic change — instrumentation only.
    """
    result: dict[str, str | None] = {k: None for k in _CF_SUB_ACCOUNTS}
    if dfc_df.empty or "DS_CONTA" not in dfc_df.columns or "CD_CONTA" not in dfc_df.columns:
        return result

    kw_configs = {
        "depreciation_amortization": ("6.01", _DA_KEYWORDS,       []),
        "capex":                     ("6.02", _CAPEX_KEYWORDS,    _CAPEX_EXCLUDE),
        "acquisitions":              ("6.02", _ACQUIS_KEYWORDS,   _ACQUIS_EXCLUDE),
        "debt_issuance":             ("6.03", _DEBT_ISS_KEYWORDS, []),
        "debt_repayment":            ("6.03", _DEBT_REP_KEYWORDS, _DEBT_REP_EXCLUDE),
        "dividends_paid":            ("6.03", _DIV_KEYWORDS,      []),
    }

    for field, (prefix, include_kws, exclude_kws) in kw_configs.items():
        section = dfc_df[dfc_df["CD_CONTA"].str.startswith(prefix + ".")]
        for _, row in section.iterrows():
            desc = str(row.get("DS_CONTA", ""))
            desc_lower = desc.lower()
            if any(ek in desc_lower for ek in exclude_kws):
                continue
            for kw in include_kws:
                if kw.lower() in desc_lower:
                    truncated = desc[:50] + "…" if len(desc) > 50 else desc
                    result[field] = truncated
                    break
            if result[field] is not None:
                break

    return result


def parse_cash_flows(
    company_name: str,
    data_dir: Path,
    years: list,
) -> tuple:
    """Parse DFC_MI_con from raw ZIPs into CashFlow objects.

    Applies YTD-to-standalone priority for quarterly data (same logic as
    income statement deduplication). Uses keyword matching on DS_CONTA for
    sub-account fields (capex, D&A, debt, dividends).
    Returns (list[CashFlow], cf_stats) sorted by period date.
    """
    dfc_all = _read_statement_from_zips(company_name, data_dir, years, "dfc_mi_con")
    if dfc_all.empty:
        return [], {
            "dfc_records_loaded": 0, "records_after_filter": 0,
            "periods_available": 0, "annual_periods": 0, "quarterly_periods": 0,
            "sub_accounts_found": {k: False for k in _CF_SUB_ACCOUNTS},
        }
    dfc_records_loaded = len(dfc_all)

    # Monetary scale normalisation
    dfc_all["VL_CONTA"] = pd.to_numeric(dfc_all["VL_CONTA"], errors="coerce")
    if "ESCALA_MOEDA" in dfc_all.columns:
        dfc_all.loc[dfc_all["ESCALA_MOEDA"] == "UNIDADE", "VL_CONTA"] /= 1000

    # DFP/ITR dedup with YTD priority (mirrors income statement logic in build_pivot)
    if "DT_INI_EXERC" in dfc_all.columns:
        ini_dt = pd.to_datetime(dfc_all["DT_INI_EXERC"], errors="coerce")
        ref_dt = pd.to_datetime(dfc_all["DT_REFER"],    errors="coerce")
        is_ytd_itr = (
            (dfc_all["_doc_type"] == "ITR") &
            (ini_dt.dt.month == 1) & (ini_dt.dt.day == 1) &
            (ini_dt.dt.year == ref_dt.dt.year) &
            (ref_dt.dt.month != 3)  # Q1 (Mar) is standalone even with Jan-1 start
        )
        dfc_all["_row_priority"] = 1   # ITR standalone
        dfc_all.loc[dfc_all["_doc_type"] == "DFP", "_row_priority"] = 0
        dfc_all.loc[is_ytd_itr, "_row_priority"] = 2  # ITR YTD (lowest priority)
    else:
        dfc_all["_row_priority"] = dfc_all["_doc_type"].map({"DFP": 0, "ITR": 1}).fillna(2)

    dfc_all = (
        dfc_all.sort_values("_row_priority")
               .drop_duplicates(subset=["DENOM_CIA", "DT_REFER", "CD_CONTA"], keep="first")
    )
    records_after_filter = len(dfc_all)

    def _kw_sum(
        grp: pd.DataFrame,
        section_prefix: str,
        include_kw: list,
        exclude_kw: list | None = None,
    ) -> float | None:
        """Sum sub-account values in *section* matching any include keyword."""
        exclude_kw = exclude_kw or []
        section = grp[grp["CD_CONTA"].str.startswith(section_prefix + ".")]
        total, found = 0.0, False
        for _, row in section.iterrows():
            desc = str(row.get("DS_CONTA", "")).lower()
            if any(ek in desc for ek in exclude_kw):
                continue
            for kw in include_kw:
                if kw.lower() in desc:
                    val = row.get("VL_CONTA")
                    if val is not None and pd.notna(val):
                        total += float(val)
                        found = True
                    break
        return total if found else None

    cash_flows: list = []
    for (co, period_str), grp in dfc_all.groupby(["DENOM_CIA", "DT_REFER"]):
        try:
            period_date = pd.to_datetime(period_str).date()
        except Exception:
            continue

        # Determine doc_type and standalone flag from group's priority column
        max_prio = grp["_row_priority"].max() if "_row_priority" in grp.columns else 1
        is_standalone = (max_prio < 2)
        # Most rows in the group should share a single doc_type after dedup
        if "_doc_type" in grp.columns and not grp["_doc_type"].empty:
            doc_type = grp["_doc_type"].mode()[0]
        else:
            doc_type = "DFP"

        granularity = "annual" if doc_type == "DFP" else "quarterly"
        month_to_q = {3: 1, 6: 2, 9: 3, 12: 4}
        fiscal_quarter = month_to_q.get(period_date.month) if granularity == "quarterly" else None

        period = Period(
            date=period_date,
            granularity=granularity,
            fiscal_year=period_date.year,
            fiscal_quarter=fiscal_quarter,
            is_standalone=is_standalone,
            filing_type=doc_type,
        )

        # Top-level account lookup (reliable across all companies)
        acct = grp.set_index("CD_CONTA")["VL_CONTA"].to_dict()
        def _exact(code: str) -> float | None:
            val = acct.get(code)
            return float(val) if val is not None and pd.notna(val) else None

        cf = CashFlow(
            company_id=company_name,
            period=period,
            operating_cash_flow=_exact("6.01"),
            investing_cash_flow=_exact("6.02"),
            financing_cash_flow=_exact("6.03"),
            # Sub-accounts: best-effort keyword matching on DS_CONTA
            depreciation_amortization=_kw_sum(grp, "6.01", _DA_KEYWORDS),
            capex=_kw_sum(grp, "6.02", _CAPEX_KEYWORDS, _CAPEX_EXCLUDE),
            acquisitions=_kw_sum(grp, "6.02", _ACQUIS_KEYWORDS, _ACQUIS_EXCLUDE),
            debt_issuance=_kw_sum(grp, "6.03", _DEBT_ISS_KEYWORDS),
            debt_repayment=_kw_sum(grp, "6.03", _DEBT_REP_KEYWORDS, _DEBT_REP_EXCLUDE),
            dividends_paid=_kw_sum(grp, "6.03", _DIV_KEYWORDS),
        )
        cash_flows.append(cf)

    cash_flows.sort(key=lambda x: x.period.date)

    # --- Loading stats (instrumentation only, no logic change) ---
    annual_periods    = sum(1 for cf in cash_flows if cf.period.filing_type == "DFP")
    quarterly_periods = len(cash_flows) - annual_periods

    sub_accounts_found_map = {
        k: any(getattr(cf, k, None) is not None for cf in cash_flows)
        for k in _CF_SUB_ACCOUNTS
    }

    # Find the first matching DS_CONTA description for each sub-account keyword set
    matched_descriptions = _find_cf_descriptions(dfc_all)

    sub_accounts_detail = [
        {
            "field":               k,
            "status":              "found" if sub_accounts_found_map[k] else "not_found",
            "matched_description": matched_descriptions.get(k),
        }
        for k in _CF_SUB_ACCOUNTS
    ]

    # Top-level CF accounts: check if any period has the value mapped
    top_level_detail = []
    for code, field_name in _DFC_TOP_CODES.items():
        found = any(getattr(cf, field_name, None) is not None for cf in cash_flows)
        top_level_detail.append({
            "field":    field_name,
            "cvm_code": code,
            "status":   "mapped" if found else "not_found",
        })

    cf_stats = {
        "dfc_records_loaded":    dfc_records_loaded,
        "records_after_filter":  records_after_filter,
        "periods_available":     len(cash_flows),
        "annual_periods":        annual_periods,
        "quarterly_periods":     quarterly_periods,
        "sub_accounts_found":    sub_accounts_found_map,
        "top_level":             top_level_detail,
        "sub_accounts":          sub_accounts_detail,
        "sub_accounts_matched":  sum(1 for k, v in sub_accounts_found_map.items() if v),
        "sub_accounts_total":    len(_CF_SUB_ACCOUNTS),
    }
    return cash_flows, cf_stats
