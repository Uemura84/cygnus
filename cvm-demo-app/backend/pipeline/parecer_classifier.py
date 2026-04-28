"""Parecer (auditor report) extraction and LLM classification.

Parses auditor reports from DFP ZIP files and classifies them via Claude API.

Public API
----------
parse_parecer(data_dir, company_name, years) -> list[dict]
    Extract auditor report texts from downloaded DFP ZIPs.
    Returns list of {"period": "2024-12-31", "texto": "..."} dicts.

classify_parecer(reports, company_name, cache_dir, api_key) -> list[dict]
    Classify each report via Claude Sonnet. Results cached per company+period.
    Returns list of classification dicts with opinion_type, has_going_concern, etc.
"""

import json
import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_FALLBACK_CLASSIFICATION = {
    "opinion_type": "unknown",
    "has_going_concern": False,
    "has_emphasis_of_matter": False,
    "emphasis_topics": [],
    "key_audit_matters": [],
    "auditor_firm": "Unknown",
    "opinion_summary": "Classification failed — review manually",
    "classification_error": True,
}

_VALID_OPINION_TYPES = {"sem_ressalva", "com_ressalva", "adverso", "abstencao"}

_CLASSIFY_SYSTEM_TEMPLATE = (
    "You are a Brazilian audit specialist analyzing CVM auditor reports (pareceres). "
    "Extract structured information from the auditor's report text. "
    "Respond ONLY with a JSON object, no other text. "
    "Write all free-text fields (opinion_summary, emphasis_topics, key_audit_matters, auditor_firm) in {language}."
)

_CLASSIFY_USER_TEMPLATE = """Analyze this Brazilian auditor report and extract:

1. opinion_type: one of ["sem_ressalva", "com_ressalva", "adverso", "abstencao"]
   - sem_ressalva = unqualified (clean) opinion
   - com_ressalva = qualified opinion
   - adverso = adverse opinion
   - abstencao = disclaimer of opinion

2. has_going_concern: boolean — true if the report contains any emphasis of matter paragraph regarding going concern (continuidade operacional, continuidade dos negócios, capacidade de continuar operando)

3. has_emphasis_of_matter: boolean — true if ANY emphasis of matter paragraph exists (not just going concern)

4. emphasis_topics: list of strings — topics mentioned in emphasis of matter paragraphs (e.g., "evento geológico em Alagoas", "reestruturação societária", "processo judicial")

5. key_audit_matters: list of strings — topics from the PAA (Principais Assuntos de Auditoria) section (e.g., "recuperabilidade de ativos", "provisões e contingências", "reconhecimento de receita")

6. auditor_firm: string — name of the audit firm (e.g., "PricewaterhouseCoopers", "KPMG", "Deloitte", "Ernst & Young")

7. opinion_summary: string — one sentence summarizing the key takeaway from the report in the same language as the report

AUDITOR REPORT TEXT:
{texto}"""


def _company_search_key(company_name: str) -> str:
    return company_name.split()[0].upper()


