# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

param(
    [string]$ArtifactPath = "samsarix-review-request.json"
)

$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

git diff --cached --quiet --exit-code
if ($LASTEXITCODE -eq 0) {
    throw "No staged changes to review."
}
if ($LASTEXITCODE -ne 1) {
    throw "git diff failed with exit code $LASTEXITCODE."
}

git diff --cached --no-ext-diff |
    samsarix-codegen build "Review these staged changes" `
        --task review `
        --stdin-name staged.diff `
        --max-context-bytes 500000 `
        --max-estimated-input-tokens 150000 `
        --format json > $ArtifactPath
if ($LASTEXITCODE -ne 0) {
    throw "samsarix-codegen build failed with exit code $LASTEXITCODE."
}

$fingerprint = samsarix-codegen inspect $ArtifactPath --format fingerprint
if ($LASTEXITCODE -ne 0) {
    throw "samsarix-codegen inspect failed with exit code $LASTEXITCODE."
}
Write-Output "Built $ArtifactPath"
Write-Output "Fingerprint: $fingerprint"
