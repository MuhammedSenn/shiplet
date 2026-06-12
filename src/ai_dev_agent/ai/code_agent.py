"""Generate a scoped, validated code change with a real LLM.

The model returns whole-file rewrites as structured JSON. A validation gate runs
on the output regardless of what the model produced: paths must stay inside the
workspace and the analyzed scope, sensitive files are off-limits, the change is
size-bounded, required tests must be present, and Python must parse.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from ai_dev_agent.ai.context import ContextBuilder, RepoContext
from ai_dev_agent.ai.prompts import load_prompt
from ai_dev_agent.ai.provider import LLMProvider
from ai_dev_agent.errors import InsufficientChangeError, ScopeViolationError
from ai_dev_agent.models import ParsedTask, RepoAnalysis
from ai_dev_agent.security.sanitize import is_within
from ai_dev_agent.security.secrets import contains_secret, is_sensitive_path


@dataclass
class Edit:
    path: str
    new_content: str


@dataclass
class CodeChangeResult:
    changed_files: list[str]
    model: str
    input_tokens: int
    output_tokens: int


class CodeAgent:
    def __init__(
        self,
        llm: LLMProvider,
        context_builder: ContextBuilder | None = None,
        max_changed_files: int = 8,
    ) -> None:
        self._llm = llm
        self._context = context_builder or ContextBuilder()
        self._max_changed_files = max_changed_files

    def generate(
        self, repo_path: Path, parsed: ParsedTask, analysis: RepoAnalysis
    ) -> CodeChangeResult:
        context = self._context.build(repo_path, analysis)
        result = self._llm.complete(
            system=load_prompt("code_writer.system"),
            user=self._render_user(parsed, context),
        )
        edits = self._parse(result.text)
        self._validate(edits, parsed, context, repo_path)
        self._apply(edits, repo_path)
        return CodeChangeResult(
            changed_files=[edit.path for edit in edits],
            model=self._llm.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    def _parse(self, text: str) -> list[Edit]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InsufficientChangeError("model returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise InsufficientChangeError("model returned an unexpected payload")
        if not data.get("canProceed", True):
            raise InsufficientChangeError(
                str(data.get("reason") or "model reported it could not proceed")
            )
        raw_edits = data.get("edits") or []
        if not raw_edits:
            raise InsufficientChangeError("model produced no edits")
        edits: list[Edit] = []
        for item in raw_edits:
            if not isinstance(item, dict) or "path" not in item or "newContent" not in item:
                raise InsufficientChangeError("malformed edit in model output")
            edits.append(Edit(str(item["path"]), str(item["newContent"])))
        return edits

    def _validate(
        self,
        edits: list[Edit],
        parsed: ParsedTask,
        context: RepoContext,
        repo_path: Path,
    ) -> None:
        if len(edits) > self._max_changed_files:
            raise ScopeViolationError(
                f"too many changed files: {len(edits)} > {self._max_changed_files}"
            )
        for edit in edits:
            relative = Path(edit.path)
            if not is_within(repo_path, repo_path / relative):
                raise ScopeViolationError(f"edit path escapes the workspace: {edit.path}")
            if is_sensitive_path(relative):
                raise ScopeViolationError(f"edit targets a sensitive file: {edit.path}")
            if not self._is_allowed(relative, context, repo_path):
                raise ScopeViolationError(
                    f"edit targets a file outside the analyzed scope: {edit.path}"
                )
            if contains_secret(edit.new_content):
                raise ScopeViolationError(f"generated content for {edit.path} contains a secret")
            if relative.suffix == ".py":
                self._check_python_syntax(edit)
        if _requires_tests(parsed) and not any(_is_test_path(edit.path) for edit in edits):
            raise InsufficientChangeError(
                "acceptance criteria require tests but no test file was changed"
            )

    def _is_allowed(self, relative: Path, context: RepoContext, repo_path: Path) -> bool:
        if str(relative) in context.allowed_paths:
            return True
        return (repo_path / relative.parent).is_dir()

    def _check_python_syntax(self, edit: Edit) -> None:
        try:
            ast.parse(edit.new_content)
        except SyntaxError as exc:
            raise InsufficientChangeError(
                f"generated Python has a syntax error in {edit.path}"
            ) from exc

    def _apply(self, edits: list[Edit], repo_path: Path) -> None:
        for edit in edits:
            target = repo_path / edit.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(edit.new_content, encoding="utf-8")

    def _render_user(self, parsed: ParsedTask, context: RepoContext) -> str:
        template = load_prompt("code_writer.user")
        files_block = (
            "\n\n".join(f"=== {file.path} ===\n{file.content}" for file in context.files)
            or "(no file contents available)"
        )
        available = "\n".join(f"- {path}" for path in context.available_files) or "- (none)"
        criteria = (
            "\n".join(f"- {item}" for item in parsed.acceptance_criteria) or "- (none specified)"
        )
        return (
            template.replace("{{REQUIREMENT}}", parsed.requirement)
            .replace("{{ACCEPTANCE_CRITERIA}}", criteria)
            .replace("{{AVAILABLE_FILES}}", available)
            .replace("{{FILE_CONTENTS}}", files_block)
        )


def _requires_tests(parsed: ParsedTask) -> bool:
    blob = " ".join([parsed.requirement, *parsed.acceptance_criteria]).lower()
    return "test" in blob


def _is_test_path(path: str) -> bool:
    relative = Path(path)
    name = relative.name.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
        or "tests" in relative.parts
        or "__tests__" in relative.parts
    )
