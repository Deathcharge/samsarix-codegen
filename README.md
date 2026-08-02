# Samsarix Codegen

Samsarix Codegen is a read-only request compiler for coding models. It turns an instruction plus
explicit files or bounded standard input into a prompt you can read or a deterministic JSON
artifact you can inspect, approve, and execute later against an OpenAI-compatible endpoint.

It is for developers and CI maintainers who want reproducible AI requests without giving a model
repository-discovery, file-write, shell, or retry authority. Samsarix Codegen never edits files,
executes generated code, scans a repository automatically, or retries a paid request.

> **Status:** `0.2.0` release candidate. The offline review workflow, one-request execution path,
> and content-free provider conformance check are implemented and tested. The package has not been
> published to PyPI or run through the documented three-developer pilot.

## What makes it useful

The core workflow separates request construction from credential-bearing execution:

1. Select the only context the model may receive with repeated `--file` options, an explicitly
   invoked context manifest, or `--stdin-name`.
2. Compile a schema-versioned artifact containing the exact messages, context provenance, content
   hashes, and an approximate input-token estimate.
3. Validate and summarize it offline with `inspect`.
4. Record its canonical SHA-256 fingerprint as the approval object.
5. Send exactly those reviewed messages once with `execute --expect-fingerprint`.

This makes staged-change review, CI approval handoffs, selected-log triage, and reproducible
provider comparisons practical without a private Samsarix service or another repository.

## Install and try it offline

Prerequisite: Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
samsarix-codegen build "Explain the behavior and edge cases" `
  --task explain `
  --file examples/sample.py
```

On macOS or Linux, activate with `source .venv/bin/activate` and use `\` for shell continuation.
`build` defaults to a readable Markdown prompt and performs no network request.

For a repeatable project review, check in a versioned context manifest:

```json
{
  "schema_version": 1,
  "files": [
    "src/samsarix_codegen/context.py",
    "src/samsarix_codegen/prompt.py",
    "tests/test_context.py"
  ]
}
```

Then invoke it explicitly:

```bash
samsarix-codegen build "Review the context boundary" \
  --task review \
  --context-manifest examples/review-context-v1.json \
  --format json > context-review.json
```

Repeat `--context-manifest` to compose checked-in context sets, and add task-specific files with
`--file`. Samsarix never searches for manifests automatically. All manifests and selected files
must resolve inside the same `--root`; direct files appear first, followed by manifest entries in
argument and array order. The [context-manifest contract](docs/CONTEXT_MANIFEST.md) defines the
portable path rules, limits, and trust boundary.

## Build, inspect, and execute one reviewed artifact

PowerShell:

```powershell
git diff --staged | samsarix-codegen build "Review these staged changes" `
  --task review `
  --stdin-name staged.diff `
  --max-estimated-input-tokens 50000 `
  --format json > request.json

samsarix-codegen inspect request.json
samsarix-codegen inspect request.json --format markdown > exact-prompt.md
$fingerprint = samsarix-codegen inspect request.json --format fingerprint

$env:SAMSARIX_MODEL = "your-local-model"
samsarix-codegen execute request.json --expect-fingerprint $fingerprint
```

POSIX shell:

```bash
git diff --staged | samsarix-codegen build "Review these staged changes" \
  --task review \
  --stdin-name staged.diff \
  --max-estimated-input-tokens 50000 \
  --format json > request.json

samsarix-codegen inspect request.json
samsarix-codegen inspect request.json --format markdown > exact-prompt.md
fingerprint="$(samsarix-codegen inspect request.json --format fingerprint)"

