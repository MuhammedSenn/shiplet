import subprocess
from pathlib import Path

import pytest

from ai_dev_agent.config import Settings
from ai_dev_agent.errors import AuthorizationError, GitPushError, InsufficientChangeError
from ai_dev_agent.git_provider.base import (
    PullRequestDraft,
    build_branch_name,
    build_commit_message,
    build_pr_title,
)
from ai_dev_agent.git_provider.github import GitHubProvider
from ai_dev_agent.git_provider.pr_body import render_pr_body
from ai_dev_agent.models import PullRequestInfo


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        github_token="github_pat_" + "x" * 30,
        agent_git_name="AI Development Agent",
        agent_git_email="ai-agent@users.noreply.github.com",
    )


DRAFT = PullRequestDraft(
    title="TASK-1 Add validation",
    body="body",
    head_branch="ai-agent/TASK-1-add-validation",
    base_branch="develop",
)


class FakeGit:
    def __init__(self, overrides: dict[str, tuple[int, str, str]] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        key = next((k for k in ("checkout", "add", "commit", "push") if k in args), args[0])
        returncode, stdout, stderr = self.overrides.get(key, (0, "", ""))
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class FakePrApi:
    def __init__(self, existing: PullRequestInfo | None = None) -> None:
        self.existing = existing
        self.created = PullRequestInfo(url="https://github.com/o/r/pull/1", branch="b", number=1)
        self.create_calls = 0

    def find_open_pr(self, repository_url: str, head_branch: str) -> PullRequestInfo | None:
        return self.existing

    def create_pr(self, repository_url: str, draft: PullRequestDraft) -> PullRequestInfo:
        self.create_calls += 1
        return self.created


def test_branch_commit_push_use_expected_args(tmp_path: Path) -> None:
    git = FakeGit()
    provider = GitHubProvider(make_settings(), git_runner=git, pr_api=FakePrApi())
    provider.create_branch(tmp_path, "ai-agent/TASK-1-x")
    provider.commit_all(tmp_path, "TASK-1 do x")
    provider.push(tmp_path, "ai-agent/TASK-1-x")

    assert ["checkout", "-b", "ai-agent/TASK-1-x"] in git.calls
    assert any("push" in call and "origin" in call for call in git.calls)
    commit_call = next(call for call in git.calls if "commit" in call)
    assert any("user.name=AI Development Agent" in part for part in commit_call)


def test_commit_with_no_changes_raises(tmp_path: Path) -> None:
    git = FakeGit({"commit": (1, "", "nothing to commit, working tree clean")})
    provider = GitHubProvider(make_settings(), git_runner=git, pr_api=FakePrApi())
    with pytest.raises(InsufficientChangeError):
        provider.commit_all(tmp_path, "msg")


def test_push_failure_raises_git_push_error(tmp_path: Path) -> None:
    git = FakeGit({"push": (1, "", "fatal: unable to access")})
    provider = GitHubProvider(make_settings(), git_runner=git, pr_api=FakePrApi())
    with pytest.raises(GitPushError):
        provider.push(tmp_path, "b")


def test_push_permission_error_raises_authorization(tmp_path: Path) -> None:
    git = FakeGit({"push": (1, "", "remote: Permission to o/r denied. 403")})
    provider = GitHubProvider(make_settings(), git_runner=git, pr_api=FakePrApi())
    with pytest.raises(AuthorizationError):
        provider.push(tmp_path, "b")


def test_ensure_pull_request_creates_when_absent(tmp_path: Path) -> None:
    api = FakePrApi(existing=None)
    provider = GitHubProvider(make_settings(), git_runner=FakeGit(), pr_api=api)
    info, created = provider.ensure_pull_request("https://github.com/o/r", DRAFT)
    assert created is True
    assert api.create_calls == 1
    assert info.number == 1


def test_ensure_pull_request_skips_when_present(tmp_path: Path) -> None:
    existing = PullRequestInfo(url="https://github.com/o/r/pull/9", branch="b", number=9)
    api = FakePrApi(existing=existing)
    provider = GitHubProvider(make_settings(), git_runner=FakeGit(), pr_api=api)
    info, created = provider.ensure_pull_request("https://github.com/o/r", DRAFT)
    assert created is False
    assert info.number == 9
    assert api.create_calls == 0


def test_render_pr_body_has_required_sections() -> None:
    body = render_pr_body(
        summary="Added email validation",
        task_id="TASK-123",
        changes=["Added validation", "Added test"],
        test_command="pytest",
        test_status="Passed",
        model="gpt-5.2",
        changed_files=["app.py", "tests/test_app.py"],
    )
    for section in ("## Summary", "## Task", "## Changes", "## Test Result", "## AI Usage"):
        assert section in body
    assert "TASK-123" in body
    assert "Model: gpt-5.2" in body
    assert "AI Development Agent" in body
    assert "- app.py" in body


def test_render_pr_body_links_issue() -> None:
    body = render_pr_body(
        summary="s",
        task_id="4",
        changes=["x"],
        test_command="pytest",
        test_status="Passed",
        model="gpt-5.2",
        changed_files=["registration.py"],
        closes_issue=4,
    )
    assert "Closes #4" in body


def test_naming_helpers() -> None:
    assert build_branch_name("TASK-123", "Add email validation API") == (
        "ai-agent/TASK-123-add-email-validation-api"
    )
    assert build_commit_message("TASK-123", "Add email validation") == (
        "TASK-123 Add email validation"
    )
    assert build_pr_title("TASK-123", "Add email validation API") == (
        "TASK-123 Add email validation API"
    )
