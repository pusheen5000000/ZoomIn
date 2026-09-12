"""Timeout-first cancel blockers. Pattern match only to *name* the stall. Never bypass."""

from __future__ import annotations

import re
from typing import Any

CAPTCHA_HINTS = (
    "recaptcha",
    "hcaptcha",
    "captcha",
    "verify you are human",
    "i'm not a robot",
    "cf-challenge",
    "attention required",
)
TWO_FACTOR_HINTS = (
    "two-factor",
    "two factor",
    "verification code",
    "enter the code",
    "authenticator",
    "one-time code",
    "otp",
)
PAYMENT_HINTS = ("card number", "cvv", "cvc", "expiry date")
BOT_HINTS = (
    "access denied",
    "unusual traffic",
    "automated queries",
    "enable javascript",
)


def classify_html(html: str, text: str) -> dict[str, Any] | None:
    blob = f"{html or ''}\n{text or ''}".lower()
    if any(h in blob for h in CAPTCHA_HINTS) or re.search(r"iframe[^>]+(captcha|recaptcha|hcaptcha)", blob):
        return {
            "kind": "captcha",
            "user_action": "Complete the human check if you see one. Do not ask us to bypass it. Then click Continue.",
        }
    if any(h in blob for h in TWO_FACTOR_HINTS) or 'autocomplete="one-time-code"' in blob:
        return {
            "kind": "2FA",
            "user_action": "Enter the code from your phone or email yourself. We will not type it. Then click Continue.",
        }
    if any(h in blob for h in PAYMENT_HINTS):
        return {
            "kind": "payment_field",
            "user_action": "We stopped because a card field is on the page. Do not enter a card in our cloud browser. Use your own device if you must pay.",
        }
    if any(h in blob for h in BOT_HINTS):
        return {
            "kind": "bot_check",
            "user_action": "The site thinks this is a robot (Steel cloud Chrome). Finish on your own phone or computer, or Continue if the page looks usable.",
        }
    return None


if __name__ == "__main__":
    assert classify_html('<iframe src="https://www.google.com/recaptcha/api2/anchor">', "")["kind"] == "captcha"
    assert classify_html("", "Enter the verification code we sent")["kind"] == "2FA"
    assert classify_html("", "Welcome to Example") is None
    print("blockers ok")
