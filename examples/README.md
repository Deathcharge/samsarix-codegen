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

`execution-plan-v1.json` is a credential-free example of the versioned provider-settings approval
contract. Its request fingerprint is a placeholder; generate a linked plan for a real artifact:

```bash
samsarix-codegen create-plan request.json \
  --model local-model \
  --max-estimated-input-tokens 50000 > execution-plan.json
samsarix-codegen verify-plan request.json execution-plan.json
```

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
  --plan execution-plan.json --expect-plan-fingerprint "$plan_fingerprint"
```

Artifacts contain the complete staged diff. Do not commit them unless that disclosure and retention
are intentional.
