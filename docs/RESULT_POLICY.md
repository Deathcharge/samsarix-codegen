# Execution-result policy contract

Samsarix Codegen execution-result policy schema version `2` is a small, checked-in set of
deterministic gates for stored result envelopes. It keeps the version `1` metadata and usage gates
and adds bounded JSON-object shape checks for workflows that need machine-consumable output.
Developers and CI can apply the same reviewed rules without repeating shell flags, invoking a
second model, or relying on machine-local configuration.

## Document shape

```json
{
  "schema_version": 2,
  "expected_model": "model-a",
  "max_response_bytes": 100000,
  "max_prompt_tokens": 10000,
  "max_completion_tokens": 2000,
  "max_total_tokens": 12000,
  "response_format": "json-object",
  "required_json_keys": ["diagnosis", "evidence", "next_step"],
  "allowed_json_keys": ["diagnosis", "evidence", "next_step"],
  "json_key_types": {
    "diagnosis": "string",
    "evidence": "array",
    "next_step": "string"
  }
}
```

Only `schema_version` is structurally required, but at least one policy rule must also be present.
Unset rules must be omitted rather than set to `null`. Unknown and duplicate fields fail closed.

The metadata fields mean:

- `expected_model`: require an exact match to the canonical model label Samsarix requested. It does
  not gate the separate provider-reported response model.
- `max_response_bytes`: limit the response's actual UTF-8 byte count from 1 through 12 MiB.
- `max_prompt_tokens`, `max_completion_tokens`, and `max_total_tokens`: limit the corresponding
  provider-reported usage values. Each is a non-negative JSON-safe integer no greater than
  `9,007,199,254,740,991`.

Schema version `2` additionally supports:

- `response_format`: currently the exact value `json-object`; require a valid top-level JSON object.
- `required_json_keys`: require every listed top-level key.
- `allowed_json_keys`: reject any top-level key outside this allowlist.
- `json_key_types`: require each named top-level value to be `array`, `boolean`, `integer`, `null`,
  `number`, `object`, or `string`. A JSON integer satisfies `number`; the reverse is not true.

Required and typed keys must be present in `allowed_json_keys` when an allowlist is configured.
Key lists are mathematical sets for canonicalization, so their input order does not affect the
policy fingerprint. Every configured rule must pass. If a configured usage field is absent from
the result envelope, enforcement fails rather than treating the missing value as zero.

## Structural bounds and semantics

The structured-response gate parses at most 1 MiB and accepts at most 256 top-level keys. A policy
can name at most 64 unique keys per structural rule, and each key is limited to 256 UTF-8 bytes.
Duplicate object keys at any nesting level, non-finite numbers such as `NaN` or `Infinity`, invalid
JSON, and a non-object top level all fail closed.

This is intentionally a top-level shape contract, not a full JSON Schema evaluator. Nested values
are classified only as `object` or `array`; their internal shape is not recursively validated.
The result must still satisfy the response envelope's overall 12 MiB bound, but a structural rule
fails if the response exceeds its stricter 1 MiB parsing ceiling.

## Pin the exact policy

Validate a policy and emit its canonical fingerprint before a credential-bearing execution:

```bash
policy_fingerprint="$(samsarix-codegen fingerprint-policy result-policy.json)"
```

The fingerprint is `sha256:` plus the lowercase SHA-256 digest of the policy's validated JSON
object encoded as UTF-8 with keys sorted, no insignificant whitespace, and unescaped Unicode.
Input indentation and object field order therefore do not change the fingerprint. The schema
version and every configured rule do change it.

## Enforce during execution

Pass the explicit policy and its separately retained approval directly to `execute`:

```bash
samsarix-codegen execute request.json \
  --plan execution-plan.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --policy result-policy.json \
  --expect-policy-fingerprint "$policy_fingerprint" \
  --format json > result.json
```

The policy file, document shape, and optional expected fingerprint are validated before the
provider client is constructed. An explicitly selected malformed, missing-file, stdin-selected, or
fingerprint-mismatched policy therefore makes no provider request. After exactly one provider
response, Samsarix creates
the same normalized execution-result envelope, enforces every configured rule, and emits the
normal text or JSON response only if all rules pass. A post-response failure returns artifact exit
code `5`, leaves normal stdout empty, does not disclose the response through the policy error, and
never retries or calls a second model.

