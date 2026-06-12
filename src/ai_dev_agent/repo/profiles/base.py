"""Language profile Protocol and shared file-scanning helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

from ai_dev_agent.models import RepoAnalysis

_IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


class LanguageProfile(Protocol):
    name: str

    def detect(self, repo_path: Path) -> bool: ...

    def analyze(self, repo_path: Path, requirement: str, top_n: int) -> RepoAnalysis: ...


def iter_files(repo_path: Path, suffixes: frozenset[str]) -> Iterator[Path]:
    for path in repo_path.rglob("*"):
        if path.is_dir() or path.suffix not in suffixes:
            continue
        relative = path.relative_to(repo_path)
        if any(part in _IGNORE_DIRS for part in relative.parts):
            continue
        yield relative


def keywords(requirement: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", requirement.lower()) if len(word) > 3}


def rank_files(files: Iterable[Path], requirement: str, top_n: int) -> list[str]:
    terms = keywords(requirement)
    scored = []
    for relative in files:
        text = str(relative).lower()
        score = sum(1 for term in terms if term in text)
        scored.append((score, str(relative)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, path in scored[:top_n]]
