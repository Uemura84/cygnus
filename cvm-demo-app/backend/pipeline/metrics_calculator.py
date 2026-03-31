"""Metrics calculator — builds DRE pivot and computes EBITDA driver metrics.

Public API
----------
build_pivot(company_name, data_dir, years) -> (pivot_df, quality_stats)
    Step 3: reads filtered DRE CSV, deduplicates, pivots, computes margin ratios.
    Saves data/analysis/pivot_{key}.csv and quality_stats_{key}.json.

compute_metrics(company_name, data_dir, years) -> pd.DataFrame
    Step 4: reads pivot CSV, adds D&A from DFC ZIPs, computes EBITDA metrics.
    Saves data/analysis/metrics_{key}.csv.
"""

import json
import zipfile
from pathlib import Path

import pandas as pd

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

    ebit_col    = DRE_ACCOUNTS.get("3.05")
    revenue_col = DRE_ACCOUNTS.get("3.01")

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
                .rename(columns={"VL_CONTA": "DA_from_DFC"})
            )
            if not da.empty:
                pivot = pivot.merge(da, on=["DENOM_CIA", "DT_REFER"], how="left")
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
