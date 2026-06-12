"""Loader for externalized prompt files.

Prompts live as named files under the repository's ``prompts/`` directory, never
inline in code. This module only reads and returns them.
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
