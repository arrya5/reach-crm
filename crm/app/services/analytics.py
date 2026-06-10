"""Campaign performance: funnel counts + attributed revenue.

Counts are computed straight from the lifecycle timestamps so they always
agree with each communication's derived status. The funnel is cumulative
(every delivered message was also sent, etc.).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Campaign, Communication


def _count(col):
    return func.count(col)


async def campaign_stats(session: AsyncSession, campaign_id: int) -> dict | None:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        return None

    C = Communication
    row = (await session.execute(
        select(
            func.count(C.id),
            _count(C.sent_at),
            _count(C.delivered_at),
            _count(C.opened_at),
            _count(C.read_at),
            _count(C.clicked_at),
            _count(C.converted_at),
            func.coalesce(func.sum(C.conversion_value), 0.0),
        ).where(C.campaign_id == campaign_id)
    )).one()

    total, sent, delivered, opened, read, clicked, converted, revenue = row
    # Failed = delivery failed and never delivered.
    failed = await session.scalar(
        select(func.count(C.id)).where(
            C.campaign_id == campaign_id,
            C.failed_at.is_not(None),
            C.delivered_at.is_(None),
        )
    )

    def rate(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "channel": campaign.channel,
        "status": campaign.status,
        "funnel": {
            "audience": total,
            "sent": sent,
            "delivered": delivered,
            "opened": opened,
            "read": read,
            "clicked": clicked,
            "converted": converted,
            "failed": failed or 0,
        },
        "rates": {
            "delivery_rate": rate(delivered, sent),
            "open_rate": rate(opened, delivered),
            "click_rate": rate(clicked, delivered),
            "conversion_rate": rate(converted, delivered),
        },
        "attributed_revenue": round(float(revenue), 2),
    }
