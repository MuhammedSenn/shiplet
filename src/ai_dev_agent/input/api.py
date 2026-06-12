"""REST API and GitHub Issue webhook that trigger the full pipeline."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from ai_dev_agent.config import get_settings
from ai_dev_agent.graph.pipeline import Orchestrator, build_default_orchestrator
from ai_dev_agent.models import ExecutionReport, Task

app = FastAPI(title="AI Development Agent")


def get_orchestrator() -> Orchestrator:
    return build_default_orchestrator(get_settings())


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str | None = None


class GitHubIssueEvent(BaseModel):
    issue: GitHubIssue


@app.post("/api/tasks", response_model=ExecutionReport)
def create_task(
    task: Task, orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)]
) -> ExecutionReport:
    return orchestrator.run(task)


@app.post("/api/webhooks/github/issues", response_model=ExecutionReport)
def github_issue(
    event: GitHubIssueEvent,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> ExecutionReport:
    task = Task(
        task_id=str(event.issue.number),
        title=event.issue.title,
        description=event.issue.body or "",
    )
    return orchestrator.run(task)
