# Three-developer pilot

This protocol tests whether Samsarix Codegen's review-first workflow is useful to people other than
its author. Run it against one exact wheel. The coordinator keeps one strict JSON record containing
only bounded counts, enumerated observations, and safety outcomes. Do not copy prompts, source,
logs, model responses, credentials, endpoint URLs, request artifacts, names, emails, or free-form
notes into that record.

## Entry criteria

- Recruit three developers who did not implement the feature being evaluated.
- Use the same wheel digest and commit for all sessions.
- Use non-production code or a repository each participant is authorized to share with their chosen
  model provider.
- Tell participants that request artifacts contain the complete selected context and must receive
  the same access and retention controls as that context.
- Do not enable screen recording, telemetry, shell-history collection, or automatic artifact upload.
- Give each participant a random identifier matching `pilot-` plus 12 lowercase hexadecimal
  characters. Do not retain an identifier-to-person lookup in the pilot record.

Prefer the `evaluator-pilot-kit` artifact from one successful manual release-workflow run. It
contains the exact wheel, this protocol, both record/decision schemas, the record checker, a
prefilled record, and its own strict manifest and checksums. The coordinator should authenticate
the outer ZIP before extraction, then run the bundled verifier:

```powershell
$run = 123456789 # successful release.yml workflow run on the chosen commit
$download = Join-Path $PWD "pilot-kit-download"
New-Item -ItemType Directory -Path $download -ErrorAction Stop | Out-Null
gh run download $run --repo Deathcharge/samsarix-codegen `
  --name evaluator-pilot-kit --dir $download
