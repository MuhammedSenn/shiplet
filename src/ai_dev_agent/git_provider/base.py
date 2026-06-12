"""Git provider abstraction and naming conventions.

The GitHub implementation lives in ``github.py``; the orchestrator depends only
on these Protocols so other providers can be added later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ai_dev_agent.models import PullRequestInfo


@dataclass
class PullRequestDraft:
    title: str
    body: str
    head_branch: str
    base_branch: str


class PullRequestApi(Protocol):
    def find_open_pr(self, repository_url: str, head_branch: str) -> PullRequestInfo | None: ...

    def create_pr(self, repository_url: str, draft: PullRequestDraft) -> PullRequestInfo: ...


class GitProvider(Protocol):
    def create_branch(self, workspace: Path, branch: str) -> None: ...

    def commit_all(self, workspace: Path, message: str) -> None: ...

    def push(self, workspace: Path, branch: str) -> None: ...

    def find_existing_pr(self, repository_url: str, head_branch: str) -> PullRequestInfo | None: ...

    def open_pull_request(
        self, repository_url: str, draft: PullRequestDraft
    ) -> PullRequestInfo: ...

    def ensure_pull_request(
        self, repository_url: str, draft: PullRequestDraft
    ) -> tuple[PullRequestInfo, bool]: ...


def build_branch_name(task_id: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-") or "change"
    return f"ai-agent/{task_id}-{slug}"


def build_commit_message(task_id: str, summary: str) -> str:
    return f"{task_id} {summary}"


def build_pr_title(task_id: str, title: str) -> str:
    return f"{task_id} {title}"
