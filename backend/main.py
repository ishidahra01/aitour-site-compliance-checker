"""
main.py

FastAPI backend for the base station site compliance checker.

Endpoints:
  POST /api/check           - Start a compliance check job
  GET  /api/check/{id}/stream - SSE stream of agent log events
  GET  /api/check/{id}      - Get final check result
  GET  /api/sites           - List available sites
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from checker import run_check
from demo_data import SITES

app = FastAPI(title="基地局設置チェッカー API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store  {job_id: {status, events, result, new_event, created_at}}
_jobs: dict[str, dict[str, Any]] = {}

_JOB_TTL_SECONDS = 3600  # clean up jobs older than 1 hour


def _cleanup_old_jobs() -> None:
    """Remove completed jobs older than _JOB_TTL_SECONDS to prevent memory leaks."""
    cutoff = time.monotonic() - _JOB_TTL_SECONDS
    stale = [
        jid
        for jid, job in _jobs.items()
        if job.get("created_at", 0) < cutoff and job["status"] in ("done", "error")
    ]
    for jid in stale:
        del _jobs[jid]


class CheckRequest(BaseModel):
    site_id: str
    check_items: list[str]


@app.get("/api/sites")
async def list_sites():
    return SITES


@app.post("/api/check")
async def start_check(request: CheckRequest):
    job_id = str(uuid.uuid4())
    _cleanup_old_jobs()
    _jobs[job_id] = {
        "status": "running",
        "events": [],   # buffered for late-joining SSE clients
        "result": None,
        "new_event": asyncio.Event(),  # signals waiting SSE consumers
        "created_at": time.monotonic(),
    }

    async def _worker():
        job = _jobs[job_id]

        def emit(event: dict):
            job["events"].append(event)
            job["new_event"].set()

        try:
            result = await run_check(request.site_id, request.check_items, emit)
            job["result"] = result
            job["status"] = "done"
            done_event = {"type": "done", "result": result}
            job["events"].append(done_event)
            job["new_event"].set()
        except Exception as exc:
            error_event = {"type": "error", "text": str(exc)}
            job["events"].append(error_event)
            job["new_event"].set()
            job["status"] = "error"
            end_event = {"type": "done"}
            job["events"].append(end_event)
            job["new_event"].set()

    asyncio.create_task(_worker())
    return {"id": job_id}


@app.get("/api/check/{job_id}/stream")
async def stream_check(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]

    async def event_generator():
        idx = 0
        while True:
            # Send all buffered events the consumer hasn't seen yet
            while idx < len(job["events"]):
                event = job["events"][idx]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                idx += 1
                if event.get("type") == "done":
                    return

            # If job is already done but we caught all events, we can exit
            if job["status"] in ("done", "error"):
                # One last drain in case a final event arrived between the
                # above while loop and this check
                while idx < len(job["events"]):
                    event = job["events"][idx]
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    idx += 1
                return

            # Wait for the next event to arrive
            job["new_event"].clear()
            # Re-check immediately after clearing to avoid missed signals
            if idx < len(job["events"]):
                continue
            try:
                await asyncio.wait_for(job["new_event"].wait(), timeout=90.0)
            except asyncio.TimeoutError:
                yield "data: {\"type\":\"heartbeat\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/check/{job_id}")
async def get_check_result(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    if job["result"] is None:
        raise HTTPException(status_code=202, detail="Check still running")
    return job["result"]


# ── Static frontend ─────────────────────────────────────────────────────────
import pathlib

_FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "frontend"

if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="static")
