# Productization Record

Last updated: 2026-07-29

## Current repository assessment

The initial repository was a single clean commit containing nine files and three disconnected
prototypes:

- `helix_codegen/src/generator.py` exposed broad code-generation classes but returned a canned
  function for every request. Its wheel contained an unintended top-level `generator.py` module and
  installed no `helix` or product-specific command.
- `helix_interactive/src/interactive.py` implemented an in-memory REPL shell but returned canned
  responses. It had no console entry point and exported sessions to the current directory without a
  deliberate product contract.
- `helix_vscode_ext/src/extension.ts` imported five files that did not exist, declared a test runner
  that did not exist, and rendered commands and chat UI backed by placeholder responses.
- The README claimed marketplace and PyPI installation, production readiness, 14 packages, 24
  agents, deployment, monitoring, cost tracking, and an Apache/proprietary dual license. None of
  those claims was supported by files in the repository.
- There were no tests, lockfiles, CI workflows, release artifacts, environment examples, license
  files, or working start commands. The only history was commit `7c04120` on `master`.

The source did establish one credible intent: turn a coding instruction and optional code context
into model guidance. The implemented product keeps that intent and removes unsupported surfaces.

## Chosen product definition

**Samsarix Codegen is a read-only Python CLI and library that builds bounded, inspectable prompts for
coding tasks and can optionally send one request to an OpenAI-compatible chat-completions endpoint.**

It is not a coding agent, IDE extension, private portfolio integration, or model provider. It does not
discover a repository, edit files, execute generated code, run tools, persist chats, or retry calls.

### Target user and primary use case

The target user is a developer who wants to give an AI model a small, explicit set of source files
without granting file-write or shell access. The primary journey is:

1. Install the package from the repository.
2. Run `samsarix-codegen build` with a task, instruction, and zero or more explicit files.
3. Inspect or pipe the generated Markdown/JSON prompt without a network call.
4. Optionally run the same request with `samsarix-codegen run --model ...` against a local or hosted
   OpenAI-compatible endpoint.
5. Review the response on standard output and use the documented exit code or provider usage.

### Independent reason to exist

Current full coding tools provide repository maps, multi-turn modes, edits, and tool execution. For
example, Aider documents repository mapping and code/ask/architect modes, while Claude Code exposes
interactive, print, resume, and MCP workflows. Rebuilding those products from this prototype would
be neither distinct nor supportable. Samsarix Codegen instead offers a small prompt boundary that is
easy to inspect, script, and embed. Ollama documents the same `/v1/chat/completions` compatibility
surface, so a local-first path does not require a private Samsarix service.

Research references:

- <https://aider.chat/docs/repomap.html>
- <https://aider.chat/docs/usage/modes.html>
- <https://docs.anthropic.com/en/docs/claude-code/cli-usage>
- <https://docs.ollama.com/api/openai-compatibility>
- <https://packaging.python.org/en/latest/guides/writing-pyproject-toml/>
- <https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/>

### Deliberate exclusions

- Autonomous file edits, shell execution, git operations, repository crawling, and code application.
- A VS Code extension until the CLI has validated demand and a real extension can call a stable API.
- Authentication, accounts, subscriptions, databases, hosted infrastructure, and telemetry.
- Provider-specific tools, streaming, images, stateful responses, or automatic fallback/retries.
- Claims of production readiness, generated-code correctness, market fit, or enterprise capability.

## Key product and architecture decisions

1. **One root package.** A standard `src/samsarix_codegen` distribution and `[project.scripts]` entry
   point replace two malformed Python wheels and one broken Node package.
2. **Offline first.** `build` is the credential-free primary journey and shares the exact message
   builder used by `run`.
3. **Explicit context.** Only repeated `--file` values are read; resolved paths must remain under
   `--root`. UTF-8, file-count, per-file, total-byte, and NUL checks bound data handling.
4. **One network contract.** The standard-library client implements non-streaming OpenAI-compatible
   `/chat/completions`, applies a timeout and response-size cap, and never retries automatically.
5. **Credential hygiene.** API keys are accepted only from `SAMSARIX_API_KEY`; endpoint URLs reject
   embedded credentials, queries, and fragments. Plain HTTP is loopback-only.
6. **Read-only output.** Model text is printed to stdout. File writes and execution remain the
   caller's explicit responsibility.
7. **Zero runtime dependencies.** This keeps installation small and avoids the prototype's unused
   Click, Rich, Requests, Pydantic, and prompt-toolkit dependencies.
8. **Honest versioning.** `0.1.0` reflects a first release candidate; the unsupported `1.0.0` claim
   was not retained.
9. **Explicit licensing.** After the owner supplied Samsarix LLC identity and requested a
   credit-preserving license, Apache-2.0 was added with a company `NOTICE`, SPDX headers, citation
   metadata, and contribution terms. It provides a patent grant and redistribution notice duties
   without requiring downstream source disclosure.
