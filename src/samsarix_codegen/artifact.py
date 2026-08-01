# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Deterministic, inspectable request artifacts for two-phase execution."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.models import ChatResult, ContextFile
from samsarix_codegen.prompt import estimate_tokens

ARTIFACT_SCHEMA_VERSION = 2
RESULT_SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 12 * 1024 * 1024
MAX_ARTIFACT_MESSAGES = 32
MAX_ARTIFACT_CONTEXT_ITEMS = 100
MAX_CONTEXT_NAME_CHARS = 4_096
FINGERPRINT_PREFIX = "sha256:"
ESTIMATE_METHOD = "ceil(total UTF-8 message bytes / 4)"


@dataclass(frozen=True, slots=True)
class ContextRecord:
    """Provenance metadata for one context item in an artifact."""

    name: str
    size_bytes: int
    content_sha256: str


@dataclass(frozen=True, slots=True)
class RequestArtifact:
    """A validated request that can be reviewed before provider execution."""

    messages: tuple[dict[str, str], ...]
    context: tuple[ContextRecord, ...]
    context_bytes: int
    estimated_input_tokens: int
    fingerprint: str

    def to_payload(self) -> dict[str, Any]:
        """Return the stable JSON-compatible representation."""

        payload = _unsigned_payload(
            messages=self.messages,
            context=self.context,
            context_bytes=self.context_bytes,
            estimated_input_tokens=self.estimated_input_tokens,
        )
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "request_fingerprint": self.fingerprint,
            "messages": payload["messages"],
            "context": payload["context"],
            "estimate": payload["estimate"],
        }


def create_request_artifact(
    messages: Sequence[Mapping[str, str]],
    context_files: Sequence[ContextFile],
) -> RequestArtifact:
    """Create a deterministic artifact from already validated messages and context."""

    normalized_messages = _normalize_messages(messages)
    if len(context_files) > MAX_ARTIFACT_CONTEXT_ITEMS:
        raise ArtifactError(
            f"request artifacts may contain at most {MAX_ARTIFACT_CONTEXT_ITEMS} context items"
        )
    for item in context_files:
        if not _is_safe_name(item.path):
            raise ArtifactError("request artifact context item has an invalid name")
        if item.size_bytes < 0:
            raise ArtifactError("request artifact context item bytes must be non-negative")
    context = tuple(
        ContextRecord(
            name=item.path,
            size_bytes=item.size_bytes,
            content_sha256=_sha256_text(item.content),
        )
        for item in context_files
    )
    context_bytes = sum(item.size_bytes for item in context)
    estimated_input_tokens = estimate_tokens(normalized_messages)
    unsigned = _unsigned_payload(
        messages=normalized_messages,
        context=context,
        context_bytes=context_bytes,
        estimated_input_tokens=estimated_input_tokens,
    )
    return RequestArtifact(
        messages=normalized_messages,
        context=context,
        context_bytes=context_bytes,
        estimated_input_tokens=estimated_input_tokens,
        fingerprint=_fingerprint(unsigned),
    )


