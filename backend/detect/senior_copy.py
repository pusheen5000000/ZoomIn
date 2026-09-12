"""Plain-language senior harm copy for heuristics and classifier labels."""

from __future__ import annotations

from typing import Any

HEURISTICS: dict[str, dict[str, str]] = {
    "fake_urgency": {
        "senior_harm": "fear_urgency",
        "plain_language": "The page rushes you with a timer or “only a few left,” which is often not a real deadline.",
    },
    "call_to_cancel": {
        "senior_harm": "trapped_cancel",
        "plain_language": "Canceling may require a phone call or chat instead of a clear button — easy to give up.",
    },
    "confirmshaming": {
        "senior_harm": "shame_choice",
        "plain_language": "The “no” choice is worded to make you feel foolish if you decline.",
    },
    "double_negative": {
        "senior_harm": "confusing_language",
        "plain_language": "A checkbox uses twisted wording (do not / unless you don’t). Easy to tick the wrong thing.",
    },
    "prechecked_consent": {
        "senior_harm": "prechecked_consent",
        "plain_language": "Something is already checked for you (calls, emails, extra charges). You must notice and untick it.",
    },
    "tiny_text": {
        "senior_harm": "hard_to_read",
        "plain_language": "Important text is very small. Fees or cancel links can be missed.",
    },
    "hidden_cancel": {
        "senior_harm": "easy_to_misclick",
        "plain_language": "A cancel link looks hidden or moved off-screen. Easy to miss; easy to hit the bigger “keep” button.",
    },
}

CLASSIFIER_HARM: dict[str, dict[str, str]] = {
    "Urgency": {
        "senior_harm": "fear_urgency",
        "plain_language": "The wording pushes you to act immediately, which is harder when you need time to read.",
    },
    "Scarcity": {
        "senior_harm": "fear_urgency",
        "plain_language": "It claims stock or the offer is almost gone so you skip comparing options.",
    },
    "Social Proof": {
        "senior_harm": "crowd_pressure",
        "plain_language": "It says other people are buying right now so you feel left out if you wait.",
    },
    "Misdirection": {
        "senior_harm": "easy_to_misclick",
        "plain_language": "The page draws your eye to the choice that helps the company, not the quiet alternative.",
    },
    "Obstruction": {
        "senior_harm": "trapped_cancel",
        "plain_language": "Leaving or canceling is made extra hard — extra steps, extra clicks.",
    },
    "Sneaking": {
        "senior_harm": "hidden_cost",
        "plain_language": "A fee or renewal may appear after you already said yes.",
    },
    "Forced Action": {
        "senior_harm": "forced_extra",
        "plain_language": "You may have to accept extra accounts or emails just to finish the task.",
    },
}


def heuristic_flag(flag_id: str, evidence: str) -> dict[str, Any]:
    meta = HEURISTICS.get(flag_id, {})
    return {
        "id": flag_id,
        "kind": "heuristic",
        "senior_harm": meta.get("senior_harm", "other"),
        "plain_language": meta.get("plain_language", "This pattern can confuse an older user."),
        "evidence": evidence,
        "confidence": 1.0,
    }


def classifier_flags(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for row in predictions:
        category = str(row.get("category") or "")
        if category in {"Not Dark Pattern", "0", "nan", ""}:
            continue
        if float(row.get("confidence") or 0) < 0.35:
            continue
        meta = CLASSIFIER_HARM.get(category, {})
        flags.append(
            {
                "id": f"clf_{category}",
                "kind": "classifier",
                "category": category,
                "senior_harm": meta.get("senior_harm", "wording_pressure"),
                "plain_language": meta.get(
                    "plain_language",
                    "The page uses sales wording that can rush a decision.",
                ),
                "evidence": category,
                "confidence": float(row["confidence"]),
                "cialdini_principle": row.get("cialdini_principle"),
            }
        )
    return flags
