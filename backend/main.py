"""
FastAPI backend for the Site Approval Bot.

Endpoints:
  GET  /models            — list available Copilot models
  POST /sessions          — create a new chat session
  DELETE /sessions/{id}   — delete a session
  WS   /ws/chat/{id}      — WebSocket chat with streaming events
  GET  /reports/{filename} — download a generated PowerPoint report
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await get_agent().start()
        logger.info("Site Approval Bot agent started successfully.")
    except Exception as exc:
        logger.warning(
            "Could not start Copilot SDK agent: %s. "
            "Ensure the Copilot CLI is installed and authenticated.",
            exc,
        )
    try:
        yield
    finally:
        if _agent:
            await _agent.stop()


app = FastAPI(
    title="Site Approval Bot API",
    description="Backend for the Site Approval Bot powered by GitHub Copilot SDK, Work IQ MCP, and local PowerPoint generation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server and configured origins
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy import: avoids failing at startup if copilot CLI is not installed yet
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        from agent import SupportAgent
        _agent = SupportAgent()
    return _agent


REPORTS_DIR = Path(__file__).parent / "generated_reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/models")
async def list_models() -> dict:
    """Return the models available via the Copilot SDK."""
    try:
        models = await get_agent().list_models()
        return {"models": models}
    except Exception as exc:
        logger.error("Failed to list models: %s", exc)
        return {"models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4.1", "name": "GPT-4.1"},
            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5"},
            {"id": "o4-mini", "name": "o4-mini"},
        ]}


@app.post("/sessions")
async def create_session() -> dict:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session and free its resources."""
    await get_agent().delete_session(session_id)
    return {"deleted": session_id}


@app.get("/reports/{filename}")
async def download_report(filename: str) -> FileResponse:
    """Download a generated PowerPoint report."""
    # Prevent path traversal
    safe_name = Path(filename).name
    filepath = REPORTS_DIR / safe_name
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        path=str(filepath),
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


# ---------------------------------------------------------------------------
# WebSocket chat endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket endpoint for streaming chat.

    Client sends:
      {"prompt": "...", "model": "gpt-4o"}

    Server streams event objects:
            {"type": "agent.event", "event_name": "...", "data": {...}}
      {"type": "assistant.message_delta", "content": "..."}
      {"type": "tool.execution_start", "tool_name": "...", "args": {...}}
      {"type": "tool.execution_complete", "tool_name": "...", "result": "..."}
      {"type": "assistant.message", "content": "..."}
      {"type": "session.idle"}
      {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info("WebSocket connected: session=%s", session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            prompt = message.get("prompt", "").strip()
            model = message.get("model", "gpt-4o")

            if not prompt:
                await websocket.send_json({"type": "error", "message": "Empty prompt"})
                continue

            logger.info("session=%s model=%s prompt=%r", session_id, model, prompt[:80])

            async for event in get_agent().send_message(session_id, prompt, model):
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as exc:
        logger.exception("WebSocket error: session=%s", session_id)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.environ.get("BACKEND_HOST", "0.0.0.0"),
        port=int(os.environ.get("BACKEND_PORT", "8000")),
        reload=True,
    )
