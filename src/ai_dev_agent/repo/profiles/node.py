"""Node.js language profile (jest / vitest / npm test)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_dev_agent.models import RepoAnalysis
from ai_dev_agent.repo.profiles.base import iter_files, rank_files

_SUFFIXES = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})
_FRAMEWORKS = {
    "@nestjs/core": "NestJS",
    "next": "Next.js",
    "express": "Express",
    "react": "React",
}


class NodeProfile:
    name = "Node.js"

    def detect(self, repo_path: Path) -> bool:
        return (repo_path / "package.json").exists()

    def analyze(self, repo_path: Path, requirement: str, top_n: int) -> RepoAnalysis:
        package = self._read_package(repo_path)
        files = list(iter_files(repo_path, _SUFFIXES))
        test_files = [str(path) for path in files if _is_test(path)]
        language = "TypeScript" if (repo_path / "tsconfig.json").exists() else "JavaScript"
        return RepoAnalysis(
            language=language,
            framework=self._framework(package),
            build_tool=self._build_tool(repo_path),
            test_command=self._test_command(package),
            relevant_files=rank_files(files, requirement, top_n),
            existing_test_files=test_files,
        )

    def _read_package(self, repo_path: Path) -> dict[str, Any]:
        try:
            data = json.loads((repo_path / "package.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _dependencies(self, package: dict[str, Any]) -> dict[str, Any]:
        return {**package.get("dependencies", {}), **package.get("devDependencies", {})}

    def _framework(self, package: dict[str, Any]) -> str | None:
        dependencies = self._dependencies(package)
        for key, label in _FRAMEWORKS.items():
            if key in dependencies:
                return label
        return None

    def _build_tool(self, repo_path: Path) -> str:
        if (repo_path / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (repo_path / "yarn.lock").exists():
            return "yarn"
        return "npm"

    def _test_command(self, package: dict[str, Any]) -> str:
        if "test" in package.get("scripts", {}):
            return "npm test"
        dependencies = self._dependencies(package)
        if "vitest" in dependencies:
            return "npx vitest run"
        if "jest" in dependencies:
            return "npx jest"
        return "npm test"


def _is_test(relative: Path) -> bool:
    name = relative.name
    return ".test." in name or ".spec." in name or "__tests__" in relative.parts
