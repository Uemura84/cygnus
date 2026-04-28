"""FRE (Formulário de Referência) data parser.

Reads CVM FRE ZIP archives and extracts:
  - Auditor profiles (firm, tenure, fees) from fre_cia_aberta_auditor_YYYY.csv
  - Foreign bond obligations (maturity, amount) from fre_cia_aberta_titulo_exterior_YYYY.csv

Public API
----------
parse_fre_auditor(data_dir, company_name, years) -> list[dict]
    Returns one AuditorProfile dict per year (latest version), sorted by year ascending.

parse_fre_foreign_bonds(data_dir, company_name, years) -> list[dict]
    Returns list of ForeignBondObligation dicts for the latest available year.

Both functions return [] when FRE data is unavailable or the company has no records.
They never raise — all errors are silently swallowed to preserve graceful degradation.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Fee regex: extract BRL millions from free-text Remuneracao_Auditor
# Examples:
#   "serviços de auditoria no valor de R$ 42,8 milhões"
#   "serviços relacionados a auditoria no valor de R$ 3,4 milhões"
#   "serviços da área de impostos de R$ 2,7 milhões"
# ---------------------------------------------------------------------------

_AUDIT_FEE_PATTERNS = [
    # "auditoria no valor de R$ 42,8 milhões" — explicit audit fee
    re.compile(
        r"(?:auditoria[^R$]*)[Rr]\$\s*([\d,.]+)\s*milh[oõ]",
        re.IGNORECASE | re.DOTALL,
    ),
]

_NON_AUDIT_FEE_PATTERNS = [
    # "serviços relacionados a auditoria no valor de R$ 3,4 milhões"
    re.compile(
        r"(?:relacionados?[^R$]*|impostos?[^R$]*|outros servi[çc]os[^R$]*)[Rr]\$\s*([\d,.]+)\s*milh[oõ]",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Broader fallback: find all "R$ N milhões" in the text
_ALL_BRL_MILLIONS = re.compile(
    r"[Rr]\$\s*([\d,.]+)\s*milh[oõ]", re.IGNORECASE
)


def _parse_brl_millions(text: str) -> float:
    """Convert Brazilian-formatted BRL millions string to BRL thousands.

    '42,8' → 42_800.0 (BRL thousands, to match pipeline's standard unit)
    Pipeline standard: BRL thousands (same as balance sheet series).
    """
    if not text:
        return 0.0
    # Replace Brazilian decimal comma with dot
    normalized = text.replace(".", "").replace(",", ".")
    try:
        return float(normalized) * 1_000  # millions → thousands
    except ValueError:
        return 0.0


def _extract_fees(remuneration_text: str) -> tuple[float, float]:
    """Extract (audit_fees, non_audit_fees) in full BRL from free-text field.

    Strategy:
    1. Find the first BRL amount (assume audit fee — it's always listed first).
    2. Sum remaining amounts as non-audit fees.
    Returns (0.0, 0.0) when no amounts found.
    """
    if not remuneration_text or pd.isna(remuneration_text):
        return 0.0, 0.0

    text = str(remuneration_text)
    all_amounts = _ALL_BRL_MILLIONS.findall(text)
    if not all_amounts:
        return 0.0, 0.0

    audit_fee = _parse_brl_millions(all_amounts[0])
    non_audit_fee = sum(_parse_brl_millions(a) for a in all_amounts[1:])
    return audit_fee, non_audit_fee


def _company_match(series: pd.Series, company_name: str) -> pd.Series:
    """Return boolean mask matching company_name. Exact match first, fallback to first-word."""
    upper = series.str.upper().str.strip()
    full_name = company_name.strip().upper()
    exact = upper == full_name
    if exact.any():
        return exact
    key = company_name.split()[0].upper()
    return upper.str.contains(key, na=False)


def _latest_version(df: pd.DataFrame, date_col: str = "Data_Referencia", ver_col: str = "Versao") -> pd.DataFrame:
    """Keep only the highest-version row per (company, year) combination."""
    if df.empty:
        return df
    try:
        df = df.copy()
        df["_year"] = pd.to_datetime(df[date_col], errors="coerce").dt.year
        df = df.sort_values(ver_col, ascending=False)
        df = df.drop_duplicates(subset=["Nome_Companhia", "_year"], keep="first")
        df = df.drop(columns=["_year"])
    except Exception:
        pass
    return df


# ---------------------------------------------------------------------------
# Public: parse_fre_auditor
# ---------------------------------------------------------------------------

def parse_fre_auditor(data_dir: Path, company_name: str, years: list[int]) -> list[dict]:
    """Return a list of AuditorProfile dicts, one per FRE year available.

    AuditorProfile dict keys:
        period           str  "YYYY-12-31" (FRE reference date)
        firm_name        str
        firm_cnpj        str
        audit_fees       float  full BRL
        non_audit_fees   float  full BRL
        service_start_date str  ISO date or ""
        tenure_years     int
        non_audit_ratio  float  (non_audit_fees / audit_fees) or 0.0
    """
    fre_dir = data_dir / "raw" / "fre"
    if not fre_dir.exists():
        return []

    profiles: list[dict] = []

    for year in sorted(years):
        zip_path = fre_dir / f"fre_cia_aberta_{year}.zip"
        if not zip_path.exists():
            continue
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                csv_names = [n for n in zf.namelist() if "fre_cia_aberta_auditor_" in n and n.endswith(".csv")]
                if not csv_names:
                    continue
                with zf.open(csv_names[0]) as f:
                    df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
        except Exception:
            continue

        mask = _company_match(df["Nome_Companhia"], company_name)
        df = df[mask]
        if df.empty:
            continue

        df = _latest_version(df)
        if df.empty:
            continue

        row = df.sort_values("Versao", ascending=False).iloc[0]

        audit_fees, non_audit_fees = _extract_fees(row.get("Remuneracao_Auditor", ""))
        start_date_str = str(row.get("Data_Inicio_Contratacao", "") or "").strip()
        # Service start date (added by CVM in 2023+)
        svc_start_str = str(row.get("Data_Inicio_Prestacao_Servico", "") or "").strip()

        # Compute tenure from Data_Inicio_Contratacao to this FRE year
        tenure_years = 0
        try:
            start = date.fromisoformat(start_date_str[:10])
            ref_year = int(str(row.get("Data_Referencia", f"{year}-12-31"))[:4])
            tenure_years = max(0, ref_year - start.year)
        except Exception:
            pass

        non_audit_ratio = (non_audit_fees / audit_fees) if audit_fees > 0 else 0.0

        period = str(row.get("Data_Referencia", f"{year}-12-31"))[:10]
        if len(period) == 4:
            period = f"{period}-12-31"

        profiles.append({
            "period":             period,
            "firm_name":          str(row.get("Auditor", "Unknown")).strip(),
            "firm_cnpj":          str(row.get("CNPJ_Auditor", "")).strip(),
            "audit_fees":         audit_fees,
            "non_audit_fees":     non_audit_fees,
            "service_start_date": svc_start_str,
            "tenure_years":       tenure_years,
            "non_audit_ratio":    round(non_audit_ratio, 3),
        })

    return sorted(profiles, key=lambda p: p["period"])


# ---------------------------------------------------------------------------
# Public: parse_fre_foreign_bonds
# ---------------------------------------------------------------------------

def parse_fre_foreign_bonds(data_dir: Path, company_name: str, years: list[int]) -> list[dict]:
    """Return a list of ForeignBondObligation dicts for the latest available FRE year.

    Note: fre_cia_aberta_titulo_exterior contains foreign-market-listed securities.
    All are assumed to be USD-denominated (no currency column present).
    Saldo_Devedor is in full BRL (already converted at reporting date rate).

    ForeignBondObligation dict keys:
        period              str  "YYYY-12-31"
        instrument_type     str  e.g. "Debêntures"
        identification      str  ISIN or description
        maturity_date       str  ISO date or "Indeterminado"
        outstanding_amount  float  BRL (full)
        currency            str  "USD" (assumed for all titulo_exterior)
    """
    fre_dir = data_dir / "raw" / "fre"
    if not fre_dir.exists():
        return []

    # Try years in reverse order — use the latest year with data
    for year in sorted(years, reverse=True):
        zip_path = fre_dir / f"fre_cia_aberta_{year}.zip"
        if not zip_path.exists():
            continue
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                csv_names = [n for n in zf.namelist() if "fre_cia_aberta_titulo_exterior_" in n and n.endswith(".csv")]
                if not csv_names:
                    continue
                with zf.open(csv_names[0]) as f:
                    df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
        except Exception:
            continue

        mask = _company_match(df["Nome_Companhia"], company_name)
        df = df[mask].copy()
        if df.empty:
            continue

        # Keep only the latest submission version (all bond rows at that version)
        max_ver = df["Versao"].max()
        df = df[df["Versao"] == max_ver].copy()

        period_raw = str(df["Data_Referencia"].iloc[0])[:10]
        obligations: list[dict] = []

        for _, row in df.iterrows():
            maturity_raw = str(row.get("Data_Vencimento", "") or "").strip()
            maturity_date = "Indeterminado"
            try:
                if maturity_raw and maturity_raw.lower() not in ("nan", "", "indeterminado"):
                    maturity_date = date.fromisoformat(maturity_raw[:10]).isoformat()
            except Exception:
                pass

            saldo = row.get("Saldo_Devedor", 0)
            try:
                # FRE Saldo_Devedor is in full BRL; convert to BRL thousands
                # to match the pipeline's standard unit (same as balance sheet series)
                amount = float(str(saldo).replace(",", ".")) / 1000.0
            except Exception:
                amount = 0.0

            obligations.append({
                "period":             period_raw,
                "instrument_type":    str(row.get("Valor_Mobiliario", "Unknown")).strip(),
                "identification":     str(row.get("Identificacao_Valor_Mobiliario", "") or "").strip(),
                "maturity_date":      maturity_date,
                "outstanding_amount": amount,
                "currency":           "USD",  # titulo_exterior = foreign market = assumed USD
            })

        if obligations:
            return sorted(obligations, key=lambda o: o["maturity_date"])

    return []
