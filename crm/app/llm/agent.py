"""The agent orchestration loop.

Flow per user message:
  1. Load (or start) the conversation's normalized history.
  2. Append the user turn and run a bounded tool-use loop:
       model -> (tool calls?) -> execute -> feed results back -> repeat.
  3. Persist the updated history and return the final text + any structured
     artifacts (segments/campaigns the agent created) for the UI to render.

The loop is bounded (``MAX_STEPS``) to protect the free-tier quota and to make
runaway tool-calling impossible.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentConversation
from .provider import LLMProvider, ToolCall, Turn, get_provider
from .tools import TOOL_SPECS, execute_tool

MAX_STEPS = 6

SYSTEM_PROMPT = """\
You are Reach, the AI marketing copilot for SUGAR Cosmetics — a D2C beauty brand.
Your job: turn a marketer's natural-language goal into a ready-to-launch campaign.

How you work:
- Understand the goal, then PREVIEW an audience with preview_audience before committing.
- When the audience looks right, create_segment, then stage_campaign with copy you write.
- Draft on-brand, concise copy for the chosen channel. Use personalization tokens
  {{name}}, {{city}}, {{last_item}} where natural.
- Recommend a channel and briefly justify it (WhatsApp = rich/high-intent, SMS = urgent/short,
  Email = detailed/value, RCS = rich fallback).
- You only ever create DRAFT campaigns. Tell the marketer to review and click
  "Approve & Launch" — you never send messages yourself.
- Be concise. After staging, summarise: audience size, channel, and the drafted message.

Audience filter fields: city, gender, signup_days_ago, last_order_days_ago,
first_order_days_ago, total_spend, order_count, avg_order_value, category, product.
Operators: gt, gte, lt, lte, eq, in, contains. Categories: lipstick, foundation,
skincare, eyes, nails, fragrance.
"""


def _history_from_db(raw: list) -> list[Turn]:
    turns: list[Turn] = []
    for t in raw:
        turns.append(Turn(
            role=t["role"],
            text=t.get("text", ""),
            tool_calls=[ToolCall(**c) for c in t.get("tool_calls", [])],
            tool_name=t.get("tool_name", ""),
            tool_result=t.get("tool_result"),
        ))
    return turns


def _history_to_db(turns: list[Turn]) -> list:
    out = []
    for t in turns:
        out.append({
            "role": t.role,
            "text": t.text,
            "tool_calls": [{"name": c.name, "args": c.args} for c in t.tool_calls],
            "tool_name": t.tool_name,
            "tool_result": t.tool_result,
        })
    return out


async def run_agent(
    session: AsyncSession,
    message: str,
    conversation_id: str | None,
    provider: LLMProvider | None = None,
) -> dict:
    provider = provider or get_provider()

    convo = await session.get(AgentConversation, conversation_id) if conversation_id else None
    if convo is None:
        convo = AgentConversation(id=uuid.uuid4().hex, history=[])
        session.add(convo)

    history = _history_from_db(convo.history)
    history.append(Turn(role="user", text=message))

    actions: list[dict] = []     # structured artifacts for the UI
    final_text = ""

    for _ in range(MAX_STEPS):
        result = await provider.generate(SYSTEM_PROMPT, history, TOOL_SPECS)

        if not result.tool_calls:
            final_text = result.text
            history.append(Turn(role="model", text=result.text))
            break

        # Record the model's tool-call turn, then execute each call.
        history.append(Turn(role="model", text=result.text, tool_calls=result.tool_calls))
        for call in result.tool_calls:
            output = await execute_tool(session, call.name, call.args)
            actions.append({"tool": call.name, "args": call.args, "result": output})
            history.append(Turn(role="tool", tool_name=call.name, tool_result=output))
    else:
        final_text = final_text or "I've reached my step limit — please refine the request."

    convo.history = _history_to_db(history)
    await session.commit()

    return {"conversation_id": convo.id, "reply": final_text, "actions": actions}
