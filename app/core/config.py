from pydantic_settings import BaseSettings
from pydantic import field_validator
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/tvoy_golos"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"   # anthropic | openai | none
    llm_timeout_sec: int = 15
    uniqualize_min_pct: int = 40
    frontend_origin: str = "http://localhost:5173"
    env: str = "development"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """
        Render/Railway/Heroku отдают DATABASE_URL в формате postgres:// или
        postgresql://, а SQLAlchemy async-движок требует явный драйвер asyncpg.
        Без этой нормализации приложение падает на старте на проде.
        """
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Neon, Supabase и другие managed-провайдеры добавляют в connection
        # string параметры sslmode/channel_binding — это формат libpq
        # (psycopg2), а не asyncpg. asyncpg не распознаёт эти параметры и
        # пытается отправить их на сервер как session-level настройки, из-за
        # чего соединение падает без внятной ошибки на уровне приложения
        # (health check просто вернёт db:false). SSL для Neon включаем
        # отдельно через connect_args в database.py, а не через query string.
        if "+asyncpg" in v:
            parts = urlsplit(v)
            query = parse_qs(parts.query)
            query.pop("sslmode", None)
            query.pop("channel_binding", None)
            new_query = urlencode(query, doseq=True)
            v = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

        return v

    class Config:
        env_file = ".env"


settings = Settings()
