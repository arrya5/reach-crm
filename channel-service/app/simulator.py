"""Pure lifecycle simulation: given a communication, produce its events.

This is intentionally separated from the I/O (worker.py) so the probabilistic
model is easy to read, tweak, and test in isolation. Each event carries a
``delay`` (seconds after dispatch begins) and a unique ``event_id``; the worker
turns those into timed, signed callbacks.

We model realistic, channel-specific funnels:
  sent -> delivered | failed -> opened -> read -> clicked -> converted
SMS has no "opened/read" stage (no read receipts), so clicks follow delivery.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

# Per-channel conditional probabilities for advancing one funnel step.
CHANNEL_PROFILE = {
    "whatsapp": {"delivered": 0.95, "opened": 0.70, "read": 0.90, "clicked": 0.35, "converted": 0.22},
    "rcs":      {"delivered": 0.93, "opened": 0.65, "read": 0.85, "clicked": 0.30, "converted": 0.20},
    "email":    {"delivered": 0.97, "opened": 0.45, "read": 0.80, "clicked": 0.20, "converted": 0.12},
    "sms":      {"delivered": 0.98, "opened": 0.0,  "read": 0.0,  "clicked": 0.18, "converted": 0.10},
}
# Baseline gaps between stages (seconds); scaled by settings.speed at dispatch.
STAGE_GAP = {
    "sent": (0.3, 1.0),
    "delivered": (0.8, 2.0),
    "opened": (1.5, 4.0),
    "read": (0.5, 2.0),
    "clicked": (1.0, 3.0),
    "converted": (1.5, 4.0),
}
FAILURE_REASONS = ["invalid_number", "unsubscribed", "carrier_rejected", "mailbox_full"]


def _event(comm_id: int, etype: str, occurred_at: datetime, delay: float, payload: dict | None = None) -> dict:
    return {
        "event_id": uuid.uuid4().hex,
        "communication_id": comm_id,
        "event_type": etype,
        "occurred_at": occurred_at.isoformat(),
        "delay": delay,
        "payload": payload or {},
    }


def build_events(comm_id: int, channel: str) -> list[dict]:
    """Return the timed event sequence for one communication."""
    profile = CHANNEL_PROFILE.get(channel, CHANNEL_PROFILE["email"])
    now = datetime.now(timezone.utc)
    events: list[dict] = []
    t = 0.0
    occurred = now

    def advance(stage: str) -> None:
        nonlocal t, occurred
        lo, hi = STAGE_GAP[stage]
        t += random.uniform(lo, hi)
        occurred = now + timedelta(seconds=t)

    advance("sent")
    events.append(_event(comm_id, "sent", occurred, t))

    advance("delivered")
    if random.random() > profile["delivered"]:
        events.append(_event(comm_id, "failed", occurred, t,
                             {"reason": random.choice(FAILURE_REASONS)}))
        return events
    events.append(_event(comm_id, "delivered", occurred, t))

    # Engagement funnel — each stage is conditional on the previous.
    reached = "delivered"
    if profile["opened"] and random.random() < profile["opened"]:
        advance("opened")
        events.append(_event(comm_id, "opened", occurred, t))
        reached = "opened"
        if profile["read"] and random.random() < profile["read"]:
            advance("read")
            events.append(_event(comm_id, "read", occurred, t))
            reached = "read"

    # Clicks can follow the furthest engagement we reached (delivery for SMS).
    if reached != "delivered" or channel == "sms":
        if random.random() < profile["clicked"]:
            advance("clicked")
            events.append(_event(comm_id, "clicked", occurred, t))
            if random.random() < profile["converted"]:
                advance("converted")
                order_value = round(random.uniform(399, 2499), 2)
                events.append(_event(comm_id, "converted", occurred, t,
                                     {"order_value": order_value}))
    return events
