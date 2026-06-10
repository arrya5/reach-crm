"""Recipient-level views backing the campaign detail screen."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Communication, Customer

router = APIRouter(prefix="/campaigns", tags=["analytics"])


@router.get("/{campaign_id}/communications")
async def list_communications(
    campaign_id: int, limit: int = 100, session: AsyncSession = Depends(get_session)
):
    rows = (await session.execute(
        select(Communication, Customer.name)
        .join(Customer, Customer.id == Communication.customer_id)
        .where(Communication.campaign_id == campaign_id)
        .order_by(Communication.id)
        .limit(limit)
    )).all()
    return [
        {
            "id": c.id,
            "customer": name,
            "recipient": c.recipient,
            "status": c.derived_status,
            "failure_reason": c.failure_reason,
            "conversion_value": c.conversion_value,
            "message": c.rendered_message,
        }
        for c, name in rows
    ]
