"""Run the target repository's tests and report a structured result.

The command runs with list args and ``shell=False`` inside the workspace, under a
timeout. Captured output keeps the tail (where failures surface) for the fixer.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from ai_dev_agent.errors import TestExecutionError
from ai_dev_agent.models import TestResult

CommandRunner = Callable[[list[str], Path, int], "subprocess.CompletedProcess[str]"]


def _default_runner(args: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )


class TestRunner:
    def __init__(
        self,
        timeout_seconds: int = 600,
        output_limit: int = 8000,
        runner: CommandRunner | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._output_limit = output_limit
        self._run = runner or _default_runner

    def run(self, workspace: Path, command: str) -> TestResult:
        args = shlex.split(command)
        if not args:
            raise TestExecutionError("empty test command")
        start = time.monotonic()
        try:
            completed = self._run(args, workspace, self._timeout)
        except FileNotFoundError as exc:
            raise TestExecutionError(f"test command not found: {args[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            captured = _coerce(exc.stdout) + _coerce(exc.stderr)
            return TestResult(
                status="error",
                command=command,
                duration_ms=_elapsed_ms(start),
                output=self._truncate(f"test run timed out after {self._timeout}s\n{captured}"),
            )
        return TestResult(
            status="passed" if completed.returncode == 0 else "failed",
            command=command,
            duration_ms=_elapsed_ms(start),
            output=self._truncate(completed.stdout + completed.stderr),
        )

    def _truncate(self, text: str) -> str:
        if len(text) <= self._output_limit:
            return text
        return "... (truncated)\n" + text[-self._output_limit :]


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _coerce(value: object) -> str:
    return value if isinstance(value, str) else ""
