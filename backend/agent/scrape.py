"""Step 1 (test this alone): open a Steel session, POST /v1/scrape, return raw text.

Run:
    cd backend && python -m agent.scrape
"""

from __future__ import annotations

from typing import Any

import httpx

from agent.steel_session import SteelSession
from config import STEEL_API_BASE, STEEL_API_KEY, STEEL_TEST_URL


def _extract_html(payload: dict[str, Any]) -> str:
    content = payload.get("content") or {}
    if not isinstance(content, dict):
        return ""
    for key in ("html", "cleanedHtml", "cleaned_html"):
        if content.get(key):
            return str(content[key])
    return ""


def _extract_text(payload: dict[str, Any]) -> str:
    content = payload.get("content") or {}
    if isinstance(content, str):
        return content
    for key in ("markdown", "readability", "cleanedHtml", "cleaned_html", "html", "text"):
        value = content.get(key) if isinstance(content, dict) else None
        if value:
            return str(value)
    metadata = payload.get("metadata") or {}
    title = metadata.get("title") if isinstance(metadata, dict) else None
    return str(title or "")


def scrape_url(
    url: str,
    session: SteelSession | None = None,
    release_session: bool | None = None,
) -> dict[str, Any]:
    """Create a Steel session (unless one is passed), scrape `url`, return structured text.

    If `session` is omitted a new session is created. It is released unless
    `release_session=False` or a caller-owned session was passed in.
    """
    if not STEEL_API_KEY:
        return {
            "ok": False,
            "error": "STEEL_API_KEY is not set",
            "url": url,
            "text": "",
            "html": "",
            "session_id": None,
            "viewer_url": None,
            "raw": None,
        }

    owned = session is None
    session = session or SteelSession.create()
    should_release = owned if release_session is None else release_session

    # Stateless scrape. Binding sessionId here 404s (“Session not found”) on
    # Steel’s scrape API even when the browser session is still live.
    body: dict[str, Any] = {
        "url": url,
        "format": ["markdown", "readability", "html"],
    }
    headers = {"steel-api-key": STEEL_API_KEY, "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(f"{STEEL_API_BASE}/v1/scrape", headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        text = _extract_text(payload)
        html = _extract_html(payload)
        metadata = payload.get("metadata") if isinstance(payload, dict) else {}
        return {
            "ok": True,
            "url": url,
            "text": text,
            "html": html,
            "title": (metadata or {}).get("title") if isinstance(metadata, dict) else None,
            "session_id": session.id,
            "viewer_url": session.viewer_url,
            "raw": payload,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "url": url,
            "text": "",
            "html": "",
            "session_id": session.id,
            "viewer_url": session.viewer_url,
            "raw": None,
        }
    finally:
        if should_release:
            session.release()


if __name__ == "__main__":
    import json

    result = scrape_url(STEEL_TEST_URL)
    preview = dict(result)
    preview["text"] = (preview.get("text") or "")[:800]
    preview.pop("raw", None)
    print(json.dumps(preview, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)
