# Structured review reports and SARIF export

Samsarix Codegen can turn one bounded coding-model response into a strict, source-located review
report and then export it as provenance-linked JSON or SARIF 2.1.0. This gives the read-only review
workflow a machine-consumable CI destination without granting repository discovery, file-write,
shell, upload, or retry authority.

The workflow has three separate contracts:

1. `--task review-report` tells the model to return review-response schema version 1.
2. An optional result-policy version 2 gate checks the top-level JSON object before `execute` emits
   it. [`examples/review-result-policy-v2.json`](../examples/review-result-policy-v2.json) is the
   checked-in example.
3. `export-review` re-parses the full nested response, verifies request/result linkage and selected
   paths, and emits either Samsarix review-report schema version 1 or SARIF 2.1.0.

The policy is an early admission gate; it does not replace the deeper `export-review` validation.

## Offline example

The repository includes a deterministic request, explicitly synthetic result, expected response,
policy, and provenance-linked report. These commands make no network request:

```bash
samsarix-codegen verify-result \
  examples/review-request-v2.json \
  examples/review-execution-result-v2.json \
  --policy examples/review-result-policy-v2.json \
  --format json > review-result-verification.json

samsarix-codegen export-review \
  examples/review-request-v2.json \
  examples/review-execution-result-v2.json \
  --format json > review-report.json

samsarix-codegen export-review \
  examples/review-request-v2.json \
  examples/review-execution-result-v2.json \
  --format sarif > review.sarif
```

The first export must equal [`examples/review-report-v1.json`](../examples/review-report-v1.json).
The result label is `synthetic-review-fixture`, its plan fingerprint is null, and its provider model
and token usage are absent. It proves deterministic local mechanics, not model quality or provider
execution.

## Build a real review request

Use explicit files or an explicitly invoked context manifest. Source locations in the response can
refer only to those exact context paths:

```bash
samsarix-codegen build \
  "Review this component. Report only concrete, source-located issues." \
  --task review-report \
  --context-manifest examples/review-context-v1.json \
  --max-estimated-input-tokens 50000 \
  --format json > review-request.json
```

For a credential-separated run, create a plan that binds the review policy, execute it once, retain
the result, and verify the complete chain before export:

```bash
request_fingerprint="$(samsarix-codegen inspect review-request.json --format fingerprint)"
policy_fingerprint="$(samsarix-codegen fingerprint-policy review-result-policy.json)"
samsarix-codegen create-plan review-request.json \
  --expect-fingerprint "$request_fingerprint" \
  --model your-model \
  --max-output-tokens 1600 \
  --max-estimated-input-tokens 50000 \
  --policy review-result-policy.json \
  --expect-policy-fingerprint "$policy_fingerprint" > review-plan.json
plan_fingerprint="$(samsarix-codegen verify-plan \
  review-request.json review-plan.json \
  --policy review-result-policy.json \
  --format fingerprint)"
samsarix-codegen execute review-request.json \
  --plan review-plan.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --policy review-result-policy.json \
  --format json > review-result.json
samsarix-codegen verify-execution \
  review-request.json review-plan.json review-result.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --policy review-result-policy.json \
  --format json > review-evidence.json
samsarix-codegen export-review \
  review-request.json review-result.json \
  --expect-fingerprint "$request_fingerprint" \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --format sarif > review.sarif
```

Only `execute` contacts the configured provider, exactly once. `build`, `inspect`, plan creation and
verification, evidence verification, policy fingerprinting, and both exports are offline.

## Review-response contract

Export the provider-facing contract with:

```bash
samsarix-codegen schema review-response > review-response-v1.schema.json
```

The response is one JSON object with exactly:

- `schema_version`: integer `1`;
- `summary`: non-empty text, at most 4,000 characters;
- `findings`: at most 100 unique findings.

Each finding has exactly:

- `category`: `correctness`, `security`, `reliability`, `maintainability`, or `testing`;
- `severity`: `error`, `warning`, or `note`;
- `title`: one non-empty line, at most 200 characters;
- `message`: non-empty text, at most 4,000 characters;
- `path`: a canonical root-relative POSIX path, at most 4,096 characters;
- `start_line` and `end_line`: integers from 1 through 10,000,000, with the end not before the
  start.

The parser also rejects duplicate JSON fields at any depth, non-finite numbers, binary or invalid
UTF-8 input, unsupported fields, duplicate findings, control characters, absolute paths,
backslashes, URI/drive prefixes, dot segments, and parent traversal. The full response is bounded
to 1 MiB.

`export-review` then requires every finding path to equal a context name in the validated request
artifact. It does not re-read the worktree or infer paths. It validates line-number bounds and
ordering but cannot prove that a cited line still exists after source drift; retain and compare the
request fingerprint and run the export against the reviewed source revision.

## Provenance-linked report

Export its self-contained schema with:

```bash
samsarix-codegen schema review-report > review-report-v1.schema.json
```

The JSON report carries the exact request fingerprint, nullable reviewed-plan fingerprint, SHA-256
of the result response text, and normalized review response. The hashes detect drift but are not
signatures or provider attestations. Anyone who can replace every artifact can recompute them.

## SARIF 2.1.0

SARIF export follows the OASIS 2.1.0 result/rule/location structure and the subset documented by
GitHub code scanning. Every finding maps to one stable category rule, one `error`, `warning`, or
`note` result, and one relative file/line location. Rules are marked `ai-generated` with `low`
precision, and each help message requires developer verification. Samsarix does not invent a
security score.

The SARIF run properties retain the request, plan, and response fingerprints plus the review
summary. Samsarix deliberately omits `partialFingerprints`: GitHub's `upload-sarif` action can
calculate them against the actual checked-out source, while a locally invented line hash could
misidentify alerts.

Uploading is an explicit CI-owner action outside Samsarix Codegen. A minimal GitHub Actions step is:

```yaml
permissions:
  contents: read
  security-events: write

steps:
  - uses: actions/checkout@v6
  - name: Upload reviewed SARIF
    uses: github/codeql-action/upload-sarif@v4
    with:
      sarif_file: review.sarif
      category: samsarix-ai-review
```

GitHub documents code scanning for public repositories and for eligible organization-owned private
or internal repositories with GitHub Code Security enabled. Check current availability and pin
third-party actions to reviewed commit SHAs in a production workflow:

- <https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file>
- <https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support-for-code-scanning>
- <https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html>

## Privacy and trust boundary

Review JSON and SARIF are not content-omitting evidence. They intentionally contain model-generated
summaries, titles, messages, file paths, and line ranges. Treat them as potentially sensitive and
untrusted, review retention and upload destinations, and never execute or interpolate their values
as commands. Use `verify-result` or `verify-execution` when ordinary logs should retain only hashes,
sizes, budgets, and linkage metadata.

Structured conformance does not establish correctness, severity, exploitability, source authorship,
provider authenticity, or adequate test coverage. A passing export means only that the response is
bounded, structurally valid, linked to the supplied result/request, and cites explicitly selected
paths. A developer remains responsible for reproducing and triaging every finding.

The typed public API exposes `ReviewFinding`, `ReviewResponse`, `ReviewReport`,
`parse_review_response()`, `verify_review_result()`, `render_review_report()`, and
`render_review_sarif()`.