export SAMSARIX_MODEL="your-local-model"
samsarix-codegen execute request.json --expect-fingerprint "$fingerprint"
```

The Markdown view is rendered from the validated artifact's exact stored messages; it does not
re-read the source files. The supplied [PowerShell](examples/review-staged.ps1) and
[POSIX](examples/review-staged.sh) scripts package this staged-diff workflow. `build` and `inspect`
are offline. `execute` validates the artifact and fingerprint before constructing a provider
client, then makes one non-streaming request.

The fingerprint detects drift; it is not a signature. Anyone able to replace an artifact can also
recompute its unkeyed hash. See the [request artifact contract](docs/REQUEST_ARTIFACT.md) before
using artifacts across trust boundaries.

Compare an earlier approval object with a rebuilt request without printing either prompt:

```bash
samsarix-codegen compare approved-request.json rebuilt-request.json
samsarix-codegen compare approved-request.json rebuilt-request.json --format json
```

The comparison reports changed zero-based message indexes, added/removed context records, byte and
estimated-token deltas, and both fingerprints. A changed context item appears as one removed record
and one added record so both content hashes remain visible.

## Other real workflows

Inspect a selected log excerpt without scanning or retaining the surrounding system:

```powershell
Get-Content .\app.log -Tail 300 | samsarix-codegen build `
  "Find the likely failure, supporting evidence, and next diagnostic" `
  --task debug `
  --stdin-name app.log `
  --max-context-bytes 200000 `
  --max-estimated-input-tokens 60000 `
  --format json > incident-request.json
```

Run the same artifact against different operator-selected endpoints and compare response envelopes:

```bash
SAMSARIX_MODEL=model-a SAMSARIX_API_BASE=https://provider-a.example/v1 \
  samsarix-codegen execute request.json --format json > result-a.json
SAMSARIX_MODEL=model-b SAMSARIX_API_BASE=https://provider-b.example/v1 \
  samsarix-codegen execute request.json --format json > result-b.json
samsarix-codegen verify-result request.json result-a.json
samsarix-codegen verify-result request.json result-a.json --format json > verified-run.json
samsarix-codegen inspect-result result-a.json
samsarix-codegen inspect-result result-a.json --format json > result-a-summary.json
samsarix-codegen compare-results result-a.json result-b.json
samsarix-codegen compare-results result-a.json result-b.json --format json
```

Both result files identify the common request fingerprint and omit the endpoint and API key.
`verify-result` strictly validates a concrete request and result together, fails unless their
fingerprints match, and emits content-omitting request metrics plus result metadata. It is a local
linkage check, not proof that a provider authored either file or received the request.
`inspect-result` strictly validates one envelope and reports its request fingerprint, model,
response character/UTF-8 byte counts and SHA-256 hash, and available usage without reproducing the
response. This makes a stored run fail-closed and loggable before a second run exists.
`compare-results` strictly validates both envelopes, refuses results with different request
fingerprints, and reports model names, response UTF-8 sizes and SHA-256 hashes, equality, and
available token-usage deltas without reproducing either response. It is an offline structural and
resource comparison, not a quality score or proof that a provider authored an envelope.

## Commands

| Command | Network | Purpose |
| --- | --- | --- |
| `build` | Never | Compile a readable Markdown prompt or schema-versioned JSON artifact |
| `inspect` | Never | Validate and summarize an artifact, or print only its fingerprint |
| `inspect-result` | Never | Validate and summarize one result without its response contents |
| `verify-result` | Never | Link one result to a supplied validated request without contents |
| `compare` | Never | Compare two validated artifacts without reproducing prompt contents |
| `compare-results` | Never | Compare same-request results without response contents |
| `schema` | Never | Print any bundled versioned contract JSON Schema |
| `provider-check` | Once | Send a tiny fixed request to test the supported provider wire contract |
| `execute` | Once | Execute the exact messages in a validated artifact |
| `run` | Once | Convenience path that builds and executes in one process |

`run --format json` and `execute --format json` return a stable result envelope with the request
fingerprint, model, response text, and provider usage when reported. Use
`samsarix-codegen <command> --help` for the complete option set.

## Machine-readable contracts

Export a self-contained [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) contract
without installing another tool or using the network:

```bash
samsarix-codegen schema request > request-artifact-v2.schema.json
samsarix-codegen schema result > execution-result-v1.schema.json
samsarix-codegen schema comparison > artifact-comparison-v1.schema.json
samsarix-codegen schema result-inspection > execution-result-inspection-v1.schema.json
samsarix-codegen schema result-verification > execution-result-verification-v1.schema.json
samsarix-codegen schema result-comparison > execution-result-comparison-v1.schema.json
samsarix-codegen schema provider-check > provider-check-v1.schema.json
samsarix-codegen schema context-manifest > context-manifest-v1.schema.json
```

The same files ship inside the typed Python package and are available through
`load_contract_schema()`. They let CI or a separate repository validate the public JSON shape
without importing Samsarix implementation code. JSON Schema validates structure; the CLI adds
semantic integrity checks such as recomputing fingerprints, estimates, and byte totals.

## Task guidance

`--task` adds focused guidance while the user's instruction remains authoritative:

| Task | Intended output |
| --- | --- |
| `generate` | Requested code, assumptions, and verification steps |
| `explain` | Behavior, inputs, outputs, edge cases, and trade-offs |
| `debug` | Plausible root cause, smallest fix, and regression tests |
| `refactor` | Behavior-preserving refactor with rationale |
| `tests` | Normal, boundary, and failure tests |
| `review` | Correctness, security, reliability, maintainability, and test gaps |

## Provider configuration

The default endpoint is `http://127.0.0.1:11434/v1`, a common local OpenAI-compatible shape. Start
your local service and name an installed model explicitly:

