# Execution plan contract

An execution plan is a credential-free, versioned approval object that binds one validated request
artifact to the provider settings and budgets that may be used when credentials become available.
It closes the gap between approving prompt contents and approving where and how that prompt runs.

## Reviewed execution journey

Create the request without network access:

```bash
git diff --staged | samsarix-codegen build "Review these staged changes" \
  --task review \
  --stdin-name staged.diff \
  --format json > request.json
request_fingerprint="$(samsarix-codegen inspect request.json --format fingerprint)"
```

Bind the approved request to exact provider settings, still without credentials or network access:

```bash
samsarix-codegen create-plan request.json \
  --expect-fingerprint "$request_fingerprint" \
  --endpoint https://provider.example/v1 \
  --model provider-model \
  --timeout 60 \
  --max-output-tokens 1200 \
  --max-estimated-input-tokens 50000 > execution-plan.json

plan_fingerprint="$(samsarix-codegen verify-plan request.json execution-plan.json \
  --format fingerprint)"
samsarix-codegen verify-plan request.json execution-plan.json \
  --expect-plan-fingerprint "$plan_fingerprint" --format json > plan-verification.json

cat > result-policy.json <<'JSON'
{
  "schema_version": 1,
  "max_response_bytes": 262144
}
JSON
cat result-policy.json
policy_fingerprint="$(samsarix-codegen fingerprint-policy result-policy.json)"
```

This example policy places a 256 KiB ceiling on the stored response without requiring
provider-reported usage. Review and tailor its explicit rules before approval; the
[result-policy contract](RESULT_POLICY.md) documents every field and stricter checked-in examples.

The credential-bearing job needs the two explicit files, separately approved plan and policy
fingerprints, the explicit policy file, and an optional environment-only API key:

```bash
export SAMSARIX_API_KEY="your-provider-key"
samsarix-codegen execute request.json \
  --plan execution-plan.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --format json > result.json

samsarix-codegen verify-execution request.json execution-plan.json result.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --policy result-policy.json \
  --expect-policy-fingerprint "$policy_fingerprint" \
  --format json > execution-evidence.json
```

`create-plan` and `verify-plan` never make a network request. `execute --plan` validates the request,
the plan's internal fingerprint, request linkage, estimated-input budget, and optional separately
approved plan fingerprint before constructing the client. It then makes one non-streaming request.
The plan-backed JSON result records the exact plan fingerprint. `verify-execution` uses that field
to validate the complete request/plan/result chain later without network access or content
disclosure. When an explicit result policy is supplied, it also requires the exact separately
approved policy fingerprint, enforces every rule, and records the fingerprint and rules in evidence
schema version 2. The [result-policy contract](RESULT_POLICY.md) defines that final gate.

## Schema version 1

```json
{
  "schema_version": 1,
  "plan_fingerprint": "sha256:<64 lowercase hex characters>",
  "request_fingerprint": "sha256:<64 lowercase hex characters>",
  "provider": {
    "endpoint": "https://provider.example/v1",
    "model": "provider-model",
    "timeout_seconds": 60,
    "max_output_tokens": 1200
  },
  "budgets": {
    "max_estimated_input_tokens": 50000
  }
}
```

The plan fingerprint is SHA-256 over canonical JSON containing every field above except
`plan_fingerprint`. Canonical JSON uses sorted keys, UTF-8, and compact separators. The exact
request fingerprint is included, so a plan cannot be reused for a rebuilt or different request.

The file contains no prompt messages, selected context contents, or API key. It can reveal internal
endpoint topology, model names, and capacity choices, so it is still operational metadata.

## Authority and precedence

Plan-backed execution deliberately has no configuration merge:

- The request comes only from the explicitly supplied validated request artifact.
- Endpoint, model, whole-second timeout, output ceiling, and estimated-input ceiling come only from
  the explicitly supplied validated plan.
- `SAMSARIX_API_KEY` is the only provider environment variable read by `execute --plan`.
- `SAMSARIX_API_BASE`, `SAMSARIX_MODEL`, `SAMSARIX_TIMEOUT`,
  `SAMSARIX_MAX_OUTPUT_TOKENS`, and `SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS` are ignored.
- Request/provider/budget override flags are refused instead of silently winning or losing.
- Plans must be files. They are never discovered automatically and cannot be read from stdin.

Inline `execute` remains available for ad hoc work without `--plan`; its documented CLI and
environment precedence is unchanged.

## Bounds and validation

- Plan files are strict UTF-8 JSON no larger than 64 KiB. NUL bytes, duplicate fields, unknown
  fields, unsupported versions, noncanonical values, and internal fingerprint drift fail closed.
- Remote endpoints require HTTPS. Plain HTTP is accepted only for localhost and loopback addresses.
- Timeout is an integer from 1 to 300 seconds; output is 1 to 32,768 tokens; estimated input is 1
  to 2,000,000 tokens.
- The default plan input ceiling is the supplied request's exact transparent estimate. Passing a
  larger limit permits reviewed growth only after producing a new request and therefore a new plan.
- `verify-plan --format json` emits a content-omitting linkage record with request counts, bytes,
  estimate, remaining budget, and executable settings. Its independent schema is version 1.

Export the portable contracts without a network request:

```bash
samsarix-codegen schema execution-plan > execution-plan-v1.schema.json
samsarix-codegen schema execution-plan-verification \
  > execution-plan-verification-v1.schema.json
samsarix-codegen schema execution-evidence \
  > execution-evidence-verification-v2.schema.json
```

JSON Schema validates the portable structure. The CLI or typed parser remains authoritative for
canonical fingerprints, request linkage, endpoint semantics, and budget enforcement.

## Trust limits

Plan and request fingerprints detect drift; they are not signatures. An actor who can replace a
plan can recompute its unkeyed fingerprint. `--expect-plan-fingerprint` adds protection only when
the approved value is held separately under stronger access control. An actor able to rewrite both
the plan and that expected value can still bypass the handoff.

The plan does not authenticate the endpoint, provider, model label, TLS operator, provider-reported
usage, or result. The result's plan fingerprint, optional policy fingerprint, and
`verify-execution` establish local structural linkage and deterministic limits, not signed provider
attestation: an actor who can rewrite every document can construct a new consistent chain. The
requested model is recorded separately from the provider-reported response model because proxies
and aliases can legitimately return a different label. Neither label proves which infrastructure
served the request. The evidence does not establish monetary cost because current price schedules
remain external. External access controls,
signing/attestation, endpoint governance, provider logs, and billing records remain the operator's
responsibility when those properties matter.

The checked-in [request](../examples/execution-request-v2.json),
[plan](../examples/execution-plan-v1.json), [synthetic result](../examples/execution-result-v2.json),
[policy](../examples/execution-evidence-policy-v1.json), and
[evidence](../examples/execution-evidence-v2.json) form one runnable policy-bound offline chain. The
test suite rebuilds the request from `examples/sample.py`, verifies all four inputs through the
public API and CLI, and requires the computed evidence to equal the checked-in record. The legacy
version 1 evidence and schema remain bundled for existing external consumers. No provider request
produced the explicitly labeled synthetic result. Create a new plan for every real request rather
than editing or reusing the fixture; reuse a team policy only while its exact fingerprint and rules
remain the intended approval.
