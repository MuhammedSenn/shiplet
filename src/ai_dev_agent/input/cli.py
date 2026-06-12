"""CLI entry point: run the full task-to-PR pipeline and print the report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ai_dev_agent.config import get_settings
from ai_dev_agent.graph.pipeline import build_default_orchestrator
from ai_dev_agent.graph.state import RunOptions
from ai_dev_agent.models import Task

app = typer.Typer(add_completion=False, help="AI Development Agent")


@app.callback()
def main() -> None:
    """AI Development Agent."""


@app.command()
def run(
    task: str = typer.Option(
        ..., "--task", help="Path to a task JSON file, or '-' to read from stdin."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run everything except push and PR."),
    fail_on_test: bool = typer.Option(
        False, "--fail-on-test", help="Do not open a PR if tests fail."
    ),
) -> None:
    raw = sys.stdin.read() if task == "-" else Path(task).read_text(encoding="utf-8")
    task_obj = Task.model_validate(json.loads(raw))
    settings = get_settings()
    orchestrator = build_default_orchestrator(settings)
    options = RunOptions(
        dry_run=dry_run,
        fail_on_test=fail_on_test,
        max_fix_attempts=settings.max_fix_attempts,
    )
    report = orchestrator.run(task_obj, options)
    typer.echo(report.model_dump_json(by_alias=True, indent=2))


if __name__ == "__main__":
    app()
