"""Read a subscription screenshot using the configured OpenAI-compatible vision API."""

from __future__ import annotations

import base64
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
    OPENAI_MODEL,
)
from nav.recipe_player import lookup_recipe

PROMPT = """Read the visible text in this subscription screenshot and return ONLY a compact JSON object.
Required keys exactly: {"name": "", "url": "", "cost": "", "renews": ""}
Rules:
- Use exact values visible in the image.
- url must be a real http(s) link shown in the image; leave blank if none are visible.
- Never invent a URL.
- cost = price as shown, such as "$29.99" or "29.99 USD".
- renews = the billing cycle or renewal date as shown.
- Do not add extra keys, markdown, commentary, or code fences.
- If a value is not visible, use an empty string.
"""


def _parse_json(text: str) -> dict[str, str]:
    blob = (text or "").strip()
    cleaned = blob.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        candidate = match.group(0)
        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            raw = {}
            for key, value in re.findall(r'"?([A-Za-z_]+)"?\s*:\s*(?:"([^"]*)"|\'([^\']*)\'|([^,}\n]+))', candidate):
                val = (value or "").strip() or ("" if not value else value)
                raw[key] = val
    else:
        raw = {}
        for key, value in re.findall(r'"?([A-Za-z_]+)"?\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|([^,\n]+))', cleaned, re.S):
            val = value or ""
            raw[key] = val.strip()

    raw = raw if isinstance(raw, dict) else {}
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
    if not ANTHROPIC_API_KEY.strip():
        raise RuntimeError("Anthropic key not configured")
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


def _via_openai(data: str, mime: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("No OpenAI key in OPENAI_API_KEY")
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
    model = OPENAI_MODEL or "gpt-4o-mini"
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

    if OPENAI_API_KEY.strip():
        try:
            text = _via_openai(data, mime)
            used = "openai"
        except Exception as exc:
            errors.append(f"OpenAI: {exc}")

    if not text and ANTHROPIC_API_KEY.strip():
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
            msg = "No vision key. Add OPENAI_API_KEY for the direct OpenAI path."
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
