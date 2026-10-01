from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.deliberation import deliberate
from app.agent.state import AgentState
from app.database import get_session
from app.llm.factory import get_llm_provider
from app.memory.embeddings import get_embedding_provider
from app.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    text: str


class ChatMessageOut(BaseModel):
    trace_id: uuid.UUID
    chosen_action: str
    response_text: str | None
    resulting_episode_id: uuid.UUID | None


@router.post("/{agent_id}/message", response_model=ChatMessageOut)
async def send_message(
    agent_id: uuid.UUID,
    payload: ChatMessageIn,
    session: AsyncSession = Depends(get_session),
) -> ChatMessageOut:
    agent_state = await session.get(AgentState, agent_id)
    if agent_state is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    llm = get_llm_provider()
    embedder = get_embedding_provider(
        settings.embedding_provider, dimension=settings.embedding_dim
    )

    result = await deliberate(
        session,
        agent_state=agent_state,
        llm=llm,
        embedder=embedder,
        raw_input=payload.text,
    )
    await session.commit()

    return ChatMessageOut(
        trace_id=result.trace_id,
        chosen_action=result.chosen_action.value,
        response_text=result.response_text,
        resulting_episode_id=result.resulting_episode_id,
    )
