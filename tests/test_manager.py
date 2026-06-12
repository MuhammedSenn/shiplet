import subprocess
from pathlib import Path

import pytest

from ai_dev_agent.config import Settings
from ai_dev_agent.errors import (
    BranchNotFoundError,
    RepositoryCloneError,
    RepositoryNotAllowedError,
)
from ai_dev_agent.repo.manager import RepoManager

ALLOWED = "https://github.com/example-org/sample-service"


def make_settings(tmp_path: Path, token: str = "") -> Settings:
    return Settings(
        _env_file=None,
        repo_allowlist=ALLOWED,
        workspace_root=tmp_path / "ws",
        github_token=token,
    )


class FakeRunner:
    def __init__(self, codes: dict[str, int]) -> None:
        self.codes = codes
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(self, args: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, cwd))
        code = self.codes.get(args[0], 0)
        if args[0] == "clone" and code == 0:
            Path(args[-1]).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(args, code, stdout="", stderr="boom" if code else "")


def test_rejects_non_allowlisted_repo(tmp_path: Path) -> None:
    manager = RepoManager(make_settings(tmp_path), runner=FakeRunner({}))
    with pytest.raises(RepositoryNotAllowedError):
        manager.prepare("https://github.com/evil/repo", "main", "trace-1")


def test_rejects_malformed_url(tmp_path: Path) -> None:
    manager = RepoManager(make_settings(tmp_path), runner=FakeRunner({}))
    with pytest.raises(RepositoryCloneError):
        manager.prepare("not-a-url", "main", "trace-1")


def test_clone_and_checkout_success(tmp_path: Path) -> None:
    runner = FakeRunner({"clone": 0, "checkout": 0})
    token = "github_pat_" + "x" * 30
    manager = RepoManager(make_settings(tmp_path, token=token), runner=runner)

    workspace = manager.prepare(ALLOWED, "develop", "trace-1")

    assert workspace.exists()
    clone_args = runner.calls[0][0]
    assert "x-access-token" in clone_args[1]
    assert token in clone_args[1]


def test_clone_failure_raises(tmp_path: Path) -> None:
    manager = RepoManager(make_settings(tmp_path), runner=FakeRunner({"clone": 1}))
    with pytest.raises(RepositoryCloneError):
        manager.prepare(ALLOWED, "develop", "trace-1")


def test_branch_checkout_failure_raises(tmp_path: Path) -> None:
    runner = FakeRunner({"clone": 0, "checkout": 1})
    manager = RepoManager(make_settings(tmp_path), runner=runner)
    with pytest.raises(BranchNotFoundError):
        manager.prepare(ALLOWED, "missing", "trace-1")


def test_workspace_recreated_cleanly(tmp_path: Path) -> None:
    runner = FakeRunner({"clone": 0, "checkout": 0})
    manager = RepoManager(make_settings(tmp_path), runner=runner)

    workspace = manager.prepare(ALLOWED, "develop", "trace-1")
    (workspace / "stale.txt").write_text("old", encoding="utf-8")
    manager.prepare(ALLOWED, "develop", "trace-1")

    assert not (workspace / "stale.txt").exists()
