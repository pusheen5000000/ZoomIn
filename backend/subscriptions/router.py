"""Manual subscription list + Playwright recipe cancel (not Browser Use)."""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, HttpUrl

from auth import require_login
from nav.recipe_player import drop_held, finish_recipe, recipe_id_for, start_recipe
from subscriptions import store
from subscriptions.extract import extract_subscription_image
from subscriptions.guide import build_guide

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class AddBody(BaseModel):
    name: str
    url: HttpUrl
    cost: str = ""
    renews: str = ""


class CancelBody(BaseModel):
    confirmed: bool = False


class ExtractBody(BaseModel):
    image_base64: str
    media_type: str = "image/png"


@router.post("/extract")
def extract_from_screenshot(body: ExtractBody, request: Request) -> dict[str, Any]:
    require_login(request)
    if len(body.image_base64) > 6_000_000:
        raise HTTPException(status_code=400, detail="Image is too large. Try a smaller screenshot.")
    return extract_subscription_image(body.image_base64, body.media_type)


def _append(job: dict[str, Any], event: dict[str, Any]) -> None:
    job["trace"].append({"at": store._now(), **event})


def _outcome_label(result: dict[str, Any]) -> str:
    if result.get("cancelled"):
        return "Cancelled successfully"
    if result.get("needs_user_action"):
        reason = result.get("user_action_reason") or "a step only you can do"
        return f"Needs you to finish ({reason})"
    if result.get("paused"):
        return "Needs your confirmation"
    if not result.get("ok"):
        return "Couldn't complete"
    return "Couldn't complete — here's what happened"


def _record(item: dict[str, Any] | None, job_id: str, result: dict[str, Any], label: str) -> None:
    if not item:
        return
    item["last_outcome"] = label
    if result.get("cancelled"):
        item["status"] = "cancelled"
    store.append_log(
        item,
        {
            "outcome": label,
            "summary": result.get("summary"),
            "cancelled": bool(result.get("cancelled")),
            "needs_user_action": bool(result.get("needs_user_action")),
            "viewer_url": result.get("viewer_url"),
            "job_id": job_id,
        },
    )


async def _run_until_pause(job_id: str) -> None:
    job = store.CANCEL_JOBS[job_id]
    item = store.get(job["username"], job["subscription_id"])
    job["status"] = "running"

    def emit(event: dict[str, Any]) -> None:
        _append(job, event)

    try:
        recipe_id = job.get("recipe_id")
        if not recipe_id:
            result = {
                "ok": False,
                "cancelled": False,
                "summary": "No reviewed recipe for this URL. Add GymPlus with https://example.com to demo.",
            }
            job["result"] = result
            job["status"] = "error"
            job["error"] = result["summary"]
            emit({"type": "complete", "message": result["summary"]})
            _record(item, job_id, result, _outcome_label(result))
            return

        emit({"type": "status", "message": f"Playwright recipe '{recipe_id}' (not Browser Use)"})
        result = await start_recipe(job_id, recipe_id, on_event=emit, start_url=job.get("url"))
        job["result"] = result
        job["viewer_url"] = result.get("viewer_url")
        if result.get("paused"):
            job["status"] = "needs_confirm"
            emit({"type": "complete", "message": "Needs your confirmation for the last click"})
            if item:
                item["last_outcome"] = "Needs your confirmation"
            return
        job["status"] = "complete" if result.get("ok") else "error"
        if not result.get("ok"):
            job["error"] = result.get("error") or result.get("summary")
        label = _outcome_label(result)
        _record(item, job_id, result, label)
        emit({"type": "complete", "message": label})
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        emit({"type": "error", "message": str(exc), "trace": traceback.format_exc()})
        if item:
            item["last_outcome"] = "Couldn't complete"
            store.append_log(item, {"outcome": "Couldn't complete", "summary": str(exc), "job_id": job_id})
        await drop_held(job_id)


async def _finish_job(job_id: str) -> None:
    job = store.CANCEL_JOBS[job_id]
    item = store.get(job["username"], job["subscription_id"])
    job["status"] = "running"

    def emit(event: dict[str, Any]) -> None:
        _append(job, event)

    try:
        result = await finish_recipe(job_id, on_event=emit)
        job["result"] = result
        if result.get("paused"):
            job["status"] = "needs_confirm"
            emit({"type": "complete", "message": result.get("summary") or "Needs you"})
            if item:
                item["last_outcome"] = _outcome_label(result)
            return
        job["status"] = "complete" if result.get("ok") else "error"
        if not result.get("ok"):
            job["error"] = result.get("error") or result.get("summary")
        label = _outcome_label(result)
        _record(item, job_id, result, label)
        emit({"type": "complete", "message": label})
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        emit({"type": "error", "message": str(exc)})
        await drop_held(job_id)


@router.get("/")
def list_subscriptions(request: Request) -> dict[str, Any]:
    user = require_login(request)
    return {"subscriptions": store.list_for(user)}


@router.post("/")
def add_subscription(body: AddBody, request: Request) -> dict[str, Any]:
    user = require_login(request)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Give this subscription a name")
    recipe_id = recipe_id_for(str(body.url), name)
    item = store.add(
        user,
        name=name,
        url=str(body.url),
        cost=body.cost,
        renews=body.renews,
        recipe_id=recipe_id,
    )
    return item


@router.post("/{sub_id}/guide")
async def guide_cancel(sub_id: str, request: Request) -> dict[str, Any]:
    user = require_login(request)
    item = store.get(user, sub_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown subscription")
    guide = build_guide(item["name"], item["url"])
    item["last_guide"] = guide
    store.append_log(item, {"outcome": "Guide opened", "summary": guide.get("summary")})
    return guide


@router.post("/{sub_id}/cancel")
async def start_cancel(sub_id: str, body: CancelBody, request: Request) -> dict[str, str]:
    user = require_login(request)
    item = store.get(user, sub_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown subscription")
    if not body.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Confirm first. This may actually try to cancel a real account.",
        )
    if not item.get("recipe_id"):
        item["recipe_id"] = recipe_id_for(item["url"], item["name"]) or "generic"
    job = store.new_job(user, item)
    store.append_log(item, {"outcome": "Cancel started", "job_id": job["job_id"]})
    asyncio.create_task(_run_until_pause(job["job_id"]))
    return {"job_id": job["job_id"], "status": "queued"}


@router.post("/jobs/{job_id}/confirm")
async def confirm_last_click(job_id: str, request: Request) -> dict[str, str]:
    user = require_login(request)
    job = store.CANCEL_JOBS.get(job_id)
    if not job or job.get("username") != user:
        raise HTTPException(status_code=404, detail="Unknown cancel job")
    if job.get("status") != "needs_confirm":
        raise HTTPException(status_code=400, detail="This job is not waiting for the last-click confirm")
    asyncio.create_task(_finish_job(job_id))
    return {"job_id": job_id, "status": "running"}


@router.get("/jobs/{job_id}")
def get_cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    user = require_login(request)
    job = store.CANCEL_JOBS.get(job_id)
    if not job or job.get("username") != user:
        raise HTTPException(status_code=404, detail="Unknown cancel job")
    return job
