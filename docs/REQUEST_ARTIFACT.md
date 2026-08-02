# Request artifact contract

Samsarix Codegen `0.2` introduces a deterministic JSON request artifact for separating prompt
construction and review from provider execution.

## Lifecycle

```text
explicit files / bounded stdin
            |
            v
         build --format json
            |
            v
schema validation + offline inspect + request fingerprint approval
            |
            v
create-plan + offline plan verification/approval
            |
            v
execute --plan -> one bounded provider request
            |
            v
plan-bound result JSON -> offline verify-execution
            |
            +-> verify-result / inspect-result / compare-results
```

`build`, `inspect`, `create-plan`, `verify-plan`, `verify-execution`, `inspect-result`,
`verify-result`, `compare`, and `compare-results` never make a network request. `execute` does not
read source files; it sends the
validated `messages` stored in the artifact. The [execution-plan contract](EXECUTION_PLAN.md)
defines how endpoint, model, timeout, input ceiling, and output ceiling can join the same approval
handoff without storing a credential or prompt contents in the plan.

`inspect --format markdown` renders those exact stored messages for human review after validation;
it does not rebuild them from files. Because that view contains the full prompt, handle it with the
same confidentiality controls as the JSON artifact.

## Schema version 2

```json
{
  "schema_version": 2,
  "request_fingerprint": "sha256:<64 lowercase hex characters>",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "context": {
    "total_bytes": 123,
    "items": [
      {
        "name": "stdin:staged.diff",
        "bytes": 123,
        "content_sha256": "sha256:<64 lowercase hex characters>"
      }
    ]
  },
  "estimate": {
    "input_tokens": 456,
    "method": "ceil(total UTF-8 message bytes / 4)"
  }
}
```

Unknown schema versions, missing or extra fields, invalid roles, inconsistent byte totals, stale
estimates, malformed digests, oversized artifacts, and fingerprint mismatches fail closed with exit
code `5`.

## Determinism and fingerprints

The request fingerprint is SHA-256 over canonical JSON containing `schema_version`, `messages`,
`context`, and `estimate`, before the fingerprint field is added. Canonical JSON uses sorted keys,
UTF-8, and compact separators. The same ordered inputs and instruction produce the same artifact and
fingerprint.

Each `content_sha256` covers the normalized UTF-8 text included in the message. A UTF-8 byte-order
mark is removed during validated decoding, so this digest is intentionally named as a content hash
rather than a hash of the original file bytes.

The fingerprint detects accidental drift and can be pinned by an approval system. It is **not a
digital signature or authenticity proof**: anyone who can modify an artifact can also recompute an
unkeyed hash. Use external access controls or signing when authenticity is required.

## Size and budget controls

- Request artifacts and execution-result envelopes are each limited to 12 MiB when read by offline
  validation commands.
- Context remains subject to the file-count and byte caps applied by `build`.
- `--max-estimated-input-tokens` can fail `build`, `run`, or `execute` before a network request.
- An execution plan persists the reviewed estimated-input ceiling alongside provider settings;
  plan-backed execution refuses request/provider/budget overrides.
- The estimate is deliberately approximate and is not provider billing data.
- Output tokens and request time remain independently bounded by provider options.

## Execution result JSON

`run --format json` and `execute --format json` produce:

```json
{
  "schema_version": 2,
  "request_fingerprint": "sha256:<...>",
  "plan_fingerprint": "sha256:<... or null>",
  "model": "operator-selected-model",
  "response_model": "provider-reported-model-or-null",
  "response": {"text": "..."},
  "usage": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "total_tokens": null
  }
}
```

The endpoint and API key are intentionally absent. `model` is the model label requested by
Samsarix; `response_model` is the distinct model label returned by the provider when present.
Plan-backed execution records the validated execution-plan fingerprint; inline `run` or `execute`
records `null`. Usage values remain `null` when the provider does not return valid non-negative
integers. `parse_execution_result()`, `inspect-result`,
`verify-result`, and `compare-results` enforce the exact fields, schema version, fingerprint syntax,
canonical model label, non-empty UTF-8 response, usage types, and size limit before emitting
metadata or comparing. The parser accepts legacy schema version 1 and represents its absent plan
and response-model fields as `null`; all newly rendered envelopes use version 2.

