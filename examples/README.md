# Examples

`sample.py` is a small input for the offline quick start in the repository README.

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

After reviewing the artifact, configure a model and use the fingerprint as an explicit approval:

```bash
fingerprint="$(samsarix-codegen inspect review-request.json --format fingerprint)"
samsarix-codegen execute review-request.json --expect-fingerprint "$fingerprint" --model local-model
```

Artifacts contain the complete staged diff. Do not commit them unless that disclosure and retention
are intentional.
