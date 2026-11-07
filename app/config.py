from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Sales Agent"
    env: str = "dev"
    dev_mode: bool = True

    secret_key: str = "dev-secret-key-change-me-in-production-0123456789"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "*"

    # LLM (OpenAI-compatible). Empty key -> deterministic offline agent.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    llm_timeout_seconds: float = 45.0

    ingest_sync: bool = True
    seed_demo: bool = True
    super_admin_email: str = "admin@aisales.uz"
    super_admin_password: str = "Admin12345"
    rate_limit_per_minute: int = 120
    max_upload_mb: int = 15

    # None -> auto: polling when PUBLIC_BASE_URL is not https, webhook otherwise.
    telegram_polling: bool | None = None

    @property
    def cors_list(self) -> list[str]:
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def embeddings_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def telegram_polling_enabled(self) -> bool:
        if self.telegram_polling is not None:
            return self.telegram_polling
        return not self.public_base_url.strip().lower().startswith("https://")

    @property
    def telegram_mode(self) -> str:
        return "polling" if self.telegram_polling_enabled else "webhook"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

PLANS: dict[str, dict] = {
    "starter": {
        "title": "Starter",
        "price": 299_000,
        "conversations": 300,
        "documents": 5,
        "team": 2,
        "features": ["Telegram bot", "Sayt widgeti", "AI RAG javoblari", "Asosiy analitika"],
    },
    "pro": {
        "title": "Pro",
        "price": 799_000,
        "conversations": 2_000,
        "documents": 30,
        "team": 10,
        "features": ["Starter +", "Buyurtmalar moduli", "Operator handoff", "Kengaytirilgan analitika"],
    },
    "business": {
        "title": "Business",
        "price": 1_990_000,
        "conversations": 10_000,
        "documents": 200,
        "team": 50,
        "features": ["Pro +", "Ko'p filial", "Prioritet qo'llab-quvvatlash", "API limitlari 10x"],
    },
}

PLAN_ORDER = ["starter", "pro", "business"]
