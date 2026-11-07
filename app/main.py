from __future__ import annotations

import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db
from app.routers import (
    admin,
    analytics,
    auth,
    billing,
    conversations,
    integrations,
    knowledge,
    orders,
    orgs,
    products,
    public,
    telegram,
)
from app.seed import seed_demo
from app.services.telegram_polling import TelegramPoller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    if settings.seed_demo:
        try:
            await seed_demo()
        except Exception:  # pragma: no cover - demo seed must never block startup
            logger.exception("Demo seed failed")
    if settings.env != "dev" and settings.secret_key.startswith("dev-secret"):
        logger.warning("SECRET_KEY production qiymatiga almashtirilmagan!")
    poller: TelegramPoller | None = None
    if settings.telegram_polling_enabled:
        poller = TelegramPoller()
        await poller.start()
        logger.info("Telegram long polling rejimi yoqilgan")
    yield
    if poller is not None:
        await poller.stop()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int, protected: tuple[str, ...]) -> None:
        super().__init__(app)
        self.limit = limit
        self.protected = protected
        self.hits: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(self.protected):
            return await call_next(request)

        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
        now = time.time()
        bucket = self.hits.setdefault(ip, deque())
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Juda ko'p so'rov. Bir daqiqadan so'ng qayta urinib ko'ring."},
            )
        bucket.append(now)
        if len(self.hits) > 10_000:
            self.hits.clear()
        return await call_next(request)


app.add_middleware(
    RateLimitMiddleware,
    limit=settings.rate_limit_per_minute,
    protected=("/api/v1/public", "/api/v1/telegram"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


API_PREFIX = "/api/v1"
for router in (
    auth.router,
    orgs.router,
    knowledge.router,
    products.router,
    orders.router,
    conversations.router,
    analytics.router,
    billing.router,
    admin.router,
    integrations.router,
    public.router,
    telegram.router,
):
    app.include_router(router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "llm_enabled": settings.llm_enabled,
        "embeddings": "openai" if settings.embeddings_enabled else "local",
        "telegram_mode": settings.telegram_mode,
    }


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _page(request: Request, name: str, **extra) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        name,
        {"request": request, "base_url": settings.public_base_url.rstrip("/"), **extra},
    )


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return _page(request, "landing.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return _page(request, "auth.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    return _page(request, "dashboard.html")


@app.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request) -> HTMLResponse:
    return _page(request, "demo.html")
