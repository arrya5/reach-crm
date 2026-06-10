"""Pydantic request/response schemas for the CRM API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .segmentation.dsl import FilterDSL


# --- customers ------------------------------------------------------------

class CustomerOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    city: str
    gender: str
    tags: list[str]

    model_config = ConfigDict(from_attributes=True)


# --- segments -------------------------------------------------------------

class SegmentPreviewIn(BaseModel):
    definition: FilterDSL


class SegmentPreviewOut(BaseModel):
    description: str
    est_count: int
    sample: list[CustomerOut]


class SegmentCreateIn(BaseModel):
    name: str
    definition: FilterDSL
    created_via: str = "agent"


class SegmentOut(BaseModel):
    id: int
    name: str
    definition: dict
    est_count: int
    created_via: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- campaigns ------------------------------------------------------------

class CampaignCreateIn(BaseModel):
    name: str
    goal_text: str = ""
    segment_id: int
    channel: str
    message_template: str


class CampaignOut(BaseModel):
    id: int
    name: str
    goal_text: str
    segment_id: int
    channel: str
    message_template: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- webhooks (receipts from the channel service) -------------------------

class ReceiptEvent(BaseModel):
    event_id: str
    communication_id: int
    event_type: str            # sent | delivered | failed | opened | read | clicked | converted
    occurred_at: datetime
    payload: dict = {}


# --- agent ----------------------------------------------------------------

class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatOut(BaseModel):
    conversation_id: str
    reply: str
    actions: list[dict] = []   # structured artifacts (segment preview, draft, campaign...)
