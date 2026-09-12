"""Static cancel checklist. We do not visit the merchant site."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def _site_hint(name: str, url: str) -> dict[str, str] | None:
    """Known-path hints from public help articles, not from loading the live site."""
    blob = f"{name} {url} {_host(url)}".lower()
    if "netflix" in blob:
        return {
            "id": "site_path",
            "title": "On Netflix, the usual path is",
            "detail": (
                "Account (top right) → Membership and billing → Cancel Membership. "
                "Stay on netflix.com in your own browser. We do not open it from our servers."
            ),
        }
    if "spotify" in blob:
        return {
            "id": "site_path",
            "title": "On Spotify, the usual path is",
            "detail": (
                "Account → Manage your plan → Cancel Premium (or Change plan). "
                "Do this on your own device. We do not open Spotify for you."
            ),
        }
    if "gymplus" in blob or _host(url).endswith("example.com"):
        return {
            "id": "site_path",
            "title": "GymPlus is our demo page",
            "detail": (
                "Use Semi-assisted cancel only for this fake membership. "
                "Guide me does not load example.com."
            ),
        }
    return None


def _base_steps(name: str, url: str) -> list[dict[str, str]]:
    hint = _site_hint(name, url)
    steps = [
        {
            "id": "you_click",
            "title": "This is a checklist only",
            "detail": (
                f"We do not visit {name}, sign in, or click Cancel. "
                "Open the site yourself (or with a family member). "
                "Semi-assisted cancel is a different button and is only reliable on the GymPlus demo."
            ),
        },
        {
            "id": "open",
            "title": "Open the site in your own browser",
            "detail": f"Go to {url} in a new tab on this computer or phone. Ignore any Steel or scan viewer.",
        },
    ]
    if hint:
        steps.append(hint)
    steps.extend(
        [
            {
                "id": "signin",
                "title": "Sign in yourself",
                "detail": "Use your own password or email code. Never type that into our app. We do not store it.",
            },
            {
                "id": "find_account",
                "title": "Find Account, Membership, Billing, or Subscription",
                "detail": (
                    "Those words are often under your name, a person icon, or Settings. "
                    "Avoid the big colorful button that says Keep, Stay, or Upgrade."
                ),
            },
            {
                "id": "find_cancel",
                "title": "Look for Cancel, Manage plan, or Turn off auto-renew",
                "detail": (
                    "It may be small gray text. Scroll the whole page. If they only offer a phone number, "
                    "keep looking for an online cancel first — that is a common trap."
                ),
            },
            {
                "id": "watch_tricks",
                "title": "Pause on guilt and timers",
                "detail": (
                    "“You’ll lose your discount,” fake urgency, or a pre-checked box are meant to make you quit. "
                    "Take a breath. Untick extras. You can still cancel."
                ),
            },
            {
                "id": "confirm",
                "title": "Save the proof",
                "detail": (
                    "After you finish, screenshot the “cancelled” or “will not renew” message and keep the email. "
                    "Check the next bank statement."
                ),
            },
        ]
    )
    return steps


def build_guide(name: str, url: str) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "guide",
        "name": name,
        "url": url,
        "summary": (
            "Checklist only. We do not load the merchant site, scrape it, or click anything. "
            "You work in your own browser."
        ),
        "visits_site": False,
        "steps": _base_steps(name, url),
    }
