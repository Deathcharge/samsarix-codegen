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
schema validation + offline inspect + fingerprint approval
            |
            v
execute --expect-fingerprint
            |
            v
one bounded provider request
```

`build`, `inspect`, and `compare` never make a network request. `execute` does not read source
files; it sends the validated `messages` stored in the artifact.

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

- Request artifacts are limited to 12 MiB when read by `inspect` or `execute`.
- Context remains subject to the file-count and byte caps applied by `build`.
- `--max-estimated-input-tokens` can fail `build`, `run`, or `execute` before a network request.
- The estimate is deliberately approximate and is not provider billing data.
- Output tokens and request time remain independently bounded by provider options.

## Execution result JSON

`run --format json` and `execute --format json` produce:

```json
{
  "schema_version": 1,
  "request_fingerprint": "sha256:<...>",
  "model": "operator-selected-model",
  "response": {"text": "..."},
  "usage": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "total_tokens": null
  }
}
```

The endpoint and API key are intentionally absent. Usage values remain `null` when the provider does
not return valid non-negative integers.

## Offline comparison

`compare BASE TARGET` validates both artifacts and reports whether their fingerprints differ. Its
text and JSON forms contain both fingerprints, zero-based indexes of changed messages,
added/removed context metadata, and byte/token-estimate deltas. They intentionally omit message
contents.

A context item whose name is unchanged but whose content hash or byte size changed is reported as
one removed record and one added record. Duplicate metadata records are compared as a multiset in
their original order. Comparison schema version `1` is independent of request schema version `2`.

Both artifact paths cannot be `-` because a single stdin stream cannot supply two independently
bounded JSON documents.
