import tempfile
from pathlib import Path

from ai_dev_agent.ai.code_agent import CodeChangeResult
from ai_dev_agent.config import Settings
from ai_dev_agent.errors import RepositoryCloneError
from ai_dev_agent.git_provider.base import PullRequestDraft
from ai_dev_agent.graph.pipeline import Orchestrator
from ai_dev_agent.graph.state import RunOptions
from ai_dev_agent.models import ParsedTask, PullRequestInfo, RepoAnalysis, Task, TestResult

PARSED = ParsedTask(
    task_id="TASK-1",
    repository_url="https://github.com/o/r",
    base_branch="main",
    requirement="Add email validation",
    acceptance_criteria=["Invalid email returns 400", "Add or update unit tests"],
)
ANALYSIS = RepoAnalysis(
    language="Python",
    test_command="pytest",
    relevant_files=["app.py"],
    existing_test_files=["tests/test_app.py"],
)
TASK = Task(task_id="TASK-1", title="Add email validation", description="...")


def make_settings() -> Settings:
    return Settings(_env_file=None)


class FakeParser:
    def parse(self, task: Task) -> ParsedTask:
        return PARSED


class FakeRepoManager:
    def __init__(self) -> None:
        self.workspace = Path(tempfile.mkdtemp())

    def prepare(self, url: str, branch: str, trace_id: str) -> Path:
        return self.workspace


class FailingRepoManager:
    def prepare(self, url: str, branch: str, trace_id: str) -> Path:
        raise RepositoryCloneError("clone failed")


class FakeAnalyzer:
    def analyze(self, workspace: Path, requirement: str) -> RepoAnalysis:
        return ANALYSIS


class FakeCodeAgent:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self, workspace: Path, parsed: ParsedTask, analysis: RepoAnalysis
    ) -> CodeChangeResult:
        self.calls += 1
        return CodeChangeResult(
            changed_files=["app.py", "tests/test_app.py"],
            model="gpt-5.2",
            input_tokens=10,
            output_tokens=20,
        )


class FakeTestRunner:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = statuses
        self.index = 0

    def run(self, workspace: Path, command: str) -> TestResult:
        status = self.statuses[min(self.index, len(self.statuses) - 1)]
        self.index += 1
        return TestResult(status=status, command=command, duration_ms=1, output="output")


class FakeGitProvider:
    def __init__(self) -> None:
        self.pushed = False
        self.pr_calls = 0
        self.last_draft: PullRequestDraft | None = None

    def create_branch(self, workspace: Path, branch: str) -> None:
        pass

    def commit_all(self, workspace: Path, message: str) -> None:
        pass

    def push(self, workspace: Path, branch: str) -> None:
        self.pushed = True

    def find_existing_pr(self, repository_url: str, head_branch: str) -> PullRequestInfo | None:
        return None

    def open_pull_request(self, repository_url: str, draft: PullRequestDraft) -> PullRequestInfo:
        return PullRequestInfo(
            url="https://github.com/o/r/pull/1", branch=draft.head_branch, number=1
        )

    def ensure_pull_request(
        self, repository_url: str, draft: PullRequestDraft
    ) -> tuple[PullRequestInfo, bool]:
        self.pr_calls += 1
        self.last_draft = draft
        return (
            PullRequestInfo(
                url="https://github.com/o/r/pull/1", branch=draft.head_branch, number=1
            ),
            True,
        )


def make_orchestrator(
    test_statuses: list[str],
    *,
    repo_manager: object | None = None,
    code_agent: object | None = None,
    git: object | None = None,
    approver: object | None = None,
) -> Orchestrator:
    return Orchestrator(
        make_settings(),
        parser=FakeParser(),  # type: ignore[arg-type]
        repo_manager=repo_manager or FakeRepoManager(),  # type: ignore[arg-type]
        analyzer=FakeAnalyzer(),  # type: ignore[arg-type]
        code_agent=code_agent or FakeCodeAgent(),  # type: ignore[arg-type]
        test_runner=FakeTestRunner(test_statuses),  # type: ignore[arg-type]
        git_provider=git or FakeGitProvider(),  # type: ignore[arg-type]
        approver=approver,  # type: ignore[arg-type]
    )


def test_happy_path_opens_pr() -> None:
    git = FakeGitProvider()
    report = make_orchestrator(["passed"], git=git).run(TASK)
    assert report.status == "success"
    assert report.pr is not None
    assert report.pr.number == 1
    assert git.pr_calls == 1
    steps = [step.step for step in report.timeline]
    assert "parse" in steps and "publish" in steps


def test_test_fix_cycle_then_success() -> None:
    agent = FakeCodeAgent()
    report = make_orchestrator(["failed", "passed"], code_agent=agent).run(
        TASK, RunOptions(max_fix_attempts=2)
    )
    assert report.status == "success"
    assert agent.calls == 2


def test_max_attempts_publishes_with_warning() -> None:
    agent = FakeCodeAgent()
    git = FakeGitProvider()
    report = make_orchestrator(["failed", "failed", "failed"], code_agent=agent, git=git).run(
        TASK, RunOptions(max_fix_attempts=1)
    )
    assert report.status == "tests_failed"
    assert report.pr is not None
    assert agent.calls == 2


def test_issue_number_adds_closes_to_pr_body() -> None:
    git = FakeGitProvider()
    make_orchestrator(["passed"], git=git).run(TASK, RunOptions(issue_number=4))
    assert git.last_draft is not None
    assert "Closes #4" in git.last_draft.body


def test_dry_run_skips_pr() -> None:
    git = FakeGitProvider()
    report = make_orchestrator(["passed"], git=git).run(TASK, RunOptions(dry_run=True))
    assert report.status == "success"
    assert report.pr is None
    assert git.pushed is False


def test_fail_on_test_skips_pr() -> None:
    git = FakeGitProvider()
    report = make_orchestrator(["failed"], git=git).run(
        TASK, RunOptions(fail_on_test=True, max_fix_attempts=0)
    )
    assert report.status == "tests_failed"
    assert report.pr is None
    assert git.pushed is False


def test_clone_error_is_reported() -> None:
    report = make_orchestrator(["passed"], repo_manager=FailingRepoManager()).run(TASK)
    assert report.status == "failed"
    assert report.errors
    assert report.errors[0]["code"] == "repository_clone_failed"
    assert report.pr is None


def test_approval_declined_skips_pr() -> None:
    git = FakeGitProvider()
    report = make_orchestrator(["passed"], git=git, approver=lambda state: False).run(
        TASK, RunOptions(require_approval=True)
    )
    assert report.status == "success"
    assert report.pr is None
    assert git.pushed is False
