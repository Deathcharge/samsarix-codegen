# Release runbook

This runbook separates a safe release dry run from the owner-controlled acts of reserving the PyPI
project, approving publication, creating a tag, and publishing a GitHub release. The workflow never
publishes from a branch or manual dispatch.

## What is automated

`.github/workflows/release.yml` has two entry paths:

- Manual `workflow_dispatch`: verifies the existing `X.Y.Z` source version, runs all source checks,
  builds and audits one sdist/wheel pair, creates `SHA256SUMS`, installs the wheel in a fresh virtual
  environment, creates and self-verifies a deterministic evaluator pilot kit, adds that ZIP to
  `SHA256SUMS`, uploads all four files as workflow artifacts, and generates GitHub build-provenance
  attestations. Both publish jobs are skipped.
- A pushed `vX.Y.Z` tag: performs the same build, but first requires an exact source/tag version
  match, a dated changelog entry, a clean checkout, and proof that the tagged commit is contained in
  `master`. After the `pypi` environment is manually approved, Trusted Publishing uploads only the
  sdist and wheel. A GitHub release is then created as a draft with both packages, the evaluator
  kit, and `SHA256SUMS` attached before it is published.

Every external action is pinned to a verified full commit SHA. Dependabot is configured to propose
monthly GitHub Actions updates while retaining the human-readable version comment.

## One-time owner setup

The project URL `https://pypi.org/project/samsarix-codegen/` still returned 404 on 2026-08-01. A 404
does not reserve the name.

1. Sign in to PyPI with the Samsarix-owned account and register a pending Trusted Publisher for:
   - PyPI project: `samsarix-codegen`
   - GitHub owner: `Deathcharge`
   - Repository: `samsarix-codegen`
   - Workflow: `release.yml`
   - Environment: `pypi`
2. Create the GitHub environment named `pypi` and require manual approval. Restrict deployment to
   protected release tags if the repository plan supports that control.
3. Add a tag rule for `v*` so only the owner/release maintainer can create release tags.
4. Enable GitHub release immutability before the first public release. The workflow already follows
   GitHub's recommended draft → attach all assets → publish sequence.

Do not create a long-lived PyPI API token. Trusted Publishing exchanges the GitHub Actions identity
for a short-lived, project-scoped credential, and the publishing action produces PyPI-hosted PEP 740
attestations by default.

## Exercise the non-publishing path

After this workflow exists on the default branch:

```powershell
gh workflow run release.yml -f version=0.2.0
$run = gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $run --exit-status
gh run download $run --name python-package-distributions --dir .\release-dry-run
gh run download $run --name release-sha256-manifest --dir .\release-dry-run
gh run download $run --name evaluator-pilot-kit --dir .\release-dry-run
Push-Location .\release-dry-run
Get-Content SHA256SUMS | ForEach-Object {
  if ($_ -notmatch '^([0-9a-f]{64})  (.+)$') { throw "Invalid SHA256SUMS line: $_" }
  $expected = $Matches[1]
  $asset = $Matches[2]
  $actual = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "SHA-256 mismatch: $asset" }
}
Pop-Location
gh attestation verify .\release-dry-run\samsarix_codegen-0.2.0.tar.gz `
  --repo Deathcharge/samsarix-codegen
if ($LASTEXITCODE -ne 0) { throw "Source-distribution provenance verification failed." }
gh attestation verify .\release-dry-run\samsarix_codegen-0.2.0-py3-none-any.whl `
  --repo Deathcharge/samsarix-codegen
if ($LASTEXITCODE -ne 0) { throw "Wheel provenance verification failed." }
gh attestation verify .\release-dry-run\samsarix-codegen-pilot-kit-0.2.0.zip `
  --repo Deathcharge/samsarix-codegen
if ($LASTEXITCODE -ne 0) { throw "Pilot-kit provenance verification failed." }
Expand-Archive .\release-dry-run\samsarix-codegen-pilot-kit-0.2.0.zip `
  -DestinationPath .\release-dry-run
Push-Location .\release-dry-run\samsarix-codegen-pilot-kit-0.2.0
try {
  python scripts/pilot_bundle.py verify-directory .
  if ($LASTEXITCODE -ne 0) { throw "Extracted pilot-kit verification failed." }
} finally {
  Pop-Location
}
```