```bash
samsarix-codegen provider-check --model your-local-model
```

This explicit preflight sends exactly one request containing two fixed messages and no source
context. It is non-streaming, never retried, and capped at 64 output tokens by default (256 maximum),
so provider charges may apply. Text and JSON reports omit the endpoint, credential, and response
content. A pass establishes only that the selected endpoint/model satisfied the package's current
Chat Completions wire contract for that request; it is not a provider endorsement or quality test.

Then run a real request:

```bash
samsarix-codegen run "Write focused tests for this function" \
  --task tests \
  --file examples/sample.py \
  --model your-local-model \
  --max-output-tokens 1200
```

For a hosted provider, use HTTPS and put credentials only in the environment:

```powershell
$env:SAMSARIX_API_BASE = "https://provider.example/v1"
$env:SAMSARIX_MODEL = "provider-model-name"
$env:SAMSARIX_API_KEY = "your-provider-key"
samsarix-codegen run "Review this module" --task review `
  --file src/samsarix_codegen/provider.py
```

| Environment variable | CLI equivalent | Default |
| --- | --- | --- |
| `SAMSARIX_API_BASE` | `--endpoint` | `http://127.0.0.1:11434/v1` |
| `SAMSARIX_MODEL` | `--model` | none; required for `run` and `execute` |
| `SAMSARIX_API_KEY` | none by design | none |
| `SAMSARIX_TIMEOUT` | `--timeout` | `60` seconds |
| `SAMSARIX_MAX_OUTPUT_TOKENS` | `--max-output-tokens` | `1024` |
| `SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS` | `--max-estimated-input-tokens` | no additional cap |

Command-line values override environment-backed defaults. Samsarix Codegen does not load `.env`
files, persist credentials, or log request content. There is intentionally no `--api-key` option,
reducing accidental exposure in shell history and process listings.

## Input, reliability, and cost limits

- Only repeated `--file` paths, entries from explicitly named context manifests, and an explicitly
  named stdin stream are read, up to 20 total declared inputs.
- A context manifest is a strict UTF-8 JSON document of at most 64 KiB and 20 portable,
  forward-slash paths. Up to 20 manifests may be composed; manifests and their file entries stay
  inside the same `--root`.
- Files are resolved inside `--root`, deduplicated, and required to be regular UTF-8 text without
  NUL bytes.
- Total context defaults to 200,000 bytes and has a hard 5,000,000-byte ceiling.
- Instructions are limited to 20,000 characters; request artifacts and execution-result envelopes
  read by offline commands are limited to 12 MiB each.
- `--max-estimated-input-tokens` rejects a request before network access. The estimate is
  `ceil(total UTF-8 message bytes / 4)`, not provider billing data.
- Provider output defaults to 1,024 tokens and is capped at 32,768. Network timeouts range from 1
  to 300 seconds and default to 60.
- Requests are non-streaming, never automatically retried, and never follow HTTP redirects.
  Responses larger than 10 MiB fail.
- `provider-check` sends no selected context and has a separate 256-token hard output ceiling.
- Remote endpoints require HTTPS; plain HTTP is accepted only for localhost and loopback addresses.

Consult the selected provider's current pricing. Samsarix cannot calculate monetary cost without a
provider, model, and price schedule, so its enforceable controls are explicit context, an estimated
input gate, one-request behavior, timeout, and output cap.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Unexpected internal failure |
| `2` | Invalid command, budget, or provider configuration |
| `3` | Invalid, unsafe, or unreadable context input |
| `4` | Endpoint, HTTP, timeout, or response-contract failure |
| `5` | Invalid, unsupported, tampered, or unapproved artifact |
| `130` | Cancelled with `Ctrl+C` |

