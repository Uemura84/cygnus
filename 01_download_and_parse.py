"""
CVM Financial Data Pipeline — Petrochemical Sector Analysis
============================================================
Downloads DFP (annual) and ITR (quarterly) financial statements from
CVM's Open Data Portal, filters for petrochemical companies, and
structures the data for EBITDA driver decomposition analysis.

Target companies:
- Braskem (BRKM3/BRKM5) — largest petrochemical in the Americas
- Unipar (UNIP6) — cloro-soda and PVC leader
- Elekeiroz — specialty chemicals (Itaúsa group)

Data source: https://dados.cvm.gov.br
License: ODbL (Open Database License)

Usage:
    python 01_download_and_parse.py

Output:
    data/raw/          — downloaded ZIP files from CVM
    data/processed/    — filtered CSV files per company
    data/analysis/     — structured DataFrames ready for analysis
"""

import io
import json
import zipfile
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================

BASE_URL_DFP = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS"
BASE_URL_ITR = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS"

# Years to download (CVM keeps last 5 years + history since 2010)
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

# Target companies — we'll search by name fragments since CVM codes
# can vary. These are the key petrochemical players.
TARGET_COMPANIES = {
    "BRASKEM": "Braskem S.A.",
    "UNIPAR": "Unipar Carbocloro S.A.",
    "ELEKEIROZ": "Elekeiroz S.A.",
}

# Additional companies for cross-sector comparison (optional)
COMPARISON_COMPANIES = {
    "SUZANO": "Suzano S.A.",           # Pulp & paper — capital intensive
    "GERDAU": "Gerdau S.A.",           # Steel — capital intensive
    "VALE": "Vale S.A.",               # Mining — capital intensive
}

# Holding/parent entities whose consolidated financials duplicate the operating
# company. Excluding them prevents double-counting in analysis.
EXCLUDE_COMPANIES = ["SUZANO HOLDING", "METALURGICA GERDAU"]

# CVM files include both ÚLTIMO (current period) and PENÚLTIMO (prior-year
# comparison row). Keep only current-period rows to avoid double-counting.
ORDEM_EXERC_FILTER = "ÚLTIMO"

# Key DRE (Income Statement) account codes in the CVM chart of accounts
# These follow the CVM standardized account numbering
DRE_ACCOUNTS = {
    "3.01": "Receita de Venda de Bens e/ou Serviços",
    "3.02": "Custo dos Bens e/ou Serviços Vendidos",
    "3.03": "Resultado Bruto",
    "3.04": "Despesas/Receitas Operacionais",
    "3.04.01": "Despesas com Vendas",
    "3.04.02": "Despesas Gerais e Administrativas",
    "3.04.04": "Outras Receitas Operacionais",
    "3.04.05": "Outras Despesas Operacionais",
    "3.04.06": "Resultado de Equivalência Patrimonial",
    "3.05": "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)",
    "3.06": "Resultado Financeiro",
    "3.06.01": "Receitas Financeiras",
    "3.06.02": "Despesas Financeiras",
    "3.07": "Resultado Antes dos Tributos sobre o Lucro",
    "3.08": "Imposto de Renda e Contribuição Social sobre o Lucro",
    "3.09": "Resultado Líquido das Operações Continuadas",
    "3.11": "Lucro/Prejuízo Consolidado do Período",
}

# Directories
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_DIR = DATA_DIR / "analysis"

