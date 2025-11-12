"""app.database
=================
Mini-README: Provides SQLAlchemy database connectivity for the Nichifier platform.
Defines the async engine, session maker, and Base declarative class. Utilities for
initialising and obtaining sessions are exported for reuse across routers.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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