def render_request_artifact(artifact: RequestArtifact) -> str:
    """Render a stable artifact suitable for review, storage, or later execution."""

    rendered = json.dumps(artifact.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if len(rendered.encode("utf-8")) > MAX_ARTIFACT_BYTES:
        raise ArtifactError(
            f"request artifact exceeds the {MAX_ARTIFACT_BYTES:,}-byte safety limit"
        )
    return rendered


def parse_request_artifact(raw: str | bytes) -> RequestArtifact:
    """Parse and validate an artifact, including its internal fingerprint."""

    if isinstance(raw, bytes):
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise ArtifactError(
                f"request artifact exceeds the {MAX_ARTIFACT_BYTES:,}-byte safety limit"
            )
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArtifactError("request artifact is not valid UTF-8") from exc
    else:
        if len(raw.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise ArtifactError(
                f"request artifact exceeds the {MAX_ARTIFACT_BYTES:,}-byte safety limit"
            )
        text = raw

    try:
        decoded: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"request artifact is not valid JSON: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ArtifactError("request artifact must be a JSON object")

    expected_keys = {
        "schema_version",
        "request_fingerprint",
        "messages",
        "context",
        "estimate",
    }
    if set(decoded) != expected_keys:
        raise ArtifactError("request artifact fields do not match schema version 2")
    if decoded.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactError(
            f"unsupported request artifact schema: {decoded.get('schema_version')!r}; "
            f"expected {ARTIFACT_SCHEMA_VERSION}"
        )

    messages = _parse_messages(decoded.get("messages"))
    context, context_bytes = _parse_context(decoded.get("context"))
    estimated_input_tokens = _parse_estimate(decoded.get("estimate"))
    fingerprint = decoded.get("request_fingerprint")
    if not isinstance(fingerprint, str) or not _is_sha256(fingerprint):
        raise ArtifactError("request artifact contains an invalid fingerprint")

    unsigned = _unsigned_payload(
        messages=messages,
        context=context,
        context_bytes=context_bytes,
        estimated_input_tokens=estimated_input_tokens,
    )
    computed = _fingerprint(unsigned)
    if not hmac.compare_digest(fingerprint, computed):
        raise ArtifactError("request artifact fingerprint does not match its contents")
    if estimated_input_tokens != estimate_tokens(messages):
        raise ArtifactError("request artifact input-token estimate does not match its messages")

    return RequestArtifact(
        messages=messages,
        context=context,
        context_bytes=context_bytes,
        estimated_input_tokens=estimated_input_tokens,
        fingerprint=fingerprint,
    )


def render_execution_result(
    artifact: RequestArtifact,
    result: ChatResult,
    *,
    model: str,
) -> str:
    """Render a machine-readable provider result without endpoint or credential data."""

    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "request_fingerprint": artifact.fingerprint,
        "model": model,
        "response": {"text": result.text},
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_artifact_summary(artifact: RequestArtifact, *, output_format: str = "text") -> str:
    """Render a validated artifact summary without exposing prompt contents."""

    if output_format == "fingerprint":
        return artifact.fingerprint + "\n"
    if output_format == "json":
        payload = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "request_fingerprint": artifact.fingerprint,
            "messages": len(artifact.messages),
            "context_items": len(artifact.context),
            "context_bytes": artifact.context_bytes,
            "estimated_input_tokens": artifact.estimated_input_tokens,
            "context": [
                {
                    "name": item.name,
                    "bytes": item.size_bytes,
                    "content_sha256": item.content_sha256,
                }
                for item in artifact.context
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    lines = [
        "Request artifact is valid.",
        f"Fingerprint: {artifact.fingerprint}",
        f"Messages: {len(artifact.messages)}",
        (f"Context: {len(artifact.context)} item(s), {artifact.context_bytes:,} bytes"),
        f"Estimated input: ~{artifact.estimated_input_tokens:,} tokens",
    ]
    for item in artifact.context:
        lines.append(f"- {item.name}: {item.size_bytes:,} bytes, {item.content_sha256}")
    return "\n".join(lines) + "\n"


def require_fingerprint(artifact: RequestArtifact, expected: str | None) -> None:
    """Fail closed when an externally approved fingerprint does not match."""

    if expected is None:
        return
    if not _is_sha256(expected):
        raise ArtifactError("--expect-fingerprint must be a sha256:<64 lowercase hex> value")
    if not hmac.compare_digest(artifact.fingerprint, expected):
        raise ArtifactError(
            "request artifact does not match the fingerprint approved by the operator"
        )


def _unsigned_payload(
    *,
    messages: Sequence[Mapping[str, str]],
    context: Sequence[ContextRecord],
    context_bytes: int,
    estimated_input_tokens: int,
) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "messages": [dict(message) for message in messages],
        "context": {
            "total_bytes": context_bytes,
            "items": [
                {
                    "name": item.name,
                    "bytes": item.size_bytes,
                    "content_sha256": item.content_sha256,
                }
                for item in context
            ],
        },
        "estimate": {
            "input_tokens": estimated_input_tokens,
            "method": ESTIMATE_METHOD,
        },
    }


def _fingerprint(unsigned_payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        unsigned_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return FINGERPRINT_PREFIX + hashlib.sha256(canonical).hexdigest()


def _sha256_text(value: str) -> str:
    return FINGERPRINT_PREFIX + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_messages(
    messages: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    return _parse_messages([dict(message) for message in messages])


def _parse_messages(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ARTIFACT_MESSAGES:
        raise ArtifactError(
            f"request artifact messages must contain 1 to {MAX_ARTIFACT_MESSAGES} items"
        )
    messages: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"role", "content"}:
            raise ArtifactError("each request artifact message must contain role and content")
        role = item.get("role")
        content = item.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise ArtifactError("request artifact messages contain an invalid role or content")
        messages.append({"role": role, "content": content})
    return tuple(messages)


def _parse_context(value: object) -> tuple[tuple[ContextRecord, ...], int]:
    if not isinstance(value, dict) or set(value) != {"total_bytes", "items"}:
        raise ArtifactError("request artifact context has an invalid shape")
    total_bytes = value.get("total_bytes")
    items = value.get("items")
    if not isinstance(total_bytes, int) or isinstance(total_bytes, bool) or total_bytes < 0:
        raise ArtifactError("request artifact context total_bytes must be non-negative")
    if not isinstance(items, list) or len(items) > MAX_ARTIFACT_CONTEXT_ITEMS:
        raise ArtifactError(
            f"request artifact context may contain at most {MAX_ARTIFACT_CONTEXT_ITEMS} items"
        )

    records: list[ContextRecord] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"name", "bytes", "content_sha256"}:
            raise ArtifactError("request artifact context item has an invalid shape")
        name = item.get("name")
        size_bytes = item.get("bytes")
        digest = item.get("content_sha256")
        if not isinstance(name, str) or not _is_safe_name(name):
            raise ArtifactError("request artifact context item has an invalid name")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise ArtifactError("request artifact context item bytes must be non-negative")
        if not isinstance(digest, str) or not _is_sha256(digest):
            raise ArtifactError("request artifact context item has an invalid content_sha256")
        records.append(ContextRecord(name=name, size_bytes=size_bytes, content_sha256=digest))

    if sum(item.size_bytes for item in records) != total_bytes:
        raise ArtifactError("request artifact context byte totals do not match")
    return tuple(records), total_bytes


def _parse_estimate(value: object) -> int:
    if not isinstance(value, dict) or set(value) != {"input_tokens", "method"}:
        raise ArtifactError("request artifact estimate has an invalid shape")
    input_tokens = value.get("input_tokens")
    if (
        not isinstance(input_tokens, int)
        or isinstance(input_tokens, bool)
        or input_tokens < 1
        or value.get("method") != ESTIMATE_METHOD
    ):
        raise ArtifactError("request artifact estimate is invalid")
    return input_tokens


def _is_sha256(value: str) -> bool:
    if not value.startswith(FINGERPRINT_PREFIX) or len(value) != len(FINGERPRINT_PREFIX) + 64:
        return False
    return all(character in "0123456789abcdef" for character in value[len(FINGERPRINT_PREFIX) :])


def _is_safe_name(value: str) -> bool:
    return 1 <= len(value) <= MAX_CONTEXT_NAME_CHARS and all(
        character.isprintable() for character in value
    )
