# Installed-package self-check

`samsarix-codegen self-check` is a deterministic preflight for a newly installed wheel. It needs no
configuration, credential, model process, project file, or network access.

```bash
samsarix-codegen self-check
samsarix-codegen self-check --format json > self-check.json
samsarix-codegen schema self-check > self-check-v1.schema.json
```

## What it checks

The command performs five fail-closed checks using only package code and bundled resources:

1. Load every public contract and require its Draft 2020-12 declaration and object root. This is an
   intentional standard-library resource/header check, not full JSON meta-schema validation; the
   development suite and every CI wheel job perform the full validation with the optional
   `jsonschema` development dependency so the shipped package can retain zero runtime dependencies.
2. Rebuild and parse the same deterministic request represented by the repository's offline
   example, then compare its pinned fingerprint.
3. Build and parse the credential-free execution plan, then compare its pinned fingerprint.
4. Build and parse an explicitly synthetic result and compare its response hash.
5. Verify the complete request/plan/result chain, pin the deterministic example result-policy
   fingerprint, enforce its exact model and response-byte rules, and check input/output limits
   through the public evidence implementation.

A passing report includes the package version, Python implementation/version, contract count, and
content-omitting request, plan, and response fingerprints. It explicitly records
`network.attempted: false` and `network.provider_called: false`. The command exits `0` only after all
checks pass. Deterministic drift, a missing or malformed bundled contract, or a broken round trip
uses the general failure exit code `1` and emits no passing report.

## Trust boundary

The self-check proves that this installed package can reproduce its own known offline fixture. It
does not inspect a project, authenticate an artifact, validate a provider, measure model quality,
test endpoint availability, or prove that a future real execution will be safe. Run
`provider-check` separately only when one explicit network request and any associated provider cost
are approved. Review every real request, execution plan, and result policy independently.
