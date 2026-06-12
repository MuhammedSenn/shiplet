"""REST API and GitHub Issue webhook that trigger the full pipeline."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from ai_dev_agent.config import get_settings
from ai_dev_agent.graph.pipeline import Orchestrator, build_default_orchestrator
from ai_dev_agent.graph.state import RunOptions
from ai_dev_agent.models import ExecutionReport, Task

app = FastAPI(title="AI Development Agent")


def get_orchestrator() -> Orchestrator:
    return build_default_orchestrator(get_settings())


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str | None = None


class GitHubRepository(BaseModel):
    html_url: str
    default_branch: str = "main"


class GitHubIssueEvent(BaseModel):
    issue: GitHubIssue
    repository: GitHubRepository | None = None


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
        description=_issue_description(event),
    )
    return orchestrator.run(task, RunOptions(issue_number=event.issue.number))


def _issue_description(event: GitHubIssueEvent) -> str:
    body = event.issue.body or ""
    if event.repository is not None and "repository:" not in body.lower():
        return (
            f"Repository: {event.repository.html_url}\n"
            f"Branch: {event.repository.default_branch}\n\n{body}"
        )
    return body
