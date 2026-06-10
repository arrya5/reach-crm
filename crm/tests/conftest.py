"""Test fixtures: an isolated in-memory SQLite DB per test.

Services in this codebase take an ``AsyncSession`` as a parameter (rather than
reaching for a global), which is exactly what makes them trivially testable —
we hand them a session bound to a throwaway in-memory database.
"""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base


@pytest_asyncio.fixture
async def session():
    # StaticPool keeps a single shared connection so the :memory: DB persists
    # across the test's queries.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()
