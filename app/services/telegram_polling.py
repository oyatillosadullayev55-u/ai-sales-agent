from __future__ import annotations

import asyncio
import hashlib
import logging

from sqlalchemy import select

from app.crypto import decrypt_secret
from app.database import SessionLocal
from app.models import TelegramIntegration
from app.services import telegram, telegram_bot

logger = logging.getLogger(__name__)

SYNC_INTERVAL = 15
RETRY_DELAY = 5


def _fingerprint(integration: TelegramIntegration) -> str:
    return hashlib.sha256(
        f"{integration.token_encrypted}|{integration.active}".encode()
    ).hexdigest()


async def poll_bot_once(
    integration_id: str, token: str, offset: int | None, timeout: int = 25
) -> int | None:
    updates = await telegram.get_updates(token, offset, timeout=timeout)
    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            offset = max(offset or 0, update_id) + 1
        try:
            async with SessionLocal() as db:
                integration = await db.get(TelegramIntegration, integration_id)
                if integration is None or not integration.active:
                    return offset
                if decrypt_secret(integration.token_encrypted) != token:
                    return offset
                await telegram_bot.process_update(db, integration, update)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram update %s could not be processed", update_id)
    return offset


async def _poll_bot(integration_id: str, token: str) -> None:
    try:
        await telegram.delete_webhook(token)
    except telegram.TelegramError as exc:
        logger.warning("Telegram deleteWebhook failed: %s", exc)
    logger.info("Telegram polling started for integration %s", integration_id)
    offset: int | None = None
    while True:
        try:
            offset = await poll_bot_once(integration_id, token, offset)
        except telegram.TelegramError as exc:
            logger.warning("Telegram getUpdates failed: %s", exc)
            await asyncio.sleep(RETRY_DELAY)


class TelegramPoller:
    def __init__(self, sync_interval: float = SYNC_INTERVAL) -> None:
        self.sync_interval = sync_interval
        self._bots: dict[str, tuple[str, asyncio.Task]] = {}
        self._runner: asyncio.Task | None = None

    async def start(self) -> None:
        if self._runner is not None:
            return
        await self.sync()
        self._runner = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._runner is not None:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
            self._runner = None
        tasks = [task for _, task in self._bots.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._bots.clear()

    async def _run(self) -> None:
        while True:
            try:
                await self.sync()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram polling sync failed")
            await asyncio.sleep(self.sync_interval)

    async def sync(self) -> None:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(TelegramIntegration).where(TelegramIntegration.active.is_(True))
                )
            ).scalars().all()
            current = {row.id: row for row in rows}

        for integration_id, row in current.items():
            fingerprint = _fingerprint(row)
            existing = self._bots.get(integration_id)
            if existing and existing[0] == fingerprint:
                continue
            if existing:
                existing[1].cancel()
                await asyncio.gather(existing[1], return_exceptions=True)
            token = decrypt_secret(row.token_encrypted)
            task = asyncio.create_task(_poll_bot(integration_id, token))
            self._bots[integration_id] = (fingerprint, task)

        for integration_id in list(self._bots):
            if integration_id not in current:
                _, task = self._bots.pop(integration_id)
                task.cancel()
