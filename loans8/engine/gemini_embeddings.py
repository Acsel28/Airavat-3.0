"""Shared Gemini embedding utilities with batching + in-process caching."""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types

from loans8.engine.rate_limit import RequestRateLimiter

MODEL_NAME = "gemini-embedding-001"
OUTPUT_DIMENSIONALITY = 384
BATCH_SIZE = 8

_CLIENT: genai.Client | None = None
_EMBED_CACHE: dict[tuple[str, str], list[float]] = {}
_EMBED_RATE_LIMITER: RequestRateLimiter | None = None


def _get_client() -> genai.Client:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY", "").strip().strip('"')
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing. Set it in .env before running.")

    _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def _get_embed_rate_limiter() -> RequestRateLimiter:
    global _EMBED_RATE_LIMITER
    if _EMBED_RATE_LIMITER is not None:
        return _EMBED_RATE_LIMITER

    # Defaults to a conservative cap unless overridden in environment.
    max_per_min = int(os.getenv("EMBEDDING_API_MAX_REQUESTS_PER_MIN", "20"))
    _EMBED_RATE_LIMITER = RequestRateLimiter(max_requests=max_per_min, window_seconds=60)
    return _EMBED_RATE_LIMITER


def _task_type(kind: Literal["document", "query"]) -> str:
    return "RETRIEVAL_DOCUMENT" if kind == "document" else "RETRIEVAL_QUERY"


def embed_texts(texts: list[str], kind: Literal["document", "query"]) -> list[list[float]]:
    """Embed texts using Gemini API with dedupe, batching, and in-process cache."""
    if not texts:
        return []

    results: list[list[float] | None] = [None] * len(texts)
    missing_indices: list[int] = []
    missing_texts: list[str] = []

    for i, text in enumerate(texts):
        key = (kind, text)
        cached = _EMBED_CACHE.get(key)
        if cached is not None:
            results[i] = cached
            continue
        missing_indices.append(i)
        missing_texts.append(text)

    if missing_texts:
        client = _get_client()
        config = types.EmbedContentConfig(
            task_type=_task_type(kind),
            output_dimensionality=OUTPUT_DIMENSIONALITY,
        )

        # Deduplicate to reduce API calls when repeated content appears.
        uniq_order: list[str] = []
        seen: set[str] = set()
        for text in missing_texts:
            if text not in seen:
                seen.add(text)
                uniq_order.append(text)

        embedded_by_text: dict[str, list[float]] = {}
        for start in range(0, len(uniq_order), BATCH_SIZE):
            chunk = uniq_order[start : start + BATCH_SIZE]
            _get_embed_rate_limiter().acquire()
            response = client.models.embed_content(
                model=MODEL_NAME,
                contents=chunk,
                config=config,
            )
            for item_text, embedding in zip(chunk, response.embeddings):
                vector = list(embedding.values)
                embedded_by_text[item_text] = vector
                _EMBED_CACHE[(kind, item_text)] = vector

        for i, text in zip(missing_indices, missing_texts):
            results[i] = embedded_by_text[text]

    if any(vector is None for vector in results):
        raise RuntimeError("Failed to compute one or more embeddings.")
    return [list(vector) for vector in results if vector is not None]
