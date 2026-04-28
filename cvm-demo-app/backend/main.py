import asyncio
import json
import logging
import re
import time
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from config import app_config, pipeline_state, CACHE_DIR, DATA_DIR
from cache_utils import load_cache, save_cache
from steps import (
    step1_download,
    step2_preparation,
    step3_transformation,
    step4_ebitda_drivers,
    step5_quality_scan,
    step6_core_analysis,
    step7_ai_agent,
    step8_reporting,
    step9_llm_analysis,
)

app = FastAPI(title="CVM Financial Analysis API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STEP_HANDLERS = {
    1: step1_download.run,
    2: step2_preparation.run,
    3: step3_transformation.run,
    4: step4_ebitda_drivers.run,
    5: step5_quality_scan.run,
    6: step6_core_analysis.run,
    7: step7_ai_agent.run,
    8: step8_reporting.run,
}


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    return {
        "company_name": app_config.company_name,
        "company_cvm_code": app_config.company_cvm_code,
        "language": app_config.language,
        "cache_mode": app_config.cache_mode,
    }


@app.post("/api/config")
def set_config(body: dict):
    if "language" in body:
        app_config.language = body["language"]
    if "cache_mode" in body:
        app_config.cache_mode = body["cache_mode"]
    if "company_name" in body and body["company_name"] != app_config.company_name:
        app_config.company_name = body["company_name"]
        # Reset pipeline state so previous company's data doesn't bleed through
        for key in list(pipeline_state.keys()):
            pipeline_state[key] = None
    return get_config()


# ---------------------------------------------------------------------------
# Company lookup endpoints
# ---------------------------------------------------------------------------

