"""Google Safe Browsing Lookup API (v4) wrapper.

Run:
    cd backend && python -m safety.check https://testsafebrowsing.appspot.com/s/malware.html
"""

from __future__ import annotations

from typing import Any

import httpx

from config import SAFE_BROWSING_API_KEY

LOOKUP_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]


def check_url(url: str) -> dict[str, Any]:
    """Return a Safe Browsing verdict for a single URL."""
    if not SAFE_BROWSING_API_KEY:
        return {
            "ok": False,
            "url": url,
            "verdict": "unknown",
            "malicious": False,
            "matches": [],
            "error": "SAFE_BROWSING_API_KEY is not set",
        }

    payload = {
        "client": {"clientId": "subscription-impossible", "clientVersion": "0.1.0"},
        "threatInfo": {
            "threatTypes": THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                LOOKUP_URL,
                params={"key": SAFE_BROWSING_API_KEY},
                json=payload,
            )
            response.raise_for_status()
            body = response.json() if response.content else {}
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "verdict": "error",
            "malicious": False,
            "matches": [],
            "error": str(exc),
        }

    matches = body.get("matches") or []
    threat_types = sorted({m.get("threatType") for m in matches if m.get("threatType")})
    malicious = bool(matches)
    return {
        "ok": True,
        "url": url,
        "verdict": "unsafe" if malicious else "safe",
        "malicious": malicious,
        "threat_types": threat_types,
        "matches": matches,
        "error": None,
    }


if __name__ == "__main__":
    import json
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_url(target), indent=2))
