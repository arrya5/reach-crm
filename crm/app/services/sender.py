"""Campaign launch: resolve audience, render messages, dispatch to channel svc.

The CRM owns *what* to send and to *whom*; the channel service owns *delivery*.
On launch we materialise one ``Communication`` per recipient (so we can track
each independently), then hand the batch off over a signed HTTP call.
"""
from __future__ import annotations

import json

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    Campaign,
    CampaignStatus,
    Channel,
    Communication,
    Customer,
    Order,
    utcnow,
)
from ..security import sign
from ..segmentation.dsl import FilterDSL, build_query


def render(template: str, customer: Customer, last_item: str | None) -> str:
    """Fill personalization tokens. Unknown tokens are left visibly intact."""
    first_name = customer.name.split(" ")[0]
    return (
        template
        .replace("{{name}}", first_name)
        .replace("{{city}}", customer.city)
        .replace("{{last_item}}", last_item or "your favourite")
    )


def _recipient(customer: Customer, channel: str) -> str:
    return customer.email if channel == Channel.email.value else customer.phone


async def _last_items(session: AsyncSession, customer_ids: list[int]) -> dict[int, str]:
    """Map customer_id -> most recently purchased product, for personalization."""
    if not customer_ids:
        return {}
    rows = (await session.execute(
        select(Order.customer_id, Order.product_name)
        .where(Order.customer_id.in_(customer_ids))
        .order_by(Order.ordered_at.desc())
    )).all()
    last: dict[int, str] = {}
    for cid, product in rows:
        last.setdefault(cid, product)  # first seen == most recent
    return last


async def launch_campaign(session: AsyncSession, campaign: Campaign) -> dict:
    """Materialise communications and dispatch them. Returns a summary."""
    segment = campaign.segment
    dsl = FilterDSL.model_validate(segment.definition)
    customers = list((await session.scalars(build_query(dsl))).all())

    last_items = await _last_items(session, [c.id for c in customers])

    # Clear any communications from a previous failed attempt so re-launching a
    # failed campaign is idempotent (no duplicate sends).
    await session.execute(
        delete(Communication).where(Communication.campaign_id == campaign.id)
    )

    campaign.status = CampaignStatus.launching.value
    comms: list[Communication] = []
    for cust in customers:
        comm = Communication(
            campaign_id=campaign.id,
            customer_id=cust.id,
            channel=campaign.channel,
            recipient=_recipient(cust, campaign.channel),
            rendered_message=render(campaign.message_template, cust, last_items.get(cust.id)),
            queued_at=utcnow(),
        )
        session.add(comm)
        comms.append(comm)
    await session.commit()
    for c in comms:
        await session.refresh(c)

    # If the channel service is cold (free tier), the first dispatch can take
    # ~50s to wake it. On failure we mark the campaign failed (not stuck in
    # 'launching') so it stays re-launchable and doesn't show as forever-live.
    try:
        await _dispatch(campaign, comms)
    except Exception:
        campaign.status = CampaignStatus.failed.value
        await session.commit()
        raise

    campaign.status = CampaignStatus.sent.value
    await session.commit()
    return {"campaign_id": campaign.id, "recipients": len(comms)}


async def _dispatch(campaign: Campaign, comms: list[Communication]) -> None:
    """POST the batch to the channel service with an HMAC signature."""
    payload = {
        "campaign_id": campaign.id,
        "channel": campaign.channel,
        "callback_url": f"{settings.crm_public_url}/webhooks/receipts",
        "communications": [
            {"id": c.id, "recipient": c.recipient, "message": c.rendered_message}
            for c in comms
        ],
    }
    raw = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Signature": sign(raw, settings.webhook_secret),
    }
    # Generous timeout: a cold (spun-down) channel service can take ~50s to wake.
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{settings.channel_service_url}/v1/send", content=raw, headers=headers
        )
        resp.raise_for_status()
