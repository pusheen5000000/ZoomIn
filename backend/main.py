"""POST /scan orchestrates scrape -> classifier -> safety -> cancel-flow agent."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from agent.cancel_flow import run_cancel_flow
from agent.scrape import scrape_url
from agent.steel_session import SteelSession
from classifier.predict import predict_window
from psych.explain import enrich
from safety.check import check_url

JOBS: dict[str, dict[str, Any]] = {}

app = FastAPI(title="Subscription Impossible", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    url: HttpUrl
    skip_agent: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(job: dict[str, Any], event: dict[str, Any]) -> None:
    event = {"at": _now(), **event}
    job["trace"].append(event)


async def run_pipeline(scan_id: str, url: str, skip_agent: bool) -> None:
    job = JOBS[scan_id]
    job["status"] = "running"
    session: SteelSession | None = None

    def emit(event: dict[str, Any]) -> None:
        _append(job, event)

    try:
        emit({"type": "status", "message": "Opening Steel session"})
        try:
            session = await asyncio.to_thread(SteelSession.create)
            job["session_id"] = session.id
            job["viewer_url"] = session.viewer_url
            emit(
                {
                    "type": "session",
                    "message": "Steel session ready",
                    "session_id": session.id,
                    "viewer_url": session.viewer_url,
                }
            )
        except Exception as exc:
            emit({"type": "status", "message": f"Steel session failed ({exc}); scraping without session"})
            session = None

        emit({"type": "status", "message": f"Scraping {url}"})
        scrape = await asyncio.to_thread(
            scrape_url, url, session, False if session else True
        )
        job["scrape"] = {k: scrape.get(k) for k in ("ok", "title", "text", "error", "session_id") if k in scrape}
        if scrape.get("text"):
            job["scrape"]["text_preview"] = scrape["text"][:1200]
        emit(
            {
                "type": "scrape",
                "ok": scrape.get("ok"),
                "title": scrape.get("title"),
                "chars": len(scrape.get("text") or ""),
                "error": scrape.get("error"),
            }
        )

        emit({"type": "status", "message": "Running dark-pattern classifier"})
        try:
            classified = await asyncio.to_thread(predict_window, scrape.get("text") or "")
        except FileNotFoundError as exc:
            classified = {"predictions": [], "top_label": None, "error": str(exc)}
        patterns = enrich(classified.get("predictions") or [])
        job["patterns"] = patterns
        emit({"type": "classifier", "patterns": patterns})

        emit({"type": "status", "message": "Checking Google Safe Browsing"})
        safety = await asyncio.to_thread(check_url, url)
        job["safety"] = safety
        emit({"type": "safety", "verdict": safety.get("verdict"), "malicious": safety.get("malicious")})

        if skip_agent:
            agent_result = {
                "ok": True,
                "skipped": True,
                "steps": [],
                "friction_points": [],
                "summary": "Agent skipped by request.",
            }
            emit({"type": "agent_status", "message": "Browser Use skipped"})
        else:
            emit({"type": "status", "message": "Starting cancel-flow agent (this takes a while)"})
            agent_result = await run_cancel_flow(
                url,
                session=session,
                on_event=emit,
            )
        job["agent"] = agent_result

        report = {
            "url": url,
            "generated_at": _now(),
            "session_id": job.get("session_id") or scrape.get("session_id"),
            "viewer_url": job.get("viewer_url") or scrape.get("viewer_url"),
            "safety": safety,
            "patterns": patterns,
            "scrape": {
                "ok": scrape.get("ok"),
                "title": scrape.get("title"),
                "text_preview": (scrape.get("text") or "")[:1200],
                "error": scrape.get("error"),
            },
            "agent": {
                "ok": agent_result.get("ok"),
                "skipped": agent_result.get("skipped", False),
                "reached_cancel_ui": agent_result.get("reached_cancel_ui"),
                "cancelled": agent_result.get("cancelled"),
                "summary": agent_result.get("summary"),
                "friction_points": agent_result.get("friction_points") or [],
                "steps": agent_result.get("steps") or [],
                "error": agent_result.get("error"),
            },
        }
        job["report"] = report
        job["status"] = "complete"
        emit({"type": "complete", "message": "Scan finished"})
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        emit({"type": "error", "message": str(exc), "trace": traceback.format_exc()})
    finally:
        if session is not None:
            await asyncio.to_thread(session.release)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scan")
async def start_scan(body: ScanRequest) -> dict[str, str]:
    scan_id = uuid.uuid4().hex[:12]
    JOBS[scan_id] = {
        "scan_id": scan_id,
        "status": "queued",
        "url": str(body.url),
        "created_at": _now(),
        "trace": [],
        "report": None,
        "error": None,
    }
    asyncio.create_task(run_pipeline(scan_id, str(body.url), body.skip_agent))
    return {"scan_id": scan_id, "status": "queued"}


@app.get("/scan/{scan_id}")
def get_scan(scan_id: str) -> dict[str, Any]:
    job = JOBS.get(scan_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown scan_id")
    return job


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
