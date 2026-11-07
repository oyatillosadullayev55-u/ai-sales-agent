from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt_secret
from app.models import Message, Organization, TelegramIntegration, utcnow
from app.services import telegram
from app.services.agent import get_agent_settings, greeting_text
from app.services.chat import find_conversation, get_or_create_conversation, handle_message
from app.services.limits import ensure_conversation_limit

logger = logging.getLogger(__name__)

OPERATOR_TEXT = {
    "uz": "Operatorimiz tez orada javob beradi. Iltimos, biroz kuting.",
    "ru": "Наш оператор скоро ответит. Пожалуйста, подождите немного.",
    "en": "Our operator will reply shortly. Please wait a moment.",
}

_seen_updates: dict[int, bool] = {}


def _already_seen(update_id: int | None) -> bool:
    if update_id is None:
        return False
    if update_id in _seen_updates:
        return True
    _seen_updates[update_id] = True
    if len(_seen_updates) > 5000:
        _seen_updates.clear()
    return False


def _normalize_command(text: str) -> str:
    if not text.startswith("/"):
        return text
    head, _, rest = text.partition(" ")
    command = head.split("@", 1)[0].lower()
    return f"{command} {rest}".strip() if rest else command


async def process_update(
    db: AsyncSession, integration: TelegramIntegration, update: dict
) -> None:
    if _already_seen(update.get("update_id")):
        return

    message = update.get("message") or update.get("edited_message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not text or chat_id is None:
        return

    org = await db.get(Organization, integration.org_id)
    if org is None:
        return
    token = decrypt_secret(integration.token_encrypted)

    sender = message.get("from") or {}
    name = " ".join(
        part for part in [sender.get("first_name"), sender.get("last_name")] if part
    ).strip() or sender.get("username", "")

    conversation = await find_conversation(db, org.id, "telegram", str(chat_id))
    if conversation is None:
        try:
            await ensure_conversation_limit(db, org)
        except HTTPException:
            await _safe_send(token, chat_id, "Tarif limiti tugagan. Administratorga murojaat qiling.")
            return
        conversation = await get_or_create_conversation(db, org, "telegram", str(chat_id), name)

    lang = (conversation.state or {}).get("lang") or "uz"
    if not conversation.ai_enabled:
        db.add(
            Message(
                org_id=org.id,
                conversation_id=conversation.id,
                role="user",
                content=text,
                meta={"channel": "telegram", "chat_id": chat_id},
            )
        )
        conversation.last_message_at = utcnow()
        await db.commit()
        await _safe_send(token, chat_id, OPERATOR_TEXT.get(lang, OPERATOR_TEXT["uz"]))
        return

    command = _normalize_command(text)
    if command in {"/start", "/help"}:
        agent_settings = await get_agent_settings(db, org)
        reply = greeting_text(org, agent_settings, lang)
        db.add(
            Message(
                org_id=org.id,
                conversation_id=conversation.id,
                role="user",
                content=text,
                meta={"channel": "telegram", "chat_id": chat_id},
            )
        )
        db.add(
            Message(
                org_id=org.id,
                conversation_id=conversation.id,
                role="assistant",
                content=reply,
                meta={"channel": "telegram"},
            )
        )
        conversation.last_message_at = utcnow()
        await db.commit()
        await _safe_send(token, chat_id, reply)
        return

    result = await handle_message(db, org, conversation, text, source="telegram")
    await db.commit()

    reply = result.text
    if result.products and "—" not in reply:
        lines = "\n".join(
            f"• {p['name']} — {int(p['price']):,}".replace(",", " ") + " so'm"
            for p in result.products[:3]
        )
        reply = f"{reply}\n\n{lines}"
    await _safe_send(token, chat_id, reply)


async def _safe_send(token: str, chat_id: int | str, text: str) -> None:
    try:
        await telegram.send_message(token, chat_id, text)
    except telegram.TelegramError as exc:
        logger.warning("Telegram send failed: %s", exc)
