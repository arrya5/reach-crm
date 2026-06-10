"""Idempotent, order-independent ingestion of channel callbacks.

This is the heart of the callback loop's resilience. Every receipt is applied
through :func:`apply_receipt`, which guarantees:

* **Exactly-once** — the UNIQUE ``event_id`` means a retried or duplicated
  callback is recorded once; the second attempt is a no-op.
* **Order-independent** — we set the lifecycle *timestamp* for the event's
  stage (only if not already set). Final status is *derived* from the set of
  timestamps (see ``Communication.derived_status``), so a ``read`` arriving
  before ``delivered`` still produces a correct funnel.
* **Monotonic conversions** — conversion revenue is attributed once, guarded by
  the same dedupe, so retries never double-count money.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Communication, CommunicationEvent
from ..schemas import ReceiptEvent

# event_type -> the timestamp column it stamps on the communication
_STAGE_COLUMN = {
    "sent": "sent_at",
    "delivered": "delivered_at",
    "failed": "failed_at",
    "opened": "opened_at",
    "read": "read_at",
    "clicked": "clicked_at",
    "converted": "converted_at",
}


async def apply_receipt(session: AsyncSession, event: ReceiptEvent) -> dict:
    """Apply one callback. Returns a small status dict for the API/log."""
    if event.event_type not in _STAGE_COLUMN:
        return {"status": "ignored", "reason": f"unknown event_type {event.event_type}"}

    # 1) Dedupe: already-seen event_id is a no-op.
    seen = await session.scalar(
        select(CommunicationEvent).where(CommunicationEvent.event_id == event.event_id)
    )
    if seen is not None:
        return {"status": "duplicate", "event_id": event.event_id}

    comm = await session.get(Communication, event.communication_id)
    if comm is None:
        return {"status": "unknown_communication", "id": event.communication_id}

    # 2) Append to the audit log (UNIQUE event_id also guards against races).
    session.add(CommunicationEvent(
        communication_id=comm.id,
        event_id=event.event_id,
        event_type=event.event_type,
        payload=event.payload,
        occurred_at=event.occurred_at,
    ))

    # 3) Stamp the stage timestamp once (idempotent even if the same stage is
    #    reported twice with different event_ids — e.g. provider re-sends).
    column = _STAGE_COLUMN[event.event_type]
    if getattr(comm, column) is None:
        setattr(comm, column, event.occurred_at)

    if event.event_type == "failed" and comm.failure_reason is None:
        comm.failure_reason = event.payload.get("reason", "delivery_failed")

    if event.event_type == "converted" and comm.conversion_value is None:
        comm.conversion_value = float(event.payload.get("order_value", 0.0))

    try:
        await session.commit()
    except IntegrityError:
        # Concurrent duplicate slipped past the read check; the UNIQUE
        # constraint rejected it. Safe to treat as already-applied.
        await session.rollback()
        return {"status": "duplicate", "event_id": event.event_id}

    await session.refresh(comm)
    return {"status": "applied", "communication_id": comm.id, "state": comm.derived_status}
