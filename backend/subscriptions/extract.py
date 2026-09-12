"""Read a subscription screenshot. Groq vision by default; Anthropic if that key is set."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GROQ_VISION_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)
from nav.recipe_player import lookup_recipe

PROMPT = """This is a screenshot of a subscription email, billing page, or app-store list.
Extract JSON only, no markdown:
{"name": "", "url": "", "cost": "", "renews": ""}
url = a visible http(s) manage/cancel/account link in the image. Empty string if none.
Do not invent a URL that is not clearly in the image (no guessing Netflix/Spotify links).
cost = price as shown. renews = date or billing cycle as shown."""


def _parse_json(text: str) -> dict[str, str]:
    blob = (text or "").strip()
    match = re.search(r"\{.*\}", blob, re.S)
    if not match:
        return {"name": "", "url": "", "cost": "", "renews": ""}
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"name": "", "url": "", "cost": "", "renews": ""}
    url = str(raw.get("url") or "").strip()
    if url and not url.lower().startswith("http"):
        url = ""
    return {
        "name": str(raw.get("name") or "").strip(),
        "url": url,
        "cost": str(raw.get("cost") or "").strip(),
        "renews": str(raw.get("renews") or "").strip(),
    }


def _strip_b64(image_b64: str) -> str:
    return re.sub(r"^data:[^;]+;base64,", "", image_b64 or "").strip()


def _via_anthropic(data: str, mime: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": data},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )
    text = ""
    for block in message.content:
        if getattr(block, "type", None) == "text":
            text += block.text or ""
    return text


def _via_groq(data: str, mime: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("No Groq/OpenAI key in OPENAI_API_KEY")
    base = OPENAI_BASE_URL or "https://api.groq.com/openai/v1"
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=base)
    models = [GROQ_VISION_MODEL, "qwen/qwen3.6-27b", "qwen/qwen3.8-27b"]
    last_err: Exception | None = None
    seen: set[str] = set()
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{data}"},
                            },
                        ],
                    }
                ],
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            last_err = exc
            continue
    raise RuntimeError(str(last_err) if last_err else "Groq vision failed")


def extract_subscription_image(image_b64: str, media_type: str) -> dict[str, Any]:
    empty = {"name": "", "url": "", "cost": "", "renews": ""}
    mime = media_type if media_type in {"image/png", "image/jpeg", "image/gif", "image/webp"} else "image/png"
    data = _strip_b64(image_b64)
    if not data:
        return {
            "ok": False,
            "error": "No image data.",
            "fields": empty,
            "recipe_id": None,
            "url_from_recipe": False,
            "provider": None,
        }

    used = None
    text = ""
    errors: list[str] = []
    # Claude if they pasted ANTHROPIC_API_KEY; otherwise the Groq key already in .env.
    if ANTHROPIC_API_KEY.strip():
        try:
            text = _via_anthropic(data, mime)
            used = "anthropic"
        except Exception as exc:
            errors.append(f"Anthropic: {exc}")
    if not text and OPENAI_API_KEY.strip():
        try:
            text = _via_groq(data, mime)
            used = "groq"
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    if not text:
        if not ANTHROPIC_API_KEY.strip() and not OPENAI_API_KEY.strip():
            msg = "No vision key. Groq uses OPENAI_API_KEY (gsk_…). Claude uses ANTHROPIC_API_KEY when you have one."
        else:
            msg = "Could not read the screenshot. " + " ".join(errors)[:400]
        return {
            "ok": False,
            "error": msg + " You can still type the fields by hand.",
            "fields": empty,
            "recipe_id": None,
            "url_from_recipe": False,
            "provider": None,
        }

    fields = _parse_json(text)
    recipe = lookup_recipe(fields.get("name") or "", fields.get("url") or "")
    url_from_recipe = False
    if recipe and not (fields.get("url") or "").startswith("http"):
        fields["url"] = recipe["url"]
        url_from_recipe = True
    return {
        "ok": True,
        "error": None,
        "fields": fields,
        "recipe_id": recipe["id"] if recipe else None,
        "url_from_recipe": url_from_recipe,
        "provider": used,
        "note": "Review these fields. Nothing is saved until you click Add subscription.",
    }
