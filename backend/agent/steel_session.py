"""Create / release Steel cloud browser sessions and build the CDP websocket URL."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from steel import Steel

from config import STEEL_API_KEY

# Keep the cloud tab alive after we finish so “Watch Steel session” still works.
# Immediate release is why Steel’s dashboard shows “Session not found”.
VIEWER_KEEPALIVE_S = 120.0


def steel_client() -> Steel:
    if not STEEL_API_KEY:
        raise RuntimeError("STEEL_API_KEY is not set")
    return Steel(steel_api_key=STEEL_API_KEY)


def cdp_url_for(session_id: str) -> str:
    # Steel docs: do not use session.websocket_url as-is; include apiKey + sessionId.
    return f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session_id}"


@dataclass
class SteelSession:
    client: Steel
    session: Any

    @property
    def id(self) -> str:
        return self.session.id

    @property
    def viewer_url(self) -> str | None:
        return getattr(self.session, "session_viewer_url", None) or getattr(
            self.session, "sessionViewerUrl", None
        )

    @property
    def cdp_url(self) -> str:
        return cdp_url_for(self.id)

    def release(self) -> None:
        try:
            self.client.sessions.release(self.id)
        except Exception:
            pass

    def release_later(self, delay_s: float = VIEWER_KEEPALIVE_S) -> None:
        def _go() -> None:
            time.sleep(max(0.0, delay_s))
            self.release()

        threading.Thread(target=_go, daemon=True, name="steel-release").start()

    @classmethod
    def create(cls, timeout_ms: int = 180_000) -> "SteelSession":
        client = steel_client()
        # Steel Python SDK: api_timeout -> JSON "timeout" (session lifetime in ms).
        # The kwarg named timeout is the HTTP client timeout, not session length.
        session = client.sessions.create(api_timeout=timeout_ms)
        return cls(client=client, session=session)
