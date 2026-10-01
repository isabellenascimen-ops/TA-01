"""
AgentState — o estado persistente central de UM agente (seção 8 da spec).

Princípio fundamental (seção 2): o agente nasce com identidade mínima:
    nome = inexistente          → name = None
    autodescrição = vazia       → self_description = ""
Nada aqui pode ter um default "de personalidade" — isso violaria a seção 3
("não programar uma personalidade fixa").

SelfModel, Belief, Preference, Goal e Relationship (identidade "rica",
seções 13-19) são deliberadamente adiados para uma fase posterior — a
Fase 1 só precisa do suficiente para o agente ter uma trajetória de
conversas, não uma identidade elaborada ainda.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentState(Base):
    __tablename__ = "agent_state"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Seção 2: identidade mínima. name é NULLable de propósito — "inexistente"
    # é um estado válido e distinto de string vazia.
    name: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    self_description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Optimistic locking (ADR de concorrência, risco técnico #4 da Fase 0):
    # toda escrita em AgentState incrementa version; escrita concorrente
    # com version desatualizada falha e deve ser re-tentada, nunca sobrescrita
    # silenciosamente.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentState id={self.agent_id} name={self.name!r}>"
