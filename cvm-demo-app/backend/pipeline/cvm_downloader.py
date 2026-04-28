"""CVM open-data downloader.

Refactored from 01_download_and_parse.py — download logic only.
The parse/filter logic lives in data_cleaner.py.

Public API
----------
download(company_name, years, data_dir) -> dict
    Downloads DFP and ITR ZIP files from CVM for the given years.
    Counts DRE rows for the target company and returns Step 1 result data.
"""
import zipfile
from pathlib import Path

import requests
import pandas as pd

BASE_URL_DFP = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS"
BASE_URL_ITR = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS"
BASE_URL_FRE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS"

# Holding/parent entities that share a company name fragment but duplicate
# the operating company's numbers. Extend per company as needed (Phase 2).
EXCLUDE_MAP: dict[str, list[str]] = {
    "BRASKEM": [],          # No separate listed holding for Braskem
    "SUZANO":  ["SUZANO HOLDING"],
    "GERDAU":  ["METALURGICA GERDAU"],
}

# Statement file types inside each ZIP (used for statements_found counting)
_STATEMENT_TYPES = ["dre_con", "bpa_con", "bpp_con", "dfc_mi_con", "dva_con", "dmpl_con", "dra_con"]

# Parecer file pattern (separate from statement types — counted differently)
_PARECER_PATTERN = "parecer"


def _company_search_key(company_name: str) -> str:
    """Extract uppercase search key from full company name.
    e.g. 'BRASKEM S.A.' -> 'BRASKEM'
    """
    return company_name.split()[0].upper()


def _download_file(url: str, dest: Path, timeout: int = 60) -> bool:
    """Download *url* to *dest* if not already present.
    Returns True on success (including cache-hit), False on network failure.
    """
    if dest.exists():
        return True
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException:
        return False


def _count_statement_rows_in_zip(
    zip_path: Path,
    company_key: str,
    exclude: list[str],
    file_types: list[str],
) -> dict[str, dict]:
    """Count company rows per statement file type inside *zip_path*.

    Returns a dict keyed by file_type with {"found": bool, "rows": int}.
    Only reads DENOM_CIA column to keep this fast.
    """
    result = {ft: {"found": False, "rows": 0} for ft in file_types}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for csv_name in zf.namelist():
                if not csv_name.endswith(".csv"):
                    continue
                matched_ft = next(
                    (ft for ft in file_types if ft in csv_name.lower()), None
                )
                if matched_ft is None:
                    continue
                result[matched_ft]["found"] = True
                try:
                    with zf.open(csv_name) as f:
                        df = pd.read_csv(
                            f, sep=";", encoding="latin-1",
                            low_memory=False, usecols=["DENOM_CIA"],
                        )
                    mask = df["DENOM_CIA"].str.upper().str.contains(
                        company_key, na=False
                    )
                    for excl in exclude:
                        mask &= ~df["DENOM_CIA"].str.upper().str.contains(
                            excl, na=False
                        )
                    result[matched_ft]["rows"] += int(mask.sum())
                except Exception:
                    pass
    except (zipfile.BadZipFile, FileNotFoundError):
        pass
    return result


