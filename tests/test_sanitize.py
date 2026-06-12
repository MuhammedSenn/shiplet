from pathlib import Path

import pytest

from ai_dev_agent.security.sanitize import (
    is_within,
    safe_subprocess_env,
    validate_branch_name,
    validate_repo_url,
)


def test_validate_repo_url_accepts_github() -> None:
    assert validate_repo_url("https://github.com/o/r") == "https://github.com/o/r"
    assert validate_repo_url("https://github.com/o/r.git").endswith(".git")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "ftp://github.com/o/r",
        "https://github.com/o",
        "git@github.com:o/r.git",
        "https://github.com/o/r; rm -rf /",
    ],
)
def test_validate_repo_url_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_repo_url(bad)


def test_validate_branch_name_accepts() -> None:
    assert validate_branch_name("develop") == "develop"
    assert validate_branch_name("feature/email-1") == "feature/email-1"


@pytest.mark.parametrize("bad", ["", "-x", "a b", "a;b", "a$(x)", "a&&b"])
def test_validate_branch_name_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_branch_name(bad)


def test_is_within(tmp_path: Path) -> None:
    assert is_within(tmp_path, tmp_path / "a" / "b")
    assert not is_within(tmp_path, tmp_path / ".." / "evil")


def test_safe_subprocess_env_drops_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    monkeypatch.setenv("DB_PASSWORD", "secret-pw")
    monkeypatch.setenv("PATH", "/usr/bin")

    env = safe_subprocess_env()

    assert "GITHUB_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert "DB_PASSWORD" not in env
    assert env.get("PATH") == "/usr/bin"
