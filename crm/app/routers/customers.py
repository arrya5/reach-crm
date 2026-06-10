"""Read-only customer endpoints (the dashboard's customers table)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Customer, Order
from ..schemas import CustomerOut

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_session)
):
    rows = await session.scalars(
        select(Customer).order_by(Customer.id).limit(limit).offset(offset)
    )
    return list(rows.all())


@router.get("/stats")
async def customer_stats(session: AsyncSession = Depends(get_session)):
    total = await session.scalar(select(func.count(Customer.id)))
    orders = await session.scalar(select(func.count(Order.id)))
    revenue = await session.scalar(select(func.coalesce(func.sum(Order.amount), 0.0)))
    return {
        "customers": total or 0,
        "orders": orders or 0,
        "lifetime_revenue": round(float(revenue or 0), 2),
    }
