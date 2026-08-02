# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Strict, versioned execution-result policy documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from samsarix_codegen.artifact import ExecutionResultPolicy
from samsarix_codegen.errors import ArtifactError

RESULT_POLICY_SCHEMA_VERSION = 1
MAX_RESULT_POLICY_BYTES = 64 * 1024
_POLICY_FIELDS = (
    "expected_model",
    "max_response_bytes",
    "max_prompt_tokens",
    "max_completion_tokens",
    "max_total_tokens",
)


class _DuplicatePolicyKeyError(ValueError):
    """Internal signal for an ambiguous result-policy JSON object."""


def parse_execution_result_policy(raw: str | bytes) -> ExecutionResultPolicy:
    """Parse one bounded, exact execution-result policy version 1 document."""

    text = _decode_policy_document(raw)
    try:
        decoded: Any = json.loads(text, object_pairs_hook=_reject_duplicate_policy_keys)
    except _DuplicatePolicyKeyError as exc:
        raise ArtifactError(str(exc)) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        message = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
        raise ArtifactError(f"execution result policy is not valid JSON: {message}") from exc

    if not isinstance(decoded, dict):
        raise ArtifactError("execution result policy must be a JSON object")
    allowed_fields = {"schema_version", *_POLICY_FIELDS}
    if "schema_version" not in decoded or not set(decoded).issubset(allowed_fields):
        raise ArtifactError("execution result policy fields do not match schema version 1")

    schema_version = decoded.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != RESULT_POLICY_SCHEMA_VERSION
    ):
        raise ArtifactError(
            f"unsupported execution result policy schema: {schema_version!r}; "
            f"expected {RESULT_POLICY_SCHEMA_VERSION}"
        )

    configured_fields = [field for field in _POLICY_FIELDS if field in decoded]
    if not configured_fields:
        raise ArtifactError("execution result policy must configure at least one rule")
    null_fields = [field for field in configured_fields if decoded[field] is None]
    if null_fields:
        raise ArtifactError(
            "execution result policy rules cannot be null; omit unset fields: "
            + ", ".join(null_fields)
        )

    return ExecutionResultPolicy(
        expected_model=decoded.get("expected_model"),
        max_response_bytes=decoded.get("max_response_bytes"),
        max_prompt_tokens=decoded.get("max_prompt_tokens"),
        max_completion_tokens=decoded.get("max_completion_tokens"),
        max_total_tokens=decoded.get("max_total_tokens"),
    )


def render_execution_result_policy(policy: ExecutionResultPolicy) -> str:
    """Render one non-empty execution-result policy document deterministically."""

    if not isinstance(policy, ExecutionResultPolicy):
        raise ArtifactError("execution result policy rendering requires a validated policy")
    payload: dict[str, object] = {"schema_version": RESULT_POLICY_SCHEMA_VERSION}
    for field in _POLICY_FIELDS:
        value = getattr(policy, field)
        if value is not None:
            payload[field] = value
    if len(payload) == 1:
        raise ArtifactError("execution result policy must configure at least one rule")

    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        rendered_size = len(rendered.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ArtifactError("execution result policy is not valid Unicode") from exc
    if rendered_size > MAX_RESULT_POLICY_BYTES:
        raise ArtifactError(
            f"execution result policy exceeds the {MAX_RESULT_POLICY_BYTES:,}-byte safety limit"
        )
    return rendered


def load_execution_result_policy(path: str | Path) -> ExecutionResultPolicy:
    """Load one explicitly selected, bounded result-policy JSON file."""

    policy_path = Path(path)
    try:
        if not policy_path.is_file():
            raise ArtifactError(f"execution result policy is not a regular file: {path}")
        if policy_path.stat().st_size > MAX_RESULT_POLICY_BYTES:
            raise ArtifactError(
                f"execution result policy exceeds the {MAX_RESULT_POLICY_BYTES:,}-byte safety limit"
            )
        with policy_path.open("rb") as handle:
            raw = handle.read(MAX_RESULT_POLICY_BYTES + 1)
    except ArtifactError:
        raise
    except OSError as exc:
        raise ArtifactError(f"cannot read execution result policy {path}: {exc}") from exc
    return parse_execution_result_policy(raw)


def _decode_policy_document(raw: str | bytes) -> str:
    if isinstance(raw, bytes):
        if len(raw) > MAX_RESULT_POLICY_BYTES:
            raise ArtifactError(
                f"execution result policy exceeds the {MAX_RESULT_POLICY_BYTES:,}-byte safety limit"
            )
        if b"\x00" in raw:
            raise ArtifactError("binary execution result policies are not supported")
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArtifactError("execution result policy is not valid UTF-8") from exc

    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ArtifactError("execution result policy text is not valid Unicode") from exc
    if len(encoded) > MAX_RESULT_POLICY_BYTES:
        raise ArtifactError(
            f"execution result policy exceeds the {MAX_RESULT_POLICY_BYTES:,}-byte safety limit"
        )
    if "\x00" in raw:
        raise ArtifactError("binary execution result policies are not supported")
    return raw


def _reject_duplicate_policy_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicatePolicyKeyError(
                f"execution result policy contains a duplicate JSON field: {key}"
            )
        decoded[key] = value
    return decoded
