"""Step 2: drive Browser Use over the Steel session CDP socket.

Run (after scrape works):
    cd backend && python -m agent.cancel_flow https://example.com
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from pydantic import BaseModel, Field

from agent.steel_session import SteelSession
from config import OPENAI_API_KEY, OPENAI_MODEL, SKIP_BROWSER_USE, STEEL_TEST_URL

OnEvent = Callable[[dict[str, Any]], None]


class FrictionPoint(BaseModel):
    description: str
    severity: str = Field(description="low | medium | high")
    dark_pattern_hint: str | None = None


class CancelFlowOutput(BaseModel):
    reached_cancel_ui: bool
    cancelled: bool
    friction_points: list[FrictionPoint] = Field(default_factory=list)
    summary: str


DEFAULT_TASK = """You are auditing this website for dark patterns around cancellation.

1. Open the given URL.
2. Look for account, billing, membership, trial, or subscription settings.
3. Attempt to cancel any subscription or free trial. Do not enter real payment data.
   If login is required, record that as a friction point and stop the cancel attempt.
4. At every step, note friction: hidden cancel links, confirmshaming copy, forced
   retention offers, chat-only cancel, long phone numbers, countdown timers, etc.
5. Finish with a structured report of whether you reached a cancel UI and why not
   if you did not.
"""


def _history_to_steps(history: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    try:
        urls = history.urls() if hasattr(history, "urls") else []
        names = history.action_names() if hasattr(history, "action_names") else []
        contents = history.extracted_content() if hasattr(history, "extracted_content") else []
        errors = history.errors() if hasattr(history, "errors") else []
        thoughts = []
        if hasattr(history, "model_thoughts"):
            try:
                thoughts = history.model_thoughts()
            except Exception:
                thoughts = []
        n = max(len(names), len(urls), len(contents), 1)
        for i in range(n):
            thought = thoughts[i] if i < len(thoughts) else None
            thought_text = None
            if thought is not None:
                thought_text = getattr(thought, "next_goal", None) or getattr(
                    thought, "memory", None
                )
                if thought_text is None:
                    thought_text = str(thought)
            steps.append(
                {
                    "index": i + 1,
                    "action": names[i] if i < len(names) else None,
                    "url": urls[i] if i < len(urls) else None,
                    "extracted": contents[i] if i < len(contents) else None,
                    "error": errors[i] if i < len(errors) else None,
                    "thought": thought_text,
                }
            )
    except Exception as exc:
        steps.append({"index": 1, "action": "trace_parse_error", "error": str(exc)})
    return steps


async def run_cancel_flow(
    url: str,
    session: SteelSession | None = None,
    task: str | None = None,
    on_event: OnEvent | None = None,
    max_steps: int = 20,
) -> dict[str, Any]:
    emit = on_event or (lambda _e: None)

    if SKIP_BROWSER_USE:
        emit({"type": "agent_status", "message": "SKIP_BROWSER_USE=1; agent not started"})
        return {
            "ok": True,
            "skipped": True,
            "url": url,
            "session_id": session.id if session else None,
            "viewer_url": session.viewer_url if session else None,
            "steps": [],
            "friction_points": [],
            "reached_cancel_ui": False,
            "cancelled": False,
            "summary": "Browser Use skipped (SKIP_BROWSER_USE=1).",
        }

    if not OPENAI_API_KEY:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY is not set",
            "url": url,
            "steps": [],
            "friction_points": [],
            "reached_cancel_ui": False,
            "cancelled": False,
            "summary": "Cannot run Browser Use without an LLM key.",
        }

    owned = session is None
    session = session or SteelSession.create()
    emit(
        {
            "type": "agent_status",
            "message": "Browser Use connected to Steel CDP",
            "session_id": session.id,
            "viewer_url": session.viewer_url,
        }
    )

    try:
        from browser_use import Agent, BrowserSession
        try:
            from browser_use.llm import ChatOpenAI
        except ImportError:
            from browser_use import ChatOpenAI  # type: ignore

        prompt = (
            f"{task or DEFAULT_TASK}\n\nStart URL: {url}\n"
            "Return the structured cancel-flow report when done."
        )
        llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY)
        agent = Agent(
            task=prompt,
            llm=llm,
            browser_session=BrowserSession(cdp_url=session.cdp_url),
            output_model_schema=CancelFlowOutput,
        )
        history = await agent.run(max_steps=max_steps)
        steps = _history_to_steps(history)
        for step in steps:
            emit({"type": "agent_step", "step": step})

        structured = None
        if getattr(history, "structured_output", None):
            structured = history.structured_output
        elif hasattr(history, "final_result") and history.final_result():
            try:
                structured = CancelFlowOutput.model_validate_json(history.final_result())
            except Exception:
                structured = None

        if isinstance(structured, CancelFlowOutput):
            payload = structured.model_dump()
        elif structured is not None:
            payload = dict(structured)
        else:
            payload = {
                "reached_cancel_ui": False,
                "cancelled": False,
                "friction_points": [],
                "summary": (history.final_result() if hasattr(history, "final_result") else None)
                or "Agent finished without structured output.",
            }

        return {
            "ok": True,
            "skipped": False,
            "url": url,
            "session_id": session.id,
            "viewer_url": session.viewer_url,
            "steps": steps,
            "is_successful": history.is_successful() if hasattr(history, "is_successful") else None,
            **payload,
        }
    except Exception as exc:
        emit({"type": "agent_error", "message": str(exc)})
        return {
            "ok": False,
            "error": str(exc),
            "url": url,
            "session_id": session.id,
            "viewer_url": session.viewer_url,
            "steps": [],
            "friction_points": [],
            "reached_cancel_ui": False,
            "cancelled": False,
            "summary": f"Browser Use failed: {exc}",
        }
    finally:
        if owned:
            session.release()


def run_cancel_flow_sync(url: str, **kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_cancel_flow(url, **kwargs))


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else STEEL_TEST_URL
    print(json.dumps(run_cancel_flow_sync(target), indent=2, default=str))
