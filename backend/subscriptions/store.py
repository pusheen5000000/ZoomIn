"""In-memory subscriptions for the demo login. Lost on API restart."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

SUBSCRIPTIONS: dict[str, list[dict[str, Any]]] = {}
CANCEL_JOBS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_for(username: str) -> list[dict[str, Any]]:
    return list(SUBSCRIPTIONS.get(username) or [])


def add(
    username: str,
    *,
    name: str,
    url: str,
    cost: str = "",
    renews: str = "",
    recipe_id: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": uuid.uuid4().hex[:10],
        "name": name.strip(),
        "url": url.strip(),
        "cost": cost.strip(),
        "renews": renews.strip(),
        "recipe_id": recipe_id,
        "status": "active",
        "last_outcome": None,
        "log": [],
        "created_at": _now(),
    }
    SUBSCRIPTIONS.setdefault(username, []).append(item)
    return item


def get(username: str, sub_id: str) -> dict[str, Any] | None:
    for item in SUBSCRIPTIONS.get(username) or []:
        if item["id"] == sub_id:
            return item
    return None


def append_log(item: dict[str, Any], entry: dict[str, Any]) -> None:
    item["log"].append({"at": _now(), **entry})


def new_job(username: str, item: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "subscription_id": item["id"],
        "username": username,
        "status": "queued",
        "url": item["url"],
        "name": item["name"],
        "recipe_id": item.get("recipe_id"),
        "trace": [],
        "result": None,
        "error": None,
        "created_at": _now(),
    }
    CANCEL_JOBS[job_id] = job
    return job
