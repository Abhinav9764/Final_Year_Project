"""
backend/app.py - Chatbot Interface FastAPI Backend (V2)
========================================================
- FastAPI with async job management
- WebSocket for live pipeline updates
- Job ID tracking and status polling
- CORS enabled for React frontend
"""

import asyncio
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import yaml

from orchestrator import Orchestrator

# Ensure Unicode log messages do not crash on Windows cp1252 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# App setup
app = FastAPI(title="RAD-ML V2 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
BASE_DIR = Path(__file__).parent
try:
    with open(BASE_DIR / "config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except Exception:
    config = {}

agent_cfg = config.get("agents", {})


def _resolve_agent_path(raw: str, default: str) -> str:
    p = Path(raw) if raw else Path(default)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    return str(p)


orchestrator = Orchestrator(
    data_collector_dir=_resolve_agent_path(
        agent_cfg.get("data_collector_dir", ""), "../../Data_Collection_Agent"
    ),
    code_gen_dir=_resolve_agent_path(
        agent_cfg.get("code_generator_dir", ""), "../../Code_Generator/RAD-ML"
    ),
)

# SQLite History & Uploads Setup
DB_PATH = BASE_DIR / "data" / "history.db"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                prompt TEXT,
                status TEXT,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# Intent classification
ML_KEYWORDS = [
    "predict",
    "classify",
    "regression",
    "train",
    "model",
    "ml",
    "machine learning",
    "dataset",
    "accuracy",
    "forecast",
    "cluster",
    "neural",
    "price",
    "detection",
]
CHAT_KEYWORDS = [
    "chatbot",
    "chat",
    "question",
    "answer",
    "explain",
    "tell me",
    "what is",
    "how to",
]


def classify_intent(prompt: str) -> str:
    prompt_lower = prompt.lower()
    ml_score = sum(1 for kw in ML_KEYWORDS if kw in prompt_lower)
    chat_score = sum(1 for kw in CHAT_KEYWORDS if kw in prompt_lower)
    return "ml" if ml_score >= chat_score else "chatbot"


# Request/Response models
class ChatRequest(BaseModel):
    message: str


class PipelineRequest(BaseModel):
    prompt: str
    uploaded_files: list[str] = []


class ChatResponse(BaseModel):
    response: str
    intent: str


class JobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: int
    logs: list
    result: dict | None = None
    error: str | None = None


# Endpoints
@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "RAD-ML V2 API is running!"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Classify intent and return a context-aware bot acknowledgement."""
    user_prompt = req.message.strip()
    intent = classify_intent(user_prompt)

    if intent == "ml":
        reply = (
            f'Great! I\'ll build a **Predictive ML Model** based on your request:\n\n'
            f'*"{user_prompt}"*\n\n'
            "I am now dispatching this exact prompt to:\n"
            "1. **Data Collection Agent** - to gather relevant datasets\n"
            "2. **Code Generator (RAD-ML)** - to train, validate, and deploy your model\n\n"
            "Watch the pipeline status panel on the right."
        )
    else:
        reply = (
            f'Got it! I\'ll build a **Chatbot** for:\n\n'
            f'*"{user_prompt}"*\n\n'
            "Dispatching this prompt to both agents:\n"
            "1. **Data Collection Agent** - scraping domain knowledge\n"
            "2. **Code Generator (RAD-ML)** - building a RAG-powered chatbot\n\n"
            "Watch the pipeline status panel."
        )
    return ChatResponse(response=reply, intent=intent)


async def _run_and_save_pipeline(job_id: str):
    await orchestrator.run_pipeline(job_id)
    job = orchestrator.get_job(job_id)
    if job and job.status in ("done", "error"):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                save_result = job.result
                if job.status == "error":
                    save_result = {"error": job.error or "Pipeline failed."}
                
                conn.execute(
                    "INSERT OR REPLACE INTO jobs (job_id, prompt, status, result) VALUES (?, ?, ?, ?)",
                    (job.job_id, job.prompt, job.status, json.dumps(save_result) if save_result else None)
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to save job %s to history DB: %s", job_id, e)

@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """Save uploaded user documents and return their absolute paths."""
    saved_paths = []
    try:
        for file in files:
            file_path = UPLOAD_DIR / file.filename
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            saved_paths.append(str(file_path.absolute()))
        
        return {"status": "success", "paths": saved_paths}
    except Exception as e:
        logger.error(f"Error handling upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded files.")


@app.post("/api/pipeline/run")
async def run_pipeline(req: PipelineRequest):
    """
    Start the pipeline asynchronously.
    The client should then connect to /api/pipeline/stream/{job_id} for SSE updates.
    """
    prompt = req.prompt.strip()
    if not prompt:
        return {"status": "error", "message": "Missing prompt"}

    job_id = orchestrator.create_job(prompt, uploaded_files=req.uploaded_files)
    orchestrator.latest_job_id = job_id
    task = asyncio.create_task(_run_and_save_pipeline(job_id))
    orchestrator._running_tasks[job_id] = task
    logger.info("Pipeline job %s started for prompt: %s", job_id, prompt[:80])
    return {"status": "started", "job_id": job_id}


@app.post("/api/pipeline/stop/{job_id}")
async def stop_pipeline(job_id: str):
    """Cancel a running pipeline job."""
    success = orchestrator.cancel_job(job_id)
    if success:
        logger.info("Pipeline job %s manually cancelled.", job_id)
        return {"status": "success", "message": "Pipeline cancelled."}
    return {"status": "error", "message": "Job not found or already finished."}

@app.get("/api/pipeline/status/{job_id}", response_model=JobStatusResponse)
async def pipeline_status(job_id: str):
    """Poll the current status of a pipeline job."""
    job = orchestrator.get_job(job_id)
    if not job:
        return JobStatusResponse(
            job_id=job_id,
            status="not_found",
            current_step=0,
            logs=[],
        )
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        current_step=job.current_step,
        logs=job.logs,
        result=job.result,
        error=job.error,
    )


@app.websocket("/ws/pipeline/{job_id}")
async def ws_pipeline(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for live pipeline updates.
    The client connects after calling /api/pipeline/run.
    """
    await websocket.accept()
    orchestrator.register_ws(job_id, websocket)
    logger.info("WebSocket connected for job %s", job_id)

    try:
        job = orchestrator.get_job(job_id)
        if job:
            for log_entry in job.logs:
                await websocket.send_json(log_entry)

        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=300)
            except asyncio.TimeoutError:
                break
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    finally:
        orchestrator.unregister_ws(job_id, websocket)


def _make_sse_stream(job_id: Optional[str]) -> StreamingResponse:
    async def event_generator():
        import json as _json

        yield 'data: {"step": 0, "status": "connected", "message": "Agent pipeline connected..."}\n\n'

        if not job_id:
            yield 'data: {"step": -1, "status": "error", "message": "No pipeline running."}\n\n'
            return

        job = orchestrator.get_job(job_id)
        if not job:
            yield 'data: {"step": -1, "status": "error", "message": "Job not found."}\n\n'
            return

        queue: asyncio.Queue = asyncio.Queue()
        orchestrator.register_sse(job_id, queue)
        try:
            for entry in job.logs:
                yield f"data: {_json.dumps(entry)}\n\n"

            while True:
                latest_job = orchestrator.get_job(job_id)
                if not latest_job:
                    yield 'data: {"step": -1, "status": "error", "message": "Job not found."}\n\n'
                    return
                if latest_job.status in ("done", "error") and queue.empty():
                    return

                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {_json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            orchestrator.unregister_sse(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/pipeline/stream/{job_id}")
async def stream_sse_job(job_id: str):
    return _make_sse_stream(job_id)


@app.get("/api/pipeline/stream")
async def stream_sse_latest():
    latest_job_id = getattr(orchestrator, "latest_job_id", None)
    return _make_sse_stream(latest_job_id)


@app.get("/api/history")
async def get_history():
    """Retrieve all past pipeline jobs from the SQLite DB."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            
            history = []
            for r in rows:
                result = None
                if r["result"]:
                    try:
                        result = json.loads(r["result"])
                    except Exception:
                        pass
                history.append({
                    "job_id": r["job_id"],
                    "prompt": r["prompt"],
                    "status": r["status"],
                    "result": result,
                    "created_at": r["created_at"]
                })
            return {"status": "success", "history": history}
    except Exception as e:
        logger.error("Failed to read history DB: %s", e)
        return {"status": "error", "message": "Could not read history."}


@app.delete("/api/history/{job_id}")
async def delete_history_item(job_id: str):
    """Delete a single persisted chat/job history entry."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="History item not found.")
        return {"status": "success", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete history item %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Could not delete history item.")


@app.delete("/api/history")
async def delete_all_history():
    """Delete ALL persisted chat/job history entries (Clear History button)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM jobs")
            conn.commit()
        return {"status": "success", "message": "All history cleared."}
    except Exception as e:
        logger.error("Failed to clear all history: %s", e)
        raise HTTPException(status_code=500, detail="Could not clear history.")


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting RAD-ML V2 API on port 5001...")
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
