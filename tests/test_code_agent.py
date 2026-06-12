import json
from pathlib import Path

import pytest

from ai_dev_agent.ai.code_agent import CodeAgent
from ai_dev_agent.ai.provider import LLMResult
from ai_dev_agent.errors import InsufficientChangeError, ScopeViolationError
from ai_dev_agent.models import ParsedTask, RepoAnalysis


class FakeLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.model = "fake-model"

    def complete(self, *, system: str, user: str) -> LLMResult:
        return LLMResult(text=self.text, input_tokens=10, output_tokens=20)


def make_repo(root: Path) -> Path:
    (root / "app.py").write_text("def register(email):\n    return True\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text(
        "def test_register():\n    assert True\n", encoding="utf-8"
    )
    return root


def make_parsed(criteria: list[str] | None = None) -> ParsedTask:
    return ParsedTask(
        task_id="TASK-1",
        repository_url="https://github.com/o/r",
        base_branch="main",
        requirement="Add email validation",
        acceptance_criteria=criteria or ["Invalid email returns error", "Add or update unit tests"],
    )


def make_analysis() -> RepoAnalysis:
    return RepoAnalysis(
        language="Python",
        test_command="pytest",
        relevant_files=["app.py", "tests/test_app.py"],
        existing_test_files=["tests/test_app.py"],
    )


def payload(edits: list[dict[str, str]], can_proceed: bool = True, reason: str = "") -> str:
    return json.dumps({"canProceed": can_proceed, "reason": reason, "summary": "x", "edits": edits})


VALIDATED_APP = (
    "def register(email):\n"
    "    if '@' not in email:\n"
    "        raise ValueError('invalid')\n"
    "    return True\n"
)


def test_applies_valid_edits(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    body = payload(
        [
            {"path": "app.py", "newContent": VALIDATED_APP},
            {"path": "tests/test_app.py", "newContent": "def test_invalid():\n    assert True\n"},
        ]
    )
    result = CodeAgent(FakeLLM(body)).generate(repo, make_parsed(), make_analysis())
    assert set(result.changed_files) == {"app.py", "tests/test_app.py"}
    assert "raise ValueError" in (repo / "app.py").read_text(encoding="utf-8")
    assert result.input_tokens == 10
    assert result.model == "fake-model"


def test_cannot_proceed_raises(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    with pytest.raises(InsufficientChangeError):
        CodeAgent(FakeLLM(payload([], can_proceed=False, reason="unclear"))).generate(
            repo, make_parsed(), make_analysis()
        )


def test_path_traversal_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    body = payload([{"path": "../evil.py", "newContent": "x = 1\n"}])
    with pytest.raises(ScopeViolationError):
        CodeAgent(FakeLLM(body)).generate(repo, make_parsed(criteria=["x"]), make_analysis())


def test_too_many_files_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    edits = [{"path": f"app{i}.py", "newContent": "x = 1\n"} for i in range(9)]
    with pytest.raises(ScopeViolationError):
        CodeAgent(FakeLLM(payload(edits)), max_changed_files=8).generate(
            repo, make_parsed(criteria=["x"]), make_analysis()
        )


def test_missing_required_test_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    body = payload([{"path": "app.py", "newContent": "def register(email):\n    return True\n"}])
    with pytest.raises(InsufficientChangeError):
        CodeAgent(FakeLLM(body)).generate(repo, make_parsed(), make_analysis())


def test_secret_in_generated_content_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    secret = "ghp_" + "a" * 30
    body = payload(
        [
            {"path": "app.py", "newContent": f"TOKEN = '{secret}'\n"},
            {"path": "tests/test_app.py", "newContent": "def test_x():\n    assert True\n"},
        ]
    )
    with pytest.raises(ScopeViolationError):
        CodeAgent(FakeLLM(body)).generate(repo, make_parsed(), make_analysis())


def test_python_syntax_error_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    body = payload(
        [
            {"path": "app.py", "newContent": "def broken(:\n"},
            {"path": "tests/test_app.py", "newContent": "def test_x():\n    assert True\n"},
        ]
    )
    with pytest.raises(InsufficientChangeError):
        CodeAgent(FakeLLM(body)).generate(repo, make_parsed(), make_analysis())
