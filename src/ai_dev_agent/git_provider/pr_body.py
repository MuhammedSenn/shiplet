"""Render the Pull Request body from the externalized template."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"


def render_pr_body(
    *,
    summary: str,
    task_id: str,
    changes: Sequence[str],
    test_command: str,
    test_status: str,
    model: str,
    changed_files: Sequence[str],
) -> str:
    template = (_TEMPLATES_DIR / "pr_body.md").read_text(encoding="utf-8")
    changes_block = "\n".join(f"- {item}" for item in changes) or "- (none)"
    files_block = "\n".join(f"- {path}" for path in changed_files) or "- (none)"
    return (
        template.replace("{{SUMMARY}}", summary)
        .replace("{{TASK_ID}}", task_id)
        .replace("{{CHANGES}}", changes_block)
        .replace("{{TEST_COMMAND}}", test_command)
        .replace("{{TEST_STATUS}}", test_status)
        .replace("{{MODEL}}", model)
        .replace("{{CHANGED_FILES}}", files_block)
    )
