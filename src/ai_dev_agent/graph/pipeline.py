"""LangGraph orchestration.

Thin nodes delegate to the existing components (parser, repo manager, analyzer,
code agent, test runner, git provider). The test-fix retry is a bounded
conditional cycle. Errors are captured into state (never swallowed), every step
is logged and timelined, and a report is always produced.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from ai_dev_agent.ai.code_agent import CodeAgent
from ai_dev_agent.ai.context import ContextBuilder
from ai_dev_agent.ai.openai_provider import openai_provider_from_settings
from ai_dev_agent.config import Settings
from ai_dev_agent.errors import AgentError, InsufficientChangeError
from ai_dev_agent.git_provider.base import (
    GitProvider,
    PullRequestDraft,
    build_branch_name,
    build_commit_message,
    build_pr_title,
)
from ai_dev_agent.git_provider.github import GitHubProvider
from ai_dev_agent.git_provider.pr_body import render_pr_body
from ai_dev_agent.graph.state import AgentState, RunOptions
from ai_dev_agent.input.parser import TaskParser
from ai_dev_agent.models import ExecutionReport, PullRequestInfo, StepResult, Task
from ai_dev_agent.observability.logging import (
    bind_trace_id,
    configure_logging,
    get_logger,
    new_trace_id,
)
from ai_dev_agent.observability.report import build_execution_report
from ai_dev_agent.repo.analyzer import RepoAnalyzer
from ai_dev_agent.repo.manager import RepoManager
from ai_dev_agent.test_runner.runner import TestRunner

NodeFn = Callable[[AgentState], dict[str, object]]
Approver = Callable[[AgentState], bool]


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        *,
        parser: TaskParser,
        repo_manager: RepoManager,
        analyzer: RepoAnalyzer,
        code_agent: CodeAgent,
        test_runner: TestRunner,
        git_provider: GitProvider,
        approver: Approver | None = None,
    ) -> None:
        self._settings = settings
        self._parser = parser
        self._repo_manager = repo_manager
        self._analyzer = analyzer
        self._code_agent = code_agent
        self._test_runner = test_runner
        self._git = git_provider
        self._approver = approver
        self._logger = get_logger("orchestrator")
        self._graph = self._build_graph()

    def run(self, task: Task, options: RunOptions | None = None) -> ExecutionReport:
        configure_logging(self._settings.log_level)
        opts = options or RunOptions(max_fix_attempts=self._settings.max_fix_attempts)
        trace_id = new_trace_id()
        bind_trace_id(trace_id)
        self._logger.info("task_received", task_id=task.task_id)
        initial: AgentState = {
            "trace_id": trace_id,
            "task": task,
            "options": opts,
            "attempt": 0,
            "timeline": [],
        }
        final = cast(AgentState, self._graph.invoke(initial))
        report = build_execution_report(final)
        self._logger.info("completed", status=report.status)
        return report

    def _build_graph(self) -> Any:
        builder: Any = StateGraph(AgentState)
        builder.add_node("parse", self._guard("parse", self._parse))
        builder.add_node("clone", self._guard("clone", self._clone))
        builder.add_node("analyze", self._guard("analyze", self._analyze))
        builder.add_node("generate", self._guard("generate", self._generate))
        builder.add_node("run_tests", self._guard("run_tests", self._run_tests))
        builder.add_node("fix", self._guard("fix", self._fix))
        builder.add_node("publish", self._publish)
        builder.add_edge(START, "parse")
        builder.add_edge("parse", "clone")
        builder.add_edge("clone", "analyze")
        builder.add_edge("analyze", "generate")
        builder.add_edge("generate", "run_tests")
        builder.add_conditional_edges(
            "run_tests", self._after_tests, {"fix": "fix", "publish": "publish"}
        )
        builder.add_edge("fix", "run_tests")
        builder.add_edge("publish", END)
        return builder.compile()

    def _guard(self, name: str, fn: NodeFn) -> NodeFn:
        def node(state: AgentState) -> dict[str, object]:
            if state.get("error"):
                return {}
            start = time.monotonic()
            try:
                update = fn(state)
            except InsufficientChangeError as exc:
                self._logger.info(name, code=exc.code, reason="no_change")
                return {
                    "error": exc.to_entry(),
                    "timeline": [StepResult(step=name, status="skipped", duration_ms=_ms(start))],
                }
            except AgentError as exc:
                self._logger.error(name, code=exc.code, error=exc.message)
                return {
                    "error": exc.to_entry(),
                    "timeline": [
                        StepResult(
                            step=name,
                            status="failed",
                            duration_ms=_ms(start),
                            error=exc.to_entry(),
                        )
                    ],
                }
            self._logger.info(name)
            update["timeline"] = [StepResult(step=name, status="ok", duration_ms=_ms(start))]
            return update

        return node

    def _parse(self, state: AgentState) -> dict[str, object]:
        return {"parsed": self._parser.parse(state["task"])}

    def _clone(self, state: AgentState) -> dict[str, object]:
        parsed = state["parsed"]
        workspace = self._repo_manager.prepare(
            parsed.repository_url, parsed.base_branch, state["trace_id"]
        )
        return {"workspace": workspace}

    def _analyze(self, state: AgentState) -> dict[str, object]:
        analysis = self._analyzer.analyze(state["workspace"], state["parsed"].requirement)
        return {"analysis": analysis}

    def _generate(self, state: AgentState) -> dict[str, object]:
        change = self._code_agent.generate(state["workspace"], state["parsed"], state["analysis"])
        return {"change": change}

    def _run_tests(self, state: AgentState) -> dict[str, object]:
        result = self._test_runner.run(state["workspace"], state["analysis"].test_command)
        return {"test_result": result}

    def _fix(self, state: AgentState) -> dict[str, object]:
        parsed = state["parsed"]
        failure = state["test_result"].output
        augmented = parsed.model_copy(
            update={
                "requirement": (
                    f"{parsed.requirement}\n\nThe previous change failed tests. "
                    f"Fix them.\nTest output:\n{failure}"
                )
            }
        )
        change = self._code_agent.generate(state["workspace"], augmented, state["analysis"])
        return {"change": change, "attempt": state["attempt"] + 1}

    def _after_tests(self, state: AgentState) -> str:
        if state.get("error"):
            return "publish"
        if state["test_result"].status == "passed":
            return "publish"
        if state["attempt"] < state["options"].max_fix_attempts:
            return "fix"
        return "publish"

    def _publish(self, state: AgentState) -> dict[str, object]:
        error = state.get("error")
        if error:
            if error.get("code") == "insufficient_change":
                return {"status": "no_change", "note": str(error.get("message", ""))}
            return {"status": "failed"}
        start = time.monotonic()
        passed = state["test_result"].status == "passed"
        status = "success" if passed else "tests_failed"
        options = state["options"]
        if options.dry_run or (options.fail_on_test and not passed):
            self._logger.info("publish_skipped", reason="dry_run_or_fail_on_test")
            return {"status": status}
        if options.require_approval and self._approver is not None and not self._approver(state):
            self._logger.info("publish_skipped", reason="approval_declined")
            return {"status": status}
        try:
            pr = self._open_pull_request(state, passed)
        except InsufficientChangeError as exc:
            self._logger.info("publish_skipped", reason="no_change")
            return {
                "status": "no_change",
                "note": exc.message,
                "timeline": [StepResult(step="publish", status="skipped", duration_ms=_ms(start))],
            }
        except AgentError as exc:
            self._logger.error("publish", code=exc.code, error=exc.message)
            return {
                "status": "failed",
                "error": exc.to_entry(),
                "timeline": [
                    StepResult(
                        step="publish",
                        status="failed",
                        duration_ms=_ms(start),
                        error=exc.to_entry(),
                    )
                ],
            }
        return {
            "status": status,
            "pr": pr,
            "timeline": [StepResult(step="publish", status="ok", duration_ms=_ms(start))],
        }

    def _open_pull_request(self, state: AgentState, passed: bool) -> PullRequestInfo:
        parsed = state["parsed"]
        change = state["change"]
        workspace = state["workspace"]
        test_result = state["test_result"]
        summary = state["task"].title.strip() or parsed.requirement
        branch = build_branch_name(parsed.task_id, summary)

        self._git.create_branch(workspace, branch)
        self._logger.info("branch_created", branch=branch)
        self._git.commit_all(
            workspace, build_commit_message(parsed.task_id, summary), change.changed_files
        )
        self._logger.info("commit_created")
        self._git.push(workspace, branch)

        title = build_pr_title(parsed.task_id, summary)
        if not passed:
            title = f"[Tests failing] {title}"
        body = render_pr_body(
            summary=summary,
            task_id=parsed.task_id,
            changes=parsed.acceptance_criteria or change.changed_files,
            test_command=test_result.command,
            test_status="Passed" if passed else "Failed",
            model=change.model,
            changed_files=change.changed_files,
            closes_issue=state["options"].issue_number,
        )
        draft = PullRequestDraft(
            title=title, body=body, head_branch=branch, base_branch=parsed.base_branch
        )
        pr, created = self._git.ensure_pull_request(parsed.repository_url, draft)
        self._logger.info("pr_opened", url=pr.url, created=created)
        return pr


def build_default_orchestrator(
    settings: Settings, approver: Approver | None = None
) -> Orchestrator:
    provider = openai_provider_from_settings(settings)
    return Orchestrator(
        settings,
        parser=TaskParser(llm=provider),
        repo_manager=RepoManager(settings),
        analyzer=RepoAnalyzer(top_n=settings.context_top_n_files),
        code_agent=CodeAgent(
            provider,
            ContextBuilder(token_budget=settings.context_token_budget),
            max_changed_files=settings.max_changed_files,
        ),
        test_runner=TestRunner(),
        git_provider=GitHubProvider(settings),
        approver=approver,
    )


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
