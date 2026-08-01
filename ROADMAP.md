# Samsarix Codegen roadmap

This roadmap separates four gates: merge, release, publication, and flagship adoption. Passing one does not imply the next.

## Product boundary

Portfolio role: **standalone product candidate**. Develop this as a focused standalone product with its own distribution and support boundary. Integrate with the flagship through versioned contracts, not shared private source.

Current disposition: The productized default is merged and preserved by a rollback ref. Version
`0.2.0` has a merged deterministic request-artifact workflow; offline human-review and comparison
tools are the next milestone. Release, publication, and flagship adoption remain separate decisions.

## Stabilize the productized default

- Keep the default branch buildable from a clean checkout and preserve exact-head CI evidence.
- Keep Samsarix LLC branding, package identity, license metadata, and compatibility aliases internally consistent.
- Preserve the pre-productization default under a rollback ref before merging; do not delete legacy history.
- Review priority: Merge after CI/name review, reserve the package, and run a three-developer offline/local-model pilot.

## Release candidate

- Run a small user pilot against the exact packaged artifact.
- Instrument only truthful, privacy-respecting product signals and define support ownership.
- Promote from prerelease only after recovery, upgrade, and failure paths are demonstrated.

Current hardening backlog:

- No external user validation yet demonstrates that the review-first artifact workflow beats direct
  copy/paste for its intended users.
- Deterministic artifacts, offline inspection, pinned execution, stdin context, and hard estimated
  input budgets are implemented and locally package-verified for `0.2.0`.
- Exact stored-prompt rendering and content-safe artifact comparison are implemented and locally
  package-verified for the review-tools follow-up.
- No live provider certification, streaming, ignore-aware manifest, or editor integration.
- Package name, signing, and publication are not owner-completed.
- A standard-library HTTP client creates a small but ongoing compatibility/security review burden across provider variants and redirects.

## Samsarix adoption

- Define a public API, event, schema, artifact, or deployment contract before connecting to Samsarix Unified.
- Add a consumer-owned contract fixture covering authentication, privacy, limits, errors, and version compatibility.
- Make one implementation canonical; remove or freeze duplicate behavior only after parity and rollback are proven.
- Record an owner, support level, compatibility window, and measurable adoption signal.

## Completion evidence

A milestone is complete only when its exact commit, commands and results, artifact digest, consumer or deployment, and rollback path are recorded in a pull request or release record. README claims must not exceed that evidence.