def parse_parecer(data_dir: Path, company_name: str, years: list[int]) -> list[dict]:
    """Extract auditor report texts from DFP ZIPs.

    Only reads DFP (annual) ZIPs — the annual opinion is authoritative.
    Handles missing files and companies without Parecer gracefully.

    CVM Parecer CSV schema:
      CNPJ_CIA, DT_REFER, VERSAO, DENOM_CIA, TP_RELAT_AUD,
      TP_PARECER_DECL, NUM_ITEM_PARECER_DECL, TXT_PARECER_DECL

    Each period has multiple rows: directors' declarations, audit committee
    reports, and the independent auditor report ("Relatório do Auditor
    Independente"). We filter to the auditor report only and concatenate
    all its items (ordered by NUM_ITEM_PARECER_DECL) into a single text.

    Returns list of:
      {"period": "2024-12-31", "year": 2024, "texto": "...", "tp_relat_aud": "Sem Ressalva"}
    sorted ascending by period.
    """
    raw_dir = data_dir / "raw"
    company_key = _company_search_key(company_name)

    all_rows: list[dict] = []

    for year in years:
        dfp_path = raw_dir / f"dfp_cia_aberta_{year}.zip"
        if not dfp_path.exists():
            continue

        try:
            with zipfile.ZipFile(dfp_path, "r") as zf:
                parecer_files = [
                    name for name in zf.namelist()
                    if "parecer" in name.lower() and name.endswith(".csv")
                ]
                for csv_name in parecer_files:
                    try:
                        with zf.open(csv_name) as f:
                            df = pd.read_csv(
                                f, sep=";", encoding="latin-1", low_memory=False,
                            )
                    except Exception as exc:
                        logger.warning("parse_parecer: failed to read %s: %s", csv_name, exc)
                        continue

                    # Actual CVM schema uses TXT_PARECER_DECL, not TEXTO
                    text_col = None
                    for candidate in ("TXT_PARECER_DECL", "TEXTO"):
                        if candidate in df.columns:
                            text_col = candidate
                            break

                    if "DENOM_CIA" not in df.columns or text_col is None:
                        logger.warning(
                            "parse_parecer: %s missing required columns (found: %s)",
                            csv_name, list(df.columns)
                        )
                        continue

                    # Filter by company (exact match first, fallback to first-word)
                    upper = df["DENOM_CIA"].str.upper().str.strip()
                    full_name = company_name.strip().upper()
                    exact = upper == full_name
                    if exact.any():
                        df = df[exact].copy()
                    else:
                        df = df[upper.str.contains(company_key, na=False)].copy()
                    if df.empty:
                        continue

                    # Keep only the independent auditor's report rows
                    # TP_PARECER_DECL contains "Relatório do Auditor Independente"
                    if "TP_PARECER_DECL" in df.columns:
                        auditor_mask = df["TP_PARECER_DECL"].str.contains(
                            "Auditor Independente", case=False, na=False
                        )
                        auditor_df = df[auditor_mask].copy()
                        if auditor_df.empty:
                            logger.warning(
                                "parse_parecer: no 'Relatório do Auditor Independente' rows "
                                "for %s in %s — skipping", company_key, csv_name
                            )
                            continue
                        df = auditor_df

                    # Filter to latest VERSAO per DT_REFER
                    if "VERSAO" in df.columns and "DT_REFER" in df.columns:
                        try:
                            df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").fillna(0)
                            max_versao = df.groupby("DT_REFER")["VERSAO"].transform("max")
                            df = df[df["VERSAO"] == max_versao].copy()
                        except Exception:
                            pass

                    # Sort items and concatenate per period
                    if "NUM_ITEM_PARECER_DECL" in df.columns:
                        df["NUM_ITEM_PARECER_DECL"] = pd.to_numeric(
                            df["NUM_ITEM_PARECER_DECL"], errors="coerce"
                        ).fillna(0)
                        df = df.sort_values(["DT_REFER", "NUM_ITEM_PARECER_DECL"])

                    for period, group in df.groupby("DT_REFER"):
                        period = str(period).strip()
                        parts = [
                            str(v).strip()
                            for v in group[text_col].tolist()
                            if pd.notna(v) and str(v).strip().lower() not in ("", "nan")
                        ]
                        texto = "\n\n".join(parts)
                        if not texto:
                            continue

                        # Extract structured opinion type if available
                        tp_relat = ""
                        if "TP_RELAT_AUD" in group.columns:
                            vals = group["TP_RELAT_AUD"].dropna().unique().tolist()
                            tp_relat = str(vals[0]).strip() if vals else ""

                        all_rows.append({
                            "period":      period,
                            "year":        year,
                            "texto":       texto,
                            "tp_relat_aud": tp_relat,
                        })
        except (zipfile.BadZipFile, FileNotFoundError):
            continue
        except Exception as exc:
            logger.warning("parse_parecer: error reading %s: %s", dfp_path, exc)
            continue

    if not all_rows:
        logger.info("parse_parecer: no Parecer data found for %s", company_name)
        return []

    # Deduplicate across years by period (latest year wins)
    seen: dict[str, dict] = {}
    for row in all_rows:
        p = row["period"]
        if p not in seen or row["year"] > seen[p]["year"]:
            seen[p] = row

    result = sorted(seen.values(), key=lambda r: r["period"])
    logger.info("parse_parecer: found %d Parecer reports for %s", len(result), company_name)
    return result