def _count_dre_rows_in_zip(
    zip_path: Path,
    company_key: str,
    exclude: list[str],
) -> tuple[int, list[str]]:
    """Count DRE (income-statement) rows for *company_key* inside a ZIP.

    Reads only DENOM_CIA + DT_REFER to keep this fast.
    Returns (row_count, list_of_date_strings).
    """
    count = 0
    dates: list[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_files = [
                name for name in zf.namelist()
                if "dre_con" in name.lower() and name.endswith(".csv")
            ]
            for csv_file in csv_files:
                try:
                    with zf.open(csv_file) as f:
                        df = pd.read_csv(
                            f,
                            sep=";",
                            encoding="latin-1",
                            low_memory=False,
                            usecols=["DENOM_CIA", "DT_REFER"],
                        )
                    mask = df["DENOM_CIA"].str.upper().str.contains(
                        company_key, na=False
                    )
                    for excl in exclude:
                        mask &= ~df["DENOM_CIA"].str.upper().str.contains(
                            excl, na=False
                        )
                    filtered = df[mask]
                    count += len(filtered)
                    dates.extend(
                        filtered["DT_REFER"].dropna().astype(str).tolist()
                    )
                except Exception:
                    continue
    except (zipfile.BadZipFile, FileNotFoundError):
        pass
    return count, dates


def extract_company_list(data_dir: Path) -> list[dict]:
    """Scan downloaded DFP ZIPs and return unique companies with CVM codes.

    Only reads the raw ZIPs already on disk — does not make network requests.
    Returns a list sorted by company name.
    """
    companies: dict[str, dict] = {}
    raw_dir = data_dir / "raw"
    if not raw_dir.exists():
        return []

    for zip_path in sorted(raw_dir.glob("dfp_cia_aberta_*.zip")):
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                csv_files = [
                    name for name in zf.namelist()
                    if "dre_con" in name.lower() and name.endswith(".csv")
                ]
                for csv_file in csv_files:
                    try:
                        with zf.open(csv_file) as f:
                            df = pd.read_csv(
                                f,
                                sep=";",
                                encoding="latin-1",
                                low_memory=False,
                                usecols=["DENOM_CIA", "CD_CVM"],
                            )
                        for _, row in df.drop_duplicates(subset=["DENOM_CIA"]).iterrows():
                            name = str(row["DENOM_CIA"]).strip()
                            if name and name not in companies:
                                companies[name] = {
                                    "name": name,
                                    "cvm_code": str(int(row["CD_CVM"])) if pd.notna(row["CD_CVM"]) else "",
                                }
                    except Exception:
                        continue
        except (zipfile.BadZipFile, FileNotFoundError):
            continue

    return sorted(companies.values(), key=lambda c: c["name"])


def download(company_name: str, years: list[int], data_dir: Path) -> dict:
    """Download DFP and ITR ZIPs for *company_name* across *years*.

    Files saved to *data_dir/raw/*.  After downloading, does a lightweight
    row-count pass to populate the Step 1 result.

    Returns a dict matching the Step 1 ``data`` shape from the spec.
    """
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    company_key = _company_search_key(company_name)
    exclude = EXCLUDE_MAP.get(company_key, [])

    files_downloaded: list[str] = []
    dfp_rows = 0
    itr_rows = 0
    all_dates: list[str] = []

    # Per-statement-type file counts and row totals (for "Statements Found" table)
    dfp_file_counts  = {ft: 0 for ft in _STATEMENT_TYPES}
    itr_file_counts  = {ft: 0 for ft in _STATEMENT_TYPES}
    total_rows_by_ft = {ft: 0 for ft in _STATEMENT_TYPES}

    # Parecer (auditor report) counts — DFP only
    parecer_dfp_count = 0

    for year in years:
        # DFP (annual)
        dfp_path = raw_dir / f"dfp_cia_aberta_{year}.zip"
        if _download_file(f"{BASE_URL_DFP}/dfp_cia_aberta_{year}.zip", dfp_path):
            files_downloaded.append(dfp_path.name)
            rows, dates = _count_dre_rows_in_zip(dfp_path, company_key, exclude)
            dfp_rows += rows
            all_dates.extend(dates)
            stmt_info = _count_statement_rows_in_zip(
                dfp_path, company_key, exclude, _STATEMENT_TYPES
            )
            for ft, info in stmt_info.items():
                if info["found"]:
                    dfp_file_counts[ft] += 1
                total_rows_by_ft[ft] += info["rows"]
            # Count Parecer files in this DFP ZIP
            try:
                with zipfile.ZipFile(dfp_path, "r") as _zf:
                    _parecer = [n for n in _zf.namelist() if _PARECER_PATTERN in n.lower() and n.endswith(".csv")]
                    if _parecer:
                        parecer_dfp_count += 1
            except Exception:
                pass

        # ITR (quarterly)
        itr_path = raw_dir / f"itr_cia_aberta_{year}.zip"
        if _download_file(f"{BASE_URL_ITR}/itr_cia_aberta_{year}.zip", itr_path):
            files_downloaded.append(itr_path.name)
            rows, dates = _count_dre_rows_in_zip(itr_path, company_key, exclude)
            itr_rows += rows
            all_dates.extend(dates)
            stmt_info = _count_statement_rows_in_zip(
                itr_path, company_key, exclude, _STATEMENT_TYPES
            )
            for ft, info in stmt_info.items():
                if info["found"]:
                    itr_file_counts[ft] += 1
                total_rows_by_ft[ft] += info["rows"]

    date_range: dict[str, object] = {"start": None, "end": None}
    if all_dates:
        sorted_dates = sorted(set(all_dates))
        date_range = {"start": sorted_dates[0], "end": sorted_dates[-1]}

    statements_found = [
        {
            "type": "dre",
            "dfp_files": dfp_file_counts["dre_con"],
            "itr_files": itr_file_counts["dre_con"],
            "total_rows": total_rows_by_ft["dre_con"],
        },
        {
            "type": "bpa",
            "dfp_files": dfp_file_counts["bpa_con"],
            "itr_files": itr_file_counts["bpa_con"],
            "total_rows": total_rows_by_ft["bpa_con"],
        },
        {
            "type": "bpp",
            "dfp_files": dfp_file_counts["bpp_con"],
            "itr_files": itr_file_counts["bpp_con"],
            "total_rows": total_rows_by_ft["bpp_con"],
        },
        {
            "type": "dfc",
            "dfp_files": dfp_file_counts["dfc_mi_con"],
            "itr_files": itr_file_counts["dfc_mi_con"],
            "total_rows": total_rows_by_ft["dfc_mi_con"],
        },
        {
            "type": "dva",
            "dfp_files": dfp_file_counts["dva_con"],
            "itr_files": itr_file_counts["dva_con"],
            "total_rows": total_rows_by_ft["dva_con"],
        },
        {
            "type": "dmpl",
            "dfp_files": dfp_file_counts["dmpl_con"],
            "itr_files": itr_file_counts["dmpl_con"],
            "total_rows": total_rows_by_ft["dmpl_con"],
        },
        {
            "type": "dra",
            "dfp_files": dfp_file_counts["dra_con"],
            "itr_files": itr_file_counts["dra_con"],
            "total_rows": total_rows_by_ft["dra_con"],
        },
        {
            "type": "parecer",
            "dfp_files": parecer_dfp_count,
            "itr_files": 0,
            "total_rows": parecer_dfp_count,
        },
    ]

    # FRE (annual reference forms)
    # Files we actively use in the pipeline
    _FRE_FILE_TYPES = [
        ("auditor",       "fre_cia_aberta_auditor",        "Nome_Companhia"),
        ("titulo_exterior", "fre_cia_aberta_titulo_exterior", "Nome_Companhia"),
    ]

    fre_dir = raw_dir / "fre"
    fre_dir.mkdir(parents=True, exist_ok=True)
    fre_files_downloaded: list[str] = []
    fre_file_sizes: list[int] = []

    # Per-file-type counts across all years
    fre_year_counts:     dict[str, int]   = {k: 0 for k, _, _ in _FRE_FILE_TYPES}
    fre_row_counts:      dict[str, int]   = {k: 0 for k, _, _ in _FRE_FILE_TYPES}

    for year in years:
        fre_path = fre_dir / f"fre_cia_aberta_{year}.zip"
        ok = _download_file(f"{BASE_URL_FRE}/fre_cia_aberta_{year}.zip", fre_path)
        if not (ok and fre_path.exists()):
            continue
        fre_files_downloaded.append(fre_path.name)
        fre_file_sizes.append(fre_path.stat().st_size)

        # Count company rows in each used file type
        try:
            with zipfile.ZipFile(fre_path, "r") as zf:
                for ftype, prefix, name_col in _FRE_FILE_TYPES:
                    matched = [n for n in zf.namelist() if prefix in n and n.endswith(".csv")]
                    if not matched:
                        continue
                    fre_year_counts[ftype] += 1
                    try:
                        with zf.open(matched[0]) as f:
                            df = pd.read_csv(
                                f, sep=";", encoding="latin-1",
                                low_memory=False, usecols=[name_col],
                            )
                        mask = df[name_col].str.upper().str.contains(
                            company_key, na=False
                        )
                        for excl in exclude:
                            mask &= ~df[name_col].str.upper().str.contains(excl, na=False)
                        fre_row_counts[ftype] += int(mask.sum())
                    except Exception:
                        pass
        except (zipfile.BadZipFile, FileNotFoundError):
            pass

    fre_total_size = sum(fre_file_sizes)
    fre_size_mb = round(fre_total_size / (1024 * 1024), 1) if fre_total_size else 0

    fre_statements_found = [
        {
            "type":       ftype,
            "fre_files":  fre_year_counts[ftype],
            "total_rows": fre_row_counts[ftype],
        }
        for ftype, _, _ in _FRE_FILE_TYPES
    ]

    return {
        "dfp_rows": dfp_rows,
        "itr_rows": itr_rows,
        "total_rows": dfp_rows + itr_rows,
        "company": company_name,
        "date_range": date_range,
        "files_downloaded": files_downloaded,
        "statements_found": statements_found,
        "fre_files_downloaded": fre_files_downloaded,
        "fre_files_count": len(fre_files_downloaded),
        "fre_size_mb": fre_size_mb,
        "fre_statements_found": fre_statements_found,
        "source": "live",
    }
