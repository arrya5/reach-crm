"""Webhook ingestion: idempotency, out-of-order tolerance, no double-count."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import (
    Campaign,
    CampaignStatus,
    Communication,
    CommunicationEvent,
    Customer,
    Segment,
)
from app.schemas import ReceiptEvent
from app.services.receipts import apply_receipt


def _now():
    return datetime.now(timezone.utc)


async def _make_comm(session) -> Communication:
    cust = Customer(name="Test U", email="t@x.com", phone="1", city="Mumbai", gender="female", tags=[])
    seg = Segment(name="s", definition={"match": "all", "conditions": []}, est_count=1)
    session.add_all([cust, seg])
    await session.flush()
    camp = Campaign(name="c", segment_id=seg.id, channel="whatsapp",
                    message_template="hi", status=CampaignStatus.sent.value)
    session.add(camp)
    await session.flush()
    comm = Communication(campaign_id=camp.id, customer_id=cust.id, channel="whatsapp",
                         recipient="1", rendered_message="hi", queued_at=_now())
    session.add(comm)
    await session.commit()
    await session.refresh(comm)
    return comm


def _evt(comm_id, etype, eid, offset_s, payload=None):
    return ReceiptEvent(
        event_id=eid, communication_id=comm_id, event_type=etype,
        occurred_at=_now() + timedelta(seconds=offset_s), payload=payload or {},
    )


@pytest.mark.asyncio
async def test_duplicate_event_is_noop(session):
    comm = await _make_comm(session)
    r1 = await apply_receipt(session, _evt(comm.id, "delivered", "e1", 1))
    r2 = await apply_receipt(session, _evt(comm.id, "delivered", "e1", 1))
    assert r1["status"] == "applied"
    assert r2["status"] == "duplicate"
    # Only one event row recorded.
    n = await session.scalar(select(func.count(CommunicationEvent.id)))
    assert n == 1


@pytest.mark.asyncio
async def test_out_of_order_yields_correct_status(session):
    comm = await _make_comm(session)
    # 'read' arrives BEFORE 'delivered' and 'sent'.
    await apply_receipt(session, _evt(comm.id, "read", "e1", 3))
    await apply_receipt(session, _evt(comm.id, "delivered", "e2", 1))
    await apply_receipt(session, _evt(comm.id, "sent", "e3", 0))
    refreshed = await session.get(Communication, comm.id)
    # Status is derived from timestamps, so order of arrival doesn't matter.
    assert refreshed.derived_status == "read"
    assert refreshed.sent_at is not None and refreshed.delivered_at is not None


@pytest.mark.asyncio
async def test_failed_only_terminal_if_not_delivered(session):
    comm = await _make_comm(session)
    await apply_receipt(session, _evt(comm.id, "failed", "e1", 1, {"reason": "invalid_number"}))
    c = await session.get(Communication, comm.id)
    assert c.derived_status == "failed"
    assert c.failure_reason == "invalid_number"


@pytest.mark.asyncio
async def test_conversion_revenue_not_double_counted(session):
    comm = await _make_comm(session)
    await apply_receipt(session, _evt(comm.id, "converted", "e1", 5, {"order_value": 1200.0}))
    # Same conversion event re-sent (retry) with the same event_id.
    await apply_receipt(session, _evt(comm.id, "converted", "e1", 5, {"order_value": 1200.0}))
    c = await session.get(Communication, comm.id)
    assert c.conversion_value == 1200.0  # counted exactly once
    assert c.derived_status == "converted"
