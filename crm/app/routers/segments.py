"""Segment preview + persistence.

``/segments/preview`` is the live feedback loop the marketer (and the agent)
use to size an audience before committing: it compiles the Filter DSL, returns
a count and a small sample, and never writes anything.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Campaign, Customer, Segment
from ..schemas import (
    SegmentCreateIn,
    SegmentOut,
    SegmentPreviewIn,
    SegmentPreviewOut,
)
from ..segmentation.dsl import build_query, describe

router = APIRouter(prefix="/segments", tags=["segments"])


async def _preview(session: AsyncSession, dsl) -> tuple[int, list[Customer], str]:
    query = build_query(dsl)
    count = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    sample = list((await session.scalars(query.limit(8))).all())
    return count or 0, sample, describe(dsl)


@router.post("/preview", response_model=SegmentPreviewOut)
async def preview_segment(
    body: SegmentPreviewIn, session: AsyncSession = Depends(get_session)
):
    count, sample, description = await _preview(session, body.definition)
    return SegmentPreviewOut(description=description, est_count=count, sample=sample)


@router.post("", response_model=SegmentOut)
async def create_segment(
    body: SegmentCreateIn, session: AsyncSession = Depends(get_session)
):
    count, _, _ = await _preview(session, body.definition)
    segment = Segment(
        name=body.name,
        definition=body.definition.model_dump(),
        created_via=body.created_via,
        est_count=count,
    )
    session.add(segment)
    await session.commit()
    await session.refresh(segment)
    return segment


@router.get("", response_model=list[SegmentOut])
async def list_segments(session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(Segment).order_by(Segment.id.desc()))
    return list(rows.all())


@router.get("/{segment_id}", response_model=SegmentOut)
async def get_segment(segment_id: int, session: AsyncSession = Depends(get_session)):
    seg = await session.get(Segment, segment_id)
    if seg is None:
        raise HTTPException(404, "segment not found")
    return seg


@router.delete("/{segment_id}")
async def delete_segment(segment_id: int, session: AsyncSession = Depends(get_session)):
    seg = await session.get(Segment, segment_id)
    if seg is None:
        raise HTTPException(404, "segment not found")
    in_use = await session.scalar(
        select(func.count(Campaign.id)).where(Campaign.segment_id == segment_id)
    )
    if in_use:
        raise HTTPException(409, f"segment is used by {in_use} campaign(s); delete those first")
    await session.delete(seg)
    await session.commit()
    return {"deleted": segment_id}
