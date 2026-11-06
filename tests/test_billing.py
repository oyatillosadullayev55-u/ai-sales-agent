from __future__ import annotations

from tests.conftest import register_org


async def test_billing_usage_and_subscription(client):
    session = await register_org(client, "billing")

    billing = await client.get("/api/v1/billing", headers=session["headers"])
    assert billing.status_code == 200
    body = billing.json()
    assert body["plan"] == "starter"
    assert set(body["plans"]) == {"starter", "pro", "business"}
    assert body["usage"]["team"] == 1
    assert body["usage"]["team_limit"] == 2
    assert body["usage"]["document_limit"] == 5
    assert body["payments"] == []

    payment = await client.post(
        "/api/v1/billing/subscribe",
        headers=session["headers"],
        json={"plan": "business", "months": 2},
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["amount"] == 3_980_000
    assert payment.json()["status"] == "paid"

    updated = await client.get("/api/v1/billing", headers=session["headers"])
    assert updated.json()["plan"] == "business"
    assert updated.json()["usage"]["conversation_limit"] == 10_000
    assert len(updated.json()["payments"]) == 1

    payments = await client.get("/api/v1/billing/payments", headers=session["headers"])
    assert len(payments.json()) == 1


async def test_team_limit_and_role_guard(client):
    session = await register_org(client, "teamlimit")

    first = await client.post(
        "/api/v1/orgs/members",
        headers=session["headers"],
        json={
            "email": f"manager-{session['org']['id']}@example.com",
            "full_name": "Manager",
            "role": "manager",
            "password": "ManagerPass123",
        },
    )
    assert first.status_code == 201, first.text

    over_limit = await client.post(
        "/api/v1/orgs/members",
        headers=session["headers"],
        json={
            "email": f"third-{session['org']['id']}@example.com",
            "full_name": "Third",
            "role": "operator",
            "password": "OperatorPass123",
        },
    )
    assert over_limit.status_code == 402

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": first.json()["email"], "password": "ManagerPass123"},
    )
    manager_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Org-Id": session["org"]["id"],
    }

    subscribe = await client.post(
        "/api/v1/billing/subscribe",
        headers=manager_headers,
        json={"plan": "pro", "months": 1},
    )
    assert subscribe.status_code == 403

    updated = await client.patch(
        "/api/v1/orgs", headers=manager_headers, json={"contact_phone": "+998 71 200 00 00"}
    )
    assert updated.status_code == 403
