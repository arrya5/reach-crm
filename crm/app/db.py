"""Async SQLAlchemy engine + session plumbing.

A single async engine is shared process-wide; ``get_session`` is the FastAPI
dependency that hands each request its own ``AsyncSession``.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


# asyncpg doesn't read libpq's ``sslmode`` from the URL (we strip it in config),
# so managed Postgres like Neon — which *requires* TLS — needs SSL enabled via
# connect_args. SQLite needs none of this.
_connect_args: dict = {}
if settings.database_url.startswith("postgresql+asyncpg"):
    _connect_args["ssl"] = True

engine = create_async_engine(
    settings.database_url, echo=False, future=True, connect_args=_connect_args
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables from the ORM metadata.

    We use ``create_all`` rather than migrations for this assignment's scope;
    at production scale this would be Alembic-managed (noted in the README).
    """
    from . import models  # noqa: F401  (register mappers before create_all)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
