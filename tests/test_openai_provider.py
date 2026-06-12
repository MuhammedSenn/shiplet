from types import SimpleNamespace
from typing import Any

from ai_dev_agent.ai.openai_provider import OpenAIProvider


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs = kwargs
        message = SimpleNamespace(content=self._content)
        usage = SimpleNamespace(prompt_tokens=11, completion_tokens=22)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def test_provider_maps_response_to_result() -> None:
    client = FakeClient('{"canProceed": true}')
    provider = OpenAIProvider(model="gpt-5.2", client=client)  # type: ignore[arg-type]

    result = provider.complete(system="s", user="u")

    assert result.text == '{"canProceed": true}'
    assert result.input_tokens == 11
    assert result.output_tokens == 22
    assert client.chat.completions.kwargs["model"] == "gpt-5.2"