10. **Clean rebrand.** The unreleased package, import, command, environment variables, user agent,
    and documentation use Samsarix naming without permanent legacy aliases.

## Assumptions

- The initial commit is an unreleased prototype; no compatibility contract or published users are
  evidenced in the repository.
- Samsarix LLC is the copyright holder and package author; `contact@samsarix.com` is the business
  contact and `support@samsarix.com` is the support and private security channel, as supplied by the
  owner.
- The initial Helix names were never published as a package, so a clean Samsarix namespace change is
  preferred over indefinite compatibility aliases.
- An OpenAI-compatible endpoint is a useful interoperability boundary, not a claim that all provider
  extensions behave identically.
- Users invoking `run` are trusted operators choosing their own endpoint and files. File contents and
  model responses remain untrusted data.
- The package name must be checked by the owner before PyPI publication.

## Baseline command results

These commands were run against commit `7c04120` before productization. Dependency installation for
the VS Code prototype was isolated in a temporary directory to preserve the worktree.

| Command | Actual baseline result |
| --- | --- |
| `git status --short --branch` | Exit 0; clean `master...origin/master` |
| `python -m compileall -q helix_codegen helix_interactive` | Exit 0 |
| `python -m pytest -q` | Exit 1; `no tests ran in 0.04s` |
| `python -m pip wheel --no-deps ... helix_codegen` | Exit 0; wheel contained top-level `generator.py`, no package or command |
| `python -m pip wheel --no-deps ... helix_interactive` | Exit 0; wheel contained top-level `interactive.py`, no package or command |
| `npm install --ignore-scripts --no-audit --no-fund` | Exit 0 in an isolated copy; six packages installed |
| `npm run compile` | Exit 1; `tsconfig.json` did not exist |
| `npm run vscode:prepublish` | Exit 1; five imported provider/UI modules did not exist |
| `npm test` | Exit 1; `out/test/runTest.js` did not exist |
| Advertised `helix generate` / `helix interactive` | Not runnable; no console entry point or parent CLI dependency existed |

Final command evidence is recorded in the **Final verification** section after each verification run.

## Prioritized findings

### P0 — release or primary journey blockers

- [x] Replace canned model output with an honest offline builder and real optional endpoint call.
- [x] Provide an installable import package and actual `samsarix-codegen` console entry point.
- [x] Remove the non-building extension and its dead commands/UI rather than advertising them.
- [x] Replace unsupported README claims with reproducible commands and explicit maturity.
- [x] Add tests for the local primary journey and network contract.
- [x] Add build, wheel-install, and cross-platform CI configuration.

### P1 — serious usefulness, reliability, security, or maintainability problems

- [x] Bound context file count, bytes, instruction length, response bytes, timeout, and output tokens.
- [x] Contain context paths to an explicit root and reject binary/non-UTF-8 content.
- [x] Require HTTPS for non-loopback endpoints and prohibit URL-embedded credentials.
- [x] Keep credentials out of CLI arguments and redact them from endpoint error text.
- [x] Add meaningful exit codes and provider response-contract validation.
- [x] Remove unused dependencies and introduce lint, formatting, strict type checking, and CI.
- [x] Document trust boundaries, privacy behavior, approximate cost controls, and limitations.
- [x] Add an owner-approved license, attribution, and contribution terms before redistribution.

### P2 — valuable later work

- [ ] Add opt-in streaming after cancellation and partial-output semantics are designed and tested.
- [ ] Add provider contract fixtures for additional confirmed compatible services.
- [ ] Consider stdin context and ignore-file-based discovery only if explicit-file ergonomics prove
  insufficient; retain visible budgets and path boundaries.
- [ ] Add signed release automation after the package name is reserved and publishing is configured.
- [ ] Reconsider an editor integration only after the CLI API is stable and real usage justifies it.

## Implementation checklist

- [x] Standard root `pyproject.toml`, source layout, minimal public API, and console script.
- [x] `build` and `run` commands with useful help and version behavior.
- [x] Task guidance for generate, explain, debug, refactor, tests, and review.
- [x] Safe explicit context loader and portable Markdown/JSON renderers.
- [x] Bounded chat-completions client and structured user-facing errors.
- [x] Unit and local HTTP integration tests covering success and ordinary failures.
- [x] Example input, changelog, contribution guidance, new-user README, and CI.
- [x] Record clean final verification results below.

## Release acceptance criteria

- Installation from the built wheel exposes `samsarix-codegen` and the documented package imports.
- `build` works without network access or secrets and includes the selected source content.
- `run` succeeds against a deterministic local HTTP fixture and fails clearly for missing model,
  unsafe endpoint, HTTP rejection, malformed response, and unavailable provider.
