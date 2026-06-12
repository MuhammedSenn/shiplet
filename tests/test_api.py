from fastapi.testclient import TestClient

from ai_dev_agent.graph.state import RunOptions
from ai_dev_agent.input.api import app, get_orchestrator
from ai_dev_agent.models import ExecutionReport, Task


class FakeOrchestrator:
    def __init__(self, report: ExecutionReport) -> None:
        self.report = report
        self.last_task: Task | None = None

    def run(self, task: Task, options: RunOptions | None = None) -> ExecutionReport:
        self.last_task = task
        return self.report


def test_create_task_runs_pipeline() -> None:
    report = ExecutionReport(trace_id="t1", task_id="TASK-1", status="success")
    app.dependency_overrides[get_orchestrator] = lambda: FakeOrchestrator(report)
    client = TestClient(app)

    response = client.post(
        "/api/tasks",
        json={"taskId": "TASK-1", "title": "x", "description": "y"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["taskId"] == "TASK-1"


def test_github_issue_webhook_injects_repository_context() -> None:
    report = ExecutionReport(trace_id="t1", task_id="7", status="success")
    fake = FakeOrchestrator(report)
    app.dependency_overrides[get_orchestrator] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/api/webhooks/github/issues",
        json={
            "issue": {"number": 7, "title": "Add validation", "body": "Validate the input."},
            "repository": {
                "html_url": "https://github.com/o/r",
                "default_branch": "develop",
            },
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["taskId"] == "7"
    assert fake.last_task is not None
    assert "Repository: https://github.com/o/r" in fake.last_task.description
    assert "Branch: develop" in fake.last_task.description