## Offline request comparison

`compare BASE TARGET` validates both artifacts and reports whether their fingerprints differ. Its
text and JSON forms contain both fingerprints, zero-based indexes of changed messages,
added/removed context metadata, and byte/token-estimate deltas. They intentionally omit message
contents.

A context item whose name is unchanged but whose content hash or byte size changed is reported as
one removed record and one added record. Duplicate metadata records are compared as a multiset in
their original order. Comparison schema version `1` is independent of request schema version `2`.

Both artifact paths cannot be `-` because a single stdin stream cannot supply two independently
bounded JSON documents.

## Offline result inspection and comparison

`verify-execution REQUEST PLAN RESULT` performs the strongest local offline check. It recomputes
and validates the request and plan fingerprints, verifies their linkage and estimated-input
budget, requires the result to record that exact plan fingerprint and requested model, and rejects
provider-reported completion usage above the plan's output ceiling. Its text and JSON forms omit
prompt and response contents while retaining the endpoint, requested and response model labels,
request metrics, budgets, usage, response size, and response SHA-256. The plan must be an explicit
file, and at most one of request/result may be `-`.

This verification shows that the three local documents are internally consistent. The result and
hashes are not signed, and the requested endpoint/model are client configuration rather than
independent proof of the infrastructure that handled the call. Anyone able to rewrite all files
can construct another consistent chain. Use separately protected approval fingerprints,
signatures/attestations, provider logs, or billing records when those properties matter.

`verify-result REQUEST RESULT` strictly validates both bounded envelopes and fails unless the
result's request fingerprint matches the recomputed fingerprint of the supplied request artifact.
Its text and JSON forms emit the common fingerprint, request message/context counts and byte/token
estimate, and the result metadata described below. They reproduce neither prompt nor response
contents. At most one input may be `-` because one stdin stream cannot supply two bounded documents.

This establishes local structural linkage to a concrete reviewed artifact. It does not prove that a
provider created the result, received that request, or reported authentic usage; anyone able to
rewrite the files can recompute unkeyed hashes. Use external access controls or signatures when
authenticity is required.

`inspect-result RESULT` validates one execution-result envelope and emits content-omitting metadata
in text or JSON. It reports the linked request and optional plan fingerprints, requested and
provider-reported models, response
character/UTF-8 byte counts and SHA-256 hash, and provider usage when present. This supports
fail-closed CI archiving and diagnostics even when there is no second run to compare. Neither form
reproduces the response body.

The inspection proves only that the stored envelope satisfies the local contract and that its
metadata was derived from that envelope. It does not authenticate a provider, establish response
quality, or make the unkeyed hashes signatures. A response hash can confirm a guessed response, so
inspection records still require handling appropriate to the underlying result.

### Post-result policy gates

`inspect-result` and `verify-result` accept the same optional deterministic policy flags:

- `--expect-model MODEL` requires an exact model-label match.
- `--max-response-bytes BYTES` limits the response's actual UTF-8 byte count.
- `--max-prompt-tokens`, `--max-completion-tokens`, and `--max-total-tokens` limit the corresponding
  provider-reported usage fields.

For repeatable team/CI rules, pass one explicit versioned JSON file with
`--policy PATH`. The [execution-result policy contract](RESULT_POLICY.md) is bounded, strict,
schema-exportable, and independently parseable. It requires at least one active rule and rejects
unknown, duplicate, or null fields. File rules cannot be mixed with inline policy flags, so there is
no hidden override order.

Every configured rule must pass before the command emits its normal inspection or verification
record. A configured token ceiling fails closed when the provider omitted that field. The gates are
local, make no network request, preserve the existing content-omitting output contracts, and return
artifact exit code `5` on rejection. They do not authenticate model labels or usage, normalize
tokenizers between providers, estimate price, or evaluate response correctness or quality.

