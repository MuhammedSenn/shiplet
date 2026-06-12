"""Detect secrets so sensitive content is never sent to the model."""

from __future__ import annotations

import re
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"gh[ps]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"""(?i)(?:api[_-]?key|secret|password|token)\s*[:=]\s*["'][^"']{8,}["']"""),
]
_SENSITIVE_NAMES = {"credentials", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
_SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def is_sensitive_path(relative: Path) -> bool:
    name = relative.name.lower()
    if name.startswith(".env") or name in _SENSITIVE_NAMES:
        return True
    return relative.suffix.lower() in _SENSITIVE_SUFFIXES
