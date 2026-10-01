from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.database import get_session

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentStateOut(BaseModel):
    agent_id: uuid.UUID
    name: str | None
    self_description: str
    version: int

    model_config = {"from_attributes": True}


@router.post("", response_model=AgentStateOut, status_code=201)
async def create_agent(session: AsyncSession = Depends(get_session)) -> AgentState:
    """
    Cria um novo agente com identidade mínima (seção 2 da spec):
    name=None, self_description="". Nada além disso é assumido.
    """
    agent = AgentState()
    session.add(agent)
    await session.commit()
    return agent


@router.get("/{agent_id}", response_model=AgentStateOut)
async def get_agent(agent_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> AgentState:
    agent = await session.get(AgentState, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    return agent


@router.get("", response_model=list[AgentStateOut])
async def list_agents(session: AsyncSession = Depends(get_session)) -> list[AgentState]:
    result = await session.execute(select(AgentState))
    return list(result.scalars().all())
