"""Payment Safety: is this page a reasonable place to type a card — not WCAG, not 'senior score'."""

from __future__ import annotations

from typing import Any

# Yamana labels follow Mathur et al. 2019 taxonomy (paper only; no GPLv3 CSV).
PAYMENT_RISK_CATEGORIES = {
    "Sneaking": "Fees or renewals may be snuck in after you commit.",
    "Forced Action": "You may be pushed into extra purchases or sign-ups to finish.",
    "Obstruction": "Leaving or canceling looks harder than paying.",
    "Urgency": "Time pressure can rush a card number before you compare.",
    "Scarcity": "Fake shortage can rush a payment.",
    "Misdirection": "The page may highlight pay and hide the cheaper or safer choice.",
}

HEAVY_FLAGS = {"call_to_cancel", "hidden_cancel", "prechecked", "hidden_cost"}


def payment_assessment(
    patterns: list[dict[str, Any]],
    flags: list[dict[str, Any]],
    browsing: dict[str, Any] | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    risk = 0
    browsing = browsing or {}

    if browsing.get("malicious") or browsing.get("verdict") == "unsafe":
        risk = 100
        reasons.append("Google Safe Browsing flagged this URL. Do not enter a card.")
    elif browsing.get("verdict") == "error":
        reasons.append("Malware list could not be checked. Treat the payment page extra carefully.")

    for pattern in patterns:
        cat = str(pattern.get("category") or "")
        if cat in PAYMENT_RISK_CATEGORIES:
            conf = float(pattern.get("confidence") or 0)
            if conf >= 0.35:
                risk = max(risk, 40 if cat in {"Sneaking", "Forced Action", "Obstruction"} else 25)
                reasons.append(PAYMENT_RISK_CATEGORIES[cat])

    for flag in flags:
        fid = flag.get("id") or ""
        harm = flag.get("senior_harm") or ""
        if fid in HEAVY_FLAGS or harm in {"trapped_cancel", "fear_urgency"}:
            risk = max(risk, 55)
            text = flag.get("plain_language") or fid
            if text not in reasons:
                reasons.append(text)

    if risk >= 80:
        band_id, band = "poor", "Do not enter a card here"
    elif risk >= 35:
        band_id, band = "ok", "Be careful before you pay"
    else:
        band_id, band = "good", "No obvious payment traps on this snapshot"

    return {
        "band": band,
        "band_id": band_id,
        "risk": min(100, risk),
        "reasons": reasons[:8],
        "source": "Yamana Apache-2.0 labels (Mathur 2019 taxonomy) + page checks + Safe Browsing",
        "disclaimer": "Heuristic only. Not a bank guarantee, not a legal opinion, not WCAG.",
    }


if __name__ == "__main__":
    clean = payment_assessment([], [], {"verdict": "safe", "malicious": False})
    assert clean["band_id"] == "good", clean
    sneaky = payment_assessment(
        [{"category": "Sneaking", "confidence": 0.9}],
        [],
        {"verdict": "safe", "malicious": False},
    )
    assert sneaky["band_id"] in {"ok", "poor"}, sneaky
    print("ok", clean["band"], sneaky["band"])
