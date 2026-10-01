"""
Episode — unidade de memória episódica (seção 9 da spec).

Toda linha carrega origem rastreável (source_type/source_id/confidence) e
status epistêmico (observed/reported/inferred/hypothesized/unknown) — isso
não é opcional no schema, é a aplicação direta de ADR-008
(ARCHITECTURE_DECISIONS.md): o sistema nunca deve poder salvar uma
afirmação do LLM como fato sem marcar de onde ela veio (seção 179/180).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base


class MemoryStatus(str, enum.Enum):
    OBSERVED = "observed"
    REPORTED = "reported"
    INFERRED = "inferred"
    HYPOTHESIZED = "hypothesized"
    UNKNOWN = "unknown"


class SourceType(str, enum.Enum):
    USER_STATEMENT = "user_statement"
    EXTERNAL_SOURCE = "external_source"
    AGENT_INFERENCE = "agent_inference"
    SYSTEM_EVENT = "system_event"


class Episode(Base):
    __tablename__ = "episode"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_state.agent_id"), nullable=False, index=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 0.0 - 1.0. Sem default "mágico": quem grava o episódio decide a importância.
    importance: Mapped[float] = mapped_column(Float, nullable=False)

    participants: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    consequences: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )

    # Origem — seções 179/180. Nunca opcional.
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType, name="source_type"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[MemoryStatus] = mapped_column(
        SAEnum(MemoryStatus, name="memory_status"), nullable=False, default=MemoryStatus.UNKNOWN
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Episode id={self.id} event_type={self.event_type!r} importance={self.importance}>"
