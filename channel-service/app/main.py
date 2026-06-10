"""Stubbed channel service entry point.

Receives signed send batches from the CRM, returns 202 immediately, and lets
the worker pool simulate delivery + fire engagement callbacks asynchronously.
It deliberately delivers nothing real — it only models the lifecycle.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from .config import settings
from .security import verify
from .worker import STATS, enqueue, get_queue, start_workers, stop_workers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_workers()
    yield
    await stop_workers()


app = FastAPI(title="Reach Channel Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reach-channel", "workers": settings.worker_count}


@app.get("/stats")
async def stats():
    return {"queue_depth": get_queue().qsize(), **STATS}


@app.post("/v1/send", status_code=202)
async def send(request: Request, x_signature: str | None = Header(default=None)):
    """Accept a batch of communications to 'deliver'. Verifies HMAC, enqueues,
    and returns 202 Accepted — outcomes arrive later via callbacks."""
    raw = await request.body()
    if not verify(raw, x_signature, settings.webhook_secret):
        raise HTTPException(401, "invalid signature")

    data = json.loads(raw)
    channel = data["channel"]
    callback_url = data["callback_url"]
    comms = data.get("communications", [])
    for comm in comms:
        await enqueue(comm, channel, callback_url)

    return {"accepted": len(comms), "channel": channel}
