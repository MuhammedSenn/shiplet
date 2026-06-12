# Shiplet Agent

Shiplet Agent is an AI development agent that turns a development task (Jira / GitHub-Issue style) into a reviewed
Pull Request. It parses the task, clones the target repository into an isolated workspace, analyzes
it, applies the required change with a real LLM (and adds/updates tests), runs the tests, opens a
GitHub PR, and emits an execution report.

## Demo

A real end-to-end run against a Python demo repository (task: add email validation to user
registration) produced this Pull Request, including the AI-generated code change and an added
test, with all tests passing:
https://github.com/MuhammedSenn/demo-user-service-python/pull/1

## 1. Purpose

Take a task input, extract the repository / branch / requirement / acceptance criteria, clone the
repo, use a real AI model to make the scoped code change, run the tests, create a branch and
commit, open a Pull Request, and report the result. The system is built to be secure, observable,
and resilient: every failed step is a typed error with a report entry, and PRs are prepared for
human review.

## 2. Technology Stack

- Python 3.13, packaged with `uv` (`pyproject.toml`, src layout).
- REST API: FastAPI + uvicorn. CLI: typer.
- Models and configuration: pydantic v2 + pydantic-settings.
- Orchestration: LangGraph (orchestration only; LLM calls stay in our own provider layer).
- LLM: OpenAI (`openai` SDK).
- Git: `git` CLI via `subprocess` (`shell=False`); GitHub PRs via PyGithub.
- Logging: structlog (JSON) with a `trace_id`.
- Quality: ruff (lint + format), mypy (strict), pytest, pre-commit, GitHub Actions CI.

## 3. AI Model

OpenAI **GPT-5.2** (configurable via `OPENAI_MODEL`). The model is accessed through an abstract
`LLMProvider` Protocol, so the provider/model can be swapped without touching the pipeline. Token
usage is captured per call as proof of real (non-mock) AI use.

## 4. Setup

```bash
uv sync --extra dev          # install dependencies
cp .env.example .env         # then fill in the required values
```

Requirements: Python 3.13, `git`, and network access (GitHub + OpenAI).

## 5. Environment Variables

Required:

- `OPENAI_API_KEY` — OpenAI key with access to the configured model.
- `GITHUB_TOKEN` — token with `Contents: read/write` and `Pull requests: read/write` on the target repo.
- `REPO_ALLOWLIST` — comma-separated list of repositories the agent may operate on.

Optional (defaults shown):

- `OPENAI_MODEL=gpt-5.2`
- `GITHUB_API_URL=https://api.github.com`
- `WORKSPACE_ROOT=./workspaces`
- `MAX_FIX_ATTEMPTS=2`
- `CONTEXT_TOKEN_BUDGET=60000`
- `CONTEXT_TOP_N_FILES=12`
- `MAX_CHANGED_FILES=8`
- `LOG_LEVEL=INFO`
- `AGENT_GIT_NAME`, `AGENT_GIT_EMAIL` — commit author identity.

`.env` is gitignored and never committed.

## 6. How to Run

```bash
# CLI: activate the virtualenv once, then use the `shiplet` command.
source .venv/bin/activate

shiplet run --task task.json                  # task JSON -> Pull Request
shiplet run --task task.json --dry-run        # everything except push and PR
shiplet run --task task.json --fail-on-test   # do not open a PR if tests fail
shiplet run --task task.json --review         # show the diff and confirm before the PR
shiplet issue --repo <url> --number 4         # resolve a GitHub issue directly
shiplet analyze --repo <url> --branch main    # clone and analyze a repo (read-only)

# Fallback launcher (works without activating the venv or the editable install):
./run.sh run --task task.json

# REST API: POST /api/tasks and a GitHub Issue webhook at /api/webhooks/github/issues.
uvicorn ai_dev_agent.input.api:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d @task.json
```

## 7. Example Task Payload

```json
{
  "taskId": "TASK-123",
  "title": "Add email validation to user registration API",
  "description": "Repository: https://github.com/example-org/user-service\nBranch: develop\n\nRequirement:\nAdd email format validation to the POST /users/register endpoint.\n\nAcceptance Criteria:\n- Invalid email returns HTTP 400\n- Error message should be Invalid email format\n- Add or update unit tests"
}
```

## 8. Example Execution Report

```json
{
  "traceId": "8f1c2e7a9b4d4f0e",
  "taskId": "TASK-123",
  "status": "success",
  "timeline": [
    {"step": "parse", "status": "ok", "durationMs": 3},
    {"step": "clone", "status": "ok", "durationMs": 1840},
    {"step": "analyze", "status": "ok", "durationMs": 22},
    {"step": "generate", "status": "ok", "durationMs": 6120},
    {"step": "run_tests", "status": "ok", "durationMs": 2470},
    {"step": "publish", "status": "ok", "durationMs": 1530}
  ],
  "analysis": {
    "language": "Python",
    "framework": "FastAPI",
    "buildTool": "uv",
    "testCommand": "pytest",
    "relevantFiles": ["app/users.py", "tests/test_users.py"],
    "existingTestFiles": ["tests/test_users.py"]
  },
  "ai": {
    "model": "gpt-5.2",
    "changedFiles": ["app/users.py", "tests/test_users.py"],
    "inputTokens": 1320,
    "outputTokens": 540,
    "costUsd": 0.0
  },
  "test": {"status": "passed", "command": "pytest", "durationMs": 2470},
  "pr": {
    "url": "https://github.com/example-org/user-service/pull/42",
    "branch": "ai-agent/TASK-123-add-email-validation-to-user-registration-api",
    "number": 42
  },
  "errors": []
}
```

