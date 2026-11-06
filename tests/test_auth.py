from __future__ import annotations

from tests.conftest import register_org


async def test_register_login_me_and_refresh(client):
    session = await register_org(client, "auth")
    assert session["role"] == "owner"
    assert session["org"]["plan"] == "starter"

    me = await client.get("/api/v1/auth/me", headers=session["headers"])
    assert me.status_code == 200
    assert me.json()["orgs"][0]["id"] == session["org"]["id"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": session["email"], "password": session["password"]},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "owner"

    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": session["email"], "password": "WrongPassword123"},
    )
    assert wrong.status_code == 401

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={
            "email": session["email"],
            "password": session["password"],
            "full_name": "Duplicate",
            "org_name": "Duplicate Store",
        },
    )
    assert duplicate.status_code == 409

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != session["refresh_token"]

    replay = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
    )
    assert replay.status_code == 401


async def test_password_reset_flow(client):
    session = await register_org(client, "reset")

    forgot = await client.post("/api/v1/auth/forgot-password", json={"email": session["email"]})
    assert forgot.status_code == 200
    token = forgot.json().get("reset_token")
    assert token

    reset = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "BrandNewPass123"}
    )
    assert reset.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": session["email"], "password": session["password"]},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": session["email"], "password": "BrandNewPass123"},
    )
    assert new_login.status_code == 200


async def test_unauthenticated_and_rbac(client):
    session = await register_org(client, "rbac")

    anonymous = await client.get("/api/v1/products")
    assert anonymous.status_code == 401

    invite = await client.post(
        "/api/v1/orgs/members",
        headers=session["headers"],
        json={
            "email": f"operator-{session['org']['id']}@example.com",
            "full_name": "Operator",
            "role": "operator",
            "password": "OperatorPass123",
        },
    )
    assert invite.status_code == 201, invite.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": invite.json()["email"], "password": "OperatorPass123"},
    )
    assert login.status_code == 200
    operator_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Org-Id": session["org"]["id"],
    }

    forbidden = await client.post(
        "/api/v1/products",
        headers=operator_headers,
        json={"name": "Operator product", "price": 1000, "category": "test"},
    )
    assert forbidden.status_code == 403

    allowed = await client.get("/api/v1/products", headers=operator_headers)
    assert allowed.status_code == 200

    admin_stats = await client.get("/api/v1/admin/stats", headers=session["headers"])
    assert admin_stats.status_code == 403
