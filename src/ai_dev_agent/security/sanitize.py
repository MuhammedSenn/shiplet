"""Input validation shared across the pipeline.

Guards against command injection (branch/URL fed to git), path traversal, and
unexpected URL shapes. These return cleaned values or raise ``ValueError``.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

_REPO_URL_RE = re.compile(r"^https://[A-Za-z0-9.\-]+/[A-Za-z0-9._\-]+/[A-Za-z0-9._\-]+/?$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._\-/]+$")


def validate_repo_url(url: str) -> str:
    candidate = url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"unsupported repository URL: {url!r}")
    if not _REPO_URL_RE.match(candidate):
        raise ValueError(f"malformed repository URL: {url!r}")
    return candidate


def validate_branch_name(name: str) -> str:
    candidate = name.strip()
    if not candidate or candidate.startswith("-") or not _BRANCH_RE.match(candidate):
        raise ValueError(f"invalid branch name: {name!r}")
    return candidate


def is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True
