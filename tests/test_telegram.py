from __future__ import annotations

import uuid

from tests.conftest import register_org

BOT_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"


async def test_telegram_connect_webhook_and_disconnect(client, monkeypatch):
    session = await register_org(client, "telegram")

    sent: list[tuple[object, str]] = []

    async def fake_get_me(token: str) -> dict:
        assert token == BOT_TOKEN
        return {"id": 1, "username": "test_sales_bot"}

    async def fake_send(token: str, chat_id, text: str) -> dict:
        sent.append((chat_id, text))
        return {"message_id": len(sent)}

    async def fake_delete(token: str) -> dict:
        return {"ok": True}

    monkeypatch.setattr("app.services.telegram.get_me", fake_get_me)
    monkeypatch.setattr("app.services.telegram.send_message", fake_send)
    monkeypatch.setattr("app.services.telegram.delete_webhook", fake_delete)

    connected = await client.post(
        "/api/v1/integrations/telegram",
        headers=session["headers"],
        json={"token": BOT_TOKEN},
    )
    assert connected.status_code == 200, connected.text
    data = connected.json()
    assert data["bot_username"] == "test_sales_bot"
    secret = data["webhook_url"].rsplit("/", 1)[-1]
    assert len(secret) > 10

    update_id = uuid.uuid4().int % 2_000_000_000
    start_update = {
        "update_id": update_id,
        "message": {
            "text": "/start",
            "chat": {"id": 777001},
            "from": {"first_name": "Aziz", "last_name": "Karimov"},
        },
    }
    first = await client.post(f"/api/v1/telegram/webhook/{secret}", json=start_update)
    assert first.status_code == 200
    assert first.json() == {"ok": True}
    assert sent and "Assalomu" in sent[-1][1]

    text_update = {
        "update_id": update_id + 1,
        "message": {"text": "Salom", "chat": {"id": 777001}, "from": {"first_name": "Aziz"}},
    }
    second = await client.post(f"/api/v1/telegram/webhook/{secret}", json=text_update)
    assert second.status_code == 200
    count_after_reply = len(sent)
    assert count_after_reply >= 2

    duplicate = await client.post(f"/api/v1/telegram/webhook/{secret}", json=text_update)
    assert duplicate.status_code == 200
    assert len(sent) == count_after_reply

    conversations = await client.get(
        "/api/v1/conversations?channel=telegram", headers=session["headers"]
    )
    assert conversations.status_code == 200
    rows = conversations.json()
    assert len(rows) == 1
    assert rows[0]["external_id"] == "777001"
    assert rows[0]["customer_name"] == "Aziz Karimov"

    forbidden = await client.post(
        f"/api/v1/telegram/webhook/{secret}",
        json={"update_id": update_id + 2, "message": {"text": "hi", "chat": {"id": 1}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert forbidden.status_code == 403

    unknown = await client.post(
        "/api/v1/telegram/webhook/not-a-real-secret",
        json={"update_id": update_id + 3, "message": {"text": "hi", "chat": {"id": 1}}},
    )
    assert unknown.status_code == 404

    no_https = await client.post(
        "/api/v1/integrations/telegram/set-webhook", headers=session["headers"]
    )
    assert no_https.status_code == 400

    removed = await client.delete("/api/v1/integrations/telegram", headers=session["headers"])
    assert removed.status_code == 204

    status = await client.get("/api/v1/integrations/telegram", headers=session["headers"])
    assert status.json()["connected"] is False


async def test_telegram_polling_processes_updates(client, monkeypatch):
    session = await register_org(client, "tg-poll")
    sent: list[tuple[object, str]] = []

    async def fake_get_me(token: str) -> dict:
        return {"id": 2, "username": "poll_sales_bot"}

    async def fake_send(token: str, chat_id, text: str) -> dict:
        sent.append((chat_id, text))
        return {"message_id": len(sent)}

    monkeypatch.setattr("app.services.telegram.get_me", fake_get_me)
    monkeypatch.setattr("app.services.telegram.send_message", fake_send)

    connected = await client.post(
        "/api/v1/integrations/telegram",
        headers=session["headers"],
        json={"token": BOT_TOKEN},
    )
    assert connected.status_code == 200, connected.text
    assert connected.json()["mode"] in {"polling", "webhook"}

    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import TelegramIntegration
    from app.services.telegram_polling import poll_bot_once

    async with SessionLocal() as db:
        integration = (
            await db.execute(
                select(TelegramIntegration).where(
                    TelegramIntegration.org_id == session["org"]["id"]
                )
            )
        ).scalar_one()
        integration_id = integration.id

    update_id = uuid.uuid4().int % 2_000_000_000

    async def fake_get_updates(token: str, offset=None, timeout: int = 25) -> list[dict]:
        assert token == BOT_TOKEN
        return [
            {
                "update_id": update_id,
                "message": {
                    "text": "/start@poll_sales_bot",
                    "chat": {"id": 888002},
                    "from": {"first_name": "Dilnoza"},
                },
            }
        ]

    monkeypatch.setattr("app.services.telegram.get_updates", fake_get_updates)

    offset = await poll_bot_once(integration_id, BOT_TOKEN, None, timeout=0)
    assert offset == update_id + 1
    assert sent and sent[-1][0] == 888002
    assert "Assalomu" in sent[-1][1]

    await poll_bot_once(integration_id, BOT_TOKEN, offset, timeout=0)
    assert len(sent) == 1
