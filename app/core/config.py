from pydantic_settings import BaseSettings
from pydantic import field_validator


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
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"


settings = Settings()
