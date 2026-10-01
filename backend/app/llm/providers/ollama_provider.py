from __future__ import annotations

import re

import httpx

from app.llm.base import LLMMessage, LLMResponse


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        think: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.think = think

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        return re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL,
        ).strip()

    async def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
    ) -> LLMResponse:

        formatted_messages: list[dict[str, str]] = []

        if system:
            formatted_messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        for message in messages:
            formatted_messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
            "think": self.think,
        }

        url = f"{self.base_url}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                )

                print("=== OLLAMA STATUS ===")
                print(response.status_code)
                print("=== OLLAMA RESPONSE ===")
                print(response.text)
                print("=== END OLLAMA RESPONSE ===")

                response.raise_for_status()

                data = response.json()

        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Erro ao comunicar com Ollama em {url}: {exc}"
            ) from exc

        raw_content = data.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )

        final_content = self._strip_think_tags(
            raw_content
        )

        return LLMResponse(
            text=final_content,
            raw=data,
        )