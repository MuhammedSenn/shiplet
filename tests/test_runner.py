import subprocess
import sys
from pathlib import Path

import pytest

from ai_dev_agent.errors import TestExecutionError
from ai_dev_agent.test_runner.runner import TestRunner


class FakeRunner:
    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        raise_timeout: bool = False,
        raise_not_found: bool = False,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.raise_timeout = raise_timeout
        self.raise_not_found = raise_not_found

    def __call__(
        self, args: list[str], cwd: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if self.raise_not_found:
            raise FileNotFoundError(args[0])
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(args, timeout, output=self.stdout, stderr=self.stderr)
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)


def test_passing_command(tmp_path: Path) -> None:
    runner = TestRunner(runner=FakeRunner(returncode=0, stdout="2 passed"))
    result = runner.run(tmp_path, "pytest")
    assert result.status == "passed"
    assert result.command == "pytest"
    assert "passed" in result.output


def test_failing_command_captures_output(tmp_path: Path) -> None:
    runner = TestRunner(runner=FakeRunner(returncode=1, stderr="1 failed: assert error"))
    result = runner.run(tmp_path, "pytest")
    assert result.status == "failed"
    assert "failed" in result.output


def test_timeout_reports_error(tmp_path: Path) -> None:
    runner = TestRunner(runner=FakeRunner(raise_timeout=True, stdout="partial"))
    result = runner.run(tmp_path, "pytest")
    assert result.status == "error"
    assert "timed out" in result.output


def test_command_not_found_raises(tmp_path: Path) -> None:
    runner = TestRunner(runner=FakeRunner(raise_not_found=True))
    with pytest.raises(TestExecutionError):
        runner.run(tmp_path, "nonexistent-tool")


def test_empty_command_raises(tmp_path: Path) -> None:
    with pytest.raises(TestExecutionError):
        TestRunner().run(tmp_path, "   ")


def test_real_subprocess_execution(tmp_path: Path) -> None:
    passing = TestRunner().run(tmp_path, f'{sys.executable} -c "import sys; sys.exit(0)"')
    failing = TestRunner().run(tmp_path, f'{sys.executable} -c "import sys; sys.exit(1)"')
    assert passing.status == "passed"
    assert failing.status == "failed"
