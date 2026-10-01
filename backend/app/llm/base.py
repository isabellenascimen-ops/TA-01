"""
LLMProvider — interface que desacopla o núcleo do agente de um fornecedor
específico de modelo de linguagem (seção 6 da spec):

    "O modelo de linguagem pode ser substituído sem destruir a trajetória
    do agente."

Nenhum módulo de app/agent/ deve importar um SDK de LLM diretamente — tudo
passa por esta interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: dict | None = None  # payload bruto do provedor, para depuração/auditoria


class LLMProvider(Protocol):
    async def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
    ) -> LLMResponse: ...
