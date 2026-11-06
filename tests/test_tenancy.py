from __future__ import annotations

from tests.conftest import (
    KB_TEXT,
    create_product,
    register_org,
    upload_txt,
    widget_key,
)


async def test_products_are_isolated_between_orgs(client):
    org_a = await register_org(client, "tenanta")
    org_b = await register_org(client, "tenantb")

    product = await create_product(
        client, org_a, name="Lenovo IdeaPad", price=8_490_000, category="laptop"
    )

    listed_b = await client.get("/api/v1/products", headers=org_b["headers"])
    assert listed_b.status_code == 200
    assert listed_b.json() == []

    patch_b = await client.patch(
        f"/api/v1/products/{product['id']}",
        headers=org_b["headers"],
        json={"price": 1},
    )
    assert patch_b.status_code == 404

    delete_b = await client.delete(f"/api/v1/products/{product['id']}", headers=org_b["headers"])
    assert delete_b.status_code == 404

    listed_a = await client.get("/api/v1/products", headers=org_a["headers"])
    assert len(listed_a.json()) == 1

    impersonate = await client.get(
        "/api/v1/products",
        headers={
            "Authorization": f"Bearer {org_b['access_token']}",
            "X-Org-Id": org_a["org"]["id"],
        },
    )
    assert impersonate.status_code == 403


async def test_documents_and_conversations_are_isolated(client):
    org_a = await register_org(client, "docsa")
    org_b = await register_org(client, "docsb")

    document = await upload_txt(client, org_a, KB_TEXT)

    delete_b = await client.delete(
        f"/api/v1/knowledge/{document['id']}", headers=org_b["headers"]
    )
    assert delete_b.status_code == 404

    query_b = await client.post(
        "/api/v1/knowledge/query",
        headers=org_b["headers"],
        json={"question": "Kafolat bormi?"},
    )
    assert query_b.status_code == 200
    assert query_b.json()["sources"] == []

    key_a = await widget_key(client, org_a)
    chat = await client.post(
        f"/api/v1/public/widget/{key_a}/messages",
        json={"visitor_id": "visitor-a1", "text": "Salom"},
    )
    assert chat.status_code == 200
    conversation_id = chat.json()["conversation_id"]

    foreign = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=org_b["headers"]
    )
    assert foreign.status_code == 404

    owner = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=org_a["headers"]
    )
    assert owner.status_code == 200
