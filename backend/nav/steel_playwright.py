"""Steel hosts Chrome; Playwright drives it over CDP. No LLM agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from playwright.async_api import Browser, Page, Playwright, async_playwright

from agent.steel_session import SteelSession


class HeldSteelPage:
    """Steel + Playwright that stays open until we call close (for pause-before-submit)."""

    def __init__(self, session: SteelSession, playwright: Playwright, browser: Browser, page: Page):
        self.session = session
        self.playwright = playwright
        self.browser = browser
        self.page = page

    @classmethod
    async def start(cls, timeout_ms: int = 180_000) -> "HeldSteelPage":
        session = SteelSession.create(timeout_ms=timeout_ms)
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(session.cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        return cls(session, playwright, browser, page)

    async def close(self) -> None:
        try:
            await self.browser.close()
        except Exception:
            pass
        try:
            await self.playwright.stop()
        except Exception:
            pass
        self.session.release_later()


@asynccontextmanager
async def open_steel_page(timeout_ms: int = 180_000) -> AsyncIterator[tuple[SteelSession, Page]]:
    session = SteelSession.create(timeout_ms=timeout_ms)
    playwright = await async_playwright().start()
    browser: Browser | None = None
    try:
        browser = await playwright.chromium.connect_over_cdp(session.cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        yield session, page
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        try:
            await playwright.stop()
        except Exception:
            pass
        session.release_later()


def session_info(session: SteelSession | None) -> dict[str, Any]:
    if session is None:
        return {"session_id": None, "viewer_url": None}
    return {"session_id": session.id, "viewer_url": session.viewer_url}
