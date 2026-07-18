from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Для asyncpg + pooled-соединений (Neon, Supabase и любой Postgres за PgBouncer
# в transaction mode) нужно отключить кэш prepared statements на уровне драйвера.
# Без этого под конкурентной нагрузкой падает DuplicatePreparedStatementError —
# PgBouncer в transaction mode переиспользует backend-соединения между разными
# клиентами, а asyncpg кэширует prepared statements привязанными к конкретному
# backend-соединению. При низкой нагрузке (локальные тесты, staging) ошибка не
# проявляется, поэтому её легко пропустить и найти только в проде под реальным
# трафиком. sqlite (используется в тестах) этот параметр не поддерживает,
# поэтому передаём connect_args только для asyncpg.
_connect_args = {}
if "postgresql" in settings.database_url and "asyncpg" in settings.database_url:
    _connect_args = {"statement_cache_size": 0}

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
