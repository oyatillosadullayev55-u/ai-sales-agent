from __future__ import annotations

from tests.conftest import KB_TEXT, register_org, upload_txt


async def test_upload_query_and_delete(client):
    session = await register_org(client, "knowledge")

    document = await upload_txt(client, session, KB_TEXT, filename="malumotlar.txt")
    assert document["status"] == "ready"
    assert document["chunk_count"] >= 3
    assert document["error"] is None

    listed = await client.get("/api/v1/knowledge", headers=session["headers"])
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document["id"]]

    answer = await client.post(
        "/api/v1/knowledge/query",
        headers=session["headers"],
        json={"question": "Kafolat bormi?"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert "12 oy" in payload["answer"]
    assert payload["sources"]
    assert payload["sources"][0]["document_name"] == "malumotlar.txt"
    assert payload["latency_ms"] >= 0

    delivery = await client.post(
        "/api/v1/knowledge/query",
        headers=session["headers"],
        json={"question": "Yetkazib berish qancha vaqt oladi?"},
    )
    assert "24 soat" in delivery.json()["answer"]

    missing = await client.post(
        "/api/v1/knowledge/query",
        headers=session["headers"],
        json={"question": "Marsda atmosfera bosimi qanday?"},
    )
    assert missing.json()["sources"] == []
    assert "topa olmadim" in missing.json()["answer"]

    deleted = await client.delete(
        f"/api/v1/knowledge/{document['id']}", headers=session["headers"]
    )
    assert deleted.status_code == 204

    assert (await client.get("/api/v1/knowledge", headers=session["headers"])).json() == []


async def test_reindex_and_validation(client):
    session = await register_org(client, "reindex")
    document = await upload_txt(client, session, KB_TEXT)

    reindexed = await client.post(
        f"/api/v1/knowledge/{document['id']}/reindex", headers=session["headers"]
    )
    assert reindexed.status_code == 200
    assert reindexed.json()["status"] == "ready"
    assert reindexed.json()["chunk_count"] == document["chunk_count"]

    unsupported = await client.post(
        "/api/v1/knowledge/upload",
        headers=session["headers"],
        files={"file": ("image.png", b"\x89PNG", "image/png")},
    )
    assert unsupported.status_code == 415


async def test_operator_cannot_manage_knowledge(client):
    session = await register_org(client, "kbops")
    invite = await client.post(
        "/api/v1/orgs/members",
        headers=session["headers"],
        json={
            "email": f"kbop-{session['org']['id']}@example.com",
            "full_name": "KB Operator",
            "role": "operator",
            "password": "OperatorPass123",
        },
    )
    assert invite.status_code == 201, invite.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": invite.json()["email"], "password": "OperatorPass123"},
    )
    operator_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Org-Id": session["org"]["id"],
    }

    upload = await client.post(
        "/api/v1/knowledge/upload",
        headers=operator_headers,
        files={"file": ("kb.txt", KB_TEXT.encode(), "text/plain")},
    )
    assert upload.status_code == 403
