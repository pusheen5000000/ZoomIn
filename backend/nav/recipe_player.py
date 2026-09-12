"""GymPlus = in-app fake page. generic = live URL on Steel + Playwright. No Browser Use."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from nav.blockers import classify_html
from nav.steel_playwright import HeldSteelPage, session_info

OnEvent = Callable[[dict[str, Any]], None]
HELD: dict[str, Any] = {}
STEP_TIMEOUT_MS = 8_000


class LocalGymplusHeld:
    """In-app GymPlus demo. Steel cannot reliably host injected HTML."""

    resume = "gymplus_submit"
    session = None

    async def close(self) -> None:
        return

ACCOUNT_SELECTORS = (
    'a[href*="account" i]',
    'a[href*="settings" i]',
    'button:has-text("Account")',
    'a:has-text("Account")',
    'a:has-text("My account")',
)
BILLING_SELECTORS = (
    'a[href*="billing" i]',
    'a[href*="subscription" i]',
    'a[href*="membership" i]',
    'a:has-text("Billing")',
    'a:has-text("Subscription")',
    'a:has-text("Membership")',
    'button:has-text("Manage")',
)
CANCEL_SELECTORS = (
    'a[href*="cancel" i]',
    'button:has-text("Cancel")',
    'a:has-text("Cancel")',
    'button:has-text("Cancel membership")',
    'a:has-text("Cancel membership")',
    'button:has-text("Turn off auto-renew")',
    'a:has-text("Turn off auto-renew")',
)


def recipe_id_for(url: str, name: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    blob = f"{name} {url}".lower()
    if host.endswith("example.com") or "gymplus" in blob or "gym plus" in blob:
        return "gymplus"
    if (url or "").lower().startswith("http"):
        return "generic"
    return None


def lookup_recipe(name: str, url: str = "") -> dict[str, str] | None:
    rid = recipe_id_for(url, name)
    if rid == "gymplus":
        return {"id": "gymplus", "url": "https://example.com"}
    if rid == "generic" and (url or "").startswith("http"):
        return {"id": "generic", "url": url}
    return None


def _pause(
    job_id: str,
    held: HeldSteelPage,
    *,
    reason: str,
    user_action: str,
    step_id: str,
    resume: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    info = session_info(held.session)
    held.resume = resume  # type: ignore[attr-defined]
    held.step_id = step_id  # type: ignore[attr-defined]
    HELD[job_id] = held
    summary = (
        "Needs your confirmation for the last click."
        if reason == "last_click"
        else f"Stuck at {step_id} — needs your input ({reason})."
    )
    payload = {
        "ok": True,
        "paused": True,
        "cancelled": False,
        "needs_user_action": reason != "last_click",
        "user_action_reason": reason,
        "user_action": user_action,
        "step_id": step_id,
        "page_url": extra.get("page_url") if extra else None,
        "summary": summary,
        **info,
    }
    if extra:
        payload.update(extra)
    return payload


async def _page_url(page) -> str:
    try:
        return page.url or ""
    except Exception:
        return ""


async def _classify(page) -> dict[str, Any] | None:
    try:
        html = await page.content()
        text = await page.inner_text("body")
    except Exception:
        return None
    return classify_html(html, text)


async def _first_visible(page, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            await loc.wait_for(state="visible", timeout=STEP_TIMEOUT_MS)
            return selector
        except Exception:
            continue
    return None


async def start_recipe(
    job_id: str,
    recipe_id: str,
    on_event: OnEvent | None = None,
    start_url: str | None = None,
) -> dict[str, Any]:
    emit = on_event or (lambda _e: None)
    emit({"type": "status", "message": f"Starting recipe {recipe_id} (Playwright, not Browser Use)"})

    if recipe_id == "gymplus":
        # Do not open Steel. Cloud Chrome often never shows the injected demo
        # (CSP, about:blank, viewer expiry). The fake page runs in our UI.
        emit({"type": "status", "message": "GymPlus demo in this app (no Steel tab)"})
        demo = LocalGymplusHeld()
        HELD[job_id] = demo
        return {
            "ok": True,
            "paused": True,
            "cancelled": False,
            "demo": "gymplus",
            "needs_user_action": False,
            "user_action_reason": "last_click",
            "user_action": "On the GymPlus demo below, click Cancel membership. Then confirm the last click here. This is not a real gym.",
            "step_id": "submit",
            "summary": "Needs your confirmation for the last click.",
            "session_id": None,
            "viewer_url": None,
        }

    held = await HeldSteelPage.start()
    info = session_info(held.session)
    emit({"type": "session", "session_id": info.get("session_id"), "viewer_url": info.get("viewer_url")})
    page = held.page

    # generic live URL
    url = start_url or "https://example.com"
    emit({"type": "step", "message": f"Going to {url}"})
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
    except Exception:
        hit = await _classify(page)
        return _pause(
            job_id,
            held,
            reason=(hit or {}).get("kind") or "timeout",
            user_action=(hit or {}).get("user_action")
            or f"The page did not load in time. Open {url} on your own device, or Continue if it loaded.",
            step_id="goto",
            resume="wait_user",
            extra={"page_url": url},
        )

    hit = await _classify(page)
    if hit:
        return _pause(
            job_id,
            held,
            reason=hit["kind"],
            user_action=hit["user_action"],
            step_id="after_goto",
            resume="wait_user",
            extra={"page_url": await _page_url(page)},
        )

    account = await _first_visible(page, ACCOUNT_SELECTORS)
    if account:
        emit({"type": "step", "message": f"Opening account control ({account})"})
        try:
            await page.locator(account).first.click(timeout=STEP_TIMEOUT_MS)
        except Exception:
            pass
        hit = await _classify(page)
        if hit:
            return _pause(
                job_id,
                held,
                reason=hit["kind"],
                user_action=hit["user_action"],
                step_id="account",
                resume="wait_user",
                extra={"page_url": await _page_url(page)},
            )

    billing = await _first_visible(page, BILLING_SELECTORS)
    if billing:
        emit({"type": "step", "message": f"Opening billing/subscription ({billing})"})
        try:
            await page.locator(billing).first.click(timeout=STEP_TIMEOUT_MS)
        except Exception:
            pass
        hit = await _classify(page)
        if hit:
            return _pause(
                job_id,
                held,
                reason=hit["kind"],
                user_action=hit["user_action"],
                step_id="billing",
                resume="wait_user",
                extra={"page_url": await _page_url(page)},
            )

    cancel = await _first_visible(page, CANCEL_SELECTORS)
    if cancel:
        emit({"type": "step", "message": "Found a Cancel control — waiting for your confirm before clicking it"})
        held.cancel_selector = cancel  # type: ignore[attr-defined]
        return _pause(
            job_id,
            held,
            reason="last_click",
            user_action="We found a Cancel control. Confirm to click it. This may affect a real account if you are signed in.",
            step_id="submit",
            resume="click_cancel",
            extra={"page_url": await _page_url(page), "needs_user_action": False},
        )

    return _pause(
        job_id,
        held,
        reason="timeout",
        user_action=(
            "We could not find a clear Cancel control (login wall, bot check, or unusual layout). "
            "Sign in or finish the blocked step in the Steel viewer if you can, or open the link on your own device. Then Continue or stop."
        ),
        step_id="find_cancel",
        resume="wait_user",
        extra={"page_url": await _page_url(page) or url},
    )


async def finish_recipe(job_id: str, on_event: OnEvent | None = None) -> dict[str, Any]:
    emit = on_event or (lambda _e: None)
    held = HELD.pop(job_id, None)
    if held is None:
        return {
            "ok": False,
            "paused": False,
            "cancelled": False,
            "summary": "That cancel session is gone. Start semi-assisted cancel again, or use Guide me.",
        }
    info = session_info(getattr(held, "session", None))
    resume = getattr(held, "resume", "wait_user")
    try:
        if resume == "gymplus_submit":
            emit({"type": "step", "message": "You confirmed. GymPlus demo membership cancelled."})
            return {
                "ok": True,
                "paused": False,
                "cancelled": True,
                "demo": "gymplus",
                "summary": "Membership cancelled. You will not be billed again.",
            }
        page = held.page

        if resume == "click_cancel":
            selector = getattr(held, "cancel_selector", None)
            if not selector:
                return {
                    "ok": False,
                    "cancelled": False,
                    "summary": "Lost the Cancel selector. Use Guide me on your own device.",
                    **info,
                }
            emit({"type": "step", "message": f"Clicking {selector}"})
            await page.locator(selector).first.click(timeout=STEP_TIMEOUT_MS)
            hit = await _classify(page)
            if hit:
                # Put the session back so they can continue again
                HELD[job_id] = held
                held.resume = "wait_user"  # type: ignore[attr-defined]
                return {
                    "ok": True,
                    "paused": True,
                    "cancelled": False,
                    "needs_user_action": True,
                    "user_action_reason": hit["kind"],
                    "user_action": hit["user_action"],
                    "step_id": "after_cancel_click",
                    "page_url": await _page_url(page),
                    "summary": f"Stuck at after_cancel_click — needs your input ({hit['kind']}).",
                    **info,
                }
            return {
                "ok": True,
                "paused": False,
                "cancelled": True,
                "summary": "Clicked Cancel. Check the page (and your email) to confirm it actually cancelled.",
                "page_url": await _page_url(page),
                **info,
            }

        # wait_user: they claim they finished the blocked step; look again for cancel
        emit({"type": "step", "message": "Resuming after your step — looking for Cancel again"})
        hit = await _classify(page)
        if hit:
            HELD[job_id] = held
            return {
                "ok": True,
                "paused": True,
                "cancelled": False,
                "needs_user_action": True,
                "user_action_reason": hit["kind"],
                "user_action": hit["user_action"],
                "step_id": "resume",
                "page_url": await _page_url(page),
                "summary": f"Still stuck — needs your input ({hit['kind']}).",
                **info,
            }
        cancel = await _first_visible(page, CANCEL_SELECTORS)
        if cancel:
            held.cancel_selector = cancel  # type: ignore[attr-defined]
            HELD[job_id] = held
            held.resume = "click_cancel"  # type: ignore[attr-defined]
            return {
                "ok": True,
                "paused": True,
                "cancelled": False,
                "needs_user_action": False,
                "user_action_reason": "last_click",
                "user_action": "Found Cancel after you continued. Confirm to click it.",
                "step_id": "submit",
                "page_url": await _page_url(page),
                "summary": "Needs your confirmation for the last click.",
                **info,
            }
        return {
            "ok": True,
            "paused": False,
            "cancelled": False,
            "summary": "Still no Cancel control. Use Guide me and finish on your own device.",
            "page_url": await _page_url(page),
            **info,
        }
    except Exception as exc:
        return {
            "ok": False,
            "paused": False,
            "cancelled": False,
            "error": str(exc),
            "summary": f"Couldn't complete — here's what happened: {exc}",
            **info,
        }
    finally:
        if job_id not in HELD:
            await held.close()


async def drop_held(job_id: str) -> None:
    held = HELD.pop(job_id, None)
    if held is not None:
        await held.close()
