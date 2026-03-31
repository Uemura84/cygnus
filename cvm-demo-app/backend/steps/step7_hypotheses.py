"""Step 7: Hypothesis Generation — deterministic theory generation from structural findings."""

from config import CACHE_DIR
from cache_utils import load_cache, save_cache
from pipeline.hypothesis_generator import generate_hypotheses


def run(config, pipeline_state: dict) -> dict:
    STEP = 7

    if config.cache_mode:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            return cached

    try:
        step6 = pipeline_state.get("step6") or {}
        findings = step6.get("findings", [])
        composite_signals = step6.get("composite_signals", [])

        # Reconstruct raw-style findings from shaped findings for the hypothesis generator
        # (hypothesis generator needs 'shift_pp', 'annual_change_pp' etc. from data_points)
        raw_findings = []
        for f in findings:
            raw = {
                "id":           f.get("id", ""),
                "pattern":      f.get("pattern", ""),
                "severity":     f.get("severity", "MEDIUM"),
                "insight":      f.get("description", ""),
                "period":       f.get("period", ""),
                "anomaly_type": f.get("anomaly_type", ""),
            }
            raw.update(f.get("data_points", {}))
            raw_findings.append(raw)

        result_data = generate_hypotheses(
            findings=raw_findings,
            composite_signals=composite_signals,
            company=config.company_name,
        )

        result = {
            "status": "complete",
            "data":   result_data,
            "metadata": {"cache_used": False, "source": "live"},
        }
        save_cache(STEP, result, CACHE_DIR)
        return result

    except Exception as exc:
        cached = load_cache(STEP, CACHE_DIR)
        if cached:
            cached["metadata"]["source"] = "cache"
            cached["metadata"]["reason"] = str(exc)
            return cached

        return {
            "status": "error",
            "data":   {},
            "metadata": {"cache_used": False, "source": "live"},
            "error":  str(exc),
        }
