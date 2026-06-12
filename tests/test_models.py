from ai_dev_agent.models import ExecutionReport, ParsedTask, StepResult


def test_parsed_task_serializes_camel_case() -> None:
    task = ParsedTask(
        task_id="TASK-1",
        repository_url="https://github.com/o/r",
        base_branch="develop",
        requirement="Add email validation",
        acceptance_criteria=["Invalid email returns HTTP 400"],
    )
    data = task.model_dump(by_alias=True)
    assert data["taskId"] == "TASK-1"
    assert data["repositoryUrl"] == "https://github.com/o/r"
    assert data["baseBranch"] == "develop"


def test_execution_report_round_trips() -> None:
    report = ExecutionReport(
        trace_id="trace-1",
        task_id="TASK-1",
        status="success",
        timeline=[StepResult(step="clone", status="ok", duration_ms=12)],
    )
    data = report.model_dump(by_alias=True)
    assert data["traceId"] == "trace-1"
    assert data["timeline"][0]["durationMs"] == 12

    restored = ExecutionReport.model_validate(data)
    assert restored.trace_id == "trace-1"
    assert restored.timeline[0].step == "clone"