The pilot kit verifier proves internal consistency and wheel/commit linkage. The outer GitHub
attestation establishes build provenance, but neither mechanism guarantees that the package is
safe or that the pilot passed. GitHub Actions artifacts have a workflow-configured 30-day retention
period; preserve the exact ZIP digest in the coordinator's release evidence rather than treating
the artifact URL as permanent. See GitHub's documentation for
[workflow artifact retention and digest validation](https://docs.github.com/en/actions/tutorials/store-and-share-data)
and [artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).

The workflow run must show both publishing jobs as skipped. A dry run does not reserve a PyPI name,
upload a package, create a release, or create a tag.

## Prepare a release candidate

1. Work from a clean release branch based on current `master`.
2. Choose the version once. Update both `pyproject.toml` and
   `src/samsarix_codegen/__init__.py` to the same `X.Y.Z` value.
3. Replace `## [X.Y.Z] - Unreleased` in `CHANGELOG.md` with the actual ISO release date.
4. Run the local gates:

```powershell
python scripts/release_check.py source --version 0.2.0 --tag v0.2.0
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -ra
if (Test-Path -LiteralPath build) { throw "Refusing to reuse a local build cache" }
if (Test-Path -LiteralPath dist) { throw "Refusing to mix prior distribution artifacts" }
python -m build
python scripts/release_check.py artifacts --version 0.2.0 `
  --dist-dir dist --write-checksums dist\SHA256SUMS
```

Python build frontends can reuse the ignored `build/` directory. Start from a fresh checkout or
verify that both generated directories are absent as above. The artifact audit independently
rejects unexpected wheel roots and a mismatched dist-info directory, but a clean input keeps a
failed release build from being created in the first place.

5. Merge the release PR only after the complete CI matrix passes. Sync `master`, rerun the source
   check with `--require-clean`, and record the commit.
6. Create a signed annotated tag locally and push only that tag:

```powershell
git tag -s v0.2.0 -m "Samsarix Codegen 0.2.0"
git push origin v0.2.0
```

The tag push starts the release workflow. Review its source, test, artifact, and attestation output
before approving the `pypi` environment. Never approve a run whose tag, commit, filenames, or hashes
do not match the release record.

## Verify the published release

After both publish jobs pass:

```powershell
python -m pip install --no-cache-dir samsarix-codegen==0.2.0
samsarix-codegen --version
gh release download v0.2.0 --repo Deathcharge/samsarix-codegen --dir .\release-0.2.0
Push-Location .\release-0.2.0
Get-Content SHA256SUMS | ForEach-Object {
  if ($_ -notmatch '^([0-9a-f]{64})  (.+)$') { throw "Invalid SHA256SUMS line: $_" }
  $expected = $Matches[1]
  $asset = $Matches[2]
  $actual = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "SHA-256 mismatch: $asset" }
}
Pop-Location
gh release verify v0.2.0 --repo Deathcharge/samsarix-codegen
gh release verify-asset v0.2.0 `
  .\release-0.2.0\samsarix_codegen-0.2.0-py3-none-any.whl `
  --repo Deathcharge/samsarix-codegen
```

Also confirm the PyPI project metadata, Samsarix contacts, Apache-2.0 expression, wheel and sdist
hashes, and PyPI attestations. Install once in a fresh environment from PyPI rather than from a local
wheel or checkout.

## Failure and rollback rules

- Before environment approval: reject the run, preserve its logs/artifacts for diagnosis, and make a
  new commit. Do not publish a known-bad build.
- After PyPI publication: PyPI versions are immutable and cannot be replaced. Yank the affected
  version in PyPI, document the reason, fix forward with a new patch version, and never reuse its
  version number.
- After an immutable GitHub release: do not move/reuse its tag or replace assets. Publish a new patch
  release. If a draft release failed before publication, inspect and delete only that draft after
  confirming PyPI state.
- For a code regression, revert through a reviewed PR on `master`; do not rewrite default-branch
  history.

## Release evidence record

Record the version, tag, exact commit, release workflow URL, four CI jobs, sdist/wheel/pilot-kit
filenames and SHA-256 values, GitHub attestation verification, extracted-kit verification, GitHub
release URL, PyPI project/version URL, fresh installation result, approving owner, and any rollback
action. Passing the build gate is not proof that PyPI publication or user adoption occurred.
