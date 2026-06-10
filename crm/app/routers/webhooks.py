"""Receipt webhook — where the channel service calls back into the CRM.

The handler verifies the HMAC signature over the raw body, then delegates to
the idempotent :func:`apply_receipt`. It accepts both a single event and a
batch so the channel service can coalesce callbacks under load.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..schemas import ReceiptEvent
from ..security import verify
from ..services.receipts import apply_receipt

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/receipts")
async def receipts(
    request: Request,
    x_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    raw = await request.body()
    if not verify(raw, x_signature, settings.webhook_secret):
        raise HTTPException(401, "invalid signature")

    data = json.loads(raw)
    events = data if isinstance(data, list) else [data]

    results = []
    for item in events:
        event = ReceiptEvent.model_validate(item)
        results.append(await apply_receipt(session, event))
    return {"received": len(results), "results": results}
