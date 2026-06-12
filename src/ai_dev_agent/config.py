"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"
    github_token: str = ""
    github_api_url: str = "https://api.github.com"
    repo_allowlist: Annotated[list[str], NoDecode] = Field(default_factory=list)
    workspace_root: Path = Path("./workspaces")
    max_fix_attempts: int = 2
    context_token_budget: int = 60_000
    context_top_n_files: int = 12
    max_changed_files: int = 8
    log_level: str = "INFO"
    agent_git_name: str = "AI Development Agent"
    agent_git_email: str = "ai-agent@users.noreply.github.com"

    @field_validator("repo_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @staticmethod
    def _normalize(url: str) -> str:
        normalized = url.strip().rstrip("/")
        if normalized.endswith(".git"):
            normalized = normalized[:-4]
        return normalized.lower()

    def is_repo_allowed(self, repository_url: str) -> bool:
        target = self._normalize(repository_url)
        return any(self._normalize(entry) == target for entry in self.repo_allowlist)


@lru_cache
def get_settings() -> Settings:
    return Settings()
