"""ORM models for the CRM.

Design note on ``Communication``: the lifecycle status is *derived* from which
timestamp columns are set (see ``derived_status``), not stored as an
independently mutable field. Combined with the UNIQUE ``event_id`` on
``CommunicationEvent``, this makes callback ingestion naturally idempotent and
order-independent — a ``read`` callback arriving before ``delivered`` still
yields a correct final state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(str, Enum):
    whatsapp = "whatsapp"
    sms = "sms"
    email = "email"
    rcs = "rcs"


class CampaignStatus(str, Enum):
    draft = "draft"          # staged by the agent, awaiting human approval
    launching = "launching"  # dispatch to channel service in progress
    sent = "sent"            # all communications handed off
    failed = "failed"


# Ordered lifecycle stages used to derive a communication's status from its
# timestamps. Higher index = further along the funnel.
LIFECYCLE_ORDER = ["queued", "sent", "delivered", "opened", "read", "clicked", "converted"]


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(40))
    city: Mapped[str] = mapped_column(String(80), index=True)
    gender: Mapped[str] = mapped_column(String(20))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(60), index=True)
    product_name: Mapped[str] = mapped_column(String(160))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    # Serialized FilterDSL describing the audience (see segmentation/dsl.py).
    definition: Mapped[dict] = mapped_column(JSON)
    created_via: Mapped[str] = mapped_column(String(20), default="agent")  # agent | manual
    est_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    goal_text: Mapped[str] = mapped_column(Text, default="")
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"))
    channel: Mapped[str] = mapped_column(String(20))
    # Message body, may contain {{name}} / {{last_item}} personalization tokens.
    message_template: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=CampaignStatus.draft.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    segment: Mapped["Segment"] = relationship()
    communications: Mapped[list["Communication"]] = relationship(back_populates="campaign")


class Communication(Base):
    """One message to one customer, with its delivery/engagement lifecycle."""

    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(200))      # email or phone
    rendered_message: Mapped[str] = mapped_column(Text)

    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Revenue attributed to this communication when a conversion is reported.
    conversion_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lifecycle timestamps — each set once, idempotently, by callbacks.
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="communications")
    events: Mapped[list["CommunicationEvent"]] = relationship(back_populates="communication")

    @property
    def derived_status(self) -> str:
        """Furthest lifecycle stage reached, derived from timestamps.

        ``failed`` is terminal *only* if delivery never happened; a later
        engagement event can never resurrect a failed send into "delivered".
        """
        if self.failed_at and not self.delivered_at:
            return "failed"
        stage_to_ts = {
            "converted": self.converted_at,
            "clicked": self.clicked_at,
            "read": self.read_at,
            "opened": self.opened_at,
            "delivered": self.delivered_at,
            "sent": self.sent_at,
            "queued": self.queued_at,
        }
        for stage in reversed(LIFECYCLE_ORDER):
            if stage_to_ts.get(stage):
                return stage
        return "queued"


class AgentConversation(Base):
    """Persisted agent chat. ``history`` is the normalized turn list (see
    ``llm/provider.py``) so a conversation can be resumed across requests."""

    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # uuid4 hex
    history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CommunicationEvent(Base):
    """Append-only audit log of every callback received.

    ``event_id`` is supplied by the channel service and is globally unique;
    the UNIQUE constraint is what guarantees exactly-once processing even when
    the channel service retries or sends duplicates.
    """

    __tablename__ = "communication_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    communication_id: Mapped[int] = mapped_column(
        ForeignKey("communications.id"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    communication: Mapped["Communication"] = relationship(back_populates="events")
