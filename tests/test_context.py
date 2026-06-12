from pathlib import Path

from ai_dev_agent.ai.context import ContextBuilder
from ai_dev_agent.models import RepoAnalysis


def make_analysis(relevant: list[str], tests: list[str] | None = None) -> RepoAnalysis:
    return RepoAnalysis(
        language="Python",
        test_command="pytest",
        relevant_files=relevant,
        existing_test_files=tests or [],
    )


def test_build_reads_relevant_files(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hi')", encoding="utf-8")
    context = ContextBuilder().build(tmp_path, make_analysis(["app.py"]))
    assert any(file.path == "app.py" for file in context.files)
    assert "app.py" in context.allowed_paths


def test_build_skips_secret_bearing_files(tmp_path: Path) -> None:
    (tmp_path / "settings.py").write_text("API_KEY = 'sk-" + "a" * 40 + "'", encoding="utf-8")
    context = ContextBuilder().build(tmp_path, make_analysis(["settings.py"]))
    assert context.files == []


def test_build_skips_sensitive_paths(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("X=1", encoding="utf-8")
    context = ContextBuilder().build(tmp_path, make_analysis([".env"]))
    assert context.files == []


def test_build_respects_token_budget(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x" * 1000, encoding="utf-8")
    (tmp_path / "b.py").write_text("y" * 1000, encoding="utf-8")
    context = ContextBuilder(token_budget=100).build(tmp_path, make_analysis(["a.py", "b.py"]))
    assert len(context.files) == 1
