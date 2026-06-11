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
    return {"llm_provider": settings.llm_provider, "configured": settings.llm_configured}


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, session: AsyncSession = Depends(get_session)):
    if not settings.llm_configured:
        raise HTTPException(
            503,
            f"LLM not configured. Set the API key for provider '{settings.llm_provider}' "
            "to enable the agent. (The dashboard works without it.)",
        )
    try:
        result = await run_agent(session, body.message, body.conversation_id)
    except Exception as exc:  # TEMP diagnostic: surface the real error
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"agent error: {type(exc).__name__}: {exc}")
    return ChatOut(**result)
