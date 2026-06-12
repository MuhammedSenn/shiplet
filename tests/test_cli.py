import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_dev_agent.graph.state import RunOptions
from ai_dev_agent.input import cli
from ai_dev_agent.models import ExecutionReport, Task

runner = CliRunner()


class FakeOrchestrator:
    def __init__(self, report: ExecutionReport) -> None:
        self.report = report

    def run(self, task: Task, options: RunOptions | None = None) -> ExecutionReport:
        return self.report


def test_cli_runs_pipeline_and_prints_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = ExecutionReport(trace_id="t1", task_id="TASK-1", status="success")
    monkeypatch.setattr(
        cli, "build_default_orchestrator", lambda settings, approver=None: FakeOrchestrator(report)
    )

    task_file = tmp_path / "task.json"
    task_file.write_text(
        json.dumps({"taskId": "TASK-1", "title": "x", "description": "y"}), encoding="utf-8"
    )

    result = runner.invoke(cli.app, ["run", "--task", str(task_file)])
    assert result.exit_code == 0
    assert "success" in result.stdout
    assert "TASK-1" in result.stdout


def test_cli_json_flag_prints_raw_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = ExecutionReport(trace_id="t1", task_id="TASK-1", status="success")
    monkeypatch.setattr(
        cli, "build_default_orchestrator", lambda settings, approver=None: FakeOrchestrator(report)
    )

    task_file = tmp_path / "task.json"
    task_file.write_text(
        json.dumps({"taskId": "TASK-1", "title": "x", "description": "y"}), encoding="utf-8"
    )

    result = runner.invoke(cli.app, ["run", "--task", str(task_file), "--json"])
    assert result.exit_code == 0
    assert '"status": "success"' in result.stdout