def _normalize_for_search(s: str) -> str:
    """Strip accents and uppercase for case/accent-insensitive matching."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").upper()


def _load_all_companies() -> list[dict]:
    """Return the full company list, from cache or from downloaded DFP ZIPs."""
    companies_cache = CACHE_DIR / "companies.json"
    if companies_cache.exists():
        try:
            with open(companies_cache, encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached.get("companies"), list):
                return cached["companies"]
        except Exception:
            pass

    from pipeline.cvm_downloader import extract_company_list
    from pipeline.enrichment import SECTOR_MAP

    raw = extract_company_list(DATA_DIR)
    companies = []
    for c in raw:
        key = c["name"].split()[0].upper()
        sector = SECTOR_MAP.get(key, "Unknown")
        source = "mapped" if sector != "Unknown" else "unmapped"
        companies.append({**c, "sector": sector, "sector_source": source})

    result = {
        "companies": companies,
        "total": len(companies),
        "mapped_sectors": sum(1 for c in companies if c["sector_source"] == "mapped"),
        "unmapped": sum(1 for c in companies if c["sector_source"] == "unmapped"),
    }
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(companies_cache, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    except Exception:
        pass
    return companies


@app.get("/api/companies")
def get_companies():
    companies = _load_all_companies()
    from pipeline.enrichment import SECTOR_MAP
    return {
        "companies": companies,
        "total": len(companies),
        "mapped_sectors": sum(1 for c in companies if c.get("sector_source") == "mapped"),
        "unmapped": sum(1 for c in companies if c.get("sector_source") == "unmapped"),
    }


@app.get("/api/companies/search")
def search_companies(q: str = Query(default="")):
    if not q.strip():
        return {"results": []}
    companies = _load_all_companies()
    q_norm = _normalize_for_search(q.strip())
    matches = [c for c in companies if q_norm in _normalize_for_search(c["name"])]
    # Score: full-word match ranks higher than substring
    def score(c):
        name_norm = _normalize_for_search(c["name"])
        if name_norm.startswith(q_norm):
            return 1.0
        if q_norm in name_norm.split():
            return 0.9
        return 0.5
    matches.sort(key=score, reverse=True)
    return {"results": [{**m, "score": score(m)} for m in matches[:10]]}


# ---------------------------------------------------------------------------
# Pipeline step endpoints
# ---------------------------------------------------------------------------

@app.post("/api/step/{step_number}")
def run_step(step_number: int):
    if step_number not in STEP_HANDLERS:
        return {"status": "error", "message": f"Unknown step {step_number}"}

    start = time.perf_counter()
    result = STEP_HANDLERS[step_number](
        config=app_config,
        pipeline_state=pipeline_state,
    )
    elapsed = round(time.perf_counter() - start, 3)

    # Persist step output in pipeline state
    pipeline_state[f"step{step_number}"] = result.get("data")

    result.setdefault("timing", {})["elapsed_seconds"] = elapsed
    return result


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

@app.get("/api/export/context")
def export_context(
    company: str = Query(default=""),
    lang: str = Query(default="en"),
):
    from export_context import build_markdown
    import re as _re
    company_name = company.strip() or app_config.company_name
    lang_norm = lang.lower().strip()
    if lang_norm not in ("en", "pt-br"):
        lang_norm = "en"
    md = build_markdown(company_name=company_name, lang=lang_norm, cache_dir=CACHE_DIR)
    today = time.strftime("%Y-%m-%d")
    safe_co = _re.sub(r"[^A-Z0-9]+", "-", company_name.upper()).strip("-")
    filename = f"cygnus-context-{safe_co}-{today}.md"
    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/report/pdf")
def report_pdf(body: dict):
    from report_pdf import build_pdf
    import re as _re
    company_name = (body.get("company") or app_config.company_name).strip()
    lang = (body.get("lang") or app_config.language or "en").lower().strip()
    if lang not in ("en", "pt-br"):
        lang = "en"
    try:
        pdf_bytes = build_pdf(company_name=company_name, lang=lang, cache_dir=CACHE_DIR)
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}
    today = time.strftime("%Y-%m-%d")
    safe_co = _re.sub(r"[^A-Z0-9]+", "-", company_name.upper()).strip("-")
    filename = f"cygnus-report-{safe_co}-{today}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# WebSocket — Step 9 LLM streaming
# ---------------------------------------------------------------------------

def _fix_literal_newlines(s: str) -> str:
    """Replace bare newlines/tabs inside JSON string values with their escape sequences.

    Claude sometimes streams actual \\n characters inside multi-line string fields
    (full_narrative, explanation) rather than the JSON escape sequence \\\\n,
    producing invalid JSON that json.loads() rejects.
    """
    out: list[str] = []
    in_string = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and in_string:
            # Valid escape sequence — pass both chars through unchanged
            out.append(ch)
            if i + 1 < len(s):
                out.append(s[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            i += 1
            continue
        if in_string:
            if ch == "\n":
                out.append("\\n")
                i += 1
                continue
            if ch == "\r":
                out.append("\\r")
                i += 1
                continue
            if ch == "\t":
                out.append("\\t")
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _clean_step7_json(raw: str) -> str:
    """Strip markdown fences, fix bare newlines, validate with json.loads, re-emit with json.dumps.

    Returns a guaranteed-valid JSON string, or the best-effort cleaned text if all
    parsing attempts fail (frontend fallback handles that case).
    """
    # 1. Strip markdown code fences (Claude often wraps output in ```json ... ```)
    cleaned = re.sub(r"^```json\s*$", "", raw, flags=re.MULTILINE | re.IGNORECASE)
    cleaned = re.sub(r"^```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # 2. Extract outermost JSON object if there is preamble text
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace : last_brace + 1]

    # 3. Try direct parse first (clean JSON needs no fixup)
    try:
        data = json.loads(cleaned)
        return json.dumps(data, ensure_ascii=False)
    except json.JSONDecodeError as e:
        logger.warning("Step 7 direct JSON parse failed (%s) — trying literal-newline fix", e)
        logger.debug("Step 7 raw first 300 chars: %s", cleaned[:300])
        logger.debug("Step 7 raw last 300 chars: %s", cleaned[-300:])

    # 4. Fix bare newlines inside string values, then retry
    fixed = _fix_literal_newlines(cleaned)
    try:
        data = json.loads(fixed)
        logger.info("Step 7 JSON parsed OK after literal-newline fix")
        return json.dumps(data, ensure_ascii=False)
    except json.JSONDecodeError as e:
        logger.error("Step 7 JSON parse failed even after fix (%s) — returning best-effort", e)
        return fixed  # frontend will fall back to MarkdownView


@app.websocket("/ws/llm")
async def llm_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        step = payload.get("step", 9)

        if step == 7:
            # Serve from cache when cache_mode is on — re-emit as section messages
            if app_config.cache_mode:
                lang_suffix = f"_{app_config.language}"
                cached = load_cache(7, CACHE_DIR, company_name=app_config.company_name, suffix=lang_suffix)
                if cached:
                    cached_text = cached.get("data", {}).get("response_text", "")
                    if cached_text:
                        pipeline_state["step7"] = {"response_text": cached_text}
                        try:
                            cached_obj = json.loads(cached_text)
                            if "macro_context" in cached_obj:
                                await websocket.send_text(json.dumps({"__section": "macro_context", "data": cached_obj["macro_context"]}))
                            for key in ("profitability", "balance_sheet", "cash_flow", "cross_module"):
                                val = cached_obj.get("modules", {}).get(key)
                                if val is not None:
                                    await websocket.send_text(json.dumps({"__section": key, "data": val}))
                        except Exception:
                            await websocket.send_text(cached_text)
                        await websocket.send_text("[DONE]")
                        return

            # Enrich payload with DVA/DMPL series from step 4 for cross-module context
            step4_ps = pipeline_state.get("step4") or {}
            if not step4_ps:
                _c4 = load_cache(4, CACHE_DIR, company_name=app_config.company_name)
                step4_ps = (_c4 or {}).get("data", {})
            if "dva_series" not in payload:
                payload["dva_series"] = step4_ps.get("dva_series", [])
            if "dmpl_series" not in payload:
                payload["dmpl_series"] = step4_ps.get("dmpl_series", [])

            # Enrich payload with FRE data from step 6 for debt structure context
            step6_ps = pipeline_state.get("step6") or {}
            if not step6_ps:
                _c6 = load_cache(6, CACHE_DIR, company_name=app_config.company_name)
                step6_ps = (_c6 or {}).get("data", {})
            if "fre_foreign_bonds" not in payload:
                payload["fre_foreign_bonds"] = step6_ps.get("fre_foreign_bonds", [])
            if "fre_auditor_profiles" not in payload:
                payload["fre_auditor_profiles"] = step6_ps.get("fre_auditor_profiles", [])

            # Live LLM call — yield one section message per completed section
            sections: dict[str, Any] = {}
            async for token in step7_ai_agent.stream(payload, config=app_config):
                await websocket.send_text(token)
                try:
                    msg = json.loads(token)
                    if isinstance(msg, dict) and "__section" in msg:
                        sections[msg["__section"]] = msg.get("data", {})
                except Exception:
                    pass

            assembled = {
                "macro_context": sections.get("macro_context", {}),
                "modules": {
                    "profitability": sections.get("profitability", {}),
                    "balance_sheet": sections.get("balance_sheet", {}),
                    "cash_flow":     sections.get("cash_flow", {}),
                    "cross_module":  sections.get("cross_module", {}),
                },
            }
            if "transparency" in sections:
                assembled["transparency"] = sections["transparency"]
            cleaned_json = json.dumps(assembled, ensure_ascii=False)
            pipeline_state["step7"] = {"response_text": cleaned_json}
            save_cache(7, {
                "status": "complete",
                "data": {"response_text": cleaned_json, "status": "complete"},
                "metadata": {"source": "websocket"},
            }, CACHE_DIR, company_name=app_config.company_name, suffix=f"_{app_config.language}")
        elif step == 8:
            # Serve from cache when cache_mode is on — re-emit as section messages
            if app_config.cache_mode:
                lang_suffix = f"_{app_config.language}"
                cached = load_cache(8, CACHE_DIR, company_name=app_config.company_name, suffix=lang_suffix)
                if cached:
                    cached_text = cached.get("data", {}).get("response_text", "")
                    if cached_text:
                        pipeline_state["step8"] = {"response_text": cached_text}
                        try:
                            cached_obj = json.loads(cached_text)
                            for section_key, fields in [
                                ("diagnosis", ["executive_summary", "key_findings", "next_step"]),
                                ("timeline",  ["what_happened", "when_things_turned"]),
                                ("severity",  ["how_serious", "what_comes_next"]),
                                ("gaps",      ["what_we_cant_answer", "data_gaps", "suggested_questions"]),
                            ]:
                                data = {k: cached_obj[k] for k in fields if k in cached_obj}
                                if data:
                                    await websocket.send_text(json.dumps({"__section": section_key, "data": data}))
                        except Exception:
                            await websocket.send_text(cached_text)
                        await websocket.send_text("[DONE]")
                        return

            # Live LLM call — yield one section message per completed section
            sections: dict[str, Any] = {}
            async for token in step8_reporting.stream(payload, config=app_config):
                await websocket.send_text(token)
                try:
                    msg = json.loads(token)
                    if isinstance(msg, dict) and "__section" in msg:
                        sections[msg["__section"]] = msg.get("data", {})
                except Exception:
                    pass

            assembled = {
                **sections.get("diagnosis", {}),
                **sections.get("timeline",  {}),
                **sections.get("severity",  {}),
                **sections.get("gaps",      {}),
            }
            cleaned_json = json.dumps(assembled, ensure_ascii=False)
            pipeline_state["step8"] = {"response_text": cleaned_json}
            save_cache(8, {
                "status": "complete",
                "data": {"response_text": cleaned_json, "status": "complete"},
                "metadata": {"source": "websocket"},
            }, CACHE_DIR, company_name=app_config.company_name, suffix=f"_{app_config.language}")
        else:
            # Step 9 Q&A — conversational streaming with pipeline context
            async for token in step9_llm_analysis.stream(
                payload, config=app_config, pipeline_state=pipeline_state
            ):
                await websocket.send_text(token)

        await websocket.send_text("[DONE]")
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_text(f"[ERROR] {exc}")
    finally:
        await websocket.close()
