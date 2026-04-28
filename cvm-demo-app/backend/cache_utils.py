"""Thin cache layer for pipeline step outputs.

Each step's result dict is stored as cache/{company_key}/step{N}.json after a
successful live run. When cache_mode is ON the endpoint loads from that file
instead. If the live run fails and a cache file exists, the caller can fall
back to it.

Company-specific subdirectories ensure that switching companies never
overwrites another company's cached data.
"""
import json
import re
from pathlib import Path


def _sanitize_company(company_name: str) -> str:
    """Convert a company name to a safe directory component.

    e.g. 'BRASKEM S.A.' -> 'BRASKEM_SA'
         'PETRÓLEO BRASILEIRO S.A. - PETROBRAS' -> 'PETROLEO_BRASILEIRO_SA_PETROBRAS'
    """
    # Normalize accented chars to ASCII equivalents
    import unicodedata
    normalized = unicodedata.normalize("NFKD", company_name).encode("ascii", "ignore").decode("ascii")
    # Replace non-alphanumeric characters with underscores and collapse runs
    sanitized = re.sub(r"[^A-Z0-9]+", "_", normalized.upper()).strip("_")
    return sanitized or "UNKNOWN"


def _resolve_dir(cache_dir: Path, company_name: str | None) -> Path:
    if company_name:
        return cache_dir / _sanitize_company(company_name)
    return cache_dir


def load_cache(step_n: int, cache_dir: Path, company_name: str | None = None, suffix: str = "") -> dict | None:
    """Return the cached result dict for step N, or None if not available.

    suffix: optional string appended before .json (e.g. "_en", "_pt_br") for
    language-keyed caches.
    """
    path = _resolve_dir(cache_dir, company_name) / f"step{step_n}{suffix}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("metadata", {})["cache_used"] = True
        data["metadata"]["source"] = "cache"
        return data
    except Exception:
        return None


def save_cache(step_n: int, result: dict, cache_dir: Path, company_name: str | None = None, suffix: str = "") -> None:
    """Persist a step result dict to cache. Silently ignores write errors.

    suffix: optional string appended before .json (e.g. "_en", "_pt_br") for
    language-keyed caches.
    """
    directory = _resolve_dir(cache_dir, company_name)
    path = directory / f"step{step_n}{suffix}.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, default=str)
    except Exception:
        pass
