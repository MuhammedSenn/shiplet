# Security Policy

Shiplet clones third-party repositories, sends repository context to a language
model, and runs untrusted test code, so security is a first-class concern.

## Reporting a vulnerability

Please do not open a public issue for security reports. Instead, email
**muhammedsnfu@gmail.com** with:

- a description of the issue and its impact,
- steps to reproduce, and
- any relevant logs (with secrets removed).

You can expect an acknowledgement within a few business days and a coordinated
disclosure once a fix is available.

## Supported versions

The project is pre-1.0; only the latest `main` receives security fixes.

## Built-in safeguards

The agent is designed defensively. The main controls are:

- **Secret management** — tokens and keys come only from the environment, are
  never committed, and are masked in logs and reports.
- **Repository allowlist** — a repository outside `REPO_ALLOWLIST` is rejected
  before any clone.
- **Workspace isolation** — each task runs in its own directory under
  `workspaces/<trace_id>/`, recreated cleanly.
- **Command-injection safety** — subprocesses use list arguments with
  `shell=False`; URLs and branch names are validated.
- **Prompt-injection defense** — task and repository content are treated as
  untrusted data; embedded instructions are ignored, and a validation gate runs
  on the model output regardless of model behavior.
- **Context limiting and secret filtering** — only ranked, relevant files are
  sent to the model, after a secret scan and a sensitive-path denylist
  (`.env`, keys, and similar).
- **Output scanning** — generated content is scanned for secrets and constrained
  to the analyzed, non-sensitive scope and a bounded file count.
- **Optional test sandbox** — with `TEST_SANDBOX=docker`, a repository's tests
  run inside a throwaway container isolated from the host filesystem, with
  capped CPU, memory, and PIDs.

Generated pull requests are always prepared for human review; the agent never
merges.
