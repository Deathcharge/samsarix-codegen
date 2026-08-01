#!/usr/bin/env sh
# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

set -eu

artifact_path="${1:-samsarix-review-request.json}"

if git diff --cached --quiet --exit-code; then
  echo "No staged changes to review." >&2
  exit 2
fi

git diff --cached --no-ext-diff |
  samsarix-codegen build "Review these staged changes" \
    --task review \
    --stdin-name staged.diff \
    --max-context-bytes 500000 \
    --max-estimated-input-tokens 150000 \
    --format json >"$artifact_path"

fingerprint="$(samsarix-codegen inspect "$artifact_path" --format fingerprint)"
printf 'Built %s\nFingerprint: %s\n' "$artifact_path" "$fingerprint"