- Context traversal, binary input, invalid UTF-8, file-count, and byte-limit cases fail closed.
- Lint, formatting, strict type checking, tests, sdist/wheel build, and wheel smoke pass.
- CI runs those checks on the declared minimum and current Python versions across Windows and Linux.
- Documentation contains only implemented commands and names all remaining external gates.
- No locally actionable P0 remains and no core-path placeholder is present.

## Completed work

- Consolidated three prototype surfaces into one independently installable CLI/library.
- Implemented the complete offline prompt-building journey and optional provider execution journey.
- Added validation, resource bounds, output separation, stable errors, and credential handling.
- Added comprehensive test and release scaffolding plus reproducible documentation.
- Removed false competitive, deployment, marketplace, package, license, and maturity claims.

## Deferred work and rationale

- Streaming, tool calls, automated edits, and repository maps would materially expand risk and move
  the product into direct competition with mature agents; they are unnecessary for the first wedge.
- A VS Code extension is deferred because there is no evidence that maintaining two distributions
  improves adoption before the CLI is validated.
- Conversation persistence is deferred to avoid storing source or model data without a validated need
  and retention design.
- Automatic retries are excluded because they can duplicate paid work and obscure failure recovery.
- Dependency locking is not used for runtime because the package has zero runtime dependencies.
  Build/dev tool ranges are bounded; released artifacts and CI verify the installed wheel shape.

## Owner-, legal-, credential-, and production-blocked work

| Blocker | Required owner action | Verification |
| --- | --- | --- |
| Package identity | Reserve `samsarix-codegen` on PyPI (the project URL returned 404 on 2026-07-29) | Owner-controlled PyPI project exists with matching metadata |
| Publication | Configure trusted publishing or a scoped PyPI token | Tagged release publishes signed artifacts from CI |
| Provider validation | Choose any hosted providers the project will officially support | Contract tests pass against owner-approved non-production test accounts |

No deployment, account creation, package publication, spending, or live infrastructure change is
required for local evaluation and none was performed.

## Security, privacy, reliability, and cost review

### Trust boundaries

- CLI arguments, environment configuration, selected file contents, endpoint responses, and model
  output are untrusted inputs.
- The invoking developer is trusted to choose a project root, files, model, and endpoint.
- The model receives only explicit context, but embedded prompt injection can still influence output.
- Generated output is never executed or written by Samsarix Codegen.

### Controls

- Resolved-path containment prevents ordinary traversal and symlink escape from `--root`.
- UTF-8/NUL checks reject accidental binary or opaque inputs.
- Count, byte, character, token, timeout, and response caps prevent unbounded local/API work.
- Remote plaintext transport and URL credentials are rejected; Python's default TLS verification is
  retained.
- Keys are environment-only, omitted from request summaries, and redacted from HTTP error bodies.
- Calls are non-streaming, cancellable by the process, and never automatically retried.

### Residual risks

- Local filesystem state can change between validation and read; this is a local trusted-operator
  utility, not a multi-tenant file service.
- Prompt injection and insecure generated code require human review; system wording is defense in
  depth, not a security boundary.
- OpenAI-compatible implementations can vary. Provider contract failures are surfaced without trying
  potentially costly fallback requests.
- The four-bytes-per-token estimate can differ materially by tokenizer and language. Actual price is
  provider/model-specific and intentionally not fabricated.

## Distribution and sustainability

The simplest distribution is a pure-Python wheel installed with `pipx` or `pip`. After the external
gates above, PyPI plus GitHub release artifacts is sufficient; there is no reason to operate a hosted
service. A plausible sustainability path is free local tooling funded by sponsorship or paid support
if adoption exists. A subscription is not justified without demand and cost evidence.

## Known risks

- The apparent availability of `samsarix-codegen` on PyPI is not a reservation; another party could
  claim it before the owner publishes or reserves the project.
- The external provider matrix has not been owner-validated.
- Model quality and output safety vary and are outside this package's control.
- CI configuration is locally reviewable but remains unproven on GitHub until pushed by the owner.

## Pre-rebrand verification

This prior verification used Python 3.11.9 on Windows. The source distribution was built into a new
temporary directory, extracted, checked there, rebuilt into a wheel, and installed into a second
fresh virtual environment with `PYTHONPATH` removed. Generated files in the repository were not used
as the smoke-test import source.

