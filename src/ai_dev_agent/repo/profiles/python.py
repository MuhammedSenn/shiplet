"""Python language profile (pytest / unittest)."""

from __future__ import annotations

from pathlib import Path

from ai_dev_agent.models import RepoAnalysis
from ai_dev_agent.repo.profiles.base import iter_files, rank_files

_MARKERS = ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")
_SUFFIXES = frozenset({".py"})
_FRAMEWORKS = {"fastapi": "FastAPI", "django": "Django", "flask": "Flask"}


class PythonProfile:
    name = "Python"

    def detect(self, repo_path: Path) -> bool:
        return any((repo_path / marker).exists() for marker in _MARKERS)

    def analyze(self, repo_path: Path, requirement: str, top_n: int) -> RepoAnalysis:
        files = list(iter_files(repo_path, _SUFFIXES))
        test_files = [str(path) for path in files if _is_test(path)]
        dependencies = self._dependency_text(repo_path)
        return RepoAnalysis(
            language=self.name,
            framework=self._framework(dependencies),
            build_tool=self._build_tool(repo_path),
            test_command=self._test_command(dependencies, test_files),
            relevant_files=rank_files(files, requirement, top_n),
            existing_test_files=test_files,
        )

    def _dependency_text(self, repo_path: Path) -> str:
        parts = []
        for marker in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"):
            path = repo_path / marker
            if path.exists():
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        return "\n".join(parts).lower()

    def _framework(self, dependencies: str) -> str | None:
        for key, label in _FRAMEWORKS.items():
            if key in dependencies:
                return label
        return None

    def _build_tool(self, repo_path: Path) -> str:
        if (repo_path / "uv.lock").exists():
            return "uv"
        if (repo_path / "poetry.lock").exists():
            return "poetry"
        return "pip"

    def _test_command(self, dependencies: str, test_files: list[str]) -> str:
        if "pytest" in dependencies or test_files:
            return "pytest"
        return "python -m unittest"


def _is_test(relative: Path) -> bool:
    name = relative.name
    return name.startswith("test_") or name.endswith("_test.py") or "tests" in relative.parts
