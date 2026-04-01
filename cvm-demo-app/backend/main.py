import asyncio
import json
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import app_config, pipeline_state
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
    # company_name / company_cvm_code intentionally not changeable in Phase 1
    return get_config()


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
# WebSocket — Step 9 LLM streaming
# ---------------------------------------------------------------------------

@app.websocket("/ws/llm")
async def llm_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        step = payload.get("step", 9)

        if step == 7:
            # Industry Specialist Agent — stream and store full response in pipeline_state
            full_text = ""
            async for token in step7_ai_agent.stream(payload, config=app_config):
                await websocket.send_text(token)
                full_text += token
            pipeline_state["step7"] = {"response_text": full_text}
        elif step == 8:
            # Executive Summary — merges Step 6 data and Step 7 analysis
            full_text = ""
            async for token in step8_reporting.stream(payload, config=app_config):
                await websocket.send_text(token)
                full_text += token
            pipeline_state["step8"] = {"response_text": full_text}
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
