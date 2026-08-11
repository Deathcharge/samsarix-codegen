# Examples

`sample.py` is a small input for the offline quick start in the repository README.

`review-context-v1.json` is a runnable versioned context manifest. It selects the context loader,
prompt builder, and loader tests without scanning the repository:

```bash
samsarix-codegen build "Review the context boundary" \
  --task review \
  --context-manifest examples/review-context-v1.json \
  --format json
```

`result-policy-v1.json` is a reusable local/CI policy for a stored result envelope. It requires the
approved model and applies response and reported-token ceilings without reproducing the response:

```bash
samsarix-codegen verify-result request.json result.json \
  --policy examples/result-policy-v1.json \
  --format json
```

`structured-result-policy-v2.json` adds a bounded JSON-object contract: required and allowed
top-level keys plus their expected JSON value types. It remains an offline structural gate rather
than a correctness or semantic-quality score.

`review-request-v2.json`, `review-execution-result-v2.json`, `review-response-v1.json`,
`review-result-policy-v2.json`, and `review-report-v1.json` form a second zero-network journey for
source-located AI review output. The request uses `--task review-report` and explicitly selects
`sample.py`; the result is labeled synthetic and reports no plan, provider model, or usage. The
policy gates its top-level shape, while `export-review` validates every nested finding and requires
its path to be present in the request before rendering report JSON or SARIF 2.1.0:

```bash
samsarix-codegen verify-result \
  examples/review-request-v2.json \
  examples/review-execution-result-v2.json \
  --policy examples/review-result-policy-v2.json \
  --format json > review-verification.json
samsarix-codegen export-review \
  examples/review-request-v2.json \
  examples/review-execution-result-v2.json \
  --format json > generated-review-report.json
samsarix-codegen export-review \
  examples/review-request-v2.json \
  examples/review-execution-result-v2.json \
  --format sarif > generated-review.sarif
python -c "import json; assert json.load(open('generated-review-report.json')) == json.load(open('examples/review-report-v1.json'))"
```

The SARIF output contains model-generated text and paths and must be reviewed before an explicit
upload. See [`docs/REVIEW_REPORT.md`](../docs/REVIEW_REPORT.md) for the real execution-plan flow and
trust boundary.

`execution-request-v2.json`, `execution-plan-v2.json`, `structured-execution-result-v2.json`,
`structured-result-policy-v2.json`, and `execution-evidence-v3.json` form one fully linked,
policy-bound offline example. The request deterministically captures `sample.py`; the plan uses a
localhost placeholder; the explicitly labeled synthetic result reports no provider model or usage;
and the policy requires the exact requested model plus a bounded, typed JSON object. The repository pins that input to LF in
`.gitattributes` so the artifact is reproducible on Windows and POSIX checkouts. No command below
contacts that endpoint:

```bash
plan_fingerprint="$(samsarix-codegen verify-plan \
  examples/execution-request-v2.json examples/execution-plan-v2.json \
  --policy examples/structured-result-policy-v2.json \
  --format fingerprint)"
samsarix-codegen verify-execution \
  examples/execution-request-v2.json \
  examples/execution-plan-v2.json \
  examples/structured-execution-result-v2.json \
  --expect-plan-fingerprint "$plan_fingerprint" \
  --policy examples/structured-result-policy-v2.json \
  --format json > checked-evidence.json
python -c "import json; assert json.load(open('checked-evidence.json')) == json.load(open('examples/execution-evidence-v3.json'))"
```

This proves local structural integrity, canonical request/plan/policy fingerprints, linkage, model,
budget and policy consistency, bounded JSON-object shape, response hashing, and deterministic
content-omitting evidence rendering. Legacy `execution-evidence-v1.json` and
`execution-evidence-v2.json` remain compatibility fixtures, and `execution-plan-v1.json` preserves
the original plan parser/fingerprint contract. This is not a provider
attestation or a claim that the synthetic result came from a model. Rebuild every artifact for real
work instead of reusing the fixture's fingerprints.

`pilot-record-v1.json` is an intentionally incomplete, privacy-minimal pilot record. It uses only
bounded counts, enumerated observations, and safety booleans; it contains no prompt, response,
endpoint, person, path, or free-form field. The maintainer-side checker validates both its strict
shape and the cross-session decision gate:

```bash
python scripts/pilot_check.py examples/pilot-record-v1.json
# exit 1: valid example, but fewer than three participants and only one workflow
```

The preferred participant handoff is the workflow-built `evaluator-pilot-kit`, which supplies an
exact wheel and source commit plus a prefilled copy of this record. See `docs/PILOT.md`.

`review-staged.sh` and `review-staged.ps1` compile the current repository's staged diff into
`samsarix-review-request.json` (or a path passed as the first argument), validate it, and print its
fingerprint. They stop when no changes are staged and never contact a model endpoint.

```bash
sh examples/review-staged.sh review-request.json
samsarix-codegen inspect review-request.json
```

```powershell
.\examples\review-staged.ps1 -ArtifactPath review-request.json
samsarix-codegen inspect review-request.json
```

After reviewing the artifact, bind both request and runtime settings into an explicit plan:

```bash
fingerprint="$(samsarix-codegen inspect review-request.json --format fingerprint)"
samsarix-codegen create-plan review-request.json \
  --expect-fingerprint "$fingerprint" --model local-model > execution-plan.json
plan_fingerprint="$(samsarix-codegen verify-plan review-request.json execution-plan.json \
  --format fingerprint)"
samsarix-codegen execute review-request.json \
  --plan execution-plan.json --expect-plan-fingerprint "$plan_fingerprint" \
  --format json > result.json
samsarix-codegen verify-execution review-request.json execution-plan.json result.json \
  --expect-plan-fingerprint "$plan_fingerprint"
```

Artifacts contain the complete staged diff. Do not commit them unless that disclosure and retention
are intentional.
