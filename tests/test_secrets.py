from pathlib import Path

from ai_dev_agent.security.secrets import contains_secret, is_sensitive_path


def test_contains_secret_detects_tokens_and_keys() -> None:
    assert contains_secret("token = ghp_" + "a" * 30)
    assert contains_secret("key: sk-" + "b" * 40)
    assert contains_secret("-----BEGIN RSA PRIVATE KEY-----")
    assert contains_secret('api_key = "supersecretvalue123"')


def test_contains_secret_ignores_normal_code() -> None:
    assert not contains_secret("def add(a, b):\n    return a + b\n")


def test_is_sensitive_path() -> None:
    assert is_sensitive_path(Path(".env"))
    assert is_sensitive_path(Path("config/.env.local"))
    assert is_sensitive_path(Path("certs/server.pem"))
    assert is_sensitive_path(Path("id_rsa"))
    assert not is_sensitive_path(Path("src/app.py"))
