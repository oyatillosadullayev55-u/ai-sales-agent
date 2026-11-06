from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    pass


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.4,
    model: str | None = None,
) -> dict[str, Any]:
    if not settings.llm_enabled:
        raise LLMUnavailable("LLM_API_KEY sozlanmagan")

    payload: dict[str, Any] = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            logger.error("LLM error %s: %s", response.status_code, response.text[:500])
            raise LLMUnavailable(f"LLM xatosi: {response.status_code}")
        data = response.json()

    try:
        return data["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise LLMUnavailable("LLM javobi noto'g'ri formatda") from exc
