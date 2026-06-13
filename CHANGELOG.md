# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

Initial release: an AI development agent that turns a task into a reviewed pull
request.

### Added

- **Task input** via CLI (`run`, `issue`, `analyze`), a FastAPI REST endpoint,
  and a GitHub Issue webhook.
- **Task parsing** into repository, base branch, requirement, and acceptance
  criteria.
- **Repository clone** into an isolated per-task workspace with token support and
  URL/branch validation.
- **Repository analysis** (language, framework, build tool, test command,
  relevant files, existing tests) for Python and Node.js via swappable
  `LanguageProfile`s.
- **AI code change** with a real model (GPT-5.2 by default) behind an
  `LLMProvider` Protocol, producing scoped whole-file edits with a validation
  gate (scope, path traversal, secret scan, size limit, syntax, test presence).
- **Bounded context building** with file ranking, a token budget, secret
  scanning, and a sensitive-path denylist.
- **Test runner** that auto-detects the test command, with an optional Docker
  sandbox (`TEST_SANDBOX=docker`) that installs the target repo's dependencies
  and isolates execution from the host.
- **Test-fix retry loop** that feeds failing output back to the model up to
  `MAX_FIX_ATTEMPTS`.
- **Git provider** that creates the branch, commits, pushes, and opens a GitHub
  pull request with a structured body, linking `Closes #N` for issues.
- **Orchestration** with LangGraph: thin nodes, a bounded retry cycle, and typed
  errors that are never swallowed.
- **Observability**: structured JSON logs with a trace id, an execution timeline,
  token usage, and a JSON execution report.
- **Safety controls**: repository allowlist, workspace isolation, command- and
  prompt-injection defenses, scrubbed subprocess environments, and human-review
  pull requests.
- **Run modes**: dry-run, interactive review with diff preview, and
  fail-on-test.
- **Idempotency**: deterministic branch names and existing-PR detection; an
  already-present change is reported as `no_change` instead of a failure.