`compare-results BASE TARGET` validates two execution-result envelopes and fails unless they
reference the same request fingerprint. Its text and JSON forms report the common fingerprint,
whether plan, requested-model, or response-model labels changed, whether response hashes match,
response character/UTF-8 byte counts,
both response SHA-256 hashes, and token-usage deltas when both providers reported the corresponding
value. Neither response body is reproduced.

The command establishes structural comparability: both envelopes claim the same reviewed request
and expose content-omitting size, identity, and usage evidence. It does not score quality,
authenticate a provider, prove that a provider received the request, or normalize provider
tokenization. Result JSON and its hashes are not signatures. A response hash can confirm a guessed
response, so comparison files still require handling appropriate to the underlying result.

Both result paths cannot be `-` because a single stdin stream cannot supply two independently
bounded JSON documents. Result-comparison schema version `2` is independent of execution-result
schema version `2` and request schema version `2`.

## Machine-readable contract schemas

The package bundles self-contained
[JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) files for every JSON contract:

| CLI name | Contract | Bundled file |
| --- | --- | --- |
| `request` | Request artifact schema version 2 | `src/samsarix_codegen/schemas/request-artifact-v2.schema.json` |
| `result` | Execution result schema version 2 | `src/samsarix_codegen/schemas/execution-result-v2.schema.json` |
| `comparison` | Artifact comparison schema version 1 | `src/samsarix_codegen/schemas/artifact-comparison-v1.schema.json` |
| `result-inspection` | Execution-result inspection schema version 2 | `src/samsarix_codegen/schemas/execution-result-inspection-v2.schema.json` |
| `result-verification` | Request/result verification schema version 2 | `src/samsarix_codegen/schemas/execution-result-verification-v2.schema.json` |
| `result-comparison` | Execution-result comparison schema version 2 | `src/samsarix_codegen/schemas/execution-result-comparison-v2.schema.json` |
| `provider-check` | Provider-check report schema version 1 | `src/samsarix_codegen/schemas/provider-check-v1.schema.json` |
| `context-manifest` | Explicit context manifest schema version 1 | `src/samsarix_codegen/schemas/context-manifest-v1.schema.json` |
| `result-policy` | Execution-result policy schema version 1 | `src/samsarix_codegen/schemas/execution-result-policy-v1.schema.json` |
| `execution-plan` | Credential-free execution plan schema version 1 | `src/samsarix_codegen/schemas/execution-plan-v1.schema.json` |
| `execution-plan-verification` | Request/plan verification schema version 1 | `src/samsarix_codegen/schemas/execution-plan-verification-v1.schema.json` |
| `execution-evidence` | Request/plan/result evidence schema version 1 | `src/samsarix_codegen/schemas/execution-evidence-verification-v1.schema.json` |

Use `samsarix-codegen schema NAME` to print one without a network request, or
`load_contract_schema()` from Python. The files are package data in both the sdist and wheel.

JSON Schema checks portable structure, types, bounds, required fields, and digest syntax. It cannot
prove semantic relationships such as whether a fingerprint matches canonical content, context
bytes sum correctly, estimates match messages, or deltas match their base/target values. Use
`inspect`, `inspect-result`, `verify-result`, `verify-execution`, `compare`, `compare-results`, or
the corresponding Python parser for those semantic checks. Context manifests are input contracts rather than
request/result envelopes; their [separate contract](CONTEXT_MANIFEST.md) defines the additional
runtime path and containment rules. Result policies are explicitly selected input contracts; their
[separate contract](RESULT_POLICY.md) defines rule enforcement and trust limits. Execution plans
are explicitly selected input contracts; their [separate contract](EXECUTION_PLAN.md) defines
authority, precedence, linkage, and trust limits.

The checked-in [result](../examples/execution-result-v2.json) and
[execution-evidence](../examples/execution-evidence-v1.json) examples are mutually consistent and
validated against the bundled schemas in the test suite. They use placeholder fingerprints and
must not be treated as approval records for a real request.
