from __future__ import annotations

from app.config import settings
from app.llm.base import LLMProvider
from app.llm.providers.local_stub_provider import LocalStubProvider


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "local_stub":
        return LocalStubProvider()

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError(
                "llm_provider='anthropic' requer ANTHROPIC_API_KEY configurada."
            )

        # import tardio: evita exigir o SDK da Anthropic quando não é usado
        from app.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )

    if settings.llm_provider == "ollama":
        from app.llm.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            think=settings.ollama_think,
        )

    raise ValueError(f"LLMProvider desconhecido: {settings.llm_provider!r}")