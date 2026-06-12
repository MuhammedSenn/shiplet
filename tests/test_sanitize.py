from pathlib import Path

import pytest

from ai_dev_agent.security.sanitize import (
    is_within,
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
