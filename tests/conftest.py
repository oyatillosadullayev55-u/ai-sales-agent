from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "data" / "test_app.db"
for suffix in ("", "-wal", "-shm"):
    Path(f"{TEST_DB}{suffix}").unlink(missing_ok=True)

os.environ.update(
    {
        "DATABASE_URL": "sqlite+aiosqlite:///./data/test_app.db",
        "SEED_DEMO": "false",
        "INGEST_SYNC": "true",
        "DEV_MODE": "true",
        "ENV": "test",
        "LLM_API_KEY": "",
        "SECRET_KEY": "test-secret-key-0123456789-0123456789",
        "RATE_LIMIT_PER_MINUTE": "1000",
        "PUBLIC_BASE_URL": "http://testserver",
    }
)

from app.database import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    await init_db()
    yield
    await engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{TEST_DB}{suffix}").unlink(missing_ok=True)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


def auth_headers(session: dict) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {session['access_token']}",
        "X-Org-Id": session["org"]["id"],
    }


async def register_org(
    client: AsyncClient,
    prefix: str = "org",
    password: str = "Password123",
    org_name: str | None = None,
) -> dict:
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": f"{prefix.title()} Owner",
            "org_name": org_name or f"{prefix.title()} Store {uuid.uuid4().hex[:4]}",
        },
    )
    assert response.status_code == 201, response.text
    session = response.json()
    session["email"] = email
    session["password"] = password
    session["headers"] = auth_headers(session)
    return session


async def widget_key(client: AsyncClient, session: dict) -> str:
    response = await client.get("/api/v1/integrations/widget", headers=session["headers"])
    assert response.status_code == 200, response.text
    return response.json()["public_key"]


async def create_product(
    client: AsyncClient,
    session: dict,
    *,
    name: str,
    price: float,
    category: str = "umumiy",
    stock_qty: int = 5,
    description: str = "",
) -> dict:
    response = await client.post(
        "/api/v1/products",
        headers=session["headers"],
        json={
            "name": name,
            "price": price,
            "category": category,
            "stock_qty": stock_qty,
            "description": description,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def upload_txt(client: AsyncClient, session: dict, text: str, filename: str = "kb.txt") -> dict:
    response = await client.post(
        "/api/v1/knowledge/upload",
        headers=session["headers"],
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


KB_TEXT = """TechNova do'koni ma'lumotlari.

KAFOLAT
Barcha mahsulotlarga 12 oy rasmiy kafolat beriladi. Kafolat servis markazlari orqali amalga oshiriladi.

YETKAZIB BERISH
Toshkent shahri bo'ylab yetkazib berish 24 soat ichida bepul.
Viloyatlarga yetkazib berish 1-3 ish kuni, narxi 50 000 so'm.

TO'LOV
Payme, Click va plastik karta orqali to'lash mumkin. 12 oygacha 0% foizli bo'lib to'lash mavjud.
"""
