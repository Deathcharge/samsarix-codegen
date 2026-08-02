# Productization Record

Last updated: 2026-08-01

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

**Samsarix Codegen is a read-only Python CLI and library that compiles explicit context into
bounded, inspectable coding requests and can optionally send one reviewed request to an
OpenAI-compatible chat-completions endpoint.**

It is not a coding agent, IDE extension, private portfolio integration, or model provider. It does not
discover a repository, edit files, execute generated code, run tools, persist chats, or retry calls.

### Target user and primary use case

The target user is a developer who wants to give an AI model a small, explicit set of source files
without granting file-write or shell access. The primary journey is:

1. Install the package from the repository.
2. Run `samsarix-codegen build` with a task, instruction, explicit files, explicitly invoked
   context manifests, or bounded stdin.
3. Inspect the generated Markdown or schema-versioned JSON artifact without a network call.
4. Record the artifact fingerprint, then create and validate a credential-free execution plan that
   binds it to an endpoint, model, timeout, input ceiling, and output ceiling.
5. Record the plan fingerprint as the complete non-secret execution approval, then use
   `execute --plan --expect-plan-fingerprint` in the credential-bearing boundary.
6. Review text output or retain the plan-bound structured result envelope, requested and
   provider-reported model labels, and provider-reported usage.
7. Verify the request, plan, and result together offline, retaining content-omitting linkage and
   budget evidence.
8. Optionally apply deterministic model, response-byte, and reported-token policy gates before CI
   retains a content-omitting inspection or request/result verification record.

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
- <https://code.claude.com/docs/en/cli-reference>
- <https://code.claude.com/docs/en/memory>
- <https://aider.chat/docs/config/options.html>
- <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions>
- <https://docs.ollama.com/api/openai-compatibility>
- <https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/>
- <https://www.braintrust.dev/docs/tracing-quickstart>
- <https://docs.langchain.com/langsmith/log-llm-trace>
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
3. **Explicit context.** Only repeated `--file` values, entries from explicitly invoked context
   manifests, and named stdin are read; resolved paths must remain under `--root`. UTF-8,
   file-count, per-file, total-byte, and NUL checks bound data handling.
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
11. **Reviewable execution artifacts.** Schema-versioned JSON captures the exact provider messages,
    normalized context hashes, approximate input estimate, and a canonical request fingerprint.
    Construction and inspection stay offline; execution can fail closed on fingerprint drift.
12. **Independent machine contracts.** Bundled Draft 2020-12 schemas describe request, result, and
    comparison envelopes without requiring a consumer to import this package. CLI parsing remains
    authoritative for integrity relationships JSON Schema cannot express.
13. **Operator-run provider evidence.** `provider-check` exercises the same non-streaming Chat
    Completions request/response path with two fixed messages, no source context, one request, no
    retry, and a separate 256-token ceiling. Its report excludes endpoint, key, and response text.
    A pass is scoped evidence, not Samsarix certification of a provider family.
14. **Release privilege separation.** Manual release-workflow dispatches build, audit, checksum,
    and attest but cannot publish. Only an exact `vX.Y.Z` tag contained in `master`, with matching
    source versions and a dated changelog, can reach the manually approved `pypi` environment.
    GitHub release publication waits for PyPI and uses a draft-first asset sequence.
15. **Structural result comparison.** Strict parsing and a shared request fingerprint let operators
    compare model labels, response equality, UTF-8 sizes, hashes, and reported token usage offline.
    The comparison omits response bodies and is not a quality score or provider-authenticity proof.
16. **Reusable context without discovery.** Context-manifest schema version 1 stores one portable
    root-relative file allowlist. Manifests are bounded, exact, explicitly named, independently
    schema-validatable, and composable. They flow into the existing contained loader and do not add
    globs, ignore rules, implicit lookup, or a second request provenance format; the resulting
    artifact records the effective context content and hashes.
17. **Fail-closed result policy.** The same typed local policy can gate one validated envelope on an
    exact model label, actual UTF-8 response size, and reported token ceilings. Missing usage rejects
    a configured token rule; output contracts remain unchanged and no evaluator/network authority
    is added.
18. **Reusable policy without discovery.** Execution-result policy schema version 2 stores one
    bounded, strict set of deterministic metadata, resource, and optional top-level JSON-object
    rules. Operators must pass its path explicitly; file rules cannot mix with flags, and no remote
    lookup, code execution, or hidden precedence is introduced. Version 1 remains compatible.
