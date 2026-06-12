"""CLI entry point: run the full task-to-PR pipeline with a formatted summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from ai_dev_agent.config import get_settings
from ai_dev_agent.graph.pipeline import build_default_orchestrator
from ai_dev_agent.graph.state import RunOptions
from ai_dev_agent.models import ExecutionReport, Task

app = typer.Typer(add_completion=False, help="AI Development Agent")
_console = Console()

_STATUS_STYLE = {"success": "green", "tests_failed": "yellow", "failed": "red"}


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
    json_output: bool = typer.Option(
        False, "--json", help="Also print the raw execution report as JSON."
    ),
) -> None:
    _console.print(
        Panel.fit(
            "[bold cyan]AI Development Agent[/bold cyan]\n"
            "[dim]Turning a task into a Pull Request[/dim]",
            border_style="cyan",
        )
    )
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
    _print_summary(report)
    if json_output:
        typer.echo(report.model_dump_json(by_alias=True, indent=2))


def _print_summary(report: ExecutionReport) -> None:
    style = _STATUS_STYLE.get(report.status, "white")
    lines = [
        f"[bold]Status:[/bold] [{style}]{report.status}[/{style}]",
        f"[bold]Task:[/bold] {report.task_id}",
    ]
    if report.analysis is not None:
        lines.append(
            f"[bold]Language:[/bold] {report.analysis.language}"
            f"  [dim]({report.analysis.test_command})[/dim]"
        )
    if report.test is not None:
        lines.append(f"[bold]Tests:[/bold] {report.test.status}")
    if report.ai is not None:
        lines.append(
            f"[bold]Model:[/bold] {report.ai.model}"
            f"  [dim]{report.ai.input_tokens}+{report.ai.output_tokens} tokens[/dim]"
        )
        lines.append(f"[bold]Changed files:[/bold] {', '.join(report.ai.changed_files) or '-'}")
    if report.pr is not None:
        lines.append(f"[bold]Pull Request:[/bold] {report.pr.url}")
    if report.errors:
        lines.append(f"[bold red]Error:[/bold red] {report.errors[0].get('message', '')}")
    _console.print(Panel("\n".join(lines), title="Execution Report", border_style=style))


if __name__ == "__main__":
    app()
