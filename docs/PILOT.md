# Three-developer pilot

This protocol tests whether Samsarix Codegen's review-first workflow is useful to people other than
its author. Run it against one exact wheel. Do not copy prompts, source, logs, model responses,
credentials, endpoint URLs, or request artifacts into the pilot record.

## Entry criteria

- Recruit three developers who did not implement the feature being evaluated.
- Use the same wheel digest and commit for all sessions.
- Use non-production code or a repository each participant is authorized to share with their chosen
  model provider.
- Tell participants that request artifacts contain the complete selected context and must receive
  the same access and retention controls as that context.
- Do not enable screen recording, telemetry, shell-history collection, or automatic artifact upload.

Record the wheel before the first session:

```powershell
python -m build
Get-FileHash .\dist\samsarix_codegen-0.2.0-py3-none-any.whl -Algorithm SHA256
python -m pip install --force-reinstall --no-deps .\dist\samsarix_codegen-0.2.0-py3-none-any.whl
samsarix-codegen --version
```

On macOS or Linux, use `sha256sum dist/samsarix_codegen-0.2.0-py3-none-any.whl`.

## Optional provider preflight

Participants who intend to execute an artifact should first check the exact endpoint/model pair they
will use:

```powershell
$env:SAMSARIX_API_BASE = "https://provider.example/v1"
$env:SAMSARIX_MODEL = "provider-model"
$env:SAMSARIX_API_KEY = "provider-key"
samsarix-codegen provider-check --format json > provider-check.json
samsarix-codegen schema provider-check > provider-check-v1.schema.json
```

`provider-check` is an explicit network action. It sends one non-streaming request with two fixed
messages, no source context, no tools, no retry, and a 64-token output cap by default. Provider
charges may apply. Its report omits the endpoint, credential, and response text.

A passing report demonstrates only that this endpoint/model returned non-empty text through the
wire contract used by this package at that time. It is not a Samsarix endorsement, uptime promise,
quality evaluation, or guarantee that every model or provider feature is compatible.

## Session A: staged-change review

Each participant completes this task once with a real, non-sensitive staged diff:

```powershell
git diff --staged | samsarix-codegen build "Review these staged changes" `
  --task review `
  --stdin-name staged.diff `
  --max-estimated-input-tokens 50000 `
  --format json > request.json

samsarix-codegen inspect request.json
samsarix-codegen inspect request.json --format markdown > exact-prompt.md
$fingerprint = samsarix-codegen inspect request.json --format fingerprint
```

The participant confirms that the exact prompt contains only the intended diff. If provider access
is approved, they may run:

```powershell
samsarix-codegen execute request.json --expect-fingerprint $fingerprint --format json > result.json
```

If the participant changes the instruction or diff, rebuild to `revised-request.json` and use
`samsarix-codegen compare request.json revised-request.json` before approving the new fingerprint.

## Session B: selected-log triage

At least one participant also completes this task using a scrubbed, non-production log excerpt:

```powershell
Get-Content .\app.log -Tail 300 | samsarix-codegen build `
  "Find the likely failure, supporting evidence, and next diagnostic" `
  --task debug `
  --stdin-name app.log `
  --max-context-bytes 200000 `
  --max-estimated-input-tokens 60000 `
  --format json > incident-request.json

samsarix-codegen inspect incident-request.json
samsarix-codegen inspect incident-request.json --format markdown > exact-incident-prompt.md
```

Stop before execution if the exact prompt contains a secret, personal data, or context that the
selected provider is not authorized to receive.

## Results record

Store one row per session using only these fields:

| Field | Allowed value |
| --- | --- |
| `pilot_id` | Random participant label; no name or email |
| `wheel_sha256` | Exact wheel digest |
| `commit` | Exact source commit |
| `platform` | OS family and Python version |
| `workflow` | `staged-review` or `log-triage` |
| `provider_mode` | `offline-only`, `local`, or `hosted`; no endpoint or account name |
| `provider_check` | `not-run`, `passed`, or failure exit code |
| `context_items` | Count from offline inspection |
| `context_bytes` | Total from offline inspection |
| `estimated_input_tokens` | Estimate from offline inspection |
| `completion_stage` | Last successful command |
| `exit_code` | First unexpected exit code, or `0` |
| `review_minutes` | Participant's rounded estimate |
| `clarity_score` | 1–5 after viewing the exact prompt |
| `usefulness_score` | 1–5 after the workflow |
| `reuse` | `yes`, `maybe`, or `no` |
| `friction` | Short scrubbed note with no code, logs, paths, response text, or secrets |

Delete local request/result files after the participant's normal retention period. A result row must
never contain prompt text, content hashes copied from private repositories, model output, API usage
account identifiers, credentials, or exact endpoint URLs.

## Decision gate

Call the pilot complete only when all of these are true:

1. Three developers complete artifact build, exact-prompt inspection, and fingerprint capture from
   the same wheel digest.
2. Both workflows are exercised, including at least one selected-log session.
3. Every executed session uses fingerprint-pinned `execute`; provider failures are retained as
   failures rather than rerun until a pass appears.
4. At least two participants score clarity and usefulness at 4 or higher and answer `yes` or `maybe`
   to reuse.
5. No session reads an unintended file, sends unreviewed context, exposes a credential, or requires
   Samsarix to collect source, prompt, response, or telemetry data.

If a safety condition fails, stop the pilot and fix the boundary before recruiting more users. If
the usefulness threshold fails, preserve the result and revisit the product wedge rather than
expanding into autonomous edits or repository discovery without evidence.
