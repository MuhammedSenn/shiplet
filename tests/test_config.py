import pytest

from ai_dev_agent.config import Settings


def test_defaults_apply() -> None:
    settings = Settings(_env_file=None)
    assert settings.openai_model == "gpt-5.2"
    assert settings.max_fix_attempts == 2
    assert settings.repo_allowlist == []


def test_repo_allowlist_splits_csv() -> None:
    settings = Settings(
        _env_file=None,
        repo_allowlist="https://github.com/a/b, https://github.com/c/d",
    )
    assert settings.repo_allowlist == [
        "https://github.com/a/b",
        "https://github.com/c/d",
    ]


def test_is_repo_allowed_normalizes_url() -> None:
    settings = Settings(
        _env_file=None,
        repo_allowlist="https://github.com/example-org/sample-service",
    )
    assert settings.is_repo_allowed("https://github.com/example-org/sample-service.git")
    assert settings.is_repo_allowed("https://github.com/example-org/sample-service/")
    assert not settings.is_repo_allowed("https://github.com/other-org/other-repo")


def test_env_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_FIX_ATTEMPTS", "5")
    settings = Settings(_env_file=None)
    assert settings.max_fix_attempts == 5
