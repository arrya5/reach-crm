"""Campaign CRUD + the human-in-the-loop launch gate.

The agent can *stage* a campaign (status ``draft``), but only an explicit call
to ``POST /campaigns/{id}/launch`` — wired to the "Approve & Launch" button in
the UI — actually dispatches messages. This keeps a human in control of every
real send.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..models import Campaign, CampaignStatus, Segment
from ..schemas import CampaignCreateIn, CampaignOut
from ..services.analytics import campaign_stats
from ..services.sender import launch_campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut)
async def create_campaign(
    body: CampaignCreateIn, session: AsyncSession = Depends(get_session)
):
    if await session.get(Segment, body.segment_id) is None:
        raise HTTPException(400, "segment does not exist")
    campaign = Campaign(
        name=body.name,
        goal_text=body.goal_text,
        segment_id=body.segment_id,
        channel=body.channel,
        message_template=body.message_template,
        status=CampaignStatus.draft.value,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(Campaign).order_by(Campaign.id.desc()))
    return list(rows.all())


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "campaign not found")
    return campaign


@router.post("/{campaign_id}/launch")
async def launch(campaign_id: int, session: AsyncSession = Depends(get_session)):
    campaign = (await session.scalars(
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(selectinload(Campaign.segment))
    )).first()
    if campaign is None:
        raise HTTPException(404, "campaign not found")
    if campaign.status not in (CampaignStatus.draft.value, CampaignStatus.failed.value):
        raise HTTPException(409, f"campaign already {campaign.status}")
    return await launch_campaign(session, campaign)


@router.get("/{campaign_id}/stats")
async def stats(campaign_id: int, session: AsyncSession = Depends(get_session)):
    result = await campaign_stats(session, campaign_id)
    if result is None:
        raise HTTPException(404, "campaign not found")
    return result
