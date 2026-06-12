"""Build a bounded, secret-free repository context for the model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_dev_agent.models import RepoAnalysis
from ai_dev_agent.security.secrets import contains_secret, is_sensitive_path


@dataclass
class ContextFile:
    path: str
    content: str


@dataclass
class RepoContext:
    files: list[ContextFile] = field(default_factory=list)
    available_files: list[str] = field(default_factory=list)
    allowed_paths: set[str] = field(default_factory=set)
    token_estimate: int = 0


class ContextBuilder:
    def __init__(self, token_budget: int = 60_000, per_file_chars: int = 16_000) -> None:
        self._budget = token_budget
        self._per_file_chars = per_file_chars

    def build(self, repo_path: Path, analysis: RepoAnalysis) -> RepoContext:
        context = RepoContext()
        used = 0
        for relative_str in analysis.relevant_files:
            relative = Path(relative_str)
            if is_sensitive_path(relative):
                continue
            file_path = repo_path / relative
            if not file_path.is_file():
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if contains_secret(text):
                continue
            if len(text) > self._per_file_chars:
                text = text[: self._per_file_chars]
            context.files.append(ContextFile(str(relative), text))
            used += len(text) // 4
            if used >= self._budget:
                break
        context.token_estimate = used
        context.available_files = list(
            dict.fromkeys([*analysis.relevant_files, *analysis.existing_test_files])
        )
        context.allowed_paths = set(analysis.relevant_files) | set(analysis.existing_test_files)
        return context
