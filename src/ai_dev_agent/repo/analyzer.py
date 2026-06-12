"""Detect the project language and produce a ``RepoAnalysis``.

Profiles are tried in order; the first that matches wins. Adding a language is
adding a profile to the registry.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ai_dev_agent.errors import AnalysisError
from ai_dev_agent.models import RepoAnalysis
from ai_dev_agent.repo.profiles.base import LanguageProfile
from ai_dev_agent.repo.profiles.node import NodeProfile
from ai_dev_agent.repo.profiles.python import PythonProfile


def default_profiles() -> list[LanguageProfile]:
    return [PythonProfile(), NodeProfile()]


class RepoAnalyzer:
    def __init__(self, top_n: int = 12, profiles: Sequence[LanguageProfile] | None = None) -> None:
        self._top_n = top_n
        self._profiles = list(profiles) if profiles is not None else default_profiles()

    def analyze(self, repo_path: Path, requirement: str) -> RepoAnalysis:
        for profile in self._profiles:
            if profile.detect(repo_path):
                return profile.analyze(repo_path, requirement, self._top_n)
        raise AnalysisError(
            "could not detect a supported language",
            details={"path": str(repo_path)},
        )
