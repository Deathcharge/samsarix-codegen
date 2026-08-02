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
- Strict execution-result parsing plus offline, same-request response hash/size and usage comparison
  without response-body disclosure.
- A bundled Draft 2020-12 contract for execution-result comparisons.
- Offline `inspect-result` validation and content-omitting metadata for a single stored result, with
  a standalone Draft 2020-12 contract.
- Offline `verify-result` linkage validation for a concrete request/result pair, with
  content-omitting text/JSON evidence and a standalone Draft 2020-12 contract.
- Optional fail-closed result policies on `inspect-result` and `verify-result` for an exact model,
  UTF-8 response bytes, and provider-reported prompt, completion, or total token ceilings.
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
- Execution-result rendering now rejects values outside its documented schema.
- Provider requests reject HTTP redirects so bearer credentials cannot be forwarded to a redirect
  target.
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