## 9. Architecture

Layered and abstracted; each capability sits behind a Protocol so it can be swapped or extended.
LangGraph orchestrates the pipeline but does not own the AI layer.

```
Task input (CLI / REST API / GitHub Issue)
        |
        v
   Task Parser  ->  ParsedTask
        |
        v
   Orchestrator (LangGraph graph)
   |    |        |        |          |            |
   v    v        v        v          v            v
 Repo  Repo     AI Code  Test     Git Provider   Execution
 Mgr   Analyzer Agent    Runner   (GitHub PR)    Report
```

Module map:

```
ai_dev_agent/
  config.py · models.py · errors.py
  input/      cli.py · api.py · parser.py
  repo/       manager.py · analyzer.py · profiles/ (python, node)
  ai/         provider.py · openai_provider.py · code_agent.py · context.py · prompts.py
  test_runner/ runner.py
  git_provider/ base.py · github.py · pr_body.py
  graph/      state.py · pipeline.py
  observability/ logging.py · report.py
  security/   sanitize.py · secrets.py
prompts/      externalized prompt files · templates/ pr_body.md
```

## 10. AI Agent Flow

The LangGraph pipeline (thin nodes delegate to the components above):

```
parse -> clone -> analyze -> generate -> run_tests
                                              |
                          tests passed? --------------- no --> attempts < MAX ? -- yes --> fix --> run_tests
                                |                                       | no
                                v                                       v
                             publish (open PR)                 publish (PR with [Tests failing])
```

- Context for the model is built from the analyzer's ranked relevant files, bounded by a token
  budget, with secret-bearing and sensitive files excluded.
- The model returns whole-file rewrites as structured JSON. A validation gate runs on the output
  regardless of the model: paths must stay inside the workspace and the analyzed scope, sensitive
  files are off-limits, the change is size-bounded, required tests must be present, and Python must
  parse.
- On test failure, the failing output is fed back to the model to fix, up to `MAX_FIX_ATTEMPTS`.

## 11. Security Approach

- Token/secret management: secrets come only from the environment, are never committed, and are
  masked in logs and reports.
- Repository allowlist: a repo outside `REPO_ALLOWLIST` is rejected before any clone.
- Workspace isolation: one directory per task (`workspaces/<trace_id>/`), recreated cleanly.
- Command-injection safe: git runs with list args and `shell=False`; URLs and branch names are validated.
- Prompt-injection safe: task and repo content are treated as untrusted data; embedded instructions
  are ignored, and a validation gate runs on the AI output regardless of model behavior.
- Context limiting and secret filtering: only ranked relevant files are sent, after a secret scan
  and a sensitive-path denylist (`.env`, keys, etc.).
- Private repositories: cloned over a token-injected URL that is never logged.

## 12. Known Limitations

- Full end-to-end support (analysis + test execution) is implemented for Python and Node;
  additional languages need a `LanguageProfile` and their toolchain installed.
- The AI-output syntax check is currently Python-only (`ast`); other languages rely on the test run.
- AI-generated tests can in principle pass trivially; a test-presence check is enforced, but
  semantic test quality is not guaranteed.
- Cost in USD is reported as `0.0` (token usage is captured; per-model pricing is not wired in).
- Tests run in a local subprocess, not a sandbox.

## 13. Behavior on Test Failure and Production Notes

Test-failure strategy: the failing test output is fed back to the model to fix, up to
`MAX_FIX_ATTEMPTS`. If tests still fail, the PR is still opened but its title is prefixed with
`[Tests failing]` and the report status is `tests_failed`, leaving it for human review.
`--fail-on-test` instead skips opening a PR on failure.

Improvements for production:

- Run tests in a Docker sandbox; pass a scrubbed environment to subprocesses.
- Use a secret manager instead of `.env`; add per-model cost tracking.
- Add a job queue / worker for async task processing and horizontal scaling.
- Add more `LanguageProfile`s (Java, C#, Go) and language-specific syntax checks.
- Persist LangGraph checkpoints for resumable, human-in-the-loop approvals.

## Trade-offs and Deliberate Scope-Outs

Out of scope by choice (documented rather than half-built): Jira/Trello webhooks (represented by the
GitHub Issue trigger), Docker test sandbox, embedding-based repository indexing (replaced by
keyword/path ranking), and multi-repo tasks.
