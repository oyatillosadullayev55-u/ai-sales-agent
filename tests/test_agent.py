from __future__ import annotations

from tests.conftest import (
    KB_TEXT,
    create_product,
    register_org,
    upload_txt,
    widget_key,
)


async def _widget(client, key: str, visitor: str, text: str):
    response = await client.post(
        f"/api/v1/public/widget/{key}/messages",
        json={"visitor_id": visitor, "text": text},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_product_search_budget_and_price(client):
    session = await register_org(client, "shop")
    await create_product(
        client, session, name="Lenovo IdeaPad Slim 5", price=8_490_000, category="laptop"
    )
    await create_product(
        client, session, name="Acer Aspire 5", price=6_500_000, category="laptop"
    )
    await create_product(
        client, session, name="iPhone 15", price=12_000_000, category="phone"
    )
    key = await widget_key(client, session)

    budget = await _widget(client, key, "budget-1", "8 mln gacha noutbuk kerak")
    names = [item["name"] for item in budget["products"]]
    assert names == ["Acer Aspire 5"]
    assert all(item["price"] <= 8_000_000 for item in budget["products"])

    tight = await _widget(client, key, "budget-2", "3 mln gacha noutbuk kerak")
    assert "Acer Aspire 5" in tight["text"]
    assert [item["name"] for item in tight["products"]] == ["Acer Aspire 5", "Lenovo IdeaPad Slim 5"]

    price = await _widget(client, key, "price-1", "Lenovo IdeaPad narxi qancha?")
    assert "8 490 000" in price["text"]
    assert price["products"][0]["name"] == "Lenovo IdeaPad Slim 5"

    russian = await _widget(client, key, "price-ru-1", "Сколько стоит Lenovo IdeaPad?")
    assert "8 490 000" in russian["text"]


async def test_ai_order_flow_updates_stock(client):
    session = await register_org(client, "orders")
    product = await create_product(
        client, session, name="Lenovo IdeaPad Slim 5", price=8_490_000, category="laptop", stock_qty=5
    )
    key = await widget_key(client, session)
    visitor = "order-visitor-1"

    first = await _widget(client, key, visitor, "Lenovo IdeaPad ni sotib olmoqchiman")
    assert "Ismingizni" in first["text"]

    second = await _widget(client, key, visitor, "Aziz")
    assert "Telefon" in second["text"]

    third = await _widget(client, key, visitor, "+998 90 123 45 67")
    assert "Tasdiqlaysizmi" in third["text"]

    fourth = await _widget(client, key, visitor, "Ha")
    order = fourth["order"]
    assert order is not None
    assert order["total"] == 8_490_000
    assert "Buyurtma qabul qilindi" in fourth["text"]

    orders = await client.get("/api/v1/orders", headers=session["headers"])
    assert orders.status_code == 200
    rows = orders.json()
    assert len(rows) == 1
    assert rows[0]["number"] == order["number"]
    assert rows[0]["customer_name"] == "Aziz"
    assert rows[0]["customer_phone"].endswith("45 67")
    assert rows[0]["source"] == "ai"

    products = await client.get("/api/v1/products", headers=session["headers"])
    stock = {row["id"]: row["stock_qty"] for row in products.json()}
    assert stock[product["id"]] == 4

    analytics = await client.get("/api/v1/analytics/overview", headers=session["headers"])
    assert analytics.status_code == 200
    assert analytics.json()["orders"] == 1
    assert analytics.json()["revenue"] == 8_490_000


async def test_manual_order_and_cancel_restores_stock(client):
    session = await register_org(client, "manual")
    product = await create_product(
        client, session, name="Acer Aspire 5", price=6_500_000, category="laptop", stock_qty=3
    )

    created = await client.post(
        "/api/v1/orders",
        headers=session["headers"],
        json={
            "customer_name": "Dilnoza",
            "customer_phone": "+998 91 555 44 33",
            "items": [{"product_id": product["id"], "qty": 2}],
            "note": "Kuryer bilan kelishildi",
        },
    )
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["total"] == 13_000_000
    assert order["source"] == "dashboard"
    assert order["status"] == "pending"

    after_create = await client.get("/api/v1/products", headers=session["headers"])
    assert {row["id"]: row["stock_qty"] for row in after_create.json()}[product["id"]] == 1

    cancelled = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=session["headers"],
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    after_cancel = await client.get("/api/v1/products", headers=session["headers"])
    assert {row["id"]: row["stock_qty"] for row in after_cancel.json()}[product["id"]] == 3


async def test_handoff_and_knowledge_answers(client):
    session = await register_org(client, "support")
    await create_product(client, session, name="Lenovo IdeaPad Slim 5", price=8_490_000, category="laptop")
    await upload_txt(client, session, KB_TEXT)
    key = await widget_key(client, session)

    handoff = await _widget(client, key, "handoff-1", "Operator bilan gaplashsam bo'ladimi?")
    assert handoff["handoff"] is True
    assert handoff["ai_enabled"] is False

    follow_up = await _widget(client, key, "handoff-1", "Salom")
    assert follow_up["ai_enabled"] is False
    assert follow_up["handoff"] is True
    assert "Operatorimiz" in follow_up["text"]

    knowledge = await _widget(client, key, "kb-1", "Kafolat bormi?")
    assert "12 oy" in knowledge["text"]
    assert knowledge["sources"]
    assert knowledge["sources"][0]["document_name"] == "kb.txt"

    delivery = await _widget(client, key, "kb-2", "Yetkazib berish qancha vaqt oladi?")
    assert "24 soat" in delivery["text"]

    conversation = await client.get(
        f"/api/v1/conversations?channel=widget",
        headers=session["headers"],
    )
    assert conversation.status_code == 200
    handoff_row = next(row for row in conversation.json() if row["external_id"] == "handoff-1")
    assert handoff_row["is_handoff"] is True
    assert handoff_row["ai_enabled"] is False
