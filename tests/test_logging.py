from ai_dev_agent.observability.logging import mask_secrets, new_trace_id, redact


def test_redact_masks_github_token() -> None:
    token = "github_pat_" + "A" * 30
    masked = redact(f"using {token} now")
    assert token not in masked
    assert "***REDACTED***" in masked


def test_redact_masks_openai_key() -> None:
    key = "sk-" + "b" * 40
    assert key not in redact(key)


def test_mask_secrets_processor_redacts_values() -> None:
    event = {"event": "clone", "token": "ghp_" + "c" * 30}
    result = mask_secrets(None, "info", event)  # type: ignore[arg-type]
    assert "ghp_" not in result["token"]


def test_new_trace_id_is_unique() -> None:
    assert new_trace_id() != new_trace_id()
