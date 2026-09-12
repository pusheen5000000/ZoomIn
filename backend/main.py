"""POST /scan orchestrates scrape -> classifier -> safety -> cancel-flow agent."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from starlette.middleware.sessions import SessionMiddleware

from agent.cancel_flow import run_cancel_flow
from agent.scrape import scrape_url
from agent.steel_session import SteelSession
from auth import require_login, router as auth_router
from classifier.predict import predict_window
from detect.a11y import scan_page_a11y
from detect.heuristics import scan_dom_and_text
from detect.senior_copy import classifier_flags
from config import SESSION_MAX_AGE, SESSION_SECRET
from nav.login_demo import run_login_demo
from psych.explain import enrich
from safety.check import check_url
from score.payment import payment_assessment
from subscriptions.router import router as subscriptions_router

JOBS: dict[str, dict[str, Any]] = {}

app = FastAPI(title="Senior Safety Web Agent", version="0.2.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
    max_age=SESSION_MAX_AGE,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(subscriptions_router)


class ScanRequest(BaseModel):
    url: HttpUrl
    skip_agent: bool = True
    include_a11y: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(job: dict[str, Any], event: dict[str, Any]) -> None:
    event = {"at": _now(), **event}
    job["trace"].append(event)


async def run_pipeline(scan_id: str, url: str, skip_agent: bool, include_a11y: bool) -> None:
    job = JOBS[scan_id]
    job["status"] = "running"
    session: SteelSession | None = None

    def emit(event: dict[str, Any]) -> None:
        _append(job, event)

    try:
        if include_a11y:
            emit({"type": "status", "message": "Skipping extra Steel scrape session; axe uses its own tab"})
        else:
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

        emit({"type": "status", "message": f"Loading {url}"})
        scrape: dict[str, Any] = {
            "ok": False,
            "title": None,
            "text": "",
            "html": "",
            "error": None,
            "session_id": session.id if session else None,
        }
        a11y_flags: list[dict[str, Any]] = []
        a11y_meta: dict[str, Any] = {"ran": False, "ok": False, "error": None, "raw_violation_count": 0}

        if include_a11y:
            emit({"type": "status", "message": "Steel tab + axe-core (opt-in accessibility scan)"})
            try:
                a11y_result = await scan_page_a11y(url)
                a11y_flags = a11y_result.get("flags") or []
                a11y_meta = {
                    "ran": True,
                    "ok": bool(a11y_result.get("ok")),
                    "error": a11y_result.get("error"),
                    "raw_violation_count": a11y_result.get("raw_violation_count") or 0,
                    "session_id": a11y_result.get("session_id"),
                    "viewer_url": a11y_result.get("viewer_url"),
                }
                if a11y_result.get("ok"):
                    scrape = {
                        "ok": True,
                        "title": a11y_result.get("title"),
                        "text": a11y_result.get("text") or "",
                        "html": a11y_result.get("html") or "",
                        "error": None,
                        "session_id": a11y_result.get("session_id"),
                    }
                    job["session_id"] = job.get("session_id") or a11y_result.get("session_id")
                    job["viewer_url"] = a11y_result.get("viewer_url")
            except Exception as exc:
                a11y_meta = {"ran": True, "ok": False, "error": str(exc), "raw_violation_count": 0}
            emit({"type": "a11y", "ok": a11y_meta.get("ok"), "error": a11y_meta.get("error"), "raw_violation_count": a11y_meta.get("raw_violation_count")})
        else:
            emit({"type": "a11y", "message": "Accessibility scan skipped (opt in with Include accessibility scan)"})

        if not scrape.get("ok"):
            emit({"type": "status", "message": f"Scraping {url} (Steel /v1/scrape)"})
            scrape = await asyncio.to_thread(
                scrape_url, url, session, False if session else True
            )
            if scrape.get("viewer_url"):
                job["viewer_url"] = job.get("viewer_url") or scrape.get("viewer_url")
            emit(
                {
                    "type": "scrape",
                    "ok": scrape.get("ok"),
                    "title": scrape.get("title"),
                    "chars": len(scrape.get("text") or ""),
                    "error": scrape.get("error"),
                }
            )
        else:
            emit(
                {
                    "type": "scrape",
                    "ok": True,
                    "title": scrape.get("title"),
                    "chars": len(scrape.get("text") or ""),
                    "from": "playwright_steel_tab",
                }
            )
        job["scrape"] = {k: scrape.get(k) for k in ("ok", "title", "text", "error", "session_id") if k in scrape}
        if scrape.get("text"):
            job["scrape"]["text_preview"] = (scrape.get("text") or "")[:1200]

        emit({"type": "status", "message": "Running dark-pattern classifier and senior heuristics"})
        try:
            classified = await asyncio.to_thread(predict_window, scrape.get("text") or "")
        except FileNotFoundError as exc:
            classified = {"predictions": [], "top_label": None, "error": str(exc)}
        patterns = enrich(classified.get("predictions") or [])
        senior_flags = classifier_flags(patterns) + scan_dom_and_text(
            scrape.get("html") or "",
            scrape.get("text") or "",
        )
        job["patterns"] = patterns
        job["senior_flags"] = senior_flags
        job["a11y_flags"] = a11y_flags
        emit({"type": "classifier", "patterns": patterns, "senior_flags": senior_flags})

        emit({"type": "status", "message": "Checking Google Safe Browsing"})
        safety = await asyncio.to_thread(check_url, url)
        job["safety"] = safety
        emit({"type": "safety", "verdict": safety.get("verdict"), "malicious": safety.get("malicious")})

        payment_safety = payment_assessment(patterns, senior_flags, safety)
        job["payment_safety"] = payment_safety
        emit({"type": "payment_safety", "band": payment_safety.get("band"), "band_id": payment_safety.get("band_id")})

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
            "senior_flags": senior_flags,
            "a11y_flags": a11y_flags,
            "a11y": a11y_meta,
            "payment_safety": payment_safety,
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
            session.release_later()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/demo/login")
async def demo_login_flow(request: Request) -> dict[str, Any]:
    require_login(request)
    try:
        return await run_login_demo()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Steel + Playwright login demo failed.",
            "error": str(exc),
            "steps": [],
        }


@app.post("/scan")
async def start_scan(body: ScanRequest, request: Request) -> dict[str, str]:
    require_login(request)
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
    asyncio.create_task(run_pipeline(scan_id, str(body.url), body.skip_agent, body.include_a11y))
    return {"scan_id": scan_id, "status": "queued"}


@app.get("/scan/{scan_id}")
def get_scan(scan_id: str, request: Request) -> dict[str, Any]:
    require_login(request)
    job = JOBS.get(scan_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown scan_id")
    return job


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