## Library API

The typed public API exposes request construction, artifact parsing/rendering, and the minimal
provider client:

```python
from samsarix_codegen import (
    ContractSchema,
    ContextManifest,
    PromptRequest,
    Task,
    build_messages,
    create_request_artifact,
    load_contract_schema,
    parse_context_manifest,
    render_context_manifest,
    render_request_artifact,
)

request = PromptRequest(task=Task.DEBUG, instruction="Find the likely failure")
artifact = create_request_artifact(build_messages(request), request.files)
print(render_request_artifact(artifact))
request_schema = load_contract_schema(ContractSchema.REQUEST)
manifest = ContextManifest(files=("src/app.py", "tests/test_app.py"))
assert parse_context_manifest(render_context_manifest(manifest)) == manifest
```

`parse_execution_result()`, `inspect_execution_result()`, `verify_execution_result()`, and
`compare_execution_results()` provide the same strict, content-omitting result metadata paths to
typed consumers. Unstable implementation helpers are not exported from `samsarix_codegen`.

## Development and package verification

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -ra
python -m build
```

CI runs these checks plus built-wheel request/result inspection, linkage verification, and
comparison, provider-check contract, and schema smoke tests on Python 3.10 and 3.14 across Ubuntu
and Windows. See
[CONTRIBUTING.md](CONTRIBUTING.md),
[SECURITY.md](SECURITY.md), [SUPPORT.md](SUPPORT.md), and the living
[productization record](docs/PRODUCTIZATION.md). The [three-developer pilot](docs/PILOT.md) defines
the remaining external usefulness gate and its privacy-preserving evidence record.

The [release runbook](docs/RELEASING.md) documents a non-publishing workflow dry run, exact
version/tag/changelog gates, SHA-256 manifests, provenance attestation, manually approved PyPI
Trusted Publishing, immutable-ready GitHub releases, verification, and rollback. No package is
published merely by running CI or manually dispatching that workflow.

## Architecture

```text
instruction + explicit files / explicit manifests / named stdin
                    |
                    v
          validated provider-neutral messages
                    |
          +---------+------------------+
          |                            |
          v                            v
 readable Markdown          deterministic JSON artifact
                                       |
                                       v
                           offline validation + approval
                                       |
                                       v
                         one bounded provider request
                                       |
                                       v
                           text or JSON result envelope
```

The package has no runtime dependencies. The standard-library network client implements only the
non-streaming OpenAI-compatible `/chat/completions` subset used by this workflow.

## Security and privacy

- Instructions and selected context leave the machine only through `run` or `execute`.
- Manifests contain file names rather than file contents, but can still reveal project structure;
  treat them as repository metadata.
- Artifacts contain the complete prompt and selected source/log content. Treat them with the same
  confidentiality and retention controls as their inputs.
- Artifact and context hashes detect drift but do not authenticate an author or reviewer.
- Result comparisons contain response hashes, which can confirm a guessed response even though
  response text is omitted; protect comparison files according to the result sensitivity.
- File contents are untrusted prompt data. Prompt injection cannot be eliminated; review every
  response.
- Model output may be incorrect or unsafe. Samsarix Codegen never executes, applies, or persists it.
- There is no telemetry, analytics, background process, automatic history, or retry loop.

Tool calling, image input, streaming, automatic edits, repository discovery, ignore/glob expansion,
sessions, signing, provider-specific Responses APIs, and provider endorsement are intentionally out
of scope for `0.2.0`. The [competitive strategy](docs/COMPETITIVE_STRATEGY.md) explains this boundary
and the evidence behind it.

## License, attribution, and support

Copyright 2026 Samsarix LLC. Licensed under the [Apache License 2.0](LICENSE).

Apache-2.0 preserves copyright and notice obligations for redistribution and includes an express
patent grant. It is permissive: downstream modifications do not have to be published. [NOTICE](NOTICE)
identifies Samsarix LLC, and [CITATION.cff](CITATION.cff) supplies citation metadata. The license
does not grant broader rights to use Samsarix branding.

For product and licensing questions, email `contact@samsarix.com`. For support or private security
reports, email `support@samsarix.com`.
