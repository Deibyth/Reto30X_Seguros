"""Async SQLAlchemy database engine and session management.

Provides async engine initialization, session factory, and FastAPI
dependency injection via the get_db async generator.

PostgreSQL migration path: Replace create_async_engine URL with
postgresql+asyncpg://... and remove aiosqlite dependency.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

__all__ = [
    "engine",
    "async_session_maker",
    "init_engine",
    "dispose_engine",
    "get_db",
]

engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, echo: bool = False) -> None:
    """Initialize the async engine and session factory.

    Must be called once during application startup.
    """
    global engine, async_session_maker  # noqa: PLW0603
    engine = create_async_engine(database_url, echo=echo)
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def dispose_engine() -> None:
    """Dispose the async engine. Must be called during application shutdown."""
    global engine, async_session_maker  # noqa: PLW0603
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_maker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically closed when the request finishes.
    """
    if async_session_maker is None:
        raise RuntimeError(
            "Database not initialized. Call init_engine() before using get_db()."
        )
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
