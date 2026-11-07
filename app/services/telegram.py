from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    pass


async def api_call(
    token: str, method: str, payload: dict | None = None, timeout: float = 20
) -> dict | list:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload or {})
    except httpx.HTTPError as exc:
        raise TelegramError(f"Telegram bilan aloqa xatosi: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise TelegramError("Telegram javobi noto'g'ri") from exc
    if not data.get("ok"):
        raise TelegramError(str(data.get("description") or "Telegram API xatosi"))
    return data.get("result", {})


async def get_me(token: str) -> dict:
    return await api_call(token, "getMe")


async def send_message(token: str, chat_id: str | int, text: str) -> dict:
    return await api_call(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text[:4096],
            "disable_web_page_preview": True,
        },
    )


async def set_webhook(token: str, url: str, secret: str) -> dict:
    return await api_call(
        token,
        "setWebhook",
        {
            "url": f"{url}",
            "secret_token": secret[:64],
            "allowed_updates": ["message"],
            "drop_pending_updates": True,
        },
    )


async def delete_webhook(token: str) -> dict:
    return await api_call(token, "deleteWebhook", {"drop_pending_updates": True})


async def get_updates(
    token: str, offset: int | None = None, timeout: int = 25
) -> list[dict]:
    payload: dict = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        payload["offset"] = offset
    result = await api_call(token, "getUpdates", payload, timeout=timeout + 10)
    return result if isinstance(result, list) else []


def webhook_url(secret: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/v1/telegram/webhook/{secret}"
