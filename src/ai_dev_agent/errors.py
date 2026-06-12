"""Typed error hierarchy mapped to the documented failure scenarios.

Every error carries a stable machine-readable ``code`` and serializes into a
report error entry so failures are never silently swallowed.
"""

from __future__ import annotations


class AgentError(Exception):
    code = "agent_error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_entry(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ConfigError(AgentError):
    code = "config_error"


class TaskParseError(AgentError):
    code = "task_parse_failed"


class RepositoryNotAllowedError(AgentError):
    code = "repository_not_allowed"


class RepositoryCloneError(AgentError):
    code = "repository_clone_failed"


class BranchNotFoundError(AgentError):
    code = "branch_not_found"


class AnalysisError(AgentError):
    code = "analysis_failed"


class InsufficientChangeError(AgentError):
    code = "insufficient_change"


class ScopeViolationError(AgentError):
    code = "scope_violation"


class TestExecutionError(AgentError):
    code = "test_execution_failed"


class GitPushError(AgentError):
    code = "git_push_failed"


class PullRequestError(AgentError):
    code = "pull_request_failed"


class DuplicatePullRequestError(AgentError):
    code = "duplicate_pull_request"


class AuthorizationError(AgentError):
    code = "authorization_failed"
