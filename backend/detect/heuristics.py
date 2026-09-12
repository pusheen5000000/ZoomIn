"""Senior-weighted DOM + text heuristics (no LLM)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from detect.senior_copy import heuristic_flag

_COUNTDOWN = re.compile(
    r"\b(hurry|limited time|expires?|act now|only \d+ left|ends? (in|tonight)|last chance)\b",
    re.I,
)
_CALL_CANCEL = re.compile(
    r"\b(call (us )?(to|for) cancel|must call|phone (us )?to cancel|chat (with us )?to cancel)\b",
    re.I,
)
_SHAME = re.compile(
    r"\bno,?\s+i (don'?t want|hate|prefer to pay|want to miss)\b|"
    r"\b(i'?ll pass on saving|no thanks,? i like wasting)\b",
    re.I,
)
_DOUBLE_NEG = re.compile(
    r"\b(uncheck|do not (check|tick)|if you do not want|unless you don'?t)\b",
    re.I,
)


def _font_px(style: str | None) -> float | None:
    if not style:
        return None
    match = re.search(r"font-size:\s*([\d.]+)\s*px", style, re.I)
    return float(match.group(1)) if match else None


def scan_dom_and_text(html: str, text: str) -> list[dict[str, Any]]:
    blob = f"{text or ''}\n{html or ''}"
    soup = BeautifulSoup(html or "", "html.parser") if html else None
    flags: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(flag_id: str, evidence: str) -> None:
        if flag_id in seen:
            return
        seen.add(flag_id)
        flags.append(heuristic_flag(flag_id, evidence[:240]))

    if _COUNTDOWN.search(blob):
        add("fake_urgency", _COUNTDOWN.search(blob).group(0))
    if _CALL_CANCEL.search(blob):
        add("call_to_cancel", _CALL_CANCEL.search(blob).group(0))
    if _SHAME.search(blob):
        add("confirmshaming", _SHAME.search(blob).group(0))
    if _DOUBLE_NEG.search(blob):
        add("double_negative", _DOUBLE_NEG.search(blob).group(0))

    if soup:
        for box in soup.find_all("input", {"type": "checkbox"}):
            if box.has_attr("checked"):
                label = " ".join(box.parent.get_text(" ", strip=True).split())[:200]
                add("prechecked_consent", label or "A checkbox is already ticked.")
        for el in soup.find_all(style=True):
            size = _font_px(el.get("style"))
            if size is not None and size <= 10:
                snippet = el.get_text(" ", strip=True)[:120]
                if snippet:
                    add("tiny_text", f"{size}px: {snippet}")
        for el in soup.find_all(href=True):
            href = (el.get("href") or "").lower()
            style = (el.get("style") or "").lower()
            if "cancel" in href or "cancel" in (el.get_text() or "").lower():
                if any(tok in style for tok in ("display:none", "font-size:0", "opacity:0", "left:-")):
                    add("hidden_cancel", el.get("href", "")[:160])

    return flags
