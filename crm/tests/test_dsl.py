"""Filter DSL -> query translation, validated against known fixtures."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import Customer, Order
from app.segmentation.dsl import ALLOWED_FIELDS, Condition, FilterDSL, build_query


def _now():
    return datetime.now(timezone.utc)


async def _count(session, dsl: FilterDSL) -> int:
    return await session.scalar(select(func.count()).select_from(build_query(dsl).subquery()))


@pytest.mark.asyncio
async def test_relative_date_and_category(session):
    now = _now()
    # Alice: bought lipstick 90 days ago (lapsed).
    alice = Customer(name="Alice A", email="a@x.com", phone="1", city="Mumbai", gender="female", tags=[])
    # Bob: bought lipstick 5 days ago (active).
    bob = Customer(name="Bob B", email="b@x.com", phone="2", city="Delhi", gender="male", tags=[])
    session.add_all([alice, bob])
    await session.flush()
    session.add_all([
        Order(customer_id=alice.id, amount=500, category="lipstick",
              product_name="Matte", ordered_at=now - timedelta(days=90)),
        Order(customer_id=bob.id, amount=500, category="lipstick",
              product_name="Matte", ordered_at=now - timedelta(days=5)),
    ])
    await session.commit()

    lapsed = FilterDSL.model_validate({"match": "all", "conditions": [
        {"field": "last_order_days_ago", "op": "gt", "value": 60},
        {"field": "category", "op": "in", "value": ["lipstick"]},
    ]})
    assert await _count(session, lapsed) == 1  # only Alice

    recent = FilterDSL.model_validate({"match": "all", "conditions": [
        {"field": "last_order_days_ago", "op": "lt", "value": 60},
    ]})
    assert await _count(session, recent) == 1  # only Bob


@pytest.mark.asyncio
async def test_spend_and_match_any(session):
    now = _now()
    c = Customer(name="Big Spender", email="c@x.com", phone="3", city="Pune", gender="female", tags=[])
    session.add(c)
    await session.flush()
    session.add_all([
        Order(customer_id=c.id, amount=3000, category="skincare", product_name="Serum", ordered_at=now),
        Order(customer_id=c.id, amount=3000, category="skincare", product_name="Serum", ordered_at=now),
    ])
    await session.commit()

    spend = FilterDSL.model_validate({"match": "all", "conditions": [
        {"field": "total_spend", "op": "gte", "value": 5000},
    ]})
    assert await _count(session, spend) == 1

    # match=any: either high spend OR in Chennai (no Chennai customer) -> still 1
    any_dsl = FilterDSL.model_validate({"match": "any", "conditions": [
        {"field": "total_spend", "op": "gte", "value": 5000},
        {"field": "city", "op": "eq", "value": "Chennai"},
    ]})
    assert await _count(session, any_dsl) == 1


def test_rejects_unknown_field():
    with pytest.raises(ValueError):
        Condition(field="not_a_field", op="eq", value=1)


def test_rejects_disallowed_op():
    # 'contains' is not valid for a numeric field.
    with pytest.raises(ValueError):
        FilterDSL.model_validate({"conditions": [
            {"field": "total_spend", "op": "contains", "value": "x"},
        ]})


def test_field_registry_self_consistent():
    assert "last_order_days_ago" in ALLOWED_FIELDS
    assert "in" in ALLOWED_FIELDS["category"]
