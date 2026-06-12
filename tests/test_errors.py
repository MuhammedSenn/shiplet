from ai_dev_agent.errors import AgentError, DuplicatePullRequestError, TaskParseError


def test_error_exposes_code_and_entry() -> None:
    error = TaskParseError("could not parse description")
    assert isinstance(error, AgentError)
    assert error.code == "task_parse_failed"

    entry = error.to_entry()
    assert entry["code"] == "task_parse_failed"
    assert entry["message"] == "could not parse description"
    assert entry["details"] == {}


def test_error_carries_details() -> None:
    error = DuplicatePullRequestError(
        "PR already exists", details={"url": "https://github.com/o/r/pull/1"}
    )
    assert error.to_entry()["details"] == {"url": "https://github.com/o/r/pull/1"}
