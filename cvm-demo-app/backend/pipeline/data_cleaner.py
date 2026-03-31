"""CVM data preparation / cleaning.

Refactored from 01_download_and_parse.py — parse + filter logic only.
Reads already-downloaded ZIPs from data_dir/raw/ and applies the three
sequential filters that make up Step 2 of the pipeline.

Public API
----------
prepare(company_name, data_dir, years) -> dict
    Reads raw ZIPs, applies DRE / ORDEM_EXERC / holding filters.
    Saves filtered DRE CSV to data_dir/processed/ for downstream steps.
    Returns the Step 2 result data dict.
"""
import zipfile
from pathlib import Path

import pandas as pd

# CVM ITR/DFP files carry both ÚLTIMO (current) and PENÚLTIMO (prior-year
# restated comparison) rows.  We keep only ÚLTIMO to avoid double-counting.
ORDEM_EXERC_KEEP = "ÚLTIMO"

# DRE account prefix — income-statement accounts all start with "3."
DRE_ACCOUNT_PREFIX = "3."

# Same holding-exclusion map as cvm_downloader (keep in sync or centralise).
EXCLUDE_MAP: dict[str, list[str]] = {
    "BRASKEM": [],
    "SUZANO":  ["SUZANO HOLDING"],
    "GERDAU":  ["METALURGICA GERDAU"],
}


def _company_search_key(company_name: str) -> str:
    return company_name.split()[0].upper()


def _read_dre_from_zip(zip_path: Path) -> pd.DataFrame:
    """Extract all *_DRE_con*.csv files from *zip_path* into one DataFrame."""
    frames = []
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
                        )
                        df["_source_file"] = csv_file
                        frames.append(df)
                except Exception:
                    continue
    except (zipfile.BadZipFile, FileNotFoundError):
        pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def prepare(company_name: str, data_dir: Path, years: list[int]) -> dict:
    """Read raw ZIPs and apply the three Step 2 filters in sequence.

    Filter waterfall (matching the spec):
      1. DRE accounts only       (CD_CONTA starts with '3.')
      2. ORDEM_EXERC = ÚLTIMO    (drop prior-year restated rows)
      3. Holding company exclusion

    Returns the Step 2 ``data`` shape and saves a filtered CSV for Step 3.
    """
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    company_key = _company_search_key(company_name)
    exclude = EXCLUDE_MAP.get(company_key, [])

    # ------------------------------------------------------------------ #
    # 1. Load all raw DRE data for the target company                     #
    # ------------------------------------------------------------------ #
    all_frames = []
    for year in years:
        for doc_type in ("dfp", "itr"):
            zip_path = raw_dir / f"{doc_type}_cia_aberta_{year}.zip"
            if not zip_path.exists():
                continue
            df = _read_dre_from_zip(zip_path)
            if df.empty or "DENOM_CIA" not in df.columns:
                continue
            # Company filter (applied here so we don't carry all companies forward)
            mask = df["DENOM_CIA"].str.upper().str.contains(company_key, na=False)
            for excl in exclude:
                mask &= ~df["DENOM_CIA"].str.upper().str.contains(excl, na=False)
            df = df[mask].copy()
            if not df.empty:
                df["_doc_type"] = doc_type.upper()
                all_frames.append(df)

    if not all_frames:
        return {
            "raw_rows": 0,
            "after_dre_filter": 0,
            "after_ordem_exerc": 0,
            "after_holding_exclusion": 0,
            "filters_applied": [],
            "source": "live",
            "error": f"No data found for {company_name}",
        }

    raw_df = pd.concat(all_frames, ignore_index=True)
    raw_rows = len(raw_df)

    # ------------------------------------------------------------------ #
    # Filter 1: DRE accounts only (CD_CONTA starts with '3.')            #
    # ------------------------------------------------------------------ #
    if "CD_CONTA" in raw_df.columns:
        dre_mask = raw_df["CD_CONTA"].astype(str).str.startswith(DRE_ACCOUNT_PREFIX)
        after_dre_df = raw_df[dre_mask].copy()
    else:
        after_dre_df = raw_df.copy()

    after_dre = len(after_dre_df)
    removed_dre = raw_rows - after_dre

    # ------------------------------------------------------------------ #
    # Filter 2: ORDEM_EXERC = ÚLTIMO                                     #
    # ------------------------------------------------------------------ #
    if "ORDEM_EXERC" in after_dre_df.columns:
        ordem_mask = after_dre_df["ORDEM_EXERC"] == ORDEM_EXERC_KEEP
        after_ordem_df = after_dre_df[ordem_mask].copy()
    else:
        after_ordem_df = after_dre_df.copy()

    after_ordem = len(after_ordem_df)
    removed_ordem = after_dre - after_ordem

    # ------------------------------------------------------------------ #
    # Filter 3: Holding company exclusion                                #
    # (already applied during load for company_key, but for other        #
    # fragments that might slip through we re-apply explicitly)          #
    # ------------------------------------------------------------------ #
    holding_df = after_ordem_df.copy()
    if exclude:
        for excl in exclude:
            holding_df = holding_df[
                ~holding_df["DENOM_CIA"].str.upper().str.contains(excl, na=False)
            ]

    after_holding = len(holding_df)
    removed_holding = after_ordem - after_holding

    # ------------------------------------------------------------------ #
    # Save filtered DRE for downstream steps (Step 3 reads this)         #
    # ------------------------------------------------------------------ #
    out_path = processed_dir / f"dre_filtered_{company_key.lower()}.csv"
    holding_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    return {
        "raw_rows": raw_rows,
        "after_dre_filter": after_dre,
        "after_ordem_exerc": after_ordem,
        "after_holding_exclusion": after_holding,
        "filters_applied": [
            {
                "name": "DRE accounts only",
                "removed": removed_dre,
                "reason": "Non-income statement accounts excluded (CD_CONTA not starting with '3.')",
            },
            {
                "name": "ORDEM_EXERC = ÚLTIMO",
                "removed": removed_ordem,
                "reason": "Prior-year restated comparison rows removed",
            },
            {
                "name": "Holding company exclusion",
                "removed": removed_holding,
                "reason": "Separate holding-entity rows excluded to avoid double-counting",
            },
        ],
        "filtered_file": str(out_path),
        "source": "live",
    }