19. **Reviewed execution intent.** Execution-plan schema version 1 binds one request fingerprint to
    canonical endpoint, model, whole-second timeout, estimated-input ceiling, and output ceiling.
    The plan is credential-free, explicit, bounded, internally fingerprinted, and independently
    schema-validatable. Plan-backed execution reads only `SAMSARIX_API_KEY` at runtime and refuses
    request/provider/budget overrides rather than merging configuration layers.
20. **Portable policy-bound execution evidence.** Execution-result schema version 2 carries a
    nullable reviewed plan fingerprint and distinguishes the requested model from the
    provider-reported response model. Plan-backed execution populates the link automatically.
    `verify-execution` validates the full request/plan/result chain, requested model, input budget,
    any reported completion usage, and an optional separately approved result-policy fingerprint
    offline. Evidence schema version 3 emits exact passing policy rules, response hash/size, and
    only a structured response format/key count rather than response-derived names or values;
    versions 1 and 2 remain bundled. Legacy result version 1 remains parseable. This
    is local integrity and deterministic-policy evidence, not signed approval or provider
    attestation.
21. **Machine-consumable response gate.** A version 2 policy can require bounded valid JSON, a
    top-level object, required/allowed top-level keys, and JSON value types. Duplicate keys and
    non-finite numbers fail. This dependency-free offline check is deliberately narrower than
    recursive JSON Schema validation and does not score correctness or quality.

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
- [x] Add a deterministic local provider fixture and an operator-run conformance command.
- [ ] Record results for any provider/model Samsarix chooses to support explicitly.
- [x] Add bounded, explicitly named stdin context for staged diffs and selected log excerpts.
- [x] Add strict, versioned, explicitly invoked context manifests for repeatable file allowlists.
- [ ] Consider ignore-file-based discovery only if manifests and direct inputs prove insufficient;
  retain visible budgets and path boundaries.
- [x] Add dry-runnable release verification, provenance, and gated Trusted Publishing automation.
- [x] Add strict same-request execution-result comparison without reproducing response contents.
- [x] Add strict single-result inspection without reproducing response contents.
- [x] Add offline request/result linkage verification without reproducing either content body.
- [x] Add deterministic post-result model, size, and reported-usage gates for CI.
- [x] Add a versioned, checked-in execution-result policy contract for repeatable team CI rules.
- [x] Add bounded JSON-object shape gates and privacy-minimal structure evidence for downstream CI.
- [x] Add a versioned execution-plan contract so approval covers the request and exact non-secret
  provider/budget intent across the credential boundary.
- [x] Bind plan-backed results to that approval and verify the complete request/plan/result chain
  offline without reproducing prompt or response contents.
- [x] Canonically fingerprint one explicit result policy and bind its successful enforcement into
  the same versioned request/plan/result evidence record.
- [x] Add a fully linked offline request/plan/synthetic-result/policy fixture whose evidence is
  reproduced through both the public API and installed CLI in CI.
- [x] Add an installed-package self-check that validates every bundled contract and reproduces the
  synthetic request/plan/result/evidence path without project input or network access.
- [ ] Configure the PyPI publisher/environment, reserve the package, and execute the first release.
- [ ] Reconsider an editor integration only after the CLI API is stable and real usage justifies it.

## Implementation checklist

- [x] Standard root `pyproject.toml`, source layout, minimal public API, and console script.
- [x] `self-check`, `build`, `inspect`, `create-plan`, `verify-plan`, `verify-execution`, `inspect-result`,
  `verify-result`, `compare`, `compare-results`, `execute`, `run`, `schema`, and `provider-check`
  commands with useful help and
  version behavior.
- [x] Fail-closed post-result policy flags and a typed public enforcement API.
- [x] Strict result-policy parsing/rendering/loading, bundled schema, example, and installed-wheel
  CI journey.
- [x] Task guidance for generate, explain, debug, refactor, tests, and review.
- [x] Safe explicit context/manifest loader and portable Markdown/JSON renderers.
- [x] Bounded chat-completions client and structured user-facing errors.
- [x] Unit and local HTTP integration tests covering success and ordinary failures.
- [x] Example input, changelog, contribution guidance, new-user README, and CI.
- [x] Record clean final verification results below.

## Release acceptance criteria

