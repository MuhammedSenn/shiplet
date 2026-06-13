"""Run a test command inside a disposable Docker container (sandbox).

A cloned repository's test suite is third-party code. Running it directly on the
host exposes the host filesystem, network, and resources to untrusted code. This
runner executes the same command inside a throwaway container, so it is isolated
from the host: the workspace is the only shared path, CPU/memory/PID use is
capped, and the container is removed on exit.

It implements the ``CommandRunner`` callable the test runner already expects, so
it is a drop-in replacement selected by configuration; nothing else changes.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path

from ai_dev_agent.security.sanitize import safe_subprocess_env

DockerProcess = Callable[[list[str], int], "subprocess.CompletedProcess[str]"]

# Install the repository's own dependencies first so its tests can import it,
# then ensure the test runner is present. Each clause is best-effort; a repo may
# declare deps in pyproject.toml, requirements.txt, both, or neither.
_PY_SETUP = (
    "pip install -q --disable-pip-version-check -e . 2>/dev/null "
    "|| pip install -q --disable-pip-version-check -r requirements.txt 2>/dev/null || true; "
    "pip install -q --disable-pip-version-check pytest"
)
_PYTHON = ("python:3.13-slim", _PY_SETUP)
_NODE = ("node:20-slim", "npm install --no-audit --no-fund --silent")
_IMAGES: dict[str, tuple[str, str]] = {
    "pytest": _PYTHON,
    "python": _PYTHON,
    "npm": _NODE,
    "npx": _NODE,
    "node": _NODE,
    "yarn": _NODE,
    "pnpm": _NODE,
}
_DEFAULT_IMAGE = _PYTHON


def _default_process(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=safe_subprocess_env(),
    )


def docker_available(docker_bin: str = "docker") -> bool:
    """Return True only if the Docker CLI is installed and the daemon responds."""
    try:
        result = subprocess.run(
            [docker_bin, "info"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=safe_subprocess_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


class DockerCommandRunner:
    def __init__(
        self,
        *,
        memory: str = "512m",
        cpus: str = "1",
        pids_limit: int = 256,
        network: str = "bridge",
        docker_bin: str = "docker",
        process: DockerProcess | None = None,
    ) -> None:
        self._memory = memory
        self._cpus = cpus
        self._pids_limit = pids_limit
        self._network = network
        self._docker = docker_bin
        self._run = process or _default_process

    def __call__(
        self, args: list[str], cwd: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        image, setup = _IMAGES.get(args[0], _DEFAULT_IMAGE)
        script = f"{setup} && {shlex.join(args)}"
        docker_args = [
            self._docker,
            "run",
            "--rm",
            "--network",
            self._network,
            "--memory",
            self._memory,
            "--cpus",
            self._cpus,
            "--pids-limit",
            str(self._pids_limit),
            "-v",
            f"{cwd.resolve()}:/work",
            "-w",
            "/work",
            image,
            "sh",
            "-c",
            script,
        ]
        return self._run(docker_args, timeout)
