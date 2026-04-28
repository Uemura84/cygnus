"""DVA (Demonstração de Valor Adicionado) parser.

Parses Value Added Statement CSV files from DFP/ITR ZIPs.

Public API
----------
parse_dva(company_name, data_dir, years) -> tuple[list[dict], dict]
    Returns (records, stats).
    Each record: {"period", "period_type", "revenues", "third_party_inputs",
                  "gross_value_added", "retentions", "net_value_added",
                  "value_received", "total_to_distribute",
                  "employees", "government", "lenders", "shareholders"}
"""

import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ORDEM_EXERC_KEEP = "ÚLTIMO"

# Parent-level DVA account codes to extract (exact match; children are aggregated into parent by CVM)
_DVA_ACCOUNTS = {
    "7.01":    "revenues",
    "7.02":    "third_party_inputs",
    "7.03":    "gross_value_added",
    "7.04":    "retentions",
    "7.05":    "net_value_added",
    "7.06":    "value_received",
    "7.07":    "total_to_distribute",
    "7.08.01": "employees",
    "7.08.02": "government",
    "7.08.03": "lenders",
    "7.08.04": "shareholders",
}


def _read_dva_from_zips(company_name: str, data_dir: Path, years: list) -> pd.DataFrame:
    """Read all dva_con CSV files from DFP/ITR ZIPs, filtered to company."""
    company_full = company_name.strip().upper()
    company_key  = company_name.split()[0].upper()
    raw_dir = data_dir / "raw"
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
                        if "dva_con" in n.lower() and n.endswith(".csv")
                    ]
                    for csv_file in csv_files:
                        try:
                            with zf.open(csv_file) as f:
                                df = pd.read_csv(f, sep=";", encoding="latin-1",
                                                 low_memory=False)
                            if "DENOM_CIA" not in df.columns:
                                continue
                            if "ORDEM_EXERC" in df.columns:
                                df = df[df["ORDEM_EXERC"] == ORDEM_EXERC_KEEP].copy()
                            # Exact match first; fall back to first-word match
                            exact = df["DENOM_CIA"].str.upper().str.strip() == company_full
                            if exact.any():
                                df = df[exact].copy()
                            else:
                                df = df[df["DENOM_CIA"].str.upper().str.contains(
                                    company_key, na=False)].copy()
                            if not df.empty:
                                df["_doc_type"] = doc_type.upper()
                                frames.append(df)
                        except Exception:
                            continue
            except (zipfile.BadZipFile, FileNotFoundError):
                continue

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parse_dva(company_name: str, data_dir: Path, years: list) -> tuple:
    """Parse DVA_con from raw ZIPs into per-period records.

    Returns (list[dict], stats_dict).
    records are sorted by period date ascending.
    """
    raw = _read_dva_from_zips(company_name, data_dir, years)
    if raw.empty:
        return [], {
            "records_loaded": 0, "records_after_filter": 0,
            "annual_periods": 0, "quarterly_periods": 0,
            "periods_available": 0,
        }

    records_loaded = len(raw)

    # Monetary scale normalisation
    raw["VL_CONTA"] = pd.to_numeric(raw["VL_CONTA"], errors="coerce")
    if "ESCALA_MOEDA" in raw.columns:
        raw.loc[raw["ESCALA_MOEDA"] == "UNIDADE", "VL_CONTA"] /= 1000

    # DFP/ITR dedup: DFP=0, ITR standalone=1, ITR YTD=2
    if "DT_INI_EXERC" in raw.columns:
        ini_dt = pd.to_datetime(raw["DT_INI_EXERC"], errors="coerce")
        ref_dt = pd.to_datetime(raw["DT_REFER"],    errors="coerce")
        is_ytd = (
            (raw["_doc_type"] == "ITR") &
            (ini_dt.dt.month == 1) & (ini_dt.dt.day == 1) &
            (ini_dt.dt.year == ref_dt.dt.year) &
            (ref_dt.dt.month != 3)
        )
        raw["_row_priority"] = 1
        raw.loc[raw["_doc_type"] == "DFP", "_row_priority"] = 0
        raw.loc[is_ytd, "_row_priority"] = 2
    else:
        raw["_row_priority"] = raw["_doc_type"].map({"DFP": 0, "ITR": 1}).fillna(2)

    raw = (
        raw.sort_values("_row_priority")
           .drop_duplicates(subset=["DENOM_CIA", "DT_REFER", "CD_CONTA"], keep="first")
    )
    records_after_filter = len(raw)

    results: list[dict] = []
    annual_count = 0
    quarterly_count = 0

    for (co, period_str, doc_type), grp in raw.groupby(["DENOM_CIA", "DT_REFER", "_doc_type"]):
        try:
            pd.to_datetime(period_str)
        except Exception:
            continue

        record: dict = {
            "period":      period_str,
            "period_type": "annual" if doc_type == "DFP" else "quarterly",
            "doc_type":    doc_type,
        }

        # Extract each target account (exact CD_CONTA match at parent level)
        for code, field in _DVA_ACCOUNTS.items():
            rows = grp[grp["CD_CONTA"] == code]
            if not rows.empty:
                val = rows["VL_CONTA"].iloc[0]
                record[field] = float(val) if pd.notna(val) else None
            else:
                record[field] = None

        # Derived metrics (annual only — quarterly data may be incomplete)
        if doc_type == "DFP":
            total = record.get("total_to_distribute")
            rev   = record.get("revenues")
            nva   = record.get("net_value_added")

            for field in ("employees", "government", "lenders", "shareholders"):
                val = record.get(field)
                if total and total != 0 and val is not None:
                    record[f"{field}_share_pct"] = round(val / total * 100, 2)
                else:
                    record[f"{field}_share_pct"] = None

            record["va_margin_pct"] = (
                round(nva / rev * 100, 2)
                if (nva is not None and rev is not None and rev != 0)
                else None
            )
            record["input_intensity_pct"] = (
                round(abs(record["third_party_inputs"]) / rev * 100, 2)
                if (record.get("third_party_inputs") is not None and rev is not None and rev != 0)
                else None
            )
            annual_count += 1
        else:
            for field in ("employees", "government", "lenders", "shareholders"):
                record[f"{field}_share_pct"] = None
            record["va_margin_pct"] = None
            record["input_intensity_pct"] = None
            quarterly_count += 1

        results.append(record)

    results.sort(key=lambda r: r["period"])

    stats = {
        "records_loaded":    records_loaded,
        "records_after_filter": records_after_filter,
        "annual_periods":    annual_count,
        "quarterly_periods": quarterly_count,
        "periods_available": len(results),
    }
    logger.info(
        "parse_dva: %s → %d periods (%d annual, %d quarterly)",
        company_name, len(results), annual_count, quarterly_count,
    )
    return results, stats
