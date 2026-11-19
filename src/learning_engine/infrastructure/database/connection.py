from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from learning_engine.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


def live_session_factory(session: AsyncSession):
    """A session_factory that reuses an existing live session (never closes it).

    Used by the Test Playground so the pipeline sees the caller's uncommitted
    temp docs. Production passes ``async_session_factory`` (real short sessions).
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory
