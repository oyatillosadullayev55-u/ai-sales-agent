from __future__ import annotations

import hashlib
import logging
import math
import re

import httpx
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

DIM = 384
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


def _hash_index(token: str) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    index = value % DIM
    sign = 1.0 if (value >> 17) & 1 else -1.0
    return index, sign


def local_embed(text: str) -> list[float]:
    """Deterministic hashing embedding (word + char trigram). Works offline, any language."""
    vector = np.zeros(DIM, dtype=np.float32)
    words = _WORD_RE.findall(text.lower())
    counts: dict[str, float] = {}
    for word in words:
        counts[word] = counts.get(word, 0.0) + 1.0
        if len(word) >= 5:
            for i in range(len(word) - 2):
                gram = f"#{word[i:i + 3]}"
                counts[gram] = counts.get(gram, 0.0) + 0.35

    for token, count in counts.items():
        index, sign = _hash_index(token)
        vector[index] += sign * (1.0 + math.log(count))

    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= norm
    return [round(float(v), 6) for v in vector]


async def openai_embed(texts: list[str]) -> list[list[float]]:
    payload = {"model": settings.embedding_model, "input": texts}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    url = settings.llm_base_url.rstrip("/") + "/embeddings"
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [item["embedding"] for item in data["data"]]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embeddings_enabled:
        try:
            return await openai_embed(texts)
        except Exception as exc:  # network/API issues must not break ingestion
            logger.warning("OpenAI embeddings failed, using local fallback: %s", exc)
    return [local_embed(text) for text in texts]


def cosine_matrix(query: list[float], vectors: list[list[float]]) -> np.ndarray:
    if not vectors:
        return np.array([])
    matrix = np.array(vectors, dtype=np.float32)
    q = np.array(query, dtype=np.float32)
    if matrix.shape[1] != q.shape[0]:
        return np.zeros(len(vectors), dtype=np.float32)
    denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(q)
    denom[denom == 0] = 1.0
    return (matrix @ q) / denom
