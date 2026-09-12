"""Create / release Steel cloud browser sessions and build the CDP websocket URL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from steel import Steel

from config import STEEL_API_KEY


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

    @classmethod
    def create(cls, api_timeout_ms: int = 180_000) -> "SteelSession":
        client = steel_client()
        session = client.sessions.create(api_timeout=api_timeout_ms)
        return cls(client=client, session=session)
