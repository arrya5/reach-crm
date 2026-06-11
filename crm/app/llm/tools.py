"""Agent tools: the only ways the LLM can touch the CRM.

Each tool maps to an existing CRM service function. Note the audience filter is
passed as a JSON *string* (``filter_json``) which we strictly validate against
``FilterDSL`` server-side — the model proposes, Pydantic disposes. Invalid
filters return an error the agent can read and correct, never raw SQL.

Crucially, there is **no ``launch`` tool**. The agent can only stage a campaign
(``draft``); a human must click "Approve & Launch" in the UI. Human-in-the-loop
by construction.
"""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Campaign, CampaignStatus, Segment
from ..segmentation.dsl import FilterDSL, build_query, describe
from ..services.analytics import campaign_stats
from .provider import ToolSpec

_FILTER_HINT = (
    "A JSON object: {\"match\": \"all|any\", \"conditions\": [{\"field\", \"op\", \"value\"}]}. "
    "Pick the operator that matches the field:\n"
    "- category: use 'eq' (one) or 'in' (list). Values: lipstick, foundation, skincare, eyes, nails, fragrance.\n"
    "- city: 'eq' or 'in'.  gender: 'eq' or 'in' (female/male/other).\n"
    "- product: 'contains' (free-text product-name match).\n"
    "- numeric fields use gt/gte/lt/lte/eq with a NUMBER (not a string): "
    "signup_days_ago, last_order_days_ago, first_order_days_ago, total_spend, order_count, avg_order_value.\n"
    "Example: {\"match\":\"all\",\"conditions\":[{\"field\":\"category\",\"op\":\"in\",\"value\":[\"lipstick\"]},"
    "{\"field\":\"last_order_days_ago\",\"op\":\"gt\",\"value\":60}]}"
)

TOOL_SPECS = [
    ToolSpec(
        name="preview_audience",
        description="Estimate how many shoppers match an audience filter, with a few samples. "
                    "Use this to size an audience before creating it.",
        parameters={
            "type": "object",
            "properties": {"filter_json": {"type": "string", "description": _FILTER_HINT}},
            "required": ["filter_json"],
        },
    ),
    ToolSpec(
        name="create_segment",
        description="Persist an audience segment from a filter so a campaign can target it.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "filter_json": {"type": "string", "description": _FILTER_HINT},
            },
            "required": ["name", "filter_json"],
        },
    ),
    ToolSpec(
        name="stage_campaign",
        description="Create a DRAFT campaign (not sent). Provide channel and the message copy "
                    "you drafted. Personalization tokens allowed: {{name}}, {{city}}, {{last_item}}. "
                    "A human approves the launch afterwards.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "goal_text": {"type": "string"},
                "segment_id": {"type": "integer"},
                "channel": {"type": "string", "enum": ["whatsapp", "sms", "email", "rcs"]},
                "message_template": {"type": "string"},
            },
            "required": ["name", "segment_id", "channel", "message_template"],
        },
    ),
    ToolSpec(
        name="get_campaign_performance",
        description="Get the delivery/engagement funnel and attributed revenue for a campaign.",
        parameters={
            "type": "object",
            "properties": {"campaign_id": {"type": "integer"}},
            "required": ["campaign_id"],
        },
    ),
]


def _parse_filter(filter_json: str) -> FilterDSL:
    return FilterDSL.model_validate(json.loads(filter_json))


async def execute_tool(session: AsyncSession, name: str, args: dict) -> dict:
    """Run one tool call; always returns a JSON-serializable dict."""
    try:
        if name == "preview_audience":
            dsl = _parse_filter(args["filter_json"])
            query = build_query(dsl)
            count = await session.scalar(select(func.count()).select_from(query.subquery()))
            sample = list((await session.scalars(query.limit(5))).all())
            return {
                "description": describe(dsl),
                "estimated_count": count or 0,
                "sample": [{"name": c.name, "city": c.city} for c in sample],
            }

        if name == "create_segment":
            dsl = _parse_filter(args["filter_json"])
            count = await session.scalar(select(func.count()).select_from(build_query(dsl).subquery()))
            seg = Segment(
                name=args["name"], definition=dsl.model_dump(),
                created_via="agent", est_count=count or 0,
            )
            session.add(seg)
            await session.commit()
            await session.refresh(seg)
            return {"segment_id": seg.id, "name": seg.name, "estimated_count": seg.est_count}

        if name == "stage_campaign":
            seg = await session.get(Segment, int(args["segment_id"]))
            if seg is None:
                return {"error": f"segment {args['segment_id']} not found. Create it first."}
            camp = Campaign(
                name=args["name"], goal_text=args.get("goal_text", ""),
                segment_id=seg.id, channel=args["channel"],
                message_template=args["message_template"],
                status=CampaignStatus.draft.value,
            )
            session.add(camp)
            await session.commit()
            await session.refresh(camp)
            return {
                "campaign_id": camp.id, "status": "draft",
                "name": camp.name,
                "channel": camp.channel,
                "message_template": camp.message_template,
                "audience": seg.name,
                "estimated_recipients": seg.est_count,
                "note": "Staged as DRAFT. The marketer must click 'Approve & Launch' to send.",
            }

        if name == "get_campaign_performance":
            stats = await campaign_stats(session, int(args["campaign_id"]))
            return stats or {"error": "campaign not found"}

        return {"error": f"unknown tool {name}"}
    except Exception as exc:  # surfaced back to the agent so it can recover
        return {"error": f"{type(exc).__name__}: {exc}"}
