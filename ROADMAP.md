# Samsarix Codegen roadmap

This roadmap separates four gates: merge, release, publication, and flagship adoption. Passing one does not imply the next.

## Product boundary

Portfolio role: **standalone product candidate**. Develop this as a focused standalone product with its own distribution and support boundary. Integrate with the flagship through versioned contracts, not shared private source.

Current disposition: The productized default is merged and preserved by a rollback ref. Version
`0.2.0` has merged deterministic request-artifact and offline review/comparison workflows.
Versioned machine-readable contracts, explicitly invoked context manifests, an operator-run
provider conformance check, offline single-result inspection, request/result linkage verification,
same-request result comparison, and deterministic post-result policy gates are implemented
milestones. A versioned, checked-in result-policy contract makes those gates repeatable across local
and CI workflows without implicit discovery. Versioned execution plans now bind a reviewed request
to exact non-secret provider settings and budgets across an offline-to-credentialed handoff without
execution-time override precedence. Plan-backed result schema version 2 now carries that reviewed
plan fingerprint, and offline execution verification validates the full request/plan/result chain
plus requested-model and reported-output-budget consistency without content disclosure. Evidence
schema version 3 can also bind and enforce one separately approved result-policy fingerprint in the
same fail-closed command. Result-policy schema version 2 optionally requires a bounded JSON object
with reviewed top-level keys and types, while response-structure evidence exposes only its format
and key count. A
checked-in offline request/plan/synthetic-result/policy chain now makes
that verifier runnable from a clone without credentials, a provider process, or network access.
An installed-package self-check reproduces the same deterministic chain and validates every
bundled contract before a pilot participant selects project context or configures a provider.
A gated release workflow can build and attest without publishing; PyPI owner setup, publication,
pilot validation, and flagship adoption remain separate decisions.

## Stabilize the productized default

- Keep the default branch buildable from a clean checkout and preserve exact-head CI evidence.
- Keep Samsarix LLC branding, package identity, license metadata, and compatibility aliases internally consistent.
- Preserve the pre-productization default under a rollback ref before merging; do not delete legacy history.
- Review priority: Merge after CI/name review, reserve the package, and run a three-developer offline/local-model pilot.

## Release candidate

- Run the documented three-developer pilot against one exact packaged artifact; its plan-backed
  workflow, privacy-minimal record, and deterministic decision checker are ready for participants.
- Instrument only truthful, privacy-respecting product signals and define support ownership.
- Promote from prerelease only after recovery, upgrade, and failure paths are demonstrated.

Current hardening backlog:

- No external user validation yet demonstrates that the review-first artifact workflow beats direct
  copy/paste for its intended users.
- Deterministic artifacts, offline inspection, pinned execution, stdin context, and hard estimated
  input budgets are implemented and locally package-verified for `0.2.0`.
- Credential-free execution plans, offline request/plan verification, exact plan-backed execution,
  and standalone plan/verification schemas are implemented; live endpoints remain optional owner
  evidence rather than a hidden release dependency.
- Plan-bound result schema version 2, legacy result parsing, separate requested/response model
  labels, and policy-capable offline request/plan/result evidence verification are implemented and
  locally tested; the evidence is intentionally not a provider signature or attestation.
- Exact stored-prompt rendering and content-safe artifact comparison are implemented and locally
  package-verified for the review-tools follow-up.
- Strict execution-result parsing and content-omitting same-request comparison are implemented for
  reproducible provider experiments; they intentionally do not score output quality.
- Content-omitting single-result inspection is implemented for fail-closed CI evidence before a
  comparison partner exists; it intentionally does not authenticate or score a response.
- Offline request/result linkage verification confirms a result fingerprint against a concrete
  validated artifact without exposing either content body; it intentionally is not a signature.
- Exact-model, UTF-8 response-byte, and reported-token limits can now fail closed in CI through
  either single-result path. A strict versioned file can carry the same rules across team workflows;
  neither form authenticates usage or scores quality.
- Result-policy version 2 can additionally reject invalid, duplicate-keyed, non-object, over-wide,
  or top-level shape-incompatible JSON offline. This is a bounded machine-consumability gate, not
  recursive JSON Schema validation or a semantic correctness score.
- Strict versioned context manifests make repeated component reviews portable without automatic
  repository discovery, glob expansion, or a second path-loading boundary.
- Draft 2020-12 request, result, and comparison schemas plus offline schema export are implemented
  and locally package-verified for the contract milestone.
- A content-free, one-request provider check is implemented; no owner-selected live provider has
  been certified. Streaming, ignore-aware discovery, and editor integration remain deferred.
- Package name reservation and publication are not owner-completed. Release checks, SHA-256
  manifests, unexpected-wheel-root rejection, GitHub provenance attestations, and Trusted
  Publishing workflow support are implemented.
- A standard-library HTTP client creates a small but ongoing compatibility review burden across
  provider variants. Redirects are rejected to prevent bearer-credential forwarding.

## Samsarix adoption

- Define a public API, event, schema, artifact, or deployment contract before connecting to Samsarix Unified.
- Add a consumer-owned contract fixture covering authentication, privacy, limits, errors, and version compatibility.
- Make one implementation canonical; remove or freeze duplicate behavior only after parity and rollback are proven.
- Record an owner, support level, compatibility window, and measurable adoption signal.

## Completion evidence

A milestone is complete only when its exact commit, commands and results, artifact digest, consumer or deployment, and rollback path are recorded in a pull request or release record. README claims must not exceed that evidence.
