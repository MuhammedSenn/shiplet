"""Domain models shared across the pipeline.

Attributes use snake_case in Python and serialize to camelCase JSON to match
the task and report schemas in the challenge document.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ReportStatus = Literal["success", "tests_failed", "failed"]
StepStatus = Literal["ok", "failed", "skipped"]
TestStatus = Literal["passed", "failed", "error"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Task(CamelModel):
    task_id: str
    title: str
    description: str


class ParsedTask(CamelModel):
    task_id: str
    repository_url: str
    base_branch: str
    requirement: str
    acceptance_criteria: list[str] = Field(default_factory=list)


class RepoAnalysis(CamelModel):
    language: str
    test_command: str
    framework: str | None = None
    build_tool: str | None = None
    relevant_files: list[str] = Field(default_factory=list)
    existing_test_files: list[str] = Field(default_factory=list)


class TestResult(CamelModel):
    status: TestStatus
    command: str
    duration_ms: int
    output: str = ""


class AIUsage(CamelModel):
    model: str
    changed_files: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class PullRequestInfo(CamelModel):
    url: str
    branch: str
    number: int | None = None


class StepResult(CamelModel):
    step: str
    status: StepStatus
    duration_ms: int = 0
    error: dict[str, object] | None = None


class ExecutionReport(CamelModel):
    trace_id: str
    task_id: str
    status: ReportStatus
    timeline: list[StepResult] = Field(default_factory=list)
    analysis: RepoAnalysis | None = None
    ai: AIUsage | None = None
    test: TestResult | None = None
    pr: PullRequestInfo | None = None
    errors: list[dict[str, object]] = Field(default_factory=list)
