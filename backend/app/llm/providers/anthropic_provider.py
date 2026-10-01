"""
AnthropicProvider — implementação real de LLMProvider via SDK oficial.

Esta é a ÚNICA classe do projeto que importa o SDK da Anthropic. Se um
dia o agente precisar trocar de fornecedor de LLM, este é o único arquivo
que muda — o restante do sistema depende apenas de app/llm/base.py.
"""
from __future__ import annotations

from anthropic import AsyncAnthropic

from app.llm.base import LLMMessage, LLMResponse

MAX_TOKENS_DEFAULT = 1024


class AnthropicProvider:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, *, system: str, messages: list[LLMMessage]) -> LLMResponse:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS_DEFAULT,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return LLMResponse(text="\n".join(text_parts), raw=response.model_dump())
