# Changelog

All notable changes will be documented here. Versions follow semantic versioning once the owner
approves a first public release.

## [0.2.0] - Unreleased

### Added

- Deterministic schema-versioned request artifacts with canonical SHA-256 fingerprints, per-context
  content hashes, and transparent input estimates.
- Offline `inspect` and fingerprint-pinned `execute` commands for separating prompt review from
  credential-bearing provider execution.
- Explicit bounded UTF-8 stdin context for staged diffs, selected log excerpts, and shell pipelines.
- Optional hard `--max-estimated-input-tokens` gate before any provider request.
- Machine-readable provider result envelopes for `run` and `execute`.
- Exact stored-prompt rendering with `inspect --format markdown`.
- Content-safe offline artifact comparison in text and JSON formats.
- Bundled JSON Schema Draft 2020-12 contracts and an offline `schema` export command for request,
  result, and comparison envelopes.
- A one-request `provider-check` preflight with a content-safe JSON evidence envelope, a 256-token
  hard ceiling, and a bundled Draft 2020-12 contract.
- A privacy-preserving three-developer pilot protocol with explicit evidence and decision gates.
- A strict privacy-minimal pilot record, portable JSON Schemas, and zero-dependency maintainer
  checker that validates cross-session adoption gates without collecting prompts or responses.
- A deterministic evaluator pilot kit with the exact wheel, source commit, quick-start, prefilled
  record, schemas, license notices, strict content manifest, SHA-256 checksums, and standalone
  archive/extracted-directory verification.
- Release-workflow upload and GitHub provenance attestation for the evaluator kit without widening
  the PyPI publication payload or claiming real-user pilot results.
- Strict execution-result parsing plus offline, same-request response hash/size and usage comparison
  without response-body disclosure.
- A bundled Draft 2020-12 contract for execution-result comparisons.
- Offline `inspect-result` validation and content-omitting metadata for a single stored result, with
  a standalone Draft 2020-12 contract.
- Offline `verify-result` linkage validation for a concrete request/result pair, with
  content-omitting text/JSON evidence and a standalone Draft 2020-12 contract.
- Optional fail-closed result policies on `inspect-result` and `verify-result` for an exact model,
  UTF-8 response bytes, and provider-reported prompt, completion, or total token ceilings.
- A strict versioned execution-result policy file, bundled Draft 2020-12 schema, typed
  parse/render/load API, checked-in example, and explicit `--policy` application in local/CI runs.
- A strict versioned execution-plan contract that binds one request fingerprint to an endpoint,
  model, whole-second timeout, estimated-input ceiling, and output ceiling without credentials.
- Offline `create-plan` and `verify-plan` commands, plan-backed `execute` with no provider/budget
  override precedence, typed public APIs, independent plan/verification schemas, and an example.
- Backward-compatible execution-plan schema version 2, which optionally binds the exact
  result-policy fingerprint so one approved plan fingerprint covers request, provider settings,
  budgets, and output rules; missing, substituted, or model-incompatible policies fail before
  provider setup.
- An installed-wheel smoke harness that proves the exact plan-backed journey against one local
  provider request and proves tamper/override failures make no additional request.
- Execution-result schema version 2 with an optional reviewed-plan fingerprint and separate
  requested/provider-reported model labels, while retaining legacy version-1 parsing.
- Offline `verify-execution` validation for a concrete request, execution plan, and plan-bound
  result, with content-omitting linkage, budget, usage, response-size, and response-hash evidence.
- A standalone Draft 2020-12 execution-evidence contract and typed public verification/rendering
  API.
- Canonical result-policy fingerprints, an offline `fingerprint-policy` command, and policy-bound
  `verify-execution` enforcement that records the exact passing policy in execution evidence.
- Result-policy schema version 2 with bounded JSON-object parsing, required/allowed top-level keys,
  top-level type gates, duplicate-key rejection, and compatibility with version 1 policies.
- Execution-evidence schema version 3 with response format and top-level key count after structured
  policy success, without emitting response-derived key names or values.
- Policy-gated `execute` with pre-network policy/fingerprint approval, one provider request,
  post-response fail-closed enforcement before normal stdout, and no retry on rejection.
- A fully linked, reproducible offline request/plan/synthetic-result example whose rendered
  evidence must exactly match the checked-in record in tests and the installed-wheel CI journey.
- An installed-package `self-check` command and standalone report schema that load every bundled
  contract and reproduce the synthetic evidence chain without project input, credentials, or a
  network request.
- Strict, versioned, explicitly invoked context manifests that compose reusable root-contained file
  allowlists without repository discovery, globs, or ignore-file interpretation.
- A bundled Draft 2020-12 context-manifest contract, typed parse/render API, and runnable example.
- Fail-closed source/distribution release checks, a non-publishing dry-run path, SHA-256 manifests,
  build-provenance attestations, and gated PyPI/GitHub release automation.
- Distribution auditing that rejects an unexpected import package or dist-info directory in the
  wheel, including stale local build-cache contamination.
- A release and rollback runbook plus monthly GitHub Actions dependency updates.
- Competitive-positioning and request-artifact contract documentation.

### Changed

- JSON `build` output is now executable request-artifact schema version 2.
- Redirected and piped CLI output is emitted as UTF-8 consistently across platforms.
- Current execution-plan and plan-verification schema exports now emit version 2 while the version 1
  schema, example, parser behavior, and original fingerprints remain available for compatibility.
- Execution-result rendering now rejects values outside its documented schema.
- Result inspection, verification, and comparison records advance to schema version 2 so plan and
  response-model metadata remain visible in content-omitting workflows.
- Execution evidence advances to schema version 3 with explicit null structure when not evaluated
  and bounded JSON-object format/key-count evidence after a version 2 policy passes; versions 1 and
  2 remain bundled for compatibility.
- Provider requests reject HTTP redirects so bearer credentials cannot be forwarded to a redirect
  target.
- Provider configuration now rejects malformed public types, control characters, overlong values,
  and non-loopback plaintext endpoints consistently across inline and planned execution.
- GitHub Actions dependencies are pinned to verified full commit SHAs.
- The version advances to `0.2.0` to mark the first post-productization workflow milestone.

## [0.1.0] - Unreleased

### Added

- Read-only `samsarix-codegen build` journey with Markdown and JSON output.
- Bounded `samsarix-codegen run` journey for OpenAI-compatible chat-completions endpoints.
- Explicit UTF-8 context loading with root containment, file-count, and byte limits.
- Stable public Python API, CLI exit codes, usage estimates, and provider error handling.
- Unit, integration, package-build, wheel-smoke, lint, format, type-check, and cross-platform CI
  configuration.
- Apache-2.0 licensing, Samsarix LLC attribution, citation metadata, security reporting, and support
  guidance.

### Changed

- Reframed the repository from an unimplemented three-product suite into one narrow developer tool.
- Reset the honest maturity indicator from the prototype's unsupported `1.0.0` claim to `0.1.0`.
- Renamed the unreleased Helix prototype to Samsarix Codegen across the distribution, import package,
  CLI command, environment variables, documentation, and repository metadata.

### Removed

- Canned model responses that were presented as AI code generation and interactive assistance.
- The non-building VS Code extension and its commands, providers, sidebar, and webview claims.
- Unused runtime dependencies and unsupported references to a private legacy CLI ecosystem.
- Conflicting license declarations that referenced license files absent from the repository.
