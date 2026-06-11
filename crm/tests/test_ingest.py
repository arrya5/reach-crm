"""Data ingestion: customers + orders, idempotency, order-to-customer linking."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import Customer, Order
from app.routers.ingest import ingest
from app.schemas import IngestRequest


@pytest.mark.asyncio
async def test_ingest_customers_and_orders(session):
    req = IngestRequest.model_validate({
        "customers": [
            {"name": "Asha", "email": "asha@x.com", "city": "Mumbai"},
            {"name": "Ravi", "email": "ravi@x.com"},
        ],
        "orders": [
            {"customer_email": "asha@x.com", "amount": 799, "category": "skincare"},
            {"customer_email": "ravi@x.com", "amount": 499, "category": "lipstick"},
            {"customer_email": "ghost@x.com", "amount": 100, "category": "nails"},
        ],
    })
    res = await ingest(req, session)
    assert res.customers_added == 2
    assert res.orders_added == 2
    assert res.orders_skipped == 1          # ghost has no customer
    assert await session.scalar(select(func.count(Customer.id))) == 2
    assert await session.scalar(select(func.count(Order.id))) == 2


@pytest.mark.asyncio
async def test_ingest_is_idempotent_on_email(session):
    body = {"customers": [{"name": "Asha", "email": "asha@x.com"}]}
    first = await ingest(IngestRequest.model_validate(body), session)
    second = await ingest(IngestRequest.model_validate(body), session)
    assert first.customers_added == 1
    assert second.customers_added == 0
    assert second.customers_skipped == 1
    assert await session.scalar(select(func.count(Customer.id))) == 1
