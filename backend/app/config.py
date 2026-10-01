"""
Configuração central da aplicação.

Nenhum segredo tem valor default de produção — tudo vem de variáveis de
ambiente (ver .env.example). Isso evita acoplar o núcleo do agente a um
provedor específico "escondido" em código (seção 6 da especificação).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Banco de dados ---
    database_url: str = "postgresql+asyncpg://trajectory:trajectory_dev_pw@localhost:5432/trajectory_dev"

    # --- Provedor de LLM (ver app/llm/base.py) ---
    # "anthropic" (real) ou "local_stub" (determinístico, sem custo, usado em testes)
    llm_provider: str = "local_stub"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:8b"
    ollama_think: bool = False
    

    # --- Provedor de embeddings (ver app/memory/embeddings.py) ---
    # Deliberadamente desacoplado do LLMProvider: a Anthropic não oferece
    # embeddings, então o agente não pode depender do mesmo fornecedor para
    # as duas coisas (mesmo princípio da seção 6, aplicado a embeddings).
    embedding_provider: str = "local_hash"
    embedding_dim: int = 256

    # --- Orçamento computacional mínimo (preparação para a Fase de autonomia) ---
    max_llm_calls_per_deliberation: int = 3


settings = Settings()
