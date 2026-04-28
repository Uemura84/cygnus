"""DMPL (Demonstração das Mutações do Patrimônio Líquido) parser.

Parses Changes in Equity CSV files from DFP/ITR ZIPs.
Focuses on the "Patrimônio Líquido Consolidado" column (total equity) to extract
equity movements: net income, dividends declared, OCI, opening/closing equity.

Public API
----------
parse_dmpl(company_name, data_dir, years) -> tuple[list[dict], dict]
    Returns (records, stats).
    Each record: {"period", "period_type", "net_income", "dividends_declared",
                  "jcp_declared", "total_dividends", "treasury_shares_net",
                  "capital_increase", "oci_total", "opening_equity", "closing_equity"}
"""

import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ORDEM_EXERC_KEEP = "ÚLTIMO"

# COLUNA_DF value identifying total consolidated equity (the only column we need)
_TOTAL_EQUITY_COLUMN = "Patrimônio Líquido Consolidado"

# CD_CONTA → field mapping for well-known accounts
_DMPL_CODES = {
    "5.01":    "opening_equity",       # Saldos Iniciais
    "5.07":    "closing_equity",       # Saldos Finais
    "5.05.01": "net_income",           # Lucro/Prejuízo do Período
    "5.04.06": "dividends_declared",   # Dividendos
    "5.04.07": "jcp_declared",         # Juros sobre Capital Próprio
    "5.04.12": "dividends_additional", # Dividendos adicionais
    "5.04.14": "dividends_proposed",   # Dividendos propostos
    "5.04.04": "treasury_acquired",    # Ações em Tesouraria Adquiridas
    "5.04.05": "treasury_sold",        # Ações em Tesouraria Vendidas
    "5.04.01": "capital_increase",     # Aumentos de Capital
    "5.05.02": "oci_total",            # Outros Resultados Abrangentes
}

# DS_CONTA keyword fallback patterns (case-insensitive contains)
_DS_KEYWORDS = {
    "dividends_declared": ["dividendos", "dividendo"],
    "jcp_declared":       ["juros sobre capital próprio", "jcp"],
    "net_income":         ["lucro líquido", "resultado do exercício", "lucro/prejuízo do período",
                           "lucro ou prejuízo do período"],
    "oci_total":          ["outros resultados abrangentes", "resultado abrangente total"],
    "opening_equity":     ["saldos iniciais ajustados", "saldos iniciais"],
    "closing_equity":     ["saldos finais"],
    "capital_increase":   ["aumentos de capital", "aumento de capital"],
    "treasury_acquired":  ["ações em tesouraria adquiridas"],
    "treasury_sold":      ["ações em tesouraria vendidas"],
}


def _read_dmpl_from_zips(company_name: str, data_dir: Path, years: list) -> pd.DataFrame:
    """Read all dmpl_con CSV files from DFP/ITR ZIPs, filtered to company."""
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
                        if "dmpl_con" in n.lower() and n.endswith(".csv")
                    ]
                    for csv_file in csv_files:
                        try:
                            with zf.open(csv_file) as f:
                                df = pd.read_csv(f, sep=";", encoding="latin-1",
                                                 low_memory=False)
                            if "DENOM_CIA" not in df.columns or "COLUNA_DF" not in df.columns:
                                continue
                            if "ORDEM_EXERC" in df.columns:
                                df = df[df["ORDEM_EXERC"] == ORDEM_EXERC_KEEP].copy()
                            exact = df["DENOM_CIA"].str.upper().str.strip() == company_full
                            if exact.any():
                                df = df[exact].copy()
                            else:
                                df = df[df["DENOM_CIA"].str.upper().str.contains(
                                    company_key, na=False)].copy()
                            # Filter to total consolidated equity column
                            equity_mask = (
                                df["COLUNA_DF"].str.strip() == _TOTAL_EQUITY_COLUMN
                            )
                            if not equity_mask.any():
                                # Fallback: contains match
                                equity_mask = df["COLUNA_DF"].str.contains(
                                    _TOTAL_EQUITY_COLUMN, na=False)
                            df = df[equity_mask].copy()
                            if not df.empty:
                                df["_doc_type"] = doc_type.upper()
                                frames.append(df)
                        except Exception:
                            continue
            except (zipfile.BadZipFile, FileNotFoundError):
                continue

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _extract_field(grp: pd.DataFrame, field: str) -> float | None:
    """Extract a single field value from a group using code+keyword matching."""
    # 1. Try exact CD_CONTA match
    for code, f in _DMPL_CODES.items():
        if f == field:
            rows = grp[grp["CD_CONTA"] == code]
            if not rows.empty:
                val = rows["VL_CONTA"].iloc[0]
                return float(val) if pd.notna(val) else None

    # 2. Fallback: DS_CONTA keyword search
    keywords = _DS_KEYWORDS.get(field, [])
    for _, row in grp.iterrows():
        desc = str(row.get("DS_CONTA", "")).lower()
        for kw in keywords:
            if kw in desc:
                val = row.get("VL_CONTA")
                return float(val) if val is not None and pd.notna(val) else None
    return None


def parse_dmpl(company_name: str, data_dir: Path, years: list) -> tuple:
    """Parse DMPL_con from raw ZIPs into per-period records.

    Returns (list[dict], stats_dict).
    Records are sorted by period date ascending.
    """
    raw = _read_dmpl_from_zips(company_name, data_dir, years)
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

    # DFP/ITR dedup
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

        # Extract each known field
        fields = [
            "opening_equity", "closing_equity", "net_income",
            "dividends_declared", "jcp_declared", "dividends_additional",
            "dividends_proposed", "treasury_acquired", "treasury_sold",
            "capital_increase", "oci_total",
        ]
        for field in fields:
            record[field] = _extract_field(grp, field)

        # Aggregate total dividends (declared + JCP + additional + proposed)
        div_parts = [
            record.get("dividends_declared"),
            record.get("jcp_declared"),
            record.get("dividends_additional"),
            record.get("dividends_proposed"),
        ]
        non_null = [v for v in div_parts if v is not None]
        record["total_dividends"] = sum(non_null) if non_null else None

        # Net treasury activity
        t_acq  = record.get("treasury_acquired")
        t_sold = record.get("treasury_sold")
        if t_acq is not None or t_sold is not None:
            record["treasury_shares_net"] = (t_acq or 0.0) + (t_sold or 0.0)
        else:
            record["treasury_shares_net"] = None

        # Equity erosion rate (annual only)
        if doc_type == "DFP":
            opening = record.get("opening_equity")
            closing = record.get("closing_equity")
            if opening is not None and closing is not None and abs(opening) > 0:
                record["equity_erosion_pct"] = round(
                    (closing - opening) / abs(opening) * 100, 2
                )
            else:
                record["equity_erosion_pct"] = None
            annual_count += 1
        else:
            record["equity_erosion_pct"] = None
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
        "parse_dmpl: %s → %d periods (%d annual, %d quarterly)",
        company_name, len(results), annual_count, quarterly_count,
    )
    return results, stats
