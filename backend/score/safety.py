"""Senior Safety Score: 100 = safer for an older / less tech-fluent user."""

from __future__ import annotations

from typing import Any


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def score_report(
    senior_flags: list[dict[str, Any]],
    a11y_flags: list[dict[str, Any]],
    a11y_ran: bool,
) -> dict[str, Any]:
    heavy = 0  # cancel traps
    medium = 0  # read/misclick/precheck
    wording = 0
    urgency = 0
    a11y_pts = 0
    reading_hit = 0
    click_hit = 0

    for flag in senior_flags:
        fid = flag.get("id") or ""
        kind = flag.get("kind")
        harm = flag.get("senior_harm") or ""
        if kind == "classifier":
            add = min(5, 20 - wording)
            wording += add
        elif fid in {"call_to_cancel", "hidden_cancel"} or harm == "trapped_cancel":
            add = min(15, 40 - heavy)
            heavy += add
            click_hit += add
        elif fid == "fake_urgency" or harm == "fear_urgency":
            add = min(8, 16 - urgency)
            urgency += add
        elif fid in {"tiny_text"} or harm == "hard_to_read":
            add = min(10, 30 - medium)
            medium += add
            reading_hit += add
        else:
            add = min(10, 30 - medium)
            medium += add
            click_hit += add

    crit = 0
    mod = 0
    minor = 0
    if a11y_ran:
        for flag in a11y_flags:
            impact = flag.get("impact") or "moderate"
            if impact in {"critical", "serious"}:
                add = min(12, 40 - crit)
                crit += add
                if flag.get("senior_harm") == "hard_to_read":
                    reading_hit += min(add, 12)
            elif impact == "moderate":
                add = min(5, 15 - mod)
                mod += add
            else:
                add = min(2, 10 - minor)
                minor += add
        a11y_pts = crit + mod + minor

    score = _clamp(100 - heavy - medium - wording - urgency - a11y_pts)

    if score >= 80:
        band, band_id = "Easier for seniors", "good"
    elif score >= 50:
        band, band_id = "Use with care", "ok"
    else:
        band, band_id = "Easy to get stuck or miss fees", "poor"

    return {
        "score": score,
        "band": band,
        "band_id": band_id,
        "direction": "higher_is_safer",
        "a11y_included": a11y_ran,
        "breakdown": {
            "reading": _clamp(100 - reading_hit),
            "clicking_or_cancel": _clamp(100 - click_hit),
            "pressure_wording": _clamp(100 - wording - urgency),
            "page_accessibility": _clamp(100 - a11y_pts) if a11y_ran else None,
        },
        "deductions": {
            "cancel_traps": heavy,
            "ui_friction": medium,
            "wording_model": wording,
            "urgency_copy": urgency,
            "a11y": a11y_pts,
        },
    }


if __name__ == "__main__":
    empty = score_report([], [], False)
    assert empty["score"] == 100, empty
    bad = score_report(
        [{"kind": "heuristic", "id": "call_to_cancel", "senior_harm": "trapped_cancel"}],
        [{"impact": "critical", "senior_harm": "hard_to_read"}],
        True,
    )
    assert bad["score"] < empty["score"], bad
    print("ok", empty["score"], bad["score"], bad["band"])
