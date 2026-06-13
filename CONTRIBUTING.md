# Contributing

Thanks for your interest in improving Shiplet. This document explains how to set
up the project, the quality gates every change must pass, and the conventions the
codebase follows.

## Prerequisites

- Python 3.13
- [uv](https://github.com/astral-sh/uv) for dependency and environment management
- `git`
- Docker (optional) — only needed to run tests in the isolated sandbox
  (`TEST_SANDBOX=docker`)

## Setup

```bash
uv sync --extra dev
source .venv/bin/activate
```

Copy `.env.example` to `.env` and fill in the required values before running the
agent against a real repository.

## Quality gates

Every change must pass the same checks that run in CI:

```bash
uv run ruff format .      # format
uv run ruff check .       # lint
uv run mypy               # static types (strict)
uv run pytest             # unit tests
```

Unit tests use a fake `LLMProvider`; they never call a real model, so the suite
runs offline and without API keys.

## Conventions

- **PEP 8 and clean code.** Small, single-responsibility functions; type hints
  everywhere.
- **English** for all code, identifiers, comments, docs, and commit messages.
- **No decorative emojis.** Status markers use plain text (for example
  `[Tests failing]`).
- **Comment intent, not mechanics.** The code should read on its own; comment
  only the "why".
- **Prompts are externalized.** Every prompt is a file under
  `src/ai_dev_agent/prompts/`; code only loads and fills them. Output templates
  live under `src/ai_dev_agent/templates/`.
- **Layers behind Protocols.** `LLMProvider`, `GitProvider`, the test runner, and
  `LanguageProfile` are abstractions; add a new implementation rather than
  branching existing code.

## Extending the agent

- **New language:** add a `LanguageProfile` under `src/ai_dev_agent/repo/profiles/`
  that detects the project and reports its test command and relevant files.
- **New LLM provider:** add an implementation of `LLMProvider` and wire it through
  the orchestrator factory.
- **New Git provider:** implement `GitProvider` (branch, commit, push, pull
  request) for the target platform.

## Pull requests

- Branch from `main`, keep changes focused, and include tests.
- Make sure all quality gates pass locally.
- Describe what changed and why; link any related issue.
