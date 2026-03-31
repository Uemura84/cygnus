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

# Holding/parent entities that share a company name fragment but duplicate
# the operating company's numbers. Extend per company as needed (Phase 2).
EXCLUDE_MAP: dict[str, list[str]] = {
    "BRASKEM": [],          # No separate listed holding for Braskem
    "SUZANO":  ["SUZANO HOLDING"],
    "GERDAU":  ["METALURGICA GERDAU"],
}


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

    for year in years:
        # DFP (annual)
        dfp_path = raw_dir / f"dfp_cia_aberta_{year}.zip"
        if _download_file(f"{BASE_URL_DFP}/dfp_cia_aberta_{year}.zip", dfp_path):
            files_downloaded.append(dfp_path.name)
            rows, dates = _count_dre_rows_in_zip(dfp_path, company_key, exclude)
            dfp_rows += rows
            all_dates.extend(dates)

        # ITR (quarterly)
        itr_path = raw_dir / f"itr_cia_aberta_{year}.zip"
        if _download_file(f"{BASE_URL_ITR}/itr_cia_aberta_{year}.zip", itr_path):
            files_downloaded.append(itr_path.name)
            rows, dates = _count_dre_rows_in_zip(itr_path, company_key, exclude)
            itr_rows += rows
            all_dates.extend(dates)

    date_range: dict[str, object] = {"start": None, "end": None}
    if all_dates:
        sorted_dates = sorted(set(all_dates))
        date_range = {"start": sorted_dates[0], "end": sorted_dates[-1]}

    return {
        "dfp_rows": dfp_rows,
        "itr_rows": itr_rows,
        "total_rows": dfp_rows + itr_rows,
        "company": company_name,
        "date_range": date_range,
        "files_downloaded": files_downloaded,
        "source": "live",
    }
