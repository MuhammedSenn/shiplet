"""GitHub provider: local git via subprocess, PRs via the GitHub API.

Local git runs with list args and ``shell=False``. The clone origin already
carries the token (set by RepoManager), so push uses it without re-logging it.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from github import Auth, Github

from ai_dev_agent.config import Settings
from ai_dev_agent.errors import AuthorizationError, GitPushError, InsufficientChangeError
from ai_dev_agent.git_provider.base import PullRequestApi, PullRequestDraft
from ai_dev_agent.models import PullRequestInfo
from ai_dev_agent.observability.logging import redact

GitRunner = Callable[[list[str], Path], "subprocess.CompletedProcess[str]"]


def _default_git_runner(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _owner_repo(repository_url: str) -> str:
    path = urlparse(repository_url).path.strip("/")
    return path[:-4] if path.endswith(".git") else path


def _is_auth_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered for token in ("403", "401", "permission", "denied", "authentication")
    )


class PyGithubApi:
    def __init__(self, token: str, api_url: str) -> None:
        self._github = Github(base_url=api_url, auth=Auth.Token(token))

    def find_open_pr(self, repository_url: str, head_branch: str) -> PullRequestInfo | None:
        repo = self._github.get_repo(_owner_repo(repository_url))
        owner = _owner_repo(repository_url).split("/")[0]
        for pull in repo.get_pulls(state="open", head=f"{owner}:{head_branch}"):
            return PullRequestInfo(url=pull.html_url, branch=head_branch, number=pull.number)
        return None

    def create_pr(self, repository_url: str, draft: PullRequestDraft) -> PullRequestInfo:
        repo = self._github.get_repo(_owner_repo(repository_url))
        pull = repo.create_pull(
            title=draft.title,
            body=draft.body,
            head=draft.head_branch,
            base=draft.base_branch,
        )
        return PullRequestInfo(url=pull.html_url, branch=draft.head_branch, number=pull.number)


class GitHubProvider:
    def __init__(
        self,
        settings: Settings,
        git_runner: GitRunner | None = None,
        pr_api: PullRequestApi | None = None,
    ) -> None:
        self._settings = settings
        self._run = git_runner or _default_git_runner
        self._pr_api = pr_api

    def create_branch(self, workspace: Path, branch: str) -> None:
        self._git(["checkout", "-b", branch], workspace, "failed to create branch")

    def commit_all(self, workspace: Path, message: str) -> None:
        self._git(["add", "-A"], workspace, "failed to stage changes")
        result = self._run(
            [
                "-c",
                f"user.name={self._settings.agent_git_name}",
                "-c",
                f"user.email={self._settings.agent_git_email}",
                "commit",
                "-m",
                message,
            ],
            workspace,
        )
        if result.returncode != 0:
            if "nothing to commit" in (result.stdout + result.stderr).lower():
                raise InsufficientChangeError("no changes to commit")
            raise GitPushError("git commit failed", details={"stderr": redact(result.stderr)})

    def push(self, workspace: Path, branch: str) -> None:
        result = self._run(["push", "origin", branch], workspace)
        if result.returncode != 0:
            stderr = redact(result.stderr)
            if _is_auth_error(stderr):
                raise AuthorizationError("git push was not authorized", details={"stderr": stderr})
            raise GitPushError("git push failed", details={"stderr": stderr})

    def find_existing_pr(self, repository_url: str, head_branch: str) -> PullRequestInfo | None:
        return self._api().find_open_pr(repository_url, head_branch)

    def open_pull_request(self, repository_url: str, draft: PullRequestDraft) -> PullRequestInfo:
        return self._api().create_pr(repository_url, draft)

    def ensure_pull_request(
        self, repository_url: str, draft: PullRequestDraft
    ) -> tuple[PullRequestInfo, bool]:
        existing = self.find_existing_pr(repository_url, draft.head_branch)
        if existing is not None:
            return existing, False
        return self.open_pull_request(repository_url, draft), True

    def _api(self) -> PullRequestApi:
        if self._pr_api is None:
            self._pr_api = PyGithubApi(self._settings.github_token, self._settings.github_api_url)
        return self._pr_api

    def _git(self, args: list[str], workspace: Path, error_message: str) -> None:
        result = self._run(args, workspace)
        if result.returncode != 0:
            raise GitPushError(error_message, details={"stderr": redact(result.stderr)})
