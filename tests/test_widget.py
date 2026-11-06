from __future__ import annotations

from tests.conftest import register_org, widget_key


async def test_widget_config_embed_and_history(client):
    session = await register_org(client, "widget")
    key = await widget_key(client, session)

    config = await client.get(f"/api/v1/public/widget/{key}/config")
    assert config.status_code == 200
    body = config.json()
    assert body["org_name"].startswith("Widget")
    assert body["title"] == "AI yordamchi"

    unknown = await client.get("/api/v1/public/widget/missing-key/config")
    assert unknown.status_code == 404

    sent = await client.post(
        f"/api/v1/public/widget/{key}/messages",
        json={"visitor_id": "visitor-one", "text": "Salom", "name": "Aziz"},
    )
    assert sent.status_code == 200

    history = await client.get(
        f"/api/v1/public/widget/{key}/history", params={"visitor_id": "visitor-one"}
    )
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Salom"

    other = await client.get(
        f"/api/v1/public/widget/{key}/history", params={"visitor_id": "visitor-two"}
    )
    assert other.json()["messages"] == []

    widget = await client.get("/api/v1/integrations/widget", headers=session["headers"])
    assert widget.status_code == 200
    data = widget.json()
    assert key in data["embed_code"]
    assert data["embed_code"].startswith("<script")

    updated = await client.put(
        "/api/v1/integrations/widget",
        headers=session["headers"],
        json={"title": "Yordamchi", "color": "#ff8800", "greeting": "Salom!"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Yordamchi"
    assert updated.json()["color"] == "#ff8800"


async def test_operator_cannot_update_widget(client):
    session = await register_org(client, "widgetops")
    invite = await client.post(
        "/api/v1/orgs/members",
        headers=session["headers"],
        json={
            "email": f"widgetop-{session['org']['id']}@example.com",
            "full_name": "Widget Operator",
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

    response = await client.put(
        "/api/v1/integrations/widget",
        headers=operator_headers,
        json={"title": "Hacked"},
    )
    assert response.status_code == 403
