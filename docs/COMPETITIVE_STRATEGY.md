# Competitive strategy

Last reviewed: 2026-08-01

## Positioning

Samsarix Codegen is a **review-first request compiler for coding models**. It is deliberately not a
general coding agent and not a whole-repository context packer.

Its product promise is narrower and testable:

1. Accept only context that the operator explicitly names or pipes in.
2. Compile that context into a deterministic, provider-neutral request artifact.
3. Make size, provenance, and the approximate input budget visible before any network request.
4. Let a reviewer validate and pin the artifact fingerprint offline.
5. Execute exactly that reviewed message payload once, without file writes, tools, or retries.
6. Publish versioned JSON contracts that independent CI systems can validate without private code.
7. Let operators test the exact provider wire contract with one fixed, content-free request before
   sending reviewed source or logs.

## Evidence from adjacent products

The mature agent category already offers capabilities Samsarix should not try to clone:

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode.md) supports CI,
  stdin, sandbox policies, JSONL events, and schema-constrained outputs.
- [Claude Code's CLI](https://docs.anthropic.com/en/docs/claude-code/cli-usage) supports
  non-interactive operation, structured output, turn limits, sessions, and permission modes.
- [Continue CLI](https://docs.continue.dev/cli/headless-mode) supports headless pipelines, rules,
  JSON output, sessions, and opt-in editing or shell tools.
- [Aider](https://aider.chat/docs/usage/modes.html) provides ask, code, and architect modes, while
  its [Git integration](https://aider.chat/docs/git.html) manages edits, commits, and undo.
- [GitHub Copilot CLI review](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/agentic-code-review)
  can inspect local changes and request permission before running supporting commands.

The context-packing category is also established:

- [Repomix](https://repomix.com/guide/) packs repositories with ignore handling, multiple formats,
  token counts, and secret detection. Its configuration can also include diffs, logs, and token
  budgets.
- [Gitingest](https://gitingest.com/) turns local or remote repositories into prompt-friendly
  digests.
- [Aider's repository map](https://aider.chat/docs/repomap.html) selects important symbols from a
  repository to give its editing agent wider context.

These products validate demand for automation and broad context. They also leave a useful boundary
for teams that want a smaller approval object without granting repository discovery, shell access,
or edit authority.

## Initial real-world use cases

### Pre-commit review

Pipe `git diff --staged` into a bounded request artifact. A developer or CI job can inspect its file
label, bytes, estimate, and fingerprint before choosing a provider.

### CI approval handoff

Build an artifact in an unprivileged job, record its fingerprint as the approval object, and execute
it later in a credential-bearing job with `--expect-fingerprint`. The artifact contains the model
messages, so the execution job does not need source-tree access.

### Incident and log triage

Pipe a selected log excerpt into a debug request with a hard estimated-input budget. No repository
scan, history, telemetry, or persistent session is required.

### Reproducible provider comparison

Execute the same artifact against two operator-chosen OpenAI-compatible endpoints. The common
fingerprint proves that the message payload and context metadata were identical; it does not claim
that provider behavior, tokenization, or outputs are equivalent.

## Defensible product constraints

- No automatic repository crawl in the core path.
- No file writes, patch application, shell execution, or tool loop.
- No implicit network request from `build` or `inspect`.
- No automatic retry or provider fallback.
- No credential in CLI arguments, artifacts, summaries, or result JSON.
- No claim that an unkeyed fingerprint authenticates the artifact.

## Next evidence gates

1. Complete the [three-developer pilot](PILOT.md) using pre-commit review and one non-code
   incident-triage workflow.
2. Record operator-run conformance reports and deeper contract tests against any local/provider
   endpoints Samsarix chooses to support explicitly.
3. Configure the implemented trusted-publishing/attestation pipeline, reserve the package, and
   execute the documented release and rollback verification.
4. Only after pilot evidence: consider opt-in streaming, ignore-aware manifests, or editor hooks.
