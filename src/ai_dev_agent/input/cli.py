"""CLI: run the task-to-PR pipeline from a JSON task, stdin, or a GitHub issue."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import typer
from github import Auth, Github
from pyfiglet import figlet_format
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ai_dev_agent.config import get_settings
from ai_dev_agent.graph.pipeline import build_default_orchestrator
from ai_dev_agent.graph.state import AgentState, RunOptions
from ai_dev_agent.models import ExecutionReport, Task
from ai_dev_agent.observability.logging import new_trace_id
from ai_dev_agent.repo.analyzer import RepoAnalyzer
from ai_dev_agent.repo.manager import RepoManager

app = typer.Typer(
    add_completion=False,
    help="Shiplet: an AI development agent that turns a task into a reviewed PR.",
)
_console = Console()

_STATUS_STYLE = {
    "success": "green",
    "tests_failed": "yellow",
    "failed": "red",
    "no_change": "cyan",
}


@app.callback()
def main() -> None:
    """Shiplet - AI development agent."""


@app.command()
def run(
    task: str = typer.Option(
        ..., "--task", help="Path to a task JSON file, or '-' to read from stdin."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run everything except push and PR."),
    fail_on_test: bool = typer.Option(
        False, "--fail-on-test", help="Do not open a PR if tests fail."
    ),
    review: bool = typer.Option(
        False, "--review", help="Show the change and confirm before opening a PR."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Also print the raw execution report as JSON."
    ),
) -> None:
    _print_banner()
    raw = sys.stdin.read() if task == "-" else Path(task).read_text(encoding="utf-8")
    task_obj = Task.model_validate(json.loads(raw))
    report = _execute(task_obj, _options(dry_run, fail_on_test, review), review)
    _print_summary(report)
    if json_output:
        typer.echo(report.model_dump_json(by_alias=True, indent=2))


@app.command()
def issue(
    repo: str = typer.Option(..., "--repo", help="Repository URL (must be allowlisted)."),
    number: int = typer.Option(..., "--number", help="Issue number to resolve."),
    branch: str = typer.Option(
        "", "--branch", help="Base branch (default: the repository's default branch)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run everything except push and PR."),
    fail_on_test: bool = typer.Option(
        False, "--fail-on-test", help="Do not open a PR if tests fail."
    ),
    review: bool = typer.Option(
        False, "--review", help="Show the change and confirm before opening a PR."
    ),
) -> None:
    _print_banner()
    settings = get_settings()
    owner_repo = urlparse(repo).path.strip("/").removesuffix(".git")
    client = Github(base_url=settings.github_api_url, auth=Auth.Token(settings.github_token))
    repository = client.get_repo(owner_repo)
    gh_issue = repository.get_issue(number)
    base = branch or repository.default_branch
    description = f"Repository: {repo}\nBranch: {base}\n\n{gh_issue.body or ''}"
    task = Task(task_id=str(number), title=gh_issue.title, description=description)
    report = _execute(task, _options(dry_run, fail_on_test, review, issue_number=number), review)
    _print_summary(report)


@app.command()
def analyze(
    repo: str = typer.Option(..., "--repo", help="Repository URL (must be allowlisted)."),
    branch: str = typer.Option("main", "--branch", help="Base branch to analyze."),
    requirement: str = typer.Option(
        "", "--requirement", help="Optional requirement used to rank the relevant files."
    ),
) -> None:
    _print_banner()
    settings = get_settings()
    manager = RepoManager(settings)
    trace_id = new_trace_id()
    try:
        workspace = manager.prepare(repo, branch, trace_id)
        analysis = RepoAnalyzer(top_n=settings.context_top_n_files).analyze(workspace, requirement)
        _console.print(
            Panel(
                analysis.model_dump_json(by_alias=True, indent=2),
                title="Repository Analysis",
                border_style="cyan",
            )
        )
    finally:
        manager.cleanup(trace_id)


def _options(
    dry_run: bool, fail_on_test: bool, review: bool, issue_number: int | None = None
) -> RunOptions:
    return RunOptions(
        dry_run=dry_run,
        fail_on_test=fail_on_test,
        require_approval=review,
        max_fix_attempts=get_settings().max_fix_attempts,
        issue_number=issue_number,
    )


def _execute(task: Task, options: RunOptions, review: bool) -> ExecutionReport:
    approver = _interactive_approver if review else None
    orchestrator = build_default_orchestrator(get_settings(), approver=approver)
    return orchestrator.run(task, options)


def _interactive_approver(state: AgentState) -> bool:
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(state["workspace"]),
            "--no-pager",
            "diff",
            "--",
            *state["change"].changed_files,
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    _console.print(
        Panel(diff.strip() or "(no diff)", title="Proposed change", border_style="yellow")
    )
    return typer.confirm("Apply this change and open a Pull Request?")


def _print_banner() -> None:
    art = figlet_format("Shiplet", font="slant").rstrip("\n")
    _console.print(Text(art, style="bold cyan"))
    _console.print(Text("AI Development Agent", style="dim cyan"))
    _console.print()


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
        cost = f"  [dim](${report.ai.cost_usd:.4f})[/dim]" if report.ai.cost_usd else ""
        lines.append(
            f"[bold]Model:[/bold] {report.ai.model}"
            f"  [dim]{report.ai.input_tokens}+{report.ai.output_tokens} tokens[/dim]{cost}"
        )
        lines.append(f"[bold]Changed files:[/bold] {', '.join(report.ai.changed_files) or '-'}")
    if report.pr is not None:
        lines.append(f"[bold]Pull Request:[/bold] {report.pr.url}")
    if report.note:
        lines.append(f"[bold]Note:[/bold] {report.note}")
    if report.errors:
        lines.append(f"[bold red]Error:[/bold red] {report.errors[0].get('message', '')}")
    _console.print(Panel("\n".join(lines), title="Execution Report", border_style=style))


if __name__ == "__main__":
    app()