for d in [RAW_DIR, PROCESSED_DIR, ANALYSIS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Step 1: Download CVM Data
# =============================================================================

def download_cvm_file(url: str, dest_path: Path) -> bool:
    """Download a file from CVM if it doesn't already exist."""
    if dest_path.exists():
        print(f"  ✓ Already exists: {dest_path.name}")
        return True

    print(f"  ↓ Downloading: {dest_path.name} ... ", end="")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        dest_path.write_bytes(response.content)
        size_mb = len(response.content) / (1024 * 1024)
        print(f"OK ({size_mb:.1f} MB)")
        return True
    except requests.RequestException as e:
        print(f"FAILED ({e})")
        return False


def download_all():
    """Download DFP and ITR files for all configured years."""
    print("\n" + "=" * 60)
    print("STEP 1: Downloading CVM financial data")
    print("=" * 60)

    for year in YEARS:
        # DFP (annual)
        dfp_url = f"{BASE_URL_DFP}/dfp_cia_aberta_{year}.zip"
        dfp_path = RAW_DIR / f"dfp_cia_aberta_{year}.zip"
        download_cvm_file(dfp_url, dfp_path)

        # ITR (quarterly)
        itr_url = f"{BASE_URL_ITR}/itr_cia_aberta_{year}.zip"
        itr_path = RAW_DIR / f"itr_cia_aberta_{year}.zip"
        download_cvm_file(itr_url, itr_path)


# =============================================================================
# Step 2: Parse and Filter
# =============================================================================

def read_cvm_zip(zip_path: Path, file_pattern: str) -> pd.DataFrame:
    """
    Read CSV files from a CVM ZIP archive.

    CVM ZIPs contain multiple CSVs:
    - *_DRE_con.csv  — Consolidated Income Statement
    - *_DRE_ind.csv  — Individual Income Statement
    - *_BPA_con.csv  — Consolidated Balance Sheet (Assets)
    - *_BPP_con.csv  — Consolidated Balance Sheet (Liabilities)
    - *_DFC_MI_con.csv — Cash Flow (Indirect Method)
    - *_DVA_con.csv  — Value Added Statement
    - *_parecer.csv  — Auditor opinions
    - *_empresa.csv  — Company data

    We focus on consolidated (_con) statements.
    """
    frames = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            matching_files = [
                f for f in zf.namelist()
                if file_pattern.lower() in f.lower() and f.endswith('.csv')
            ]

            for csv_file in matching_files:
                try:
                    with zf.open(csv_file) as f:
                        df = pd.read_csv(
                            f,
                            sep=';',
                            encoding='latin-1',
                            low_memory=False
                        )
                        df['_source_file'] = csv_file
                        frames.append(df)
                except Exception as e:
                    print(f"    Warning: Could not read {csv_file}: {e}")
    except zipfile.BadZipFile:
        print(f"    Error: {zip_path.name} is not a valid ZIP file")
        return pd.DataFrame()

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()


def filter_companies(df: pd.DataFrame, companies: dict, exclude: list = None) -> pd.DataFrame:
    """Filter DataFrame to include only target companies by name fragment.

    Args:
        companies: Dict whose keys are uppercase name fragments to include.
        exclude:   Optional list of uppercase fragments to exclude (e.g. holding
                   companies whose consolidated numbers duplicate the operating entity).
    """
    if df.empty or 'DENOM_CIA' not in df.columns:
        return pd.DataFrame()

    mask = pd.Series(False, index=df.index)
    for key in companies:
        mask |= df['DENOM_CIA'].str.upper().str.contains(key, na=False)

    if exclude:
        for excl in exclude:
            mask &= ~df['DENOM_CIA'].str.upper().str.contains(excl, na=False)

    return df[mask].copy()


def _filter_ordem_exerc(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only ÚLTIMO rows, dropping the PENÚLTIMO prior-year comparison rows."""
    if 'ORDEM_EXERC' in df.columns:
        return df[df['ORDEM_EXERC'] == ORDEM_EXERC_FILTER].copy()
    return df


def _convert_itr_ytd_to_standalone(pivot: pd.DataFrame) -> pd.DataFrame:
    """Convert ITR cumulative YTD account values to standalone quarterly values.

    CVM ITR files report cumulative year-to-date figures:
      Q1 (Mar): Jan–Mar — already standalone, no change needed
      Q2 (Jun): Jan–Jun → subtract Q1_YTD to get standalone Apr–Jun
      Q3 (Sep): Jan–Sep → subtract Q2_YTD to get standalone Jul–Sep

    Adds 'is_standalone' flag:
      True  — value is a clean standalone quarter (or annual DFP row)
      False — preceding quarter was missing; original YTD value left in place
    """
    pivot = pivot.copy()
    pivot['DT_REFER_dt'] = pd.to_datetime(pivot['DT_REFER'], errors='coerce')
    pivot['_month'] = pivot['DT_REFER_dt'].dt.month
    pivot['_year']  = pivot['DT_REFER_dt'].dt.year

    # DFP rows are annual — always standalone
    pivot['is_standalone'] = True

    # Columns to convert: financial account values (descriptions from DRE_ACCOUNTS)
    account_cols = [c for c in pivot.columns if c in set(DRE_ACCOUNTS.values())]

    itr_mask = pivot['_doc_type'] == 'ITR'

    for company in pivot.loc[itr_mask, 'DENOM_CIA'].unique():
        comp_idx = pivot[(pivot['DENOM_CIA'] == company) & itr_mask].index
        comp = pivot.loc[comp_idx]

        for year in comp['_year'].dropna().unique():
            yr_comp = comp[comp['_year'] == year]

            q1 = yr_comp[yr_comp['_month'] == 3]
            q2 = yr_comp[yr_comp['_month'] == 6]
            q3 = yr_comp[yr_comp['_month'] == 9]

            # Capture original YTD values before any modification
            q1_vals = {col: pivot.at[q1.index[0], col] for col in account_cols
                       if not q1.empty and col in pivot.columns}
            q2_vals = {col: pivot.at[q2.index[0], col] for col in account_cols
                       if not q2.empty and col in pivot.columns}

            # Convert Q2: standalone = Q2_YTD - Q1_YTD
            if not q2.empty:
                q2_idx = q2.index[0]
                if not q1.empty:
                    for col in account_cols:
                        if col in pivot.columns:
                            v_q2 = q2_vals.get(col)
                            v_q1 = q1_vals.get(col)
                            if pd.notna(v_q2) and pd.notna(v_q1):
                                pivot.at[q2_idx, col] = v_q2 - v_q1
                else:
                    pivot.at[q2_idx, 'is_standalone'] = False  # missing Q1

            # Convert Q3: standalone = Q3_YTD - Q2_YTD (original Q2_YTD used)
            if not q3.empty:
                q3_idx = q3.index[0]
                if not q2.empty:
                    for col in account_cols:
                        if col in pivot.columns:
                            v_q3_orig = pivot.at[q3_idx, col]
                            v_q2 = q2_vals.get(col)   # original Q2_YTD
                            if pd.notna(v_q3_orig) and pd.notna(v_q2):
                                pivot.at[q3_idx, col] = v_q3_orig - v_q2
                else:
                    pivot.at[q3_idx, 'is_standalone'] = False  # missing Q2

    pivot.drop(columns=['DT_REFER_dt', '_month', '_year'], inplace=True)
    return pivot


def parse_all_data():
    """Parse all downloaded ZIPs and extract target company data."""
    print("\n" + "=" * 60)
    print("STEP 2: Parsing and filtering financial statements")
    print("=" * 60)

    all_companies = {**TARGET_COMPANIES, **COMPARISON_COMPANIES}

    all_dre = []
    all_bpa = []
    all_bpp = []
    all_dfc = []

    for year in YEARS:
        for doc_type in ['dfp', 'itr']:
            zip_path = RAW_DIR / f"{doc_type}_cia_aberta_{year}.zip"
            if not zip_path.exists():
                continue

            print(f"\n  Processing: {zip_path.name}")

            # DRE — Income Statement (consolidated)
            dre = read_cvm_zip(zip_path, 'DRE_con')
            dre_filtered = filter_companies(dre, all_companies, exclude=EXCLUDE_COMPANIES)
            dre_filtered = _filter_ordem_exerc(dre_filtered)
            if not dre_filtered.empty:
                dre_filtered['_doc_type'] = doc_type.upper()
                all_dre.append(dre_filtered)
                companies_found = dre_filtered['DENOM_CIA'].nunique()
                print(f"    DRE: {len(dre_filtered)} rows, {companies_found} companies")

            # BPA — Balance Sheet Assets (consolidated)
            bpa = read_cvm_zip(zip_path, 'BPA_con')
            bpa_filtered = filter_companies(bpa, all_companies, exclude=EXCLUDE_COMPANIES)
            bpa_filtered = _filter_ordem_exerc(bpa_filtered)
            if not bpa_filtered.empty:
                bpa_filtered['_doc_type'] = doc_type.upper()
                all_bpa.append(bpa_filtered)

            # BPP — Balance Sheet Liabilities (consolidated)
            bpp = read_cvm_zip(zip_path, 'BPP_con')
            bpp_filtered = filter_companies(bpp, all_companies, exclude=EXCLUDE_COMPANIES)
            bpp_filtered = _filter_ordem_exerc(bpp_filtered)
            if not bpp_filtered.empty:
                bpp_filtered['_doc_type'] = doc_type.upper()
                all_bpp.append(bpp_filtered)

            # DFC — Cash Flow (consolidated, indirect method)
            dfc = read_cvm_zip(zip_path, 'DFC_MI_con')
            dfc_filtered = filter_companies(dfc, all_companies, exclude=EXCLUDE_COMPANIES)
            dfc_filtered = _filter_ordem_exerc(dfc_filtered)
            if not dfc_filtered.empty:
                dfc_filtered['_doc_type'] = doc_type.upper()
                all_dfc.append(dfc_filtered)

    # Combine and save
    datasets = {
        'dre': all_dre,
        'bpa': all_bpa,
        'bpp': all_bpp,
        'dfc': all_dfc,
    }

    for name, frames in datasets.items():
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            output_path = PROCESSED_DIR / f"petrochem_{name}_consolidated.csv"
            combined.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"\n  Saved: {output_path.name} ({len(combined)} rows)")
        else:
            print(f"\n  Warning: No {name.upper()} data found")

    return datasets


# =============================================================================
# Step 3: Structure for EBITDA Analysis
# =============================================================================

def build_ebitda_analysis(datasets: dict):
    """
    Build structured EBITDA driver decomposition from parsed DRE data.

    EBITDA = Revenue - COGS - SG&A (or equivalently: EBIT + D&A)

    Key patterns to look for:
    1. COGS as % of Revenue — trend and volatility
    2. SG&A as % of Revenue — operational leverage
    3. Gross margin trajectory vs stated strategy
    4. Quarter-over-quarter volatility in cost composition
    5. Divergence between individual and consolidated results

    Returns:
        (pivot, quality_stats) tuple, or None if no data.
    """
    print("\n" + "=" * 60)
    print("STEP 3: Building EBITDA driver analysis")
    print("=" * 60)

    if not datasets.get('dre'):
        print("  No DRE data available. Run download and parse first.")
        return None

    dre = pd.concat(datasets['dre'], ignore_index=True)

    # Ensure VL_CONTA is numeric
    if 'VL_CONTA' in dre.columns:
        dre['VL_CONTA'] = pd.to_numeric(dre['VL_CONTA'], errors='coerce')

    # Normalize monetary scale to thousands (MIL stays as-is; UNIDADE ÷ 1000)
    if 'ESCALA_MOEDA' in dre.columns:
        dre.loc[dre['ESCALA_MOEDA'] == 'UNIDADE', 'VL_CONTA'] /= 1000

    rows_raw = len(dre)

    # Deduplicate: prefer DFP over ITR, and within ITR prefer standalone quarterly
    # rows over YTD cumulative rows (CVM ITR files include both formats for Q2/Q3).
    # Standalone ITR rows have DT_INI_EXERC != Jan 1 (e.g., Apr 1 for Q2, Jul 1 for Q3).
    # YTD rows start on Jan 1 of the reference year (e.g., Jan 1 for a Jun 30 period).
    if 'DT_INI_EXERC' in dre.columns:
        ini_dt = pd.to_datetime(dre['DT_INI_EXERC'], errors='coerce')
        is_ytd_itr = (
            (dre['_doc_type'] == 'ITR') &
            (ini_dt.dt.month == 1) & (ini_dt.dt.day == 1)
        )
        dre['_row_priority'] = 1   # ITR standalone (non-Jan-1 start)
        dre.loc[dre['_doc_type'] == 'DFP', '_row_priority'] = 0
        dre.loc[is_ytd_itr, '_row_priority'] = 2  # ITR YTD (lowest priority)
    else:
        dre['_row_priority'] = dre['_doc_type'].map({'DFP': 0, 'ITR': 1}).fillna(2)

    dre = (
        dre.sort_values('_row_priority')
           .drop_duplicates(subset=['DENOM_CIA', 'DT_REFER', 'CD_CONTA'], keep='first')
           .drop(columns='_row_priority')
    )
    rows_after_dedup = len(dre)

    # Key columns: DENOM_CIA, DT_REFER, CD_CONTA, DS_CONTA, VL_CONTA, ESCALA_MOEDA, MOEDA
    # DT_REFER = reference date (end of period)
    # CD_CONTA = account code (3.01, 3.02, etc.)
    # DS_CONTA = account description
    # VL_CONTA = account value (normalized to thousands BRL)

    print(f"\n  Total DRE rows: {rows_after_dedup} (raw: {rows_raw}, deduped: {rows_raw - rows_after_dedup})")
    print(f"  Companies: {dre['DENOM_CIA'].unique().tolist()}")
    print(f"  Date range: {dre['DT_REFER'].min()} to {dre['DT_REFER'].max()}")

    # Compute standalone flag before pivoting so it survives the pivot_table aggregation.
    # After the dedup above, each ITR row is either:
    #   - standalone quarterly (DT_INI_EXERC != Jan 1 of reference year, e.g., Apr 1 for Q2)
    #   - Q1 / DFP annual (DT_INI_EXERC = Jan 1, but Jan–Mar = Q1 standalone = YTD identical)
    # Both cases are standalone; the YTD-only rows (Jan-1 start + Q2/Q3) were deprioritised
    # in the dedup and only survive if no standalone row existed.
    if 'DT_INI_EXERC' in dre.columns:
        ini_dt = pd.to_datetime(dre['DT_INI_EXERC'], errors='coerce')
        ref_dt = pd.to_datetime(dre['DT_REFER'], errors='coerce')
        ytd_only = (
            (dre['_doc_type'] == 'ITR') &
            (ini_dt.dt.month == 1) & (ini_dt.dt.day == 1) &
            (ini_dt.dt.year == ref_dt.dt.year) &
            (ref_dt.dt.month != 3)   # Q1 (March) is standalone even with Jan-1 start
        )
        dre['_is_standalone'] = ~ytd_only
    else:
        dre['_is_standalone'] = True

    # Filter to key EBITDA-relevant accounts
    key_accounts = list(DRE_ACCOUNTS.keys())
    dre_key = dre[dre['CD_CONTA'].isin(key_accounts)].copy()

    print(f"  Key account rows: {len(dre_key)}")

    # Capture standalone flag per (company, period, doc_type) for merging into pivot
    standalone_map = (
        dre_key.groupby(['DENOM_CIA', 'DT_REFER', '_doc_type'])['_is_standalone']
        .first().reset_index()
        .rename(columns={'_is_standalone': 'is_standalone'})
    )

    # Pivot: one row per company-period, one column per account
    pivot = dre_key.pivot_table(
        index=['DENOM_CIA', 'DT_REFER', '_doc_type'],
        columns='CD_CONTA',
        values='VL_CONTA',
        aggfunc='first'
    ).reset_index()

    # Rename columns to readable names
    pivot.columns.name = None
    col_renames = {code: desc for code, desc in DRE_ACCOUNTS.items() if code in pivot.columns}
    pivot.rename(columns=col_renames, inplace=True)

    # Attach standalone flag to pivot (replaces the old YTD subtraction approach)
    pivot = pivot.merge(standalone_map, on=['DENOM_CIA', 'DT_REFER', '_doc_type'], how='left')
    pivot['is_standalone'] = pivot['is_standalone'].fillna(True)

    # Compute derived metrics
    revenue_col = DRE_ACCOUNTS.get("3.01")
    cogs_col = DRE_ACCOUNTS.get("3.02")
    gross_col = DRE_ACCOUNTS.get("3.03")
    sga_col = DRE_ACCOUNTS.get("3.04.02")
    selling_col = DRE_ACCOUNTS.get("3.04.01")
    ebit_col = DRE_ACCOUNTS.get("3.05")

    if revenue_col in pivot.columns:
        revenue = pivot[revenue_col]

        if cogs_col in pivot.columns:
            pivot['COGS_pct_Revenue'] = (pivot[cogs_col].abs() / revenue * 100).round(2)

        if gross_col in pivot.columns:
            pivot['Gross_Margin_pct'] = (pivot[gross_col] / revenue * 100).round(2)

        if sga_col in pivot.columns:
            pivot['SGA_pct_Revenue'] = (pivot[sga_col].abs() / revenue * 100).round(2)

        if selling_col in pivot.columns:
            pivot['Selling_pct_Revenue'] = (pivot[selling_col].abs() / revenue * 100).round(2)

        if ebit_col in pivot.columns:
            pivot['EBIT_Margin_pct'] = (pivot[ebit_col] / revenue * 100).round(2)

    # D&A from DFC (indirect method cash flow)
    # Look for depreciation/amortization line items to compute true EBITDA.
    if datasets.get('dfc'):
        try:
            dfc_all = pd.concat(datasets['dfc'], ignore_index=True)
            dfc_all['VL_CONTA'] = pd.to_numeric(dfc_all['VL_CONTA'], errors='coerce')
            da_mask = dfc_all['DS_CONTA'].str.lower().str.contains(
                'deprecia|amortiza', na=False
            )
            da = (
                dfc_all[da_mask]
                .groupby(['DENOM_CIA', 'DT_REFER'])['VL_CONTA']
                .sum().abs().reset_index()
                .rename(columns={'VL_CONTA': 'DA_from_DFC'})
            )
            if not da.empty:
                pivot = pivot.merge(da, on=['DENOM_CIA', 'DT_REFER'], how='left')
                if ebit_col in pivot.columns:
                    pivot['EBITDA'] = pivot[ebit_col] + pivot['DA_from_DFC'].fillna(0)
                    if revenue_col in pivot.columns:
                        pivot['EBITDA_Margin_pct'] = (
                            pivot['EBITDA'] / pivot[revenue_col] * 100
                        ).round(2)
                coverage = da['DENOM_CIA'].nunique()
                print(f"  D&A from DFC: found for {coverage} companies")
        except Exception as e:
            print(f"  Warning: Could not extract D&A from DFC ({e})")

    # Sort by company and date
    pivot.sort_values(['DENOM_CIA', 'DT_REFER'], inplace=True)

    # Add CNPJ_CIA for reliable company identification
    if 'CNPJ_CIA' in dre.columns:
        cnpj_map = dre.groupby('DENOM_CIA')['CNPJ_CIA'].first()
        pivot.insert(1, 'CNPJ_CIA', pivot['DENOM_CIA'].map(cnpj_map))

    # Build quality stats
    missing_revenue_pct = 0.0
    if revenue_col in pivot.columns and len(pivot) > 0:
        missing_revenue_pct = round(pivot[revenue_col].isna().sum() / len(pivot) * 100, 1)

    itr_rows = pivot[pivot['_doc_type'] == 'ITR']
    itr_standalone_count = int(
        itr_rows['is_standalone'].sum() if 'is_standalone' in itr_rows.columns else len(itr_rows)
    )

    quality_stats = {
        'rows_raw': rows_raw,
        'rows_after_dedup': rows_after_dedup,
        'duplicates_removed': rows_raw - rows_after_dedup,
        'companies': dre['DENOM_CIA'].unique().tolist(),
        'date_range': (str(dre['DT_REFER'].min()), str(dre['DT_REFER'].max())),
        'doc_types': dre['_doc_type'].value_counts().to_dict(),
        'missing_revenue_pct': missing_revenue_pct,
        'itr_standalone_rows': itr_standalone_count,
    }

    # Save
    output_path = ANALYSIS_DIR / "ebitda_driver_analysis.csv"
    pivot.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n  Saved: {output_path.name} ({len(pivot)} rows)")

    # Save quality stats for use by pattern discovery script
    quality_stats_path = ANALYSIS_DIR / "quality_stats.json"
    with open(quality_stats_path, 'w') as qf:
        json.dump(quality_stats, qf, indent=2)
    print(f"  Saved: {quality_stats_path.name}")

    # Also save the full DRE with all account detail (for deep dives)
    full_output = ANALYSIS_DIR / "full_dre_detail.csv"
    dre.to_csv(full_output, index=False, encoding='utf-8-sig')
    print(f"  Saved: {full_output.name} ({len(dre)} rows)")

    # Print summary statistics
    print("\n  " + "-" * 50)
    print("  EBITDA Driver Summary (latest available period):")
    print("  " + "-" * 50)

    for company in pivot['DENOM_CIA'].unique():
        comp_data = pivot[pivot['DENOM_CIA'] == company].tail(1)
        if comp_data.empty:
            continue
        row = comp_data.iloc[0]
        print(f"\n  {company}")
        print(f"    Period: {row['DT_REFER']}")
        if 'Gross_Margin_pct' in row and pd.notna(row.get('Gross_Margin_pct')):
            print(f"    Gross Margin:    {row['Gross_Margin_pct']:.1f}%")
        if 'COGS_pct_Revenue' in row and pd.notna(row.get('COGS_pct_Revenue')):
            print(f"    COGS/Revenue:    {row['COGS_pct_Revenue']:.1f}%")
        if 'SGA_pct_Revenue' in row and pd.notna(row.get('SGA_pct_Revenue')):
            print(f"    SG&A/Revenue:    {row['SGA_pct_Revenue']:.1f}%")
        if 'EBIT_Margin_pct' in row and pd.notna(row.get('EBIT_Margin_pct')):
            print(f"    EBIT Margin:     {row['EBIT_Margin_pct']:.1f}%")
        if 'EBITDA_Margin_pct' in row and pd.notna(row.get('EBITDA_Margin_pct')):
            print(f"    EBITDA Margin:   {row['EBITDA_Margin_pct']:.1f}%")

    return pivot, quality_stats


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CVM Financial Data Pipeline — Petrochemical Sector")
    print(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Step 1: Download
    download_all()

    # Step 2: Parse and filter
    datasets = parse_all_data()

    # Step 3: Build EBITDA analysis
    if datasets.get('dre'):
        result = build_ebitda_analysis(datasets)
        if result is not None:
            pivot, quality_stats = result

    print("\n" + "=" * 60)
    print("Pipeline complete.")
    print(f"  Raw data:       {RAW_DIR}/")
    print(f"  Processed data: {PROCESSED_DIR}/")
    print(f"  Analysis data:  {ANALYSIS_DIR}/")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run 02_pattern_discovery.py to find hidden patterns")
    print("  2. Review ebitda_driver_analysis.csv for initial findings")
    print("  3. Bring findings back to Claude for interpretation")