| Command | Actual result |
| --- | --- |
| `python -m build --sdist --outdir <temp>/sdist .` | Exit 0; built `helix_codegen-0.1.0.tar.gz` |
| `tar -xf <sdist> -C <temp>/unpack` | Exit 0; changelog, contribution guide, productization record, example, source, and tests present |
| `python -m ruff check .` (from extracted sdist) | Exit 0; all checks passed |
| `python -m ruff format --check .` (from extracted sdist) | Exit 0; 18 files already formatted |
| `python -m mypy src` (from extracted sdist) | Exit 0; no issues in 8 source files |
| `python -m pytest` (from extracted sdist) | Exit 0; 39 tests passed in 7.04 seconds |
| `python -m build --wheel --outdir <temp>/wheel .` (from extracted sdist) | Exit 0; built `helix_codegen-0.1.0-py3-none-any.whl` |
| `python -m pip install --force-reinstall --no-deps <wheel>` (fresh venv) | Exit 0; console script created |
| `python -m pip check` (fresh venv) | Exit 0; no broken requirements |
| `helix-codegen --version` | Exit 0; legacy pre-rebrand command returned `helix-codegen 0.1.0` |
| `python -m helix_codegen --version` | Exit 0; legacy pre-rebrand module returned `helix-codegen 0.1.0` |
| `helix-codegen --help` | Exit 0; legacy pre-rebrand `build` and `run` documented |
| `helix-codegen build ... --file examples/sample.py --format json` | Exit 0; legacy pre-rebrand journey included one context file and `def greet` |
| `helix-codegen run "Explain this"` without a model | Expected exit 2 with actionable missing-model error |
| `helix-codegen run ... --endpoint http://127.0.0.1:1/v1 --timeout 1` | Expected exit 4 with bounded unavailable-provider error |

## Post-rebrand verification

Current verification used Python 3.11.9 on Windows. It built a new source distribution outside the
checkout, extracted and tested that source, built a wheel from the extracted source, and installed
only that wheel into a fresh virtual environment. Installed-wheel smoke commands ran from the
temporary directory so ignored artifacts in the checkout could not supply imports.

| Command or check | Actual result |
| --- | --- |
| `python -m ruff check .` | Exit 0; all checks passed |
| `python -m ruff format --check .` | Exit 0; 14 Python files already formatted |
| `python -m mypy src` | Exit 0; no issues in 8 source files |
| `python -m pytest -ra` | Exit 0; 40 tests passed in 5.95 seconds |
| Official Apache-2.0 text comparison | Exact match after newline normalization and boundary trimming |
| `python -m build --sdist --outdir <temp>/sdist .` | Exit 0; built `samsarix_codegen-0.1.0.tar.gz` |
| Required-file inspection of extracted sdist | `LICENSE`, `NOTICE`, citation, security, support, typed package, example, and tests present |
| Lint, format, mypy, and pytest from extracted sdist | Exit 0; 40 tests passed in 6.90 seconds |
| `python -m build --wheel --outdir <temp>/wheel .` from extracted sdist | Exit 0; built `samsarix_codegen-0.1.0-py3-none-any.whl` |
| Fresh-venv install plus `python -m pip check` | Exit 0; no broken requirements |
| `samsarix-codegen --version` and `python -m samsarix_codegen --version` | Exit 0; both returned `samsarix-codegen 0.1.0` |
| Fresh import isolation | `samsarix_codegen` imported at `0.1.0`; legacy `helix_codegen` was absent |
| Installed `build` smoke with `examples/sample.py` | Exit 0; one context file and `def greet` present |
| Installed `run` without a model | Expected exit 2 with `SAMSARIX_MODEL` guidance |
| Installed `run` against unavailable loopback endpoint | Expected exit 4 without retrying |
| Installed metadata and wheel inspection | Samsarix name/emails, Apache expression, `py.typed`, `LICENSE`, and `NOTICE` verified; no legacy package path |

### Validation not run

- The GitHub Actions matrix cannot run locally. It is configured for Python 3.10 and 3.14 on Ubuntu
  and Windows; its first pushed run remains a release gate.
- A live Ollama or hosted provider was not called because no model, credentials, or spending was
  required or authorized. Deterministic local HTTP integration tests cover request shape, auth
  header behavior, text/usage normalization, HTTP rejection, invalid JSON, timeouts, unavailable
  endpoints, response limits, and secret redaction.
- Package publication, signing, and installation from PyPI were not attempted; they remain
  owner-controlled actions.
- The optional Codex Security workspace scan was skipped at the owner's request due its cost. The
  repository instead received a focused manual trust-boundary review plus adversarial tests and
  searches for secrets, unsafe endpoints, path escape, unbounded reads, command execution, stale
  placeholders, and documentation drift.

## Current release disposition

**Release candidate with named external gates.** The local package and its primary journey meet the
documented acceptance criteria, with no locally actionable P0 identified. Public release remains
gated on (1) the first green GitHub Actions matrix run, (2) owner control of the PyPI project, and
(3) owner-controlled publication/signing. Live hosted provider certification is optional unless the
owner chooses to advertise specific providers.
