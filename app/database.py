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
        await _ensure_niches_columns(conn)


async def _ensure_niches_columns(conn: AsyncConnection) -> None:
    """Backfill missing columns on the ``niches`` table for legacy databases."""

    # Pull the existing schema information up front so that we only interrogate
    # SQLite once. The pragma returns rows in the shape (cid, name, type, ...)
    pragma_result = await conn.exec_driver_sql("PRAGMA table_info(niches)")
    existing_columns = {row[1] for row in pragma_result}

    # Map column names to the SQL needed to add them. Each definition mirrors the
    # ORM model defaults so that older databases remain compatible with the
    # current application expectations.
    column_definitions = {
        "currency_code": "currency_code VARCHAR(3) NOT NULL DEFAULT 'GBP'",
        "newsletter_cadence": "newsletter_cadence VARCHAR(32) NOT NULL DEFAULT 'monthly'",
        "report_cadence": "report_cadence VARCHAR(32) NOT NULL DEFAULT 'monthly'",
        "voice_instructions": "voice_instructions TEXT NOT NULL DEFAULT ''",
        "style_guide": "style_guide TEXT NOT NULL DEFAULT ''",
    }

    for column_name, ddl in column_definitions.items():
        if column_name in existing_columns:
            continue

        # SQLite only supports adding a single column at a time via ALTER TABLE,
        # so we iterate and add each missing column individually.
        await conn.exec_driver_sql(f"ALTER TABLE niches ADD COLUMN {ddl}")
