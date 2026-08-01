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
from samsarix_codegen.models import MAX_MODEL_CHARS, ChatResult, ContextFile
from samsarix_codegen.prompt import estimate_tokens

ARTIFACT_SCHEMA_VERSION = 2
RESULT_SCHEMA_VERSION = 1
COMPARISON_SCHEMA_VERSION = 1
RESULT_COMPARISON_SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 12 * 1024 * 1024
MAX_RESULT_BYTES = 12 * 1024 * 1024
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


@dataclass(frozen=True, slots=True)
class RequestArtifactComparison:
    """A content-safe structural comparison between two validated artifacts."""

    base_fingerprint: str
    target_fingerprint: str
    changed_message_indices: tuple[int, ...]
    base_message_count: int
    target_message_count: int
    added_context: tuple[ContextRecord, ...]
    removed_context: tuple[ContextRecord, ...]
    base_context_bytes: int
    target_context_bytes: int
    base_estimated_input_tokens: int
    target_estimated_input_tokens: int

    @property
    def changed(self) -> bool:
        """Return whether the canonical request fingerprints differ."""

        return not hmac.compare_digest(self.base_fingerprint, self.target_fingerprint)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-compatible comparison without prompt contents."""

        return {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "changed": self.changed,
            "base_fingerprint": self.base_fingerprint,
            "target_fingerprint": self.target_fingerprint,
            "messages": {
                "base_count": self.base_message_count,
                "target_count": self.target_message_count,
                "changed_indices": list(self.changed_message_indices),
            },
            "context": {
                "base_bytes": self.base_context_bytes,
                "target_bytes": self.target_context_bytes,
                "byte_delta": self.target_context_bytes - self.base_context_bytes,
                "added": [_context_record_payload(item) for item in self.added_context],
                "removed": [_context_record_payload(item) for item in self.removed_context],
            },
            "estimate": {
                "base_input_tokens": self.base_estimated_input_tokens,
                "target_input_tokens": self.target_estimated_input_tokens,
                "input_token_delta": (
                    self.target_estimated_input_tokens - self.base_estimated_input_tokens
                ),
            },
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """A validated provider-result envelope linked to a request fingerprint."""

    request_fingerprint: str
    model: str
    response_text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None

    def __post_init__(self) -> None:
        if not _is_sha256(self.request_fingerprint):
            raise ArtifactError("execution result contains an invalid request fingerprint")
        _normalize_result_model(self.model, require_canonical=True)
        if not isinstance(self.response_text, str) or not self.response_text:
            raise ArtifactError("execution result response text cannot be empty")
        response_bytes = _utf8_size(self.response_text, label="execution result response text")
        if response_bytes > MAX_RESULT_BYTES:
            raise ArtifactError(
                f"execution result response exceeds the {MAX_RESULT_BYTES:,}-byte safety limit"
            )
        _parse_usage_value("prompt_tokens", self.prompt_tokens)
        _parse_usage_value("completion_tokens", self.completion_tokens)
        _parse_usage_value("total_tokens", self.total_tokens)

    def to_payload(self) -> dict[str, Any]:
        """Return the stable JSON-compatible representation."""

        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "request_fingerprint": self.request_fingerprint,
            "model": self.model,
            "response": {"text": self.response_text},
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
        }


@dataclass(frozen=True, slots=True)
class ExecutionResultSummary:
    """Content-omitting metadata for one validated execution result."""

    model: str
    response_chars: int
    response_bytes: int
    response_sha256: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None

    def __post_init__(self) -> None:
        _normalize_result_model(self.model, require_canonical=True)
        for label, value in (
            ("response characters", self.response_chars),
            ("response bytes", self.response_bytes),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 1 <= value <= MAX_RESULT_BYTES
            ):
                raise ArtifactError(
                    f"execution result {label} must be between 1 and {MAX_RESULT_BYTES:,}"
                )
        if not _is_sha256(self.response_sha256):
            raise ArtifactError("execution result contains an invalid response fingerprint")
        _parse_usage_value("prompt_tokens", self.prompt_tokens)
        _parse_usage_value("completion_tokens", self.completion_tokens)
        _parse_usage_value("total_tokens", self.total_tokens)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-compatible result summary without response text."""

        return {
            "model": self.model,
            "response": {
                "chars": self.response_chars,
                "bytes": self.response_bytes,
                "sha256": self.response_sha256,
            },
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
        }


