# Changelog

All notable changes will be documented here. Versions follow semantic versioning once the owner
approves a first public release.

## [0.1.0] - Unreleased

### Added

- Read-only `helix-codegen build` journey with Markdown and JSON output.
- Bounded `helix-codegen run` journey for OpenAI-compatible chat-completions endpoints.
- Explicit UTF-8 context loading with root containment, file-count, and byte limits.
- Stable public Python API, CLI exit codes, usage estimates, and provider error handling.
- Unit, integration, package-build, wheel-smoke, lint, format, type-check, and cross-platform CI
  configuration.

### Changed

- Reframed the repository from an unimplemented three-product suite into one narrow developer tool.
- Reset the honest maturity indicator from the prototype's unsupported `1.0.0` claim to `0.1.0`.

### Removed

- Canned model responses that were presented as AI code generation and interactive assistance.
- The non-building VS Code extension and its commands, providers, sidebar, and webview claims.
- Unused runtime dependencies and unsupported references to a private Helix CLI ecosystem.
- Conflicting license declarations that referenced license files absent from the repository.
