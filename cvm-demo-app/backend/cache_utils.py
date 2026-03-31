"""Thin cache layer for pipeline step outputs.

Each step's result dict is stored as cache/step{N}.json after a successful
live run. When cache_mode is ON the endpoint loads from that file instead.
If the live run fails and a cache file exists, the caller can fall back to it.
"""
import json
from pathlib import Path


def load_cache(step_n: int, cache_dir: Path) -> dict | None:
    """Return the cached result dict for step N, or None if not available."""
    path = cache_dir / f"step{step_n}.json"
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


def save_cache(step_n: int, result: dict, cache_dir: Path) -> None:
    """Persist a step result dict to cache. Silently ignores write errors."""
    path = cache_dir / f"step{step_n}.json"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, default=str)
    except Exception:
        pass
