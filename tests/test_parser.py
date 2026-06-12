import pytest

from ai_dev_agent.ai.provider import LLMResult
from ai_dev_agent.errors import TaskParseError
from ai_dev_agent.input.parser import TaskParser
from ai_dev_agent.models import Task

DESCRIPTION = (
    "Repository: https://github.com/example-company/user-service\n"
    "Branch: develop\n\n"
    "Requirement:\n"
    "Add email validation to POST /users/register endpoint.\n\n"
    "Acceptance Criteria:\n"
    "- Invalid email returns HTTP 400\n"
    "- Error message should be Invalid email format\n"
    "- Add or update unit tests"
)


def make_task(description: str = DESCRIPTION) -> Task:
    return Task(task_id="TASK-123", title="Add email validation", description=description)


class FakeLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0
        self.model = "fake-model"

    def complete(self, *, system: str, user: str) -> LLMResult:
        self.calls += 1
        return LLMResult(text=self.text)


def test_rule_based_extracts_all_fields() -> None:
    parsed = TaskParser().parse(make_task())
    assert parsed.task_id == "TASK-123"
    assert parsed.repository_url == "https://github.com/example-company/user-service"
    assert parsed.base_branch == "develop"
    assert "email validation" in parsed.requirement.lower()
    assert parsed.acceptance_criteria == [
        "Invalid email returns HTTP 400",
        "Error message should be Invalid email format",
        "Add or update unit tests",
    ]


def test_ai_fallback_used_when_rules_fail() -> None:
    fake = FakeLLM(
        '{"repositoryUrl": "https://github.com/o/r", "baseBranch": "main", '
        '"requirement": "do x", "acceptanceCriteria": ["a"]}'
    )
    parsed = TaskParser(llm=fake).parse(make_task(description="free text, no markers"))
    assert fake.calls == 1
    assert parsed.repository_url == "https://github.com/o/r"
    assert parsed.task_id == "TASK-123"


def test_ai_not_called_when_rules_succeed() -> None:
    fake = FakeLLM("{}")
    TaskParser(llm=fake).parse(make_task())
    assert fake.calls == 0


def test_missing_fields_without_llm_raises() -> None:
    with pytest.raises(TaskParseError):
        TaskParser().parse(make_task(description="nothing structured here"))
