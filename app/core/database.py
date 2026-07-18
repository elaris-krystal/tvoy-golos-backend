from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import urlsplit
from app.core.config import settings

_is_postgres_asyncpg = "postgresql" in settings.database_url and "asyncpg" in settings.database_url

_connect_args = {}
if _is_postgres_asyncpg:
    # Для asyncpg + pooled-соединений (Neon, Supabase и любой Postgres за PgBouncer
    # в transaction mode) нужно отключить кэш prepared statements на уровне драйвера.
    # Без этого под конкурентной нагрузкой падает DuplicatePreparedStatementError —
    # PgBouncer в transaction mode переиспользует backend-соединения между разными
    # клиентами, а asyncpg кэширует prepared statements привязанными к конкретному
    # backend-соединению. При низкой нагрузке (локальные тесты, staging) ошибка не
    # проявляется, поэтому её легко пропустить и найти только в проде под реальным
    # трафиком.
    _connect_args["statement_cache_size"] = 0

    # SSL для managed-провайдеров (Neon, Supabase и т.п.) передаётся через
    # connect_args, а не через query-параметр sslmode в самой строке — asyncpg
    # не понимает sslmode/channel_binding (это формат libpq/psycopg2), их
    # убирает нормализация в config.py. Здесь включаем SSL по эвристике:
    # облачные провайдеры почти всегда требуют его, локальный/docker Postgres
    # для разработки обычно нет.
    _host = urlsplit(settings.database_url).hostname or ""
    if _host not in ("localhost", "127.0.0.1"):
        _connect_args["ssl"] = "require"

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session
