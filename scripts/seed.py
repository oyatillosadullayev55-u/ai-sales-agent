from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.database import init_db  # noqa: E402
from app.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo  # noqa: E402


async def main() -> None:
    await init_db()
    await seed_demo()
    print("Demo tayyor.")
    print(f"  Dashboard: {settings.public_base_url.rstrip('/')}/login")
    print(f"  Email: {DEMO_EMAIL}")
    print(f"  Parol: {DEMO_PASSWORD}")
    print(f"  Super admin: {settings.super_admin_email} / {settings.super_admin_password}")
    print(f"  Demo widget: {settings.public_base_url.rstrip('/')}/demo")


if __name__ == "__main__":
    asyncio.run(main())
