"""Map classifier categories onto Cialdini principles + plain-English copy."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

MAPPING_PATH = Path(__file__).resolve().parent / "mapping.json"


@lru_cache(maxsize=1)
def load_mapping() -> dict[str, dict[str, str]]:
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def enrich(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = load_mapping()
    enriched: list[dict[str, Any]] = []
    skip = {"not dark pattern", "not_dark_pattern", "none"}
    for row in predictions:
        category = row.get("category")
        if str(category).strip().lower() in skip:
            continue
        info = mapping.get(str(category), {})
        enriched.append(
            {
                **row,
                "cialdini_principle": info.get("cialdini_principle") or "Unknown",
                "explanation": info.get("explanation")
                or "This pattern nudges a decision you would not make with full, calm information.",
            }
        )
    return enriched


if __name__ == "__main__":
    demo = enrich(
        [{"category": "Urgency", "confidence": 0.91}, {"category": "Obstruction", "confidence": 0.7}]
    )
    print(json.dumps(demo, indent=2))
