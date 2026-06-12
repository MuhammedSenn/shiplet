"""LLM provider abstraction.

The concrete OpenAI implementation lives in PLAN-04; consumers depend only on
this Protocol so the model layer stays swappable and testable with a fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(Protocol):
    model: str

    def complete(self, *, system: str, user: str) -> LLMResult: ...
