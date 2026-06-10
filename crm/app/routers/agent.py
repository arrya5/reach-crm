"""Chat endpoint — the product's primary surface."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..llm.agent import run_agent
from ..schemas import ChatIn, ChatOut

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/health")
async def agent_health():
    """Lets the UI disable the chat gracefully when no LLM key is configured."""
    return {"llm_provider": settings.llm_provider, "configured": bool(settings.gemini_api_key)}


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, session: AsyncSession = Depends(get_session)):
    if not settings.gemini_api_key:
        raise HTTPException(
            503,
            "LLM not configured. Set GEMINI_API_KEY to enable the agent. "
            "(The dashboard works without it.)",
        )
    result = await run_agent(session, body.message, body.conversation_id)
    return ChatOut(**result)
