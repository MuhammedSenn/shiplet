import subprocess
from pathlib import Path

from ai_dev_agent.test_runner.docker_runner import DockerCommandRunner


class FakeProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self._result = (returncode, stdout, stderr)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        returncode, stdout, stderr = self._result
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def test_wraps_command_in_isolated_docker_run(tmp_path: Path) -> None:
    fake = FakeProcess(stdout="passed")
    result = DockerCommandRunner(process=fake)(["pytest", "-q"], tmp_path, 600)

    args = fake.calls[0]
    assert args[:3] == ["docker", "run", "--rm"]
    assert "--memory" in args and "--cpus" in args and "--pids-limit" in args
    assert "--network" in args
    assert f"{tmp_path.resolve()}:/work" in args
    assert "python:3.13-slim" in args
    script = args[-1]
    assert "pip install" in script and "pytest -q" in script
    assert result.returncode == 0


def test_infers_node_image_for_npm() -> None:
    fake = FakeProcess()
    DockerCommandRunner(process=fake)(["npm", "test"], Path("/x"), 600)
    assert "node:20-slim" in fake.calls[0]


def test_resource_limits_are_configurable() -> None:
    fake = FakeProcess()
    DockerCommandRunner(process=fake, memory="256m", cpus="2", pids_limit=128)(
        ["pytest"], Path("/x"), 600
    )
    args = fake.calls[0]
    assert "256m" in args and "2" in args and "128" in args


def test_exit_code_propagates_as_failure() -> None:
    fake = FakeProcess(returncode=1, stdout="1 failed")
    result = DockerCommandRunner(process=fake)(["pytest"], Path("/x"), 600)
    assert result.returncode == 1
