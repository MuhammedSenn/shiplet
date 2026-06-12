"""Clone the task repository into an isolated, per-task workspace.

Security: repository URLs are validated and allowlist-checked; git runs via
list-arg subprocess (no shell); the token-injected clone URL is never logged.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from ai_dev_agent.config import Settings
from ai_dev_agent.errors import (
    BranchNotFoundError,
    RepositoryCloneError,
    RepositoryNotAllowedError,
)
from ai_dev_agent.observability.logging import redact
from ai_dev_agent.security.sanitize import (
    safe_subprocess_env,
    validate_branch_name,
    validate_repo_url,
)

GitRunner = Callable[[list[str], Path | None], "subprocess.CompletedProcess[str]"]


def _default_runner(args: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=safe_subprocess_env(),
    )


class RepoManager:
    def __init__(self, settings: Settings, runner: GitRunner | None = None) -> None:
        self._settings = settings
        self._run = runner or _default_runner

    def prepare(self, repository_url: str, base_branch: str, trace_id: str) -> Path:
        url = self._validate(repository_url)
        branch = validate_branch_name(base_branch)
        workspace = self.workspace_for(trace_id)
        self._reset(workspace)
        self._clone(url, workspace)
        self._checkout(branch, workspace)
        return workspace

    def workspace_for(self, trace_id: str) -> Path:
        return self._settings.workspace_root / trace_id

    def cleanup(self, trace_id: str) -> None:
        shutil.rmtree(self.workspace_for(trace_id), ignore_errors=True)

    def _validate(self, repository_url: str) -> str:
        try:
            url = validate_repo_url(repository_url)
        except ValueError as exc:
            raise RepositoryCloneError(str(exc)) from exc
        if not self._settings.is_repo_allowed(url):
            raise RepositoryNotAllowedError(
                "repository is not in the allowlist", details={"url": url}
            )
        return url

    def _reset(self, workspace: Path) -> None:
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.parent.mkdir(parents=True, exist_ok=True)

    def _clone(self, url: str, workspace: Path) -> None:
        result = self._run(["clone", self._authed_url(url), str(workspace)], None)
        if result.returncode != 0:
            raise RepositoryCloneError(
                "git clone failed", details={"stderr": redact(result.stderr)}
            )

    def _checkout(self, branch: str, workspace: Path) -> None:
        result = self._run(["checkout", branch], workspace)
        if result.returncode != 0:
            raise BranchNotFoundError(
                f"base branch not found: {branch}",
                details={"stderr": redact(result.stderr)},
            )

    def _authed_url(self, url: str) -> str:
        token = self._settings.github_token
        if not token:
            return url
        parsed = urlparse(url)
        return f"https://x-access-token:{token}@{parsed.netloc}{parsed.path}"
