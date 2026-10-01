"""
EmbeddingProvider — abstração para geração de vetores de memória semântica.

Nota de arquitetura (extensão à Fase 0, registrar como ADR-013 quando o
ARCHITECTURE_DECISIONS.md for atualizado): a spec pede pgvector, mas não
diz de onde vêm os vetores. A Anthropic (LLMProvider) não oferece uma API
de embeddings — logo EmbeddingProvider é uma interface SEPARADA de
LLMProvider. Isso é uma aplicação direta do princípio da seção 6
("não acoplar o agente a um único fornecedor") a um segundo eixo: o
fornecedor de embeddings pode ser trocado sem tocar no fornecedor de LLM,
e vice-versa.

Duas implementações nesta fase:
- LocalHashEmbeddingProvider: determinístico, sem rede, sem custo. Usado
  em desenvolvimento/testes. NÃO captura similaridade semântica real —
  serve para exercitar o pipeline (armazenar, recuperar, ordenar por
  score), não para produzir recuperação semanticamente boa.
- VoyageEmbeddingProvider: implementação real via Voyage AI (parceiro
  recomendado pela Anthropic para embeddings). Requer VOYAGE_API_KEY e
  acesso de rede — não exercitado nos testes automatizados deste
  ambiente por não haver acesso à API nesta sandbox de desenvolvimento.
"""
from __future__ import annotations

import hashlib
from typing import Protocol


class EmbeddingProvider(Protocol):
    dimension: int

    async def embed(self, text: str) -> list[float]: ...


class LocalHashEmbeddingProvider:
    """
    Embedding determinístico baseado em hashing de n-gramas de palavras.

    Não é um substituto para um modelo de embedding real — é uma feature
    hashing trick clássica (semelhante ao HashingVectorizer do scikit-learn)
    que garante: mesmo texto → mesmo vetor, textos com palavras em comum →
    alguma sobreposição de dimensões ativas. Suficiente para testar o
    pipeline de recuperação híbrida de ponta a ponta sem rede e sem GPU.
    """

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    async def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        tokens = text.lower().split()
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class VoyageEmbeddingProvider:
    """Implementação real via Voyage AI. Ver docs: https://docs.voyageai.com"""

    def __init__(self, api_key: str, model: str = "voyage-3-lite", dimension: int = 512):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def embed(self, text: str) -> list[float]:
        try:
            import voyageai  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pacote 'voyageai' não instalado. Adicione a requirements.txt "
                "para usar VoyageEmbeddingProvider em produção."
            ) from exc
        client = voyageai.AsyncClient(api_key=self.api_key)
        result = await client.embed([text], model=self.model, input_type="document")
        return result.embeddings[0]


def get_embedding_provider(name: str, *, dimension: int, voyage_api_key: str | None = None) -> EmbeddingProvider:
    if name == "local_hash":
        return LocalHashEmbeddingProvider(dimension=dimension)
    if name == "voyage":
        if not voyage_api_key:
            raise ValueError("embedding_provider='voyage' requer VOYAGE_API_KEY configurada.")
        return VoyageEmbeddingProvider(api_key=voyage_api_key, dimension=dimension)
    raise ValueError(f"EmbeddingProvider desconhecido: {name!r}")