- Installation from the built wheel exposes `samsarix-codegen` and the documented package imports.
- `build` works without network access or secrets and includes the selected source content.
- JSON artifacts are deterministic, fail on schema/content drift, summarize offline, and can be
  pinned before execution.
- Execution plans are deterministic, fail on plan/request drift, preserve exact provider/budget
  intent, omit credentials/prompt contents, and refuse execution-time overrides.
- Plan-backed results record their reviewed plan; offline execution verification rejects linkage,
  requested-model, input-budget, or reported-output drift without disclosing either content body.
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
- Added deterministic request artifacts, offline inspection, pinned execution, bounded stdin,
  input-budget enforcement, structured results, and staged-review examples.
- Added exact stored-prompt rendering and content-safe artifact comparison so reviewers can inspect
  and explain approval-object drift without rebuilding source context.
- Added versioned bundled schemas, offline schema export, and validator-backed conformance tests for
  standalone CI and cross-repository consumers.
- Added one-request provider conformance evidence and a bounded three-developer pilot protocol that
  collects usability signals without collecting prompts, source, logs, responses, or credentials.
- Added strict execution-result parsing, same-request content-omitting comparison, and a standalone
  versioned schema for downstream CI consumers.
- Added content-omitting single-result inspection and an independent versioned schema for CI run
  evidence before a comparison partner exists.
- Added offline request/result linkage verification and an independent versioned schema for
  content-omitting CI handoff evidence.
- Added optional exact-model, UTF-8 response-byte, and reported-token policy gates to both
  single-result paths, with missing usage rejected whenever its limit is configured.
- Added a versioned execution-result policy document, standalone Draft 2020-12 schema, typed
  parse/render/load API, checked-in example, and explicit no-override CLI behavior.
- Added result-policy version 2 top-level JSON-object gates, evidence version 3 structure counts,
  checked-in offline fixtures, and installed-wheel failure-path coverage without response values.
- Added versioned execution plans, offline plan creation/verification, a typed public API, standalone
  plan and verification schemas, a checked-in example, and exact no-override plan-backed execution.
- Added result schema version 2 with plan linkage and separate requested/response model labels,
  legacy version-1 parsing, offline policy-capable chain verification, a typed public API,
  standalone versioned evidence schemas, and installed-wheel evidence-chain coverage.
- Added strict context manifests, a standalone schema and typed API, repeated-manifest composition,
  installed-wheel smoke coverage, and a runnable repository example.
- Added source/tag/changelog gates, structural distribution verification, SHA-256 manifests,
  full-SHA-pinned Actions, provenance attestations, gated Trusted Publishing, immutable-ready GitHub
  release assembly, and a recovery runbook.
- Tightened the wheel audit to reject any unexpected top-level import package or dist-info directory
  after clean-room verification exposed stale local build-cache contamination.

## Deferred work and rationale

- Streaming, tool calls, automated edits, repository maps, and automatic file discovery would
  materially expand risk and move the product into direct competition with mature agents; they are
  unnecessary for the first wedge. Explicit manifests address repeated-selection ergonomics without
  crossing that boundary.
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
| Package identity | Reserve `samsarix-codegen` on PyPI (the project URL returned 404 again on 2026-08-01) | Owner-controlled PyPI project exists with matching metadata |
| Publication | Register `release.yml` as a Trusted Publisher and require approval on the `pypi` GitHub environment | Tagged release publishes attested artifacts from CI |
| Provider validation | Choose any local/hosted providers the project will officially support and run `provider-check` plus contract tests | Exact endpoint/model/version evidence passes in an owner-approved non-production environment |

No deployment, account creation, package publication, spending, or live infrastructure change is
required for local evaluation and none was performed.

## Security, privacy, reliability, and cost review

### Trust boundaries

- CLI arguments, environment configuration, context manifests, selected file/stdin contents,
  request artifacts, execution plans, endpoint responses, and model output are untrusted inputs.
- The invoking developer is trusted to choose a project root, files, model, and endpoint.
- The model receives only explicit context, but embedded prompt injection can still influence output.
- Generated output is never executed or written by Samsarix Codegen.
- Stored artifacts contain the complete prompt. Their SHA-256 fingerprints detect drift but are not
  signatures, so access control and authenticity remain external responsibilities.

### Controls

- Resolved-path containment prevents ordinary traversal and symlink escape from `--root`.
- Context manifests are explicitly invoked, root-contained, limited to 64 KiB and 20 entries, and
  reject ambiguous fields, non-portable paths, traversal segments, and duplicate entries; no path
  syntax is expanded as a glob.
