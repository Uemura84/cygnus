"""DRA (Demonstração do Resultado Abrangente) parser.

Parses Comprehensive Income Statement CSV files from DFP/ITR ZIPs.

Public API
----------
parse_dra(company_name, data_dir, years) -> tuple[list[dict], dict]
    Returns (records, stats).
    Each record: {"period", "period_type", "net_income", "oci_total",
                  "total_comprehensive_income", "oci_fx", "oci_hedge",
                  "oci_actuarial", "comprehensive_income_ratio"}
"""

import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ORDEM_EXERC_KEEP = "ÚLTIMO"

# CD_CONTA → field mapping for well-known DRA accounts
_DRA_CODES = {
    "4.01": "net_income",
    "4.02": "oci_total",
    "4.03": "total_comprehensive_income",
}

# DS_CONTA keyword patterns for OCI sub-components (case-insensitive contains)
_OCI_KEYWORDS = {
    "oci_fx":         ["conversão de operações", "variação cambial", "diferença de conversão",
                       "ajuste de conversão"],
    "oci_hedge":      ["hedge", "proteção", "instrumento de hedge", "proteção cambial"],
    "oci_actuarial":  ["atuarial", "benefícios pós-emprego", "plano de benefícios definidos"],
}

# Fallback keyword patterns for top-level accounts when CD_CONTA doesn't match
_DRA_KEYWORDS = {
    "net_income":               ["lucro líquido", "lucro/prejuízo do período",
                                  "lucro ou prejuízo", "resultado do período"],
    "oci_total":                ["outros resultados abrangentes"],
    "total_comprehensive_income": ["resultado abrangente", "resultado abrangente total",
                                    "resultado abrangente consolidado"],
}


def _read_dra_from_zips(company_name: str, data_dir: Path, years: list) -> pd.DataFrame:
    """Read all dra_con CSV files from DFP/ITR ZIPs, filtered to company."""
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
                        if "dra_con" in n.lower() and n.endswith(".csv")
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


def _extract_by_code(grp: pd.DataFrame, code: str) -> float | None:
    rows = grp[grp["CD_CONTA"] == code]
    if not rows.empty:
        val = rows["VL_CONTA"].iloc[0]
        return float(val) if pd.notna(val) else None
    return None


def _extract_by_keywords(grp: pd.DataFrame, keywords: list[str]) -> float | None:
    for _, row in grp.iterrows():
        desc = str(row.get("DS_CONTA", "")).lower()
        for kw in keywords:
            if kw in desc:
                val = row.get("VL_CONTA")
                return float(val) if val is not None and pd.notna(val) else None
    return None


def _extract_oci_subcomponent(grp: pd.DataFrame, field: str) -> float | None:
    """Extract OCI sub-component by keyword, only from rows under 4.02 (CD_CONTA starts with 4.02.)."""
    sub_grp = grp[grp["CD_CONTA"].str.startswith("4.02.", na=False)]
    if sub_grp.empty:
        sub_grp = grp  # fallback to full group if no 4.02.x rows
    return _extract_by_keywords(sub_grp, _OCI_KEYWORDS[field])


def parse_dra(company_name: str, data_dir: Path, years: list) -> tuple:
    """Parse DRA_con from raw ZIPs into per-period records.

    Returns (list[dict], stats_dict).
    Records are sorted by period date ascending.
    """
    raw = _read_dra_from_zips(company_name, data_dir, years)
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

        # Extract top-level accounts: try exact CD_CONTA first, then keyword fallback
        for code, field in _DRA_CODES.items():
            val = _extract_by_code(grp, code)
            if val is None:
                val = _extract_by_keywords(grp, _DRA_KEYWORDS[field])
            record[field] = val

        # Extract OCI sub-components (best-effort, may be None for many companies)
        for field in _OCI_KEYWORDS:
            record[field] = _extract_oci_subcomponent(grp, field)

        # Derived: comprehensive income ratio = total_ci / net_income
        ci  = record.get("total_comprehensive_income")
        ni  = record.get("net_income")
        if ci is not None and ni is not None and ni != 0:
            record["comprehensive_income_ratio"] = round(ci / ni, 4)
        else:
            record["comprehensive_income_ratio"] = None

        # OCI as % of net income (useful for materiality check in Step 5)
        oci = record.get("oci_total")
        if oci is not None and ni is not None and ni != 0:
            record["oci_pct_net_income"] = round(oci / abs(ni) * 100, 2)
        else:
            record["oci_pct_net_income"] = None

        if doc_type == "DFP":
            annual_count += 1
        else:
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
        "parse_dra: %s → %d periods (%d annual, %d quarterly)",
        company_name, len(results), annual_count, quarterly_count,
    )
    return results, stats
