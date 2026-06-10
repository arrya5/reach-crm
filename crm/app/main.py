"""CRM service entry point.

Wires routers, CORS, and DB init. The CRM is the product: ingestion,
segmentation, the agent, campaign launch, webhook ingest, and analytics.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import agent, analytics, campaigns, customers, segments, webhooks


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Reach CRM", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (customers.router, segments.router, campaigns.router,
          analytics.router, webhooks.router, agent.router):
    app.include_router(r)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reach-crm"}