- UTF-8/NUL checks reject accidental binary or opaque inputs.
- Count, byte, character, token, timeout, and response caps prevent unbounded local/API work.
- Optional post-result limits reject an unexpected model, oversized UTF-8 response, excessive
  reported usage, or missing usage needed by a configured token rule before emitting normal output.
- Policy documents are explicitly selected, bounded to 64 KiB, require an active rule, reject
  duplicate/unknown/null fields, and keep JSON integers within the cross-language safe range.
- Structured policy enforcement parses at most 1 MiB of response JSON, caps top-level width,
  rejects duplicate keys and non-finite numbers, hashes response-derived key names internally, and
  exposes only format/key-count evidence after all approved rules pass.
- Execution plans are explicitly selected files bounded to 64 KiB. They reject duplicate/unknown
  fields, noncanonical values, invalid endpoint settings, plan/request fingerprint drift, and input
  budget excess before client construction. Provider/budget flags cannot override them, and only
  the environment-only API key is resolved at plan-backed execution time.
- Remote plaintext transport and URL credentials are rejected; Python's default TLS verification is
  retained.
- HTTP redirects are rejected so bearer credentials cannot be forwarded to a provider-selected
  target.
- Keys are environment-only, omitted from request summaries, and redacted from HTTP error bodies.
- Calls are non-streaming, cancellable by the process, and never automatically retried.

### Residual risks

- Local filesystem state can change between validation and read; this is a local trusted-operator
  utility, not a multi-tenant file service.
- A checked-in manifest can become stale or expose repository structure. Missing or escaped paths
  fail closed, but selecting sensitive root-contained files remains an operator/reviewer decision.
- Prompt injection and insecure generated code require human review; system wording is defense in
  depth, not a security boundary.
- OpenAI-compatible implementations can vary. Provider contract failures are surfaced without trying
  potentially costly fallback requests.
- The four-bytes-per-token estimate can differ materially by tokenizer and language. Actual price is
  provider/model-specific and intentionally not fabricated.
- Result model labels and usage remain unauthenticated provider-envelope data; policy checks do not
  prove authorship, normalize tokenization, or establish monetary cost or response quality.
- A valid top-level JSON shape does not prove nested application-schema conformance, semantic
  correctness, safety, or usefulness; downstream consumers still need domain validation.
- A committed policy can reveal approved model labels and becomes part of repository governance;
  Samsarix does not discover, fetch, merge, or remotely update it.
- A plan can reveal endpoint topology, model names, and capacity choices. Its unkeyed fingerprint is
  not a signature; the expected digest protects the handoff only when retained separately under
  stronger access control.
- Python build frontends can reuse a local `build/` cache. The release audit rejects unexpected wheel
  roots, but local releasers should still build from a clean checkout or remove generated caches.

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
- Request artifacts can retain sensitive source or log content outside the original repository;
  users must apply equivalent access and retention controls.
