"""Parse a raw task into a structured ``ParsedTask``.

Hybrid strategy: deterministic rule-based extraction first, with an optional LLM
fallback when the rules cannot find the required fields.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ai_dev_agent.ai.prompts import load_prompt
from ai_dev_agent.ai.provider import LLMProvider
from ai_dev_agent.errors import TaskParseError
from ai_dev_agent.models import ParsedTask, Task

_REPO_RE = re.compile(r"Repository:\s*(?P<url>\S+)", re.IGNORECASE)
_BRANCH_RE = re.compile(r"Branch:\s*(?P<branch>\S+)", re.IGNORECASE)


class TaskParser:
    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    def parse(self, task: Task) -> ParsedTask:
        parsed = self._rule_based(task)
        if parsed is not None:
            return parsed
        if self._llm is not None:
            parsed = self._ai_based(task)
            if parsed is not None:
                return parsed
        raise TaskParseError(
            "could not extract required fields (repository, branch, requirement)",
            details={"task_id": task.task_id},
        )

    def _rule_based(self, task: Task) -> ParsedTask | None:
        description = task.description
        repo = _REPO_RE.search(description)
        branch = _BRANCH_RE.search(description)
        requirement = _section(description, "Requirement", until="Acceptance Criteria")
        if repo is None or branch is None or requirement is None:
            return None
        return ParsedTask(
            task_id=task.task_id,
            repository_url=repo.group("url"),
            base_branch=branch.group("branch"),
            requirement=requirement,
            acceptance_criteria=_criteria(description),
        )

    def _ai_based(self, task: Task) -> ParsedTask | None:
        assert self._llm is not None
        result = self._llm.complete(system=load_prompt("task_parser.system"), user=task.description)
        try:
            payload = json.loads(result.text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        payload["taskId"] = task.task_id
        try:
            return ParsedTask.model_validate(payload)
        except ValidationError:
            return None


def _section(text: str, header: str, *, until: str | None) -> str | None:
    boundary = rf"(?=\n\s*{re.escape(until)}:|\Z)" if until else r"(?=\Z)"
    pattern = re.compile(rf"{re.escape(header)}:\s*(.*?){boundary}", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip() or None


def _criteria(text: str) -> list[str]:
    match = re.search(r"Acceptance Criteria:\s*(.*)\Z", text, re.IGNORECASE | re.DOTALL)
    if match is None:
        return []
    return [
        line.strip()[1:].strip()
        for line in match.group(1).splitlines()
        if line.strip().startswith("-")
    ]