This is an output-admission gate, not a request-cost prevention mechanism. A rule can evaluate only
after the provider returned the response, so that single request may still be billable even when
the gate rejects it. Store a successful JSON result and use the offline evidence command below to
prove its linkage later. The same explicit execution gate is available for inline `execute`, but
the plan-backed form retains the stronger reviewed provider/budget handoff.

Use that approval with the full offline evidence gate:

```bash
samsarix-codegen verify-execution request.json execution-plan.json result.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --policy result-policy.json \
  --expect-policy-fingerprint "$policy_fingerprint" \
  --format json > execution-evidence.json
```

Evidence schema version `3` includes the policy fingerprint and exact approved rules only after the
request, plan, result, policy fingerprint, and every policy gate pass. When a structural rule
passes, evidence records only `json-object` and the top-level key count. Response-derived key names
and values are not emitted. With no `--policy`, the same command remains valid and emits
`"result_policy": null` and `"response_structure": null`. `--expect-policy-fingerprint` without
`--policy` is a configuration error, so a caller cannot silently omit an approved gate.

## Apply one checked-in policy

```bash
samsarix-codegen inspect-result result.json \
  --policy examples/structured-result-policy-v2.json \
  --format json > result-summary.json

samsarix-codegen verify-result request.json result.json \
  --policy examples/structured-result-policy-v2.json \
  --format json > verified-run.json
```

`--policy` is explicit and never discovered automatically. A policy path cannot be `-`, and one
policy file cannot be combined with `--expect-model` or any inline `--max-*-tokens` or
`--max-response-bytes` rule. Refusing to define override precedence keeps a checked-in review object
identical across developer machines and CI.

The file is read as bounded UTF-8 JSON and must be a regular file no larger than 64 KiB. Parsing and
enforcement are local and make no provider request. A malformed document or failed rule returns
artifact exit code `5`; a file-plus-inline option conflict returns configuration exit code `2`.
Neither failure path emits the normal inspection or verification record.

## Standalone schema and typed API

Export the latest bundled Draft 2020-12 schema without network access:

```bash
samsarix-codegen schema result-policy > execution-result-policy-v2.schema.json
```

Typed consumers can use the same contract:

```python
from samsarix_codegen import (
    ExecutionResultPolicy,
    fingerprint_execution_result_policy,
    parse_execution_result_policy,
    render_execution_result_policy,
    require_execution_result_policy_fingerprint,
)

policy = ExecutionResultPolicy(
    response_format="json-object",
    required_json_keys=("diagnosis", "next_step"),
    allowed_json_keys=("diagnosis", "next_step"),
    json_key_types=(("diagnosis", "string"), ("next_step", "string")),
    schema_version=2,
)
assert parse_execution_result_policy(render_execution_result_policy(policy)) == policy
fingerprint = fingerprint_execution_result_policy(policy)
assert require_execution_result_policy_fingerprint(policy, fingerprint) == fingerprint
```

The latest public selector exports version `2`; the version `1` schema and example remain bundled
for compatibility with existing policies. Version `1` accepts only metadata/usage fields and
rejects all structural fields. The checked-in schemas validate portable structure. The Samsarix
parser remains authoritative for duplicate-field detection, exact Unicode/model rules, bounded
reads, and cross-field semantics.

## Trust and product boundary

A policy file contains approved limits and key names, not credentials, prompts, source, or response
values. Key names and model labels can still reveal deployment choices and should be reviewed as
repository metadata.

The policy and its unkeyed fingerprint do not authenticate an approval, envelope, provider, model
label, or reported usage. Structural gates prove bounded machine-consumability only; they do not
prove that a response is correct, complete, safe, or high quality. They do not normalize provider
tokenizers, look up current pricing, execute returned code, validate a full recursive JSON Schema,
or call another model as a judge. Use signatures, access controls, provider-side billing records,
domain validation, and semantic evaluation tools when those stronger properties matter.