- Execution plans omit prompt contents and credentials but can disclose deployment metadata;
  operators must govern them accordingly.

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
| [GitHub Actions run 30422299343](https://github.com/Deathcharge/samsarix-codegen/actions/runs/30422299343) | Exit 0; Python 3.10 and 3.14 passed on Ubuntu and Windows, including wheel smoke checks |

## Version 0.2 artifact-workflow verification

Current local verification used Python 3.14.6 on Windows. A new source distribution was created
outside the checkout, extracted, tested, and rebuilt into a wheel. That wheel alone was installed in
a fresh virtual environment, and installed commands ran from the temporary directory with
`PYTHONPATH` removed.

| Command or check | Actual result |
| --- | --- |
| `python -m ruff check .` | Exit 0; all checks passed |
| `python -m ruff format --check .` | Exit 0; 16 Python files already formatted |
| `python -m mypy src` | Exit 0; no issues in 9 source files |
| `python -m pytest -ra` | Exit 0; 69 tests passed in 8.84 seconds |
| `python -m build --sdist --outdir <temp>/sdist .` | Exit 0; built `samsarix_codegen-0.2.0.tar.gz` |
| Required-file inspection of extracted sdist | Legal/support files, all three docs, typed package, artifact tests, and staged-review examples present |
| Lint, format, mypy, and pytest from extracted sdist | Exit 0; 69 tests passed |
| `python -m build --wheel --outdir <temp>/wheel .` from extracted sdist | Exit 0; built `samsarix_codegen-0.2.0-py3-none-any.whl` |
| Fresh-venv install plus `python -m pip check` | Exit 0; no broken requirements |
| Installed CLI and module versions | Both returned `samsarix-codegen 0.2.0` outside the checkout |
| Installed artifact build/inspect/fingerprint smoke | Exit 0; one stdin item and valid canonical SHA-256 fingerprint |
| Installed `execute` without a model | Expected exit 2 before network access |
| Installed `inspect` after message tampering | Expected exit 5 for fingerprint/content mismatch |
| Installed metadata and wheel inspection | Version, Apache expression, Samsarix LLC emails, isolated import path, `py.typed`, `LICENSE`, and `NOTICE` verified |

The generated distribution digests are recorded with the exact commit in its pull request or
release evidence rather than embedded here, because updating a source-distribution document changes
the source-distribution digest.

### Artifact review-tools follow-up

The same Python 3.14.6 clean-room process was repeated after adding exact-prompt review and offline
comparison. Source checks passed with 75 tests in 9.84 seconds; the extracted sdist passed lint,
format, strict typing, and 75 tests in 13.61 seconds. The rebuilt wheel installed with no broken
requirements. From outside the checkout, installed commands rendered the exact stored prompt,
reported changed and identical artifacts correctly, omitted both message bodies from comparison
JSON, and exposed the typed `RequestArtifactComparison` public API. Package builds emitted no
warnings. Exact distribution digests are attached to the corresponding pull request.

### Machine-contract follow-up

Python 3.14.6 source checks passed with 87 tests in 9.48 seconds. The clean-room sdist passed lint,
format, strict typing, and 87 tests in 8.47 seconds. A dependency-free fresh-venv wheel install
exported all three bundled schemas, and real request, result, and comparison documents validated
against those exports with the Draft 2020-12 validator. Wheel inspection found all three JSON
resources, package builds emitted no warnings, and parsed wheel metadata confirmed zero
unconditional dependencies plus five development-extra requirements. The first metadata check used
a quote-sensitive text assertion and was replaced by the successful parsed-marker audit; it was a
verification-harness issue, not a package failure.

### Provider-conformance and pilot follow-up

Python 3.14.6 source checks passed with 93 tests. The clean-room sdist passed lint, format, strict
typing, and 93 tests. A follow-up review also added explicit boolean
rejection for public integer fields and independent fixed-message fixtures. Its rebuilt wheel
installed into a fresh environment with no broken or unconditional runtime dependencies. From
outside the checkout, the
installed package exported and validated the provider-check schema, constructed the typed
content-safe report envelope, returned exit 2 before network access when the model was absent, and
included both the new module and schema resource. Local two-server integration tests also proved
that a credential-bearing request stops at an HTTP redirect and never contacts its target. Package
builds emitted no warnings. Exact distribution digests are attached to the corresponding pull
request because recording a digest inside the sdist would change that digest.

### Release-readiness follow-up

Python 3.14.6 source checks passed with 103 tests. The clean-room sdist included its release scripts,
tests, pinned workflows, and roadmap; it passed lint, formatting, strict typing, and the same 103
tests before rebuilding a Twine-valid wheel. The repository-built sdist and wheel passed Twine plus
the fail-closed structural/metadata audit, which also produced a deterministic two-file
`SHA256SUMS`. A dependency-free fresh environment installed the wheel, reported version `0.2.0`,
loaded the provider-check schema, and exercised the typed public report API.

[Default-branch release run 30719609291](https://github.com/Deathcharge/samsarix-codegen/actions/runs/30719609291)
passed at commit `48e50a6`: every build, source, distribution, installed-wheel, upload, checksum, and
attestation step succeeded; both publishing jobs were skipped; and the build job had zero GitHub
annotations. Independently downloaded artifacts matched `SHA256SUMS`, and `gh attestation verify`
passed for both against this repository. The exact remote digests were
`068a55b0a2c607be5aab4c32dfd8fb441ef968e76c77d37ea367466fe328d0f1` for the wheel and
`80db412fbdafb0a76f305066fee99540574747e7b9ef16888c92c4c9ee784e7a` for the sdist.
[Post-merge CI run 30719540861](https://github.com/Deathcharge/samsarix-codegen/actions/runs/30719540861)
also passed the four-platform matrix using the current full-SHA-pinned Node 24 Actions releases.

### Execution-result comparison follow-up

Python 3.14.6 source checks passed with 120 tests. The extracted sdist passed lint, formatting,
strict typing, and the same 120 tests before producing a Twine-valid rebuilt wheel. The exact
repository-built sdist/wheel pair passed Twine and the fail-closed release audit. A dependency-free
fresh environment installed the audited wheel with no broken requirements or unconditional runtime
dependencies. From outside the checkout, the installed command exported the result-comparison
schema, compared two same-request envelopes without response-body disclosure, and produced JSON
that validated against the shipped Draft 2020-12 contract. The installed typed parser, summary,
comparison, schema enum, and render API were also exercised. Exact final distribution digests are
attached to the corresponding pull request because recording them inside the sdist would change the
sdist digest.

### Context-manifest follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing, and 161 tests in 24.64 seconds.
The repository-built sdist and wheel passed Twine and the fail-closed release audit. The extracted
sdist imported its own source path, then passed formatting, lint, strict typing, and the same 161
tests. Its isolated wheel rebuild was Twine-valid and visibly included the new
context-manifest schema. A dependency-free fresh environment installed the audited repository
wheel, reported no broken requirements, built a three-file request through the checked-in manifest,
exported a valid Draft 2020-12 manifest schema, and exercised the typed parse/render/schema API.

Exact final distribution digests are attached to the corresponding pull request because recording
them inside the sdist would change the sdist digest.

Two combined clean-room wrappers exceeded their time bounds after completing earlier checkpoints:
the first reached the fresh-wheel stage, and the final one reached unusually slow Windows virtual-
environment creation. Verification resumed against each exact artifact pair and reran every
unreturned stage separately. A first extracted rebuild requested `--no-isolation` and failed
because the host Python did not expose `setuptools.build_meta` globally; rerunning with the
project's declared isolated build path succeeded. None of these harness events was treated as a
product pass.

### Single-result inspection follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing, and 166 tests. The
repository-built sdist and wheel passed Twine and the fail-closed release audit. The extracted sdist
then passed formatting, lint, strict typing, and the same 166 tests before producing a Twine-valid
wheel. A dependency-free fresh environment installed the audited repository wheel, reported no
broken requirements, ran the installed `inspect-result` command outside the checkout, exported and
validated the result-inspection schema, and exercised the typed inspection API while asserting that
the response body was absent from both text and JSON metadata. An initial verification command used
Python's `-S` flag, which intentionally disables virtual-environment site-packages; the corrected
isolated import resolved to the installed wheel and passed. Exact final distribution digests are
attached to the corresponding pull request because recording them inside the sdist would change the
sdist digest.

### Request/result verification follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing, and 173 tests. The
repository-built sdist and wheel passed Twine and the fail-closed release audit. The extracted sdist
passed formatting, lint, strict typing, and the same 173 tests, then rebuilt a wheel that passed an
independent Twine recheck. A fresh dependency-free target installed the repository wheel and ran
`verify-result` outside the checkout: a matching request/result pair produced schema-valid
content-omitting metadata, while a different valid request failed with exit `5`. The installed
public API and bundled schema were exercised, and explicit assertions kept the fixture instruction
and response out of the record. The combined extracted-sdist wrapper reached its time limit after
printing successful output for every constituent stage, so the wrapper exit itself was not treated
as a pass; the final wheel's existence and Twine result were rechecked separately with exit `0`.
Exact final distribution digests are attached to the corresponding pull request because recording
them inside the sdist would change the sdist digest.

### Result-policy and wheel-integrity follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing, and 185 tests. Optional policy
flags on both single-result commands passed at exact model/byte/token boundaries and rejected an
unexpected model, every exceeded limit, and provider-omitted usage needed by a configured ceiling.
The typed public API enforced the same rules, including UTF-8 byte counting and bounded public
values, without changing either content-omitting output contract.

The first local package build exposed stale ignored `build/` cache content: its wheel contained a
legacy `helix_codegen` root, and the prior release audit incorrectly accepted it. The cache was moved
to the temporary evidence directory rather than deleted. A new regression test and stricter audit
then rejected that exact wheel, a clean rebuild contained only `samsarix_codegen` plus its matching
dist-info directory, and Twine and the release audit passed. The extracted clean sdist passed lint,
formatting, strict typing, and all 185 tests before rebuilding a Twine-valid wheel.

A dependency-free fresh environment installed the clean repository wheel, reported no broken
requirements, and resolved the public API from that environment. Outside the checkout,
`verify-result` passed every exact limit with exit `0`; `inspect-result` rejected excessive reported
usage with exit `5`, empty stdout, and no response disclosure. The installed typed policy API passed
the same exact limits. Exact final distribution digests are attached to the corresponding pull
request because recording them inside the sdist would change the sdist digest.

### Versioned result-policy contract follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing, workflow parsing, and 225 tests.
The source-built sdist contained the result-policy documentation, example, implementation, and
bundled schema. Its extracted tree passed the same formatting, lint, strict typing, workflow, and
225-test gates before producing a zero-runtime-dependency wheel. Both distributions passed Twine
and the fail-closed release audit.

A fresh virtual environment installed only that wheel and resolved Samsarix Codegen from the
environment outside the checkout. The installed public API round-tripped and loaded an explicit
policy, and the installed CLI exported the bundled policy schema. `verify-result` accepted an exact
model, response-byte, and reported-token boundary with exit `0` and no response disclosure;
`inspect-result` rejected an exceeded total-token ceiling with exit `5`, empty stdout, and no
response disclosure. Combining a policy file with an inline rule failed as a configuration error
with exit `2`. Exact final distribution digests are attached to the corresponding pull request
because recording them inside the sdist would change the sdist digest.

### Reviewed execution-plan follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing across 14 source files, workflow
parsing, the source release check, and 280 tests. A source-built sdist contained the execution-plan
implementation, standalone guide, example, smoke harness, and both bundled schemas. Its extracted
tree passed the same formatting, lint, typing, workflow, release-source, and 280-test gates before
building the wheel. Twine and the fail-closed release audit accepted the zero-runtime-dependency
sdist/wheel pair.

A fresh virtual environment installed only the wheel and resolved the public package from that
environment outside the checkout. The installed CLI exported both plan schemas and completed the
full build, inspect, create-plan, verify-plan, and plan-backed execute journey against a deterministic
local HTTP fixture. The fixture received exactly one request with the approved model, output limit,
messages, path, and environment-only bearer credential. Invalid provider/budget environment values
did not override the plan. A tampered plan and an explicit model override both failed before any
second request. The verification record omitted the private instruction and selected diff content.

Exact final distribution digests are attached to the corresponding pull request because recording
them inside the source distribution would change that distribution's digest.

### Portable execution-evidence follow-up

Python 3.14 source and extracted-sdist checks passed formatting, lint, strict typing across 15
source files, the source release gate, and 293 tests. The sdist contained result schema version 2,
all legacy/current result schemas, the execution-evidence implementation and schema, both new
examples, documentation, tests, CI changes, and the installed smoke harness. Twine and the
fail-closed distribution audit accepted the zero-runtime-dependency sdist/wheel pair.

A fresh dependency-free virtual environment installed only the wheel, reported no broken
requirements, and resolved `samsarix_codegen` from that environment outside the checkout. Under
`PYTHONOPTIMIZE=1`, the installed smoke completed the full request/plan/execute/verify-execution
journey against one deterministic local HTTP fixture. The one result carried the exact plan
fingerprint plus separate requested and provider-reported model labels; the evidence output omitted
both private instruction and response. The installed schemas validated the checked-in result and
evidence examples, and the installed typed API retained legacy result-version-1 parsing. Exact final
distribution digests are attached to the corresponding pull request because recording them inside
the source distribution would change that distribution's digest.

### Policy-bound execution-evidence follow-up

Python 3.14.6 source and clean extracted-sdist checks passed formatting, lint, strict typing across
16 source files, the source release gate, and 324 tests. The final sdist contained the canonical
result-policy fingerprint API, `fingerprint-policy` command, policy-capable evidence schema version
2, the preserved version 1 schema/fixture, the complete policy-bound example, documentation, tests,
CI changes, and installed smoke harness. A wheel built only from that extracted sdist and both final
distributions passed Twine and the fail-closed distribution audit. Exact final digests are attached
to the corresponding pull request because recording them inside the source distribution would
change that distribution's digest.

A fresh virtual environment installed only the audited wheel, reported no broken requirements and
zero unconditional runtime dependencies, and resolved the package outside the checkout. The
installed self-check passed its 13-contract registry and internally pinned the example result
policy. The installed CLI reproduced the exact checked-in version 2 evidence with policy fingerprint
`sha256:7e603aa13e31a93aa73d5e03fd77be9248114cd1d721d77ab05db242260e2dab`;
the emitted document passed full Draft 2020-12 validation using the installed schema. The installed
typed fingerprint/approval API passed, and the optimized installed smoke made exactly one local
fixture request, enforced the passing policy, rejected a failing policy offline, omitted private
instruction/response content from evidence, and made no additional request on failure.

The first installed-smoke attempt exposed that the new policy arguments had been placed on the
`verify-plan` step in the harness rather than the later `verify-execution` step. That artifact pair
was invalidated, the journey was corrected, and every source, sdist, distribution, installation,
schema, and one-request gate above was rerun against the final exact pair. A separate metadata
assertion initially treated optional development-extra requirements as unconditional dependencies;
the corrected marker-aware check confirmed all five requirements are gated by the `dev` extra.
Neither harness event was treated as a product pass.

### Structured-response policy follow-up

Python 3.14.6 source checks passed formatting, lint, strict typing across 16 source files, the source
release gate, installed self-check, and all 361 tests. Result-policy schema version 2 adds bounded
valid JSON-object parsing, reviewed top-level required/allowed keys and value types, duplicate-key
and non-finite-number rejection, and exact canonical fingerprints while preserving version 1
parsing. Execution evidence advances to version 3 and exposes only response format and top-level
key count after structural success; response-derived key names, key hashes, and values remain out
of public payloads and renderings.

The source-built sdist and wheel passed Twine and the fail-closed distribution audit. A fresh
zero-dependency virtual environment installed only that wheel, reported no broken requirements,
and resolved Samsarix outside the checkout. Its self-check passed all 13 public contract selectors,
and the installed CLI reproduced the exact checked-in version 3 evidence fixture. Under
`PYTHONOPTIMIZE=1`, the installed smoke made exactly one local fixture request, enforced the
structured policy, rejected metadata and missing-key policies offline with empty normal output,
omitted private response values, and made no additional request on either failure. Exact final
distribution digests belong in the pull-request evidence because recording them in the source
distribution would change the digest.

Current official Promptfoo assertion/JSON guidance and Braintrust scorer guidance both treat
deterministic format validation as a normal evaluation/CI capability. Samsarix deliberately takes
a narrower dependency-free position: top-level structural readiness within the existing approved
request/plan/result chain, not recursive JSON Schema validation, model grading, or a correctness
claim. The linked sources and inference are recorded in `docs/COMPETITIVE_STRATEGY.md`.

### Validation not run

- A live Ollama or hosted provider was not called because no model, credentials, or spending was
  required or authorized. Deterministic local HTTP integration tests and the installed-wheel plan
  smoke cover request shape, auth header behavior, exact plan-backed execution, one-request provider
  conformance, text/usage normalization, HTTP rejection, redirect blocking, invalid JSON, timeouts,
  unavailable endpoints, response limits, and secret redaction.
- The three-developer pilot protocol is ready but has not been represented as completed; it requires
  three real participants using the same exact wheel.
- Package publication, signed release-tag creation, and installation from PyPI were not attempted;
  they remain owner-controlled actions.
- The optional Codex Security workspace scan was skipped at the owner's request due its cost. The
  repository instead received a focused manual trust-boundary review plus adversarial tests and
  searches for secrets, unsafe endpoints, path escape, unbounded reads, command execution, stale
  placeholders, and documentation drift.

## Current release disposition

**Release candidate with named external gates.** The productized default and its `0.1.0` journey met
the documented acceptance criteria and four-job GitHub Actions matrix. Version `0.2.0` adds the
review-first artifact workflow, offline review/comparison, request/result linkage and deterministic
versioned result-policy tools, credential-free reviewed execution plans, portable
request/plan/result evidence,
reusable explicit context manifests, independent JSON contracts, and an operator-run provider
conformance check. Version 2 structured-result policies and version 3 privacy-minimal evidence now
cover machine-consumable CI handoffs; each capability has local clean-package evidence recorded
above.
Public release remains gated on owner control of the PyPI project, creation of the signed release
tag, and approval of the publishing environment. The usefulness claim remains gated on the
three-developer pilot, and live provider certification remains optional unless the owner advertises
specific providers.