$kits = @(Get-ChildItem -LiteralPath $download -Filter 'samsarix-codegen-pilot-kit-*.zip')
if ($kits.Count -ne 1) { throw "Expected exactly one downloaded pilot-kit ZIP." }
$kit = $kits[0]
gh attestation verify $kit.FullName --repo Deathcharge/samsarix-codegen
Expand-Archive -LiteralPath $kit.FullName -DestinationPath $download
$roots = @(Get-ChildItem -LiteralPath $download -Directory `
  | Where-Object Name -Like 'samsarix-codegen-pilot-kit-*')
if ($roots.Count -ne 1) { throw "Expected exactly one extracted pilot-kit directory." }
$root = $roots[0]
Push-Location $root.FullName
python scripts/pilot_bundle.py verify-directory .
Get-Content PILOT-START.md
Pop-Location
```

Require both verification commands to exit `0`. GitHub's attestation links the ZIP to its source
repository, commit, event, and build workflow; it is provenance evidence, not a guarantee that the
software is safe. The bundled verifier independently checks the expected file set, strict
manifest, checksums, wheel/commit linkage, and prefilled record. See GitHub's
[attestation guidance](https://docs.github.com/en/actions/concepts/security/artifact-attestations).

If the release workflow is unavailable, the coordinator may instead build from a clean checkout
and record the wheel before the first session:

```powershell
$dirty = git status --porcelain
if ($dirty) { throw "Build the pilot wheel from a clean worktree." }
git rev-parse HEAD
python -m build
Get-FileHash .\dist\samsarix_codegen-0.2.0-py3-none-any.whl -Algorithm SHA256
python -m pip install --force-reinstall --no-deps .\dist\samsarix_codegen-0.2.0-py3-none-any.whl
samsarix-codegen --version
samsarix-codegen self-check --format json > self-check.json
if ($LASTEXITCODE -ne 0) { throw "The installed package self-check failed." }
```

For either route, the installed-wheel self-check must exit `0` and report `status: passed`,
`network.attempted: false`, and
`network.provider_called: false` before recruiting participants. It validates the installed
package's bundled contracts and synthetic evidence chain; it does not validate a provider or the
participant's project. Delete `self-check.json` after confirming it unless normal release evidence
retention requires it.

The kit's `PILOT-START.md` supplies the exact install command and has already placed the commit and
wheel digest in `pilot-record.json`. For a source build, copy the printed commit with the wheel
digest. On macOS or Linux, require
`test -z "$(git status --porcelain)"`, print `git rev-parse HEAD`, and use
`sha256sum dist/samsarix_codegen-0.2.0-py3-none-any.whl`.

## Choose the reviewed provider settings

Before either workflow, choose the credential-free settings that will be reviewed in its execution
plan. An offline-only participant can use the non-routable intent of this local placeholder and must
stop before execution:

```powershell
$pilotEndpoint = "http://127.0.0.1:11434/v1"
$pilotModel = "offline-pilot-model"
```

A participant approved to use a local or hosted provider substitutes that exact endpoint and model.
Do not put either value in the pilot results record. Creating and verifying a plan is offline; the
endpoint is contacted only by `provider-check` or `execute`.

## Optional provider preflight

After reviewing a session's request and execution plan, participants who intend to execute should
check the exact endpoint/model pair before sending the reviewed request:

```powershell
$env:SAMSARIX_API_BASE = $pilotEndpoint
$env:SAMSARIX_MODEL = $pilotModel
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

Each session's `provider_check` object records only a preflight attempted as part of that session.
If one passing preflight is reused for a second workflow, record the second session's status as
`not-run` rather than copying the earlier passing outcome.

## Session A: staged-change review

Each participant completes this task once with a real, non-sensitive staged diff:

```powershell
git diff --staged | samsarix-codegen build "Review these staged changes" `
  --task review `
  --stdin-name staged.diff `
  --max-estimated-input-tokens 50000 `
  --format json > request.json

samsarix-codegen inspect request.json
samsarix-codegen inspect request.json --format markdown
$fingerprint = samsarix-codegen inspect request.json --format fingerprint

samsarix-codegen create-plan request.json `
  --expect-fingerprint $fingerprint `
  --endpoint $pilotEndpoint `
  --model $pilotModel `
  --max-output-tokens 1200 `
  --max-estimated-input-tokens 50000 > execution-plan.json

$planFingerprint = samsarix-codegen verify-plan request.json execution-plan.json `
  --format fingerprint
samsarix-codegen verify-plan request.json execution-plan.json `
  --expect-plan-fingerprint $planFingerprint `
  --format json > plan-verification.json
Get-Content execution-plan.json

@'
{"schema_version":1,"max_response_bytes":262144}
'@ | Set-Content -Encoding utf8 result-policy.json
$policyFingerprint = samsarix-codegen fingerprint-policy result-policy.json
Get-Content result-policy.json
```

The participant confirms that the exact prompt contains only the intended diff and separately
reviews the plan's endpoint, model, timeout, input ceiling, and output ceiling. If provider access
is approved, they may run the optional preflight once. An omitted or passing preflight permits one
execution attempt; a failed preflight stops the session:

```powershell
samsarix-codegen execute request.json `
  --plan execution-plan.json `
  --expect-plan-fingerprint $planFingerprint `
  --policy result-policy.json `
  --expect-policy-fingerprint $policyFingerprint `
  --format json > result.json

samsarix-codegen verify-execution request.json execution-plan.json result.json `
  --expect-plan-fingerprint $planFingerprint `
  --policy result-policy.json `
  --expect-policy-fingerprint $policyFingerprint `
  --format json > execution-evidence.json
```

If the participant changes the instruction or diff, rebuild to `revised-request.json` and use
`samsarix-codegen compare request.json revised-request.json` before approving the new fingerprint.
A revised request requires a new plan; do not edit fingerprints in either artifact.

## Session B: selected-log triage

At least one participant also completes this task using a scrubbed, non-production log excerpt:

```powershell
Get-Content .\app.log -Tail 300 | samsarix-codegen build `
  "Return one JSON object with diagnosis (string), evidence (array), and next_step (string)" `
  --task debug `
  --stdin-name app.log `
  --max-context-bytes 200000 `
  --max-estimated-input-tokens 60000 `
  --format json > incident-request.json

samsarix-codegen inspect incident-request.json
samsarix-codegen inspect incident-request.json --format markdown
$incidentFingerprint = samsarix-codegen inspect incident-request.json --format fingerprint

samsarix-codegen create-plan incident-request.json `
  --expect-fingerprint $incidentFingerprint `
  --endpoint $pilotEndpoint `
  --model $pilotModel `
  --max-output-tokens 1200 `
  --max-estimated-input-tokens 60000 > incident-plan.json

$incidentPlanFingerprint = samsarix-codegen verify-plan `
  incident-request.json incident-plan.json --format fingerprint
samsarix-codegen verify-plan incident-request.json incident-plan.json `
  --expect-plan-fingerprint $incidentPlanFingerprint `
  --format json > incident-plan-verification.json
Get-Content incident-plan.json

@'
{"schema_version":2,"max_response_bytes":262144,"response_format":"json-object","required_json_keys":["diagnosis","evidence","next_step"],"allowed_json_keys":["diagnosis","evidence","next_step"],"json_key_types":{"diagnosis":"string","evidence":"array","next_step":"string"}}
'@ | Set-Content -Encoding utf8 incident-result-policy.json
$incidentPolicyFingerprint = samsarix-codegen fingerprint-policy incident-result-policy.json
Get-Content incident-result-policy.json
```

Stop before execution if the exact prompt contains a secret, personal data, or context that the
selected provider is not authorized to receive. If execution is approved, use the same
plan-backed `execute` and `verify-execution` sequence as Session A, substituting the incident file
names and both incident fingerprints. Pass `--policy incident-result-policy.json` and
`--expect-policy-fingerprint $incidentPolicyFingerprint` to `execute` as well as to the later
offline `verify-execution`. The version 2 policy makes the incident workflow's downstream JSON
handoff fail closed on invalid JSON, unapproved top-level keys, or wrong top-level types. It does
not establish that the diagnosis or next step is correct. A rejected response still consumes the
single provider request, produces no normal stdout, and is never retried.

## Results record

With the evaluator kit, edit its prefilled `pilot-record.json`. With a source checkout, copy
[`examples/pilot-record-v1.json`](../examples/pilot-record-v1.json) to an untracked
`pilot-record.json` and replace its placeholder wheel and commit. Add one session object per
workflow attempt. Both initial records are intentionally incomplete and cannot pass the pilot gate.
Their enumerated `friction_codes` replace free-form notes; collect qualitative follow-up separately
only if the participant approves its retention and it has been manually scrubbed.

Validate the portable shape with [`pilot-record-v1.schema.json`](pilot-record-v1.schema.json), then
run the authoritative cross-session decision check from the kit or a repository checkout. Its
output follows the separate [`pilot-decision-v1.schema.json`](pilot-decision-v1.schema.json)
contract:

```powershell
python scripts/pilot_check.py pilot-record.json > pilot-decision.json
if ($LASTEXITCODE -eq 2) { throw "The pilot record is invalid." }
if ($LASTEXITCODE -eq 1) { Write-Host "The pilot is valid but not ready to pass." }
```

Exit `0` means every decision gate passed, `1` means the record is valid but the adoption gate is
not ready, and `2` means the input is invalid. The decision output contains only the exact release
identifiers, a canonical record hash, counts, workflow names, and requirement booleans. The checker
rejects duplicate JSON fields, unknown fields, repeated participant/workflow pairs, a file over 256
KiB, more than one provider-check or execution attempt per session, and inconsistent status/exit
code combinations. It intentionally does not claim that recorded observations are truthful.

Delete local request, plan, result, and evidence files after the participant's normal retention
period. Neither the record nor its decision output may contain request/context fingerprints, model
output, provider usage account identifiers, credentials, exact endpoints, names, emails, paths, or
free-form text. Keep `pilot-record.json` untracked unless its disclosure has been reviewed.

## Decision gate

Call the pilot complete only when all of these are true:

1. At least three developers complete staged-review artifact build, exact-prompt inspection,
   request fingerprint capture, plan-settings review, plan fingerprint capture, result-policy
   review, and policy fingerprint capture from the same wheel digest and commit.
2. Both workflows are exercised, including at least one selected-log session.
3. Every provider check and execution is attempted at most once. Every successful execution uses
   approved plan and policy fingerprints and passes policy-bound `verify-execution`; failures remain
   failures rather than being rerun until a pass appears.
4. At least two participants score clarity and usefulness at 4 or higher and answer `yes` or `maybe`
   to reuse.
5. No session reads an unintended file, sends unreviewed context, exposes a credential, or requires
   Samsarix to collect source, prompt, response, or telemetry data.

If a safety condition fails, stop the pilot and fix the boundary before recruiting more users. If
the usefulness threshold fails, preserve the result and revisit the product wedge rather than
expanding into autonomous edits or repository discovery without evidence.
