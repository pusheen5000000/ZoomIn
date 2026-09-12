"""predict(text) -> list of {category, confidence} above threshold."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

MODEL_PATH = Path(__file__).resolve().parent / "models" / "dark_patterns.joblib"

_CHUNK = re.compile(r"(?<=[.!?])\s+|\n+")


@lru_cache(maxsize=1)
def _load_model() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No classifier at {MODEL_PATH}. Run: python -m classifier.train"
        )
    return joblib.load(MODEL_PATH)


def _chunks(text: str, max_chunks: int = 40) -> list[str]:
    parts = [p.strip() for p in _CHUNK.split(text or "") if p and p.strip()]
    if not parts:
        return []
    # Keep medium-length UI copy; skip huge HTML dumps as single blob later.
    useful = [p for p in parts if 8 <= len(p) <= 500]
    if not useful:
        useful = parts[:max_chunks]
    return useful[:max_chunks]


def predict(text: str, threshold: float = 0.28, top_k: int = 5) -> list[dict[str, Any]]:
    """Return dark-pattern categories with confidence in [0, 1], highest first."""
    if not (text or "").strip():
        return []

    bundle = _load_model()
    pipeline = bundle["pipeline"]
    labels: list[str] = list(pipeline.classes_)

    snippets = _chunks(text)
    snippets = [text[:2000], *snippets]
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for snippet in snippets:
        if snippet not in seen:
            seen.add(snippet)
            unique.append(snippet)
    snippets = unique or [text[:2000]]

    proba = pipeline.predict_proba(snippets)
    # Max confidence per class across snippets (a page often mixes patterns).
    max_scores = proba.max(axis=0)

    scored = [
        {"category": str(label), "confidence": float(score)}
        for label, score in zip(labels, max_scores)
        if float(score) >= threshold
    ]
    scored.sort(key=lambda row: row["confidence"], reverse=True)
    return scored[:top_k]


def predict_window(text: str) -> dict[str, Any]:
    """Also classify the full concatenated window (useful for short scrapes)."""
    if not (text or "").strip():
        return {"predictions": [], "top_label": None}
    bundle = _load_model()
    pipeline = bundle["pipeline"]
    snippet = text[:8000]
    proba = pipeline.predict_proba([snippet])[0]
    labels = list(pipeline.classes_)
    ranked = sorted(
        (
            {"category": str(label), "confidence": float(score)}
            for label, score in zip(labels, proba)
        ),
        key=lambda row: row["confidence"],
        reverse=True,
    )
    by_chunk = predict(text)
    # Merge: take the max of whole-doc vs chunked scores.
    merged: dict[str, float] = {}
    for row in ranked + by_chunk:
        merged[row["category"]] = max(merged.get(row["category"], 0.0), row["confidence"])
    predictions = [
        {"category": cat, "confidence": conf}
        for cat, conf in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        if conf >= 0.28
    ][:6]
    return {
        "predictions": predictions,
        "top_label": predictions[0]["category"] if predictions else None,
        "model_labels": labels,
        "n_snippets": len(_chunks(text)),
    }
