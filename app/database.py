"""app.database
=================
Mini-README: Provides SQLAlchemy database connectivity for the Nichifier platform.
Defines the async engine, session maker, and Base declarative class. Utilities for
initialising and obtaining sessions are exported for reuse across routers.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for ORM models."""


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.database_echo, future=True)
AsyncSessionMaker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for request-scoped use."""

    async with AsyncSessionMaker() as session:
        yield session


async def init_db() -> None:
    """Create database tables based on declarative metadata."""

    async with engine.begin() as conn:
        from . import models  # Import inside to ensure metadata is populated.

        await conn.run_sync(models.Base.metadata.create_all)


async def apply_schema_upgrades() -> None:
    """Apply idempotent schema upgrades to keep SQLite in sync with models."""

    async with engine.begin() as conn:
        await _ensure_niches_currency_code(conn)


async def _ensure_niches_currency_code(conn: AsyncConnection) -> None:
    """Add the `currency_code` column to `niches` if it is missing."""

    pragma_result = await conn.exec_driver_sql("PRAGMA table_info(niches)")
    column_names = {row[1] for row in pragma_result}
    if "currency_code" in column_names:
        return

    await conn.exec_driver_sql(
        "ALTER TABLE niches ADD COLUMN currency_code VARCHAR(3) NOT NULL DEFAULT 'GBP'"
    )
