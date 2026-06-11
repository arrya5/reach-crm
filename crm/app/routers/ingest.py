"""Data ingestion — take in customers and their orders and store them.

Accepts a JSON payload of customers and/or orders. Customers are keyed by
email (idempotent: an email that already exists is skipped, not duplicated);
orders link to their customer by ``customer_email`` and are skipped if no
matching customer is found. The frontend's CSV upload parses files client-side
and posts here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Customer, Order, utcnow
from ..schemas import IngestRequest, IngestResult

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResult)
async def ingest(body: IngestRequest, session: AsyncSession = Depends(get_session)):
    emails = {c.email for c in body.customers} | {o.customer_email for o in body.orders}
    email_to_id: dict[str, int] = {}
    if emails:
        rows = await session.execute(
            select(Customer.email, Customer.id).where(Customer.email.in_(emails))
        )
        email_to_id = {email: cid for email, cid in rows.all()}

    customers_added = customers_skipped = 0
    new_customers: list[tuple[str, Customer]] = []
    for c in body.customers:
        if c.email in email_to_id:
            customers_skipped += 1
            continue
        cust = Customer(
            name=c.name, email=c.email, phone=c.phone,
            city=c.city, gender=c.gender, tags=c.tags,
        )
        session.add(cust)
        new_customers.append((c.email, cust))
        customers_added += 1
    await session.flush()  # assign ids to new customers
    for email, cust in new_customers:
        email_to_id[email] = cust.id

    orders_added = orders_skipped = 0
    for o in body.orders:
        cid = email_to_id.get(o.customer_email)
        if cid is None:
            orders_skipped += 1
            continue
        session.add(Order(
            customer_id=cid, amount=o.amount, category=o.category,
            product_name=o.product_name or o.category,
            ordered_at=o.ordered_at or utcnow(),
        ))
        orders_added += 1

    await session.commit()
    return IngestResult(
        customers_added=customers_added, customers_skipped=customers_skipped,
        orders_added=orders_added, orders_skipped=orders_skipped,
    )
