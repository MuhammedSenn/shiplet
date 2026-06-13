import json
from pathlib import Path

import pytest

from ai_dev_agent.errors import AnalysisError
from ai_dev_agent.repo.analyzer import RepoAnalyzer


def make_python_repo(root: Path) -> Path:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi"]\n\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )
    (root / "src").mkdir()
    (root / "src" / "user_service.py").write_text("def register(): ...", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_user_service.py").write_text(
        "def test_register(): ...", encoding="utf-8"
    )
    return root


def test_python_profile_analysis(tmp_path: Path) -> None:
    repo = make_python_repo(tmp_path)
    analysis = RepoAnalyzer().analyze(repo, "Add email validation to the register endpoint")

    assert analysis.language == "Python"
    assert analysis.framework == "FastAPI"
    assert analysis.build_tool == "pip"
    assert analysis.test_command == "pytest"
    assert "tests/test_user_service.py" in analysis.existing_test_files
    assert any("user_service" in path for path in analysis.relevant_files)
    assert "pyproject.toml" in analysis.relevant_files


def test_node_profile_analysis(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"express": "^4"}, "scripts": {"test": "jest"}}),
        encoding="utf-8",
    )
    (tmp_path / "index.js").write_text("// app", encoding="utf-8")
    (tmp_path / "index.test.js").write_text("// test", encoding="utf-8")

    analysis = RepoAnalyzer().analyze(tmp_path, "add a registration route")

    assert analysis.language == "JavaScript"
    assert analysis.framework == "Express"
    assert analysis.test_command == "npm test"
    assert "index.test.js" in analysis.existing_test_files


def test_unknown_language_raises(tmp_path: Path) -> None:
    (tmp_path / "main.go").write_text("package main", encoding="utf-8")
    with pytest.raises(AnalysisError):
        RepoAnalyzer().analyze(tmp_path, "do something")
