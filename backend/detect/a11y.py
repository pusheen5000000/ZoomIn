"""Run axe-core inside a live Steel + Playwright page. Map hits to senior language."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nav.steel_playwright import open_steel_page, session_info

VENDOR = Path(__file__).resolve().parent / "vendor"
AXE_JS = VENDOR / "axe.min.js"

# Keep WCAG ids out of the UI; judges can still see rule_id in evidence if needed.
SENIOR_RULES: dict[str, dict[str, str]] = {
    "color-contrast": {
        "senior_harm": "hard_to_read",
        "plain_language": "Some text is too faint against the background to read comfortably.",
    },
    "image-alt": {
        "senior_harm": "missing_description",
        "plain_language": "A picture has no text description, so it is unclear what it shows.",
    },
    "label": {
        "senior_harm": "unclear_control",
        "plain_language": "A box or field does not clearly say what to type.",
    },
    "button-name": {
        "senior_harm": "unclear_control",
        "plain_language": "A button does not say what it does.",
    },
    "link-name": {
        "senior_harm": "unclear_control",
        "plain_language": "A link does not say where it goes.",
    },
    "document-title": {
        "senior_harm": "confusing_page",
        "plain_language": "The browser tab has no clear page title.",
    },
    "html-has-lang": {
        "senior_harm": "confusing_page",
        "plain_language": "The page does not say what language it is in (harder for helpers and readers).",
    },
    "target-size": {
        "senior_harm": "easy_to_misclick",
        "plain_language": "A tap target is very small — easy to miss and hit the wrong thing.",
    },
}

IMPACT_RANK = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}


def map_violations(raw: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    violations = list(raw.get("violations") or [])
    violations.sort(key=lambda v: IMPACT_RANK.get((v.get("impact") or "minor"), 9))
    for item in violations:
        rule_id = str(item.get("id") or "unknown")
        impact = str(item.get("impact") or "moderate")
        nodes = item.get("nodes") or []
        evidence = ""
        if nodes:
            evidence = (nodes[0].get("failureSummary") or nodes[0].get("html") or "")[:240]
        meta = SENIOR_RULES.get(
            rule_id,
            {
                "senior_harm": "page_barrier",
                "plain_language": "This page has a barrier that can make it harder to use if you have low vision or use a keyboard.",
            },
        )
        flags.append(
            {
                "id": f"axe_{rule_id}",
                "kind": "a11y",
                "rule_id": rule_id,
                "impact": impact,
                "senior_harm": meta["senior_harm"],
                "plain_language": meta["plain_language"],
                "evidence": evidence or rule_id,
                "confidence": 1.0,
            }
        )
        if len(flags) >= limit:
            break
    return flags


async def scan_page_a11y(url: str) -> dict[str, Any]:
    if not AXE_JS.exists():
        return {
            "ok": False,
            "error": f"Missing vendored axe at {AXE_JS}",
            "flags": [],
            "html": "",
            "text": "",
            "title": None,
        }

    async with open_steel_page() as (session, page):
        info = session_info(session)
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        html = await page.content()
        text = await page.inner_text("body")
        title = await page.title()
        await page.add_script_tag(path=str(AXE_JS))
        raw = await page.evaluate("async () => await axe.run()")
        flags = map_violations(raw if isinstance(raw, dict) else {})
        return {
            "ok": True,
            "error": None,
            "flags": flags,
            "html": html,
            "text": text,
            "title": title,
            "raw_violation_count": len((raw or {}).get("violations") or []) if isinstance(raw, dict) else 0,
            **info,
        }
