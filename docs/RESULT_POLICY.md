# Execution-result policy contract

Samsarix Codegen execution-result policy schema version `1` is a small, checked-in set of
deterministic limits for stored result envelopes. It lets developers and CI apply the same rules
without repeating shell flags or relying on machine-local configuration.

## Document shape

```json
{
  "schema_version": 1,
  "expected_model": "model-a",
  "max_response_bytes": 100000,
  "max_prompt_tokens": 10000,
  "max_completion_tokens": 2000,
  "max_total_tokens": 12000
}
```

Only `schema_version` is structurally required, but at least one policy rule must also be present.
Unset rules must be omitted rather than set to `null`. Unknown and duplicate fields fail closed.

The fields mean:

- `expected_model`: require an exact, canonical model-label match.
- `max_response_bytes`: limit the response's actual UTF-8 byte count from 1 through 12 MiB.
- `max_prompt_tokens`, `max_completion_tokens`, and `max_total_tokens`: limit the corresponding
  provider-reported usage values. Each is a non-negative JSON-safe integer no greater than
  `9,007,199,254,740,991`.

Every configured rule must pass. If a configured token field is absent from the result envelope,
enforcement fails rather than treating the missing value as zero.

## Apply one checked-in policy

```bash
samsarix-codegen inspect-result result.json \
  --policy examples/result-policy-v1.json \
  --format json > result-summary.json

samsarix-codegen verify-result request.json result.json \
  --policy examples/result-policy-v1.json \
  --format json > verified-run.json
```

`--policy` is explicit and never discovered automatically. A policy path cannot be `-`, and one
policy file cannot be combined with `--expect-model` or any inline `--max-*-tokens` or
`--max-response-bytes` rule. Refusing to define override precedence keeps a checked-in review object
identical across developer machines and CI.

The file is read as bounded UTF-8 JSON and must be a regular file no larger than 64 KiB. Parsing and
enforcement are local and make no provider request. A malformed document or failed rule returns
artifact exit code `5`; a file-plus-inline option conflict returns configuration exit code `2`.
Neither failure path emits the normal inspection/verification record.

## Standalone schema and typed API

Export the bundled Draft 2020-12 schema without network access:

```bash
samsarix-codegen schema result-policy > execution-result-policy-v1.schema.json
```

Typed consumers can use the same contract:

```python
from samsarix_codegen import (
    ExecutionResultPolicy,
    load_execution_result_policy,
    parse_execution_result_policy,
    render_execution_result_policy,
)

policy = ExecutionResultPolicy(expected_model="model-a", max_total_tokens=12000)
assert parse_execution_result_policy(render_execution_result_policy(policy)) == policy
assert load_execution_result_policy("examples/result-policy-v1.json").expected_model == "model-a"
```

The checked-in schema validates portable structure. The Samsarix parser remains authoritative for
duplicate-field detection, exact Unicode/model rules, bounded reads, and document semantics.

## Trust and product boundary

A policy file contains limits, not credentials, prompts, source, or responses. Nevertheless, the
model label can reveal deployment choices and should be reviewed as repository metadata.

The policy does not authenticate the envelope, provider, model label, or reported usage. It does not
normalize provider tokenizers, look up current pricing, evaluate correctness, or score response
quality. It is a deterministic local contract/cost-shape guard. Use signatures, access controls,
provider-side billing records, and semantic evaluation tools when those stronger properties matter.
