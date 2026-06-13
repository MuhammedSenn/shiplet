"""Shared state and run options for the orchestration graph."""

from __future__ import annotations

from dataclasses import dataclass
from operator import add
from pathlib import Path
from typing import Annotated, TypedDict

from ai_dev_agent.ai.code_agent import CodeChangeResult
from ai_dev_agent.models import (
    ParsedTask,
    PullRequestInfo,
    RepoAnalysis,
    StepResult,
    Task,
    TestResult,
)


@dataclass
class RunOptions:
    dry_run: bool = False
    fail_on_test: bool = False
    require_approval: bool = False
    max_fix_attempts: int = 2
    issue_number: int | None = None


class AgentState(TypedDict, total=False):
    trace_id: str
    task: Task
    options: RunOptions
    attempt: int
    parsed: ParsedTask
    workspace: Path
    analysis: RepoAnalysis
    change: CodeChangeResult
    test_result: TestResult
    pr: PullRequestInfo
    status: str
    note: str
    error: dict[str, object]
    timeline: Annotated[list[StepResult], add]
    ai_input_tokens: Annotated[int, add]
    ai_output_tokens: Annotated[int, add]
