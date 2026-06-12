"""Real OpenAI implementation of the ``LLMProvider`` Protocol."""

from __future__ import annotations

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from ai_dev_agent.ai.provider import LLMResult
from ai_dev_agent.config import Settings


class OpenAIProvider:
    def __init__(
        self, api_key: str = "", model: str = "gpt-5.2", client: OpenAI | None = None
    ) -> None:
        self._client = client if client is not None else OpenAI(api_key=api_key)
        self.model = model

    def complete(self, *, system: str, user: str) -> LLMResult:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResult(
            text=content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


def openai_provider_from_settings(settings: Settings) -> OpenAIProvider:
    return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
