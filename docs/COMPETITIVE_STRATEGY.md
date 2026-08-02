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
8. Compare two same-request result envelopes offline without reproducing either response or
   pretending structural evidence is a quality score.
9. Reuse checked-in file selections through explicitly invoked manifests without granting
   repository-discovery or glob authority.

## Evidence from adjacent products

The mature agent category already offers capabilities Samsarix should not try to clone:

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode.md) supports CI,
  stdin, sandbox policies, JSONL events, and schema-constrained outputs.
- [Claude Code's CLI](https://code.claude.com/docs/en/cli-reference) supports
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

Persistent project context is also common, but usually broader or more implicit than this product's
approval boundary:

- [Aider's options](https://aider.chat/docs/config/options.html) accept repeatable editable and
  read-only files, while its [in-chat commands](https://aider.chat/docs/usage/commands.html) can save
  commands that reconstruct a session's selected files.
- [Claude Code memory](https://code.claude.com/docs/en/memory) loads project instruction files and
  path-scoped rules into sessions.
- [GitHub Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions)
  can apply repository-wide, path-specific, and agent instruction files.

Those workflows validate repeated team context. Samsarix context manifests serve a narrower use
case: an operator must name the manifest, its entries are a finite portable allowlist contained by
one root, and the resulting exact file contents are compiled into the same bounded fingerprinted
artifact used for approval.

The evaluation category validates demand for repeatable model comparisons:

- [Microsoft Foundry playgrounds](https://learn.microsoft.com/azure/foundry/concepts/concept-playgrounds)
  compare up to three models in parallel with synchronized prompt context and parameter settings.
- [LangSmith](https://docs.langchain.com/langsmith/compare-experiment-results) compares experiments,
  outputs, regressions, metrics, and full or diff views.

Samsarix is not a substitute for those quality-evaluation systems. Its smaller differentiator is a
dependency-free offline check that both bounded result envelopes reference the same reviewed
request, then emits only model labels, response hashes/sizes, and reported usage deltas.

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

Execute the same artifact against two operator-chosen OpenAI-compatible endpoints, then run
`compare-results` on their JSON envelopes. The common fingerprint links both envelopes to the same
reviewed message payload; the comparison omits response bodies and does not claim provider
authenticity, quality, tokenizer equivalence, or authorship.

### Content-omitting run evidence

Validate a stored execution result with `inspect-result` and retain a schema-valid metadata record
before a comparison partner exists. CI can record the request link, model label, response size/hash,
and reported usage without copying the response into ordinary job logs. This is validation and
provenance-adjacent bookkeeping, not response evaluation or provider authentication.

### Repeatable project review

Commit a small versioned context manifest for a component's implementation, public contract, and
tests. Developers and CI can invoke the same allowlist, add an explicit task-specific file, inspect
the effective content hashes and budget, and compare rebuilt artifacts without relying on local
shell history or repository discovery.

## Defensible product constraints

- No automatic repository crawl in the core path.
- No implicit manifest lookup, glob expansion, ignore-file interpretation, or conditional include.
- No file writes, patch application, shell execution, or tool loop.
- No implicit network request from `build`, `inspect`, or `inspect-result`.
- No automatic retry or provider fallback.
- No credential in CLI arguments, artifacts, summaries, or result JSON.
- No claim that an unkeyed fingerprint authenticates the artifact.
- No claim that result hashes, length, or provider-reported usage evaluate response quality.

## Next evidence gates

1. Complete the [three-developer pilot](PILOT.md) using pre-commit review and one non-code
   incident-triage workflow.
2. Record operator-run conformance reports and deeper contract tests against any local/provider
   endpoints Samsarix chooses to support explicitly.
3. Configure the implemented trusted-publishing/attestation pipeline, reserve the package, and
   execute the documented release and rollback verification.
4. Only after pilot evidence: consider opt-in streaming, ignore-aware discovery, or editor hooks.