@dataclass(frozen=True, slots=True)
class ExecutionResultComparison:
    """A content-omitting comparison of results for the same reviewed request."""

    request_fingerprint: str
    base: ExecutionResultSummary
    target: ExecutionResultSummary

    def __post_init__(self) -> None:
        if not _is_sha256(self.request_fingerprint):
            raise ArtifactError(
                "execution result comparison contains an invalid request fingerprint"
            )
        if not isinstance(self.base, ExecutionResultSummary) or not isinstance(
            self.target, ExecutionResultSummary
        ):
            raise ArtifactError("execution result comparison requires validated result summaries")

    @property
    def model_changed(self) -> bool:
        """Return whether the operator-recorded model names differ."""

        return self.base.model != self.target.model

    @property
    def response_identical(self) -> bool:
        """Return whether the UTF-8 response text digests match."""

        return hmac.compare_digest(self.base.response_sha256, self.target.response_sha256)

    def to_payload(self) -> dict[str, Any]:
        """Return a stable comparison without either response body."""

        return {
            "schema_version": RESULT_COMPARISON_SCHEMA_VERSION,
            "request_fingerprint": self.request_fingerprint,
            "model_changed": self.model_changed,
            "response_identical": self.response_identical,
            "base": self.base.to_payload(),
            "target": self.target.to_payload(),
            "delta": {
                "response_chars": self.target.response_chars - self.base.response_chars,
                "response_bytes": self.target.response_bytes - self.base.response_bytes,
                "prompt_tokens": _optional_delta(
                    self.base.prompt_tokens, self.target.prompt_tokens
                ),
                "completion_tokens": _optional_delta(
                    self.base.completion_tokens, self.target.completion_tokens
                ),
                "total_tokens": _optional_delta(self.base.total_tokens, self.target.total_tokens),
            },
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

    normalized_model = _normalize_result_model(model)
    if not isinstance(result.text, str) or not result.text:
        raise ArtifactError("execution result response text cannot be empty")
    prompt_tokens = _parse_usage_value("prompt_tokens", result.prompt_tokens)
    completion_tokens = _parse_usage_value("completion_tokens", result.completion_tokens)
    total_tokens = _parse_usage_value("total_tokens", result.total_tokens)
    execution_result = ExecutionResult(
        request_fingerprint=artifact.fingerprint,
        model=normalized_model,
        response_text=result.text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    rendered = json.dumps(execution_result.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if len(rendered.encode("utf-8")) > MAX_RESULT_BYTES:
        raise ArtifactError(f"execution result exceeds the {MAX_RESULT_BYTES:,}-byte safety limit")
    return rendered


def parse_execution_result(raw: str | bytes) -> ExecutionResult:
    """Parse and strictly validate one execution-result envelope."""

    text = _decode_bounded_json(raw, label="execution result", maximum=MAX_RESULT_BYTES)
    try:
        decoded: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"execution result is not valid JSON: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ArtifactError("execution result must be a JSON object")

    expected_keys = {
        "schema_version",
        "request_fingerprint",
        "model",
        "response",
        "usage",
    }
    if set(decoded) != expected_keys:
        raise ArtifactError("execution result fields do not match schema version 1")
    schema_version = decoded.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != RESULT_SCHEMA_VERSION
    ):
        raise ArtifactError(
            f"unsupported execution result schema: {schema_version!r}; "
            f"expected {RESULT_SCHEMA_VERSION}"
        )

    fingerprint = decoded.get("request_fingerprint")
    if not isinstance(fingerprint, str) or not _is_sha256(fingerprint):
        raise ArtifactError("execution result contains an invalid request fingerprint")
    model = _normalize_result_model(decoded.get("model"), require_canonical=True)

    response = decoded.get("response")
    if not isinstance(response, dict) or set(response) != {"text"}:
        raise ArtifactError("execution result response must contain exactly text")
    response_text = response.get("text")
    if not isinstance(response_text, str) or not response_text:
        raise ArtifactError("execution result response text cannot be empty")

    usage = decoded.get("usage")
    usage_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
    if not isinstance(usage, dict) or set(usage) != usage_keys:
        raise ArtifactError("execution result usage fields do not match schema version 1")

    return ExecutionResult(
        request_fingerprint=fingerprint,
        model=model,
        response_text=response_text,
        prompt_tokens=_parse_usage_value("prompt_tokens", usage.get("prompt_tokens")),
        completion_tokens=_parse_usage_value("completion_tokens", usage.get("completion_tokens")),
        total_tokens=_parse_usage_value("total_tokens", usage.get("total_tokens")),
    )


def compare_execution_results(
    base: ExecutionResult,
    target: ExecutionResult,
) -> ExecutionResultComparison:
    """Compare two results only when they reference the same reviewed request."""

    if not hmac.compare_digest(base.request_fingerprint, target.request_fingerprint):
        raise ArtifactError("execution results reference different request fingerprints")
    return ExecutionResultComparison(
        request_fingerprint=base.request_fingerprint,
        base=_summarize_execution_result(base),
        target=_summarize_execution_result(target),
    )


def render_execution_result_comparison(
    comparison: ExecutionResultComparison,
    *,
    output_format: str = "text",
) -> str:
    """Render a content-omitting execution-result comparison."""

    if output_format == "json":
        return json.dumps(comparison.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if output_format != "text":
        raise ArtifactError("execution result comparison format must be text or json")

    lines = [
        "Execution results reference the same reviewed request.",
        f"Request: {comparison.request_fingerprint}",
        (
            f"Models: {comparison.base.model} -> {comparison.target.model} "
            f"({'changed' if comparison.model_changed else 'unchanged'})"
        ),
        ("Responses: identical" if comparison.response_identical else "Responses: different"),
        (
            "Response characters: "
            f"{comparison.base.response_chars:,} -> {comparison.target.response_chars:,} "
            f"({_format_delta(comparison.target.response_chars - comparison.base.response_chars)})"
        ),
        (
            "Response bytes: "
            f"{comparison.base.response_bytes:,} -> {comparison.target.response_bytes:,} "
            f"({_format_delta(comparison.target.response_bytes - comparison.base.response_bytes)})"
        ),
        f"Base response: {comparison.base.response_sha256}",
        f"Target response: {comparison.target.response_sha256}",
        _render_usage_comparison(
            "Prompt tokens", comparison.base.prompt_tokens, comparison.target.prompt_tokens
        ),
        _render_usage_comparison(
            "Completion tokens",
            comparison.base.completion_tokens,
            comparison.target.completion_tokens,
        ),
        _render_usage_comparison(
            "Total tokens", comparison.base.total_tokens, comparison.target.total_tokens
        ),
    ]
    return "\n".join(lines) + "\n"


def compare_request_artifacts(
    base: RequestArtifact,
    target: RequestArtifact,
) -> RequestArtifactComparison:
    """Compare validated artifacts without reproducing their prompt contents."""

    message_count = max(len(base.messages), len(target.messages))
    changed_message_indices = tuple(
        index
        for index in range(message_count)
        if index >= len(base.messages)
        or index >= len(target.messages)
        or base.messages[index] != target.messages[index]
    )
    added_context = _ordered_context_difference(target.context, base.context)
    removed_context = _ordered_context_difference(base.context, target.context)
    return RequestArtifactComparison(
        base_fingerprint=base.fingerprint,
        target_fingerprint=target.fingerprint,
        changed_message_indices=changed_message_indices,
        base_message_count=len(base.messages),
        target_message_count=len(target.messages),
        added_context=added_context,
        removed_context=removed_context,
        base_context_bytes=base.context_bytes,
        target_context_bytes=target.context_bytes,
        base_estimated_input_tokens=base.estimated_input_tokens,
        target_estimated_input_tokens=target.estimated_input_tokens,
    )


def render_artifact_comparison(
    comparison: RequestArtifactComparison,
    *,
    output_format: str = "text",
) -> str:
    """Render an artifact comparison as text or stable JSON."""

    if output_format == "json":
        return json.dumps(comparison.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if output_format != "text":
        raise ArtifactError("artifact comparison format must be text or json")

    lines = [
        "Request artifacts differ." if comparison.changed else "Request artifacts are identical.",
        f"Base: {comparison.base_fingerprint}",
        f"Target: {comparison.target_fingerprint}",
    ]
    if comparison.changed_message_indices:
        indices = ", ".join(str(index) for index in comparison.changed_message_indices)
        lines.append(f"Messages: changed at zero-based index(es) {indices}")
    else:
        lines.append("Messages: unchanged")
    lines.append(
        "Context: "
        f"{len(comparison.added_context)} added, {len(comparison.removed_context)} removed, "
        f"{_format_delta(comparison.target_context_bytes - comparison.base_context_bytes)} bytes"
    )
    for item in comparison.removed_context:
        lines.append(f"- {item.name}: {item.size_bytes:,} bytes, {item.content_sha256}")
    for item in comparison.added_context:
        lines.append(f"+ {item.name}: {item.size_bytes:,} bytes, {item.content_sha256}")
    token_delta = comparison.target_estimated_input_tokens - comparison.base_estimated_input_tokens
    lines.append(
        "Estimated input: "
        f"~{comparison.base_estimated_input_tokens:,} -> "
        f"~{comparison.target_estimated_input_tokens:,} tokens "
        f"({_format_delta(token_delta)})"
    )
    return "\n".join(lines) + "\n"


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


def _decode_bounded_json(raw: str | bytes, *, label: str, maximum: int) -> str:
    if isinstance(raw, bytes):
        if len(raw) > maximum:
            raise ArtifactError(f"{label} exceeds the {maximum:,}-byte safety limit")
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArtifactError(f"{label} is not valid UTF-8") from exc
    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ArtifactError(f"{label} is not valid UTF-8") from exc
    if len(encoded) > maximum:
        raise ArtifactError(f"{label} exceeds the {maximum:,}-byte safety limit")
    return raw


def _normalize_result_model(value: object, *, require_canonical: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactError("execution result model cannot be empty")
    normalized = value.strip()
    if require_canonical and value != normalized:
        raise ArtifactError("execution result model must not have surrounding whitespace")
    if len(normalized) > MAX_MODEL_CHARS:
        raise ArtifactError(f"execution result model exceeds the {MAX_MODEL_CHARS}-character limit")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ArtifactError("execution result model contains a control character")
    return normalized


def _parse_usage_value(label: str, value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ArtifactError(f"execution result {label} must be a non-negative integer or null")
    return value


def _summarize_execution_result(result: ExecutionResult) -> ExecutionResultSummary:
    response_bytes = _utf8_size(result.response_text, label="execution result response text")
    return ExecutionResultSummary(
        model=result.model,
        response_chars=len(result.response_text),
        response_bytes=response_bytes,
        response_sha256=_sha256_text(result.response_text),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
    )


def _optional_delta(base: int | None, target: int | None) -> int | None:
    if base is None or target is None:
        return None
    return target - base


def _utf8_size(value: str, *, label: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ArtifactError(f"{label} is not valid UTF-8") from exc


def _render_usage_comparison(label: str, base: int | None, target: int | None) -> str:
    if base is None or target is None:
        base_value = "not reported" if base is None else f"{base:,}"
        target_value = "not reported" if target is None else f"{target:,}"
        return f"{label}: unavailable (base: {base_value}, target: {target_value})"
    return f"{label}: {base:,} -> {target:,} ({_format_delta(target - base)})"


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


def _context_record_payload(item: ContextRecord) -> dict[str, Any]:
    return {
        "name": item.name,
        "bytes": item.size_bytes,
        "content_sha256": item.content_sha256,
    }


def _ordered_context_difference(
    items: Sequence[ContextRecord],
    subtract: Sequence[ContextRecord],
) -> tuple[ContextRecord, ...]:
    remaining = list(subtract)
    difference: list[ContextRecord] = []
    for item in items:
        try:
            index = remaining.index(item)
        except ValueError:
            difference.append(item)
        else:
            remaining.pop(index)
    return tuple(difference)


def _format_delta(value: int) -> str:
    return f"{value:+,}"


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