def _cache_path(cache_dir: Path, company_name: str, language: str = "en") -> Path:
    company_key = company_name.split()[0].lower()
    # cache_dir may be the base cache dir — resolve to company subdir
    company_dir = cache_dir / company_key
    company_dir.mkdir(parents=True, exist_ok=True)
    return company_dir / f"parecer_classifications_{language}.json"


def _load_classification_cache(
    cache_dir: Path, company_name: str, language: str = "en"
) -> dict[str, dict]:
    path = _cache_path(cache_dir, company_name, language)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_classification_cache(
    cache_dir: Path, company_name: str, data: dict[str, dict], language: str = "en"
) -> None:
    path = _cache_path(cache_dir, company_name, language)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("_save_classification_cache: %s", exc)


def _validate_classification(result: dict) -> dict:
    """Validate and normalise a classification dict. Returns fallback on failure."""
    if not isinstance(result, dict):
        return {**_FALLBACK_CLASSIFICATION}

    opinion = result.get("opinion_type", "")
    if opinion not in _VALID_OPINION_TYPES:
        result["opinion_type"] = "unknown"

    for bool_key in ("has_going_concern", "has_emphasis_of_matter"):
        v = result.get(bool_key)
        if not isinstance(v, bool):
            result[bool_key] = bool(v) if v is not None else False

    for list_key in ("emphasis_topics", "key_audit_matters"):
        v = result.get(list_key)
        if not isinstance(v, list):
            result[list_key] = [str(v)] if v else []
        else:
            result[list_key] = [str(x) for x in v if x]

    if not result.get("auditor_firm"):
        result["auditor_firm"] = "Unknown"

    if not result.get("opinion_summary"):
        result["opinion_summary"] = ""

    result.pop("classification_error", None)
    return result


def _classify_single(texto: str, company_name: str, api_key: str, language: str = "en") -> dict:
    """Call Claude Sonnet to classify one auditor report. Returns validated dict."""
    try:
        import anthropic
        lang_label = "English" if language == "en" else "Brazilian Portuguese"
        system_prompt = _CLASSIFY_SYSTEM_TEMPLATE.format(language=lang_label)
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _CLASSIFY_USER_TEMPLATE.format(texto=texto[:8000])  # cap at ~8k chars
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        return _validate_classification(parsed)
    except Exception as exc:
        logger.warning("_classify_single: LLM call failed for %s: %s", company_name, exc)
        return {**_FALLBACK_CLASSIFICATION}


def classify_parecer(
    reports: list[dict],
    company_name: str,
    cache_dir: Path,
    api_key: str,
    language: str = "en",
) -> list[dict]:
    """Classify each auditor report via Claude Sonnet (with per-period caching).

    Args:
        reports: Output of parse_parecer().
        company_name: Company name string.
        cache_dir: Base cache directory.
        api_key: Anthropic API key (empty string → return fallbacks with no LLM call).
        language: Output language for free-text fields ("en" or "pt").

    Returns:
        List of classification dicts, each with all fields from _validate_classification
        plus "period" and "year" from the input report.
    """
    if not reports:
        return []

    cached = _load_classification_cache(cache_dir, company_name, language)
    results: list[dict] = []
    cache_updated = False

    for report in reports:
        period = report["period"]
        year = report.get("year", "")

        if period in cached:
            classification = {**cached[period], "period": period, "year": year}
        elif not api_key:
            classification = {**_FALLBACK_CLASSIFICATION, "period": period, "year": year}
        else:
            logger.info("classify_parecer: classifying %s period %s lang=%s", company_name, period, language)
            result = _classify_single(report["texto"], company_name, api_key, language)
            cached[period] = result
            cache_updated = True
            classification = {**result, "period": period, "year": year}

        results.append(classification)

    if cache_updated:
        _save_classification_cache(cache_dir, company_name, cached, language)

    return results
