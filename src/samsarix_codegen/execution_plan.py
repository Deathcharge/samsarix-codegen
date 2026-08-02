# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Strict execution plans binding reviewed requests to provider settings."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from samsarix_codegen.artifact import (
    FINGERPRINT_PREFIX,
    MAX_ARTIFACT_CONTEXT_ITEMS,
    MAX_ARTIFACT_MESSAGES,
    ExecutionResultPolicy,
    RequestArtifact,
)
from samsarix_codegen.errors import ArtifactError, ConfigurationError
from samsarix_codegen.models import (
    MAX_ESTIMATED_INPUT_TOKENS,
    MAX_PROVIDER_OUTPUT_TOKENS,
    MAX_PROVIDER_TIMEOUT_SECONDS,
    ProviderConfig,
)
from samsarix_codegen.result_policy import fingerprint_execution_result_policy

EXECUTION_PLAN_SCHEMA_VERSION = 2
EXECUTION_PLAN_VERIFICATION_SCHEMA_VERSION = 2
SUPPORTED_EXECUTION_PLAN_SCHEMA_VERSIONS = frozenset({1, EXECUTION_PLAN_SCHEMA_VERSION})
MAX_EXECUTION_PLAN_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """One credential-free provider configuration bound to a reviewed request."""

    request_fingerprint: str
    endpoint: str
    model: str
    timeout_seconds: int
    max_output_tokens: int
    max_estimated_input_tokens: int
    result_policy_fingerprint: str | None = None
    schema_version: int = EXECUTION_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version not in SUPPORTED_EXECUTION_PLAN_SCHEMA_VERSIONS
        ):
            raise ArtifactError(
                f"unsupported execution plan schema: {self.schema_version!r}; "
                f"expected one of {sorted(SUPPORTED_EXECUTION_PLAN_SCHEMA_VERSIONS)}"
            )
        if not _is_sha256(self.request_fingerprint):
            raise ArtifactError("execution plan contains an invalid request fingerprint")
        if self.result_policy_fingerprint is not None and not _is_sha256(
            self.result_policy_fingerprint
        ):
            raise ArtifactError("execution plan contains an invalid result policy fingerprint")
        if self.schema_version == 1 and self.result_policy_fingerprint is not None:
            raise ArtifactError("execution plan schema version 1 cannot bind a result policy")
        if (
            not isinstance(self.timeout_seconds, int)
            or isinstance(self.timeout_seconds, bool)
            or not 1 <= self.timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS
        ):
            raise ArtifactError(
                "execution plan timeout_seconds must be between "
                f"1 and {MAX_PROVIDER_TIMEOUT_SECONDS}"
            )
        if (
            not isinstance(self.max_output_tokens, int)
            or isinstance(self.max_output_tokens, bool)
            or not 1 <= self.max_output_tokens <= MAX_PROVIDER_OUTPUT_TOKENS
        ):
            raise ArtifactError(
                "execution plan max_output_tokens must be between "
                f"1 and {MAX_PROVIDER_OUTPUT_TOKENS:,}"
            )
        if (
            not isinstance(self.max_estimated_input_tokens, int)
            or isinstance(self.max_estimated_input_tokens, bool)
            or not 1 <= self.max_estimated_input_tokens <= MAX_ESTIMATED_INPUT_TOKENS
        ):
            raise ArtifactError(
                "execution plan max_estimated_input_tokens must be between "
                f"1 and {MAX_ESTIMATED_INPUT_TOKENS:,}"
            )

        try:
            config = ProviderConfig(
                endpoint=self.endpoint,
                model=self.model,
                timeout_seconds=self.timeout_seconds,
                max_output_tokens=self.max_output_tokens,
            )
        except ConfigurationError as exc:
            raise ArtifactError(f"execution plan provider configuration is invalid: {exc}") from exc
        if config.endpoint != self.endpoint or config.model != self.model:
            raise ArtifactError("execution plan endpoint and model must use canonical values")

    @property
    def fingerprint(self) -> str:
        """Return the deterministic digest of all executable plan fields."""

        return _fingerprint(self._unsigned_payload())

    def _unsigned_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "request_fingerprint": self.request_fingerprint,
            "provider": {
                "endpoint": self.endpoint,
                "model": self.model,
                "timeout_seconds": self.timeout_seconds,
                "max_output_tokens": self.max_output_tokens,
            },
            "budgets": {
                "max_estimated_input_tokens": self.max_estimated_input_tokens,
            },
        }
        if self.schema_version >= 2:
            payload["result_policy_fingerprint"] = self.result_policy_fingerprint
        return payload

    def to_payload(self) -> dict[str, Any]:
        """Return the stable JSON-compatible plan representation."""

        unsigned = self._unsigned_payload()
        payload = {
            "schema_version": unsigned["schema_version"],
            "plan_fingerprint": self.fingerprint,
            "request_fingerprint": unsigned["request_fingerprint"],
            "provider": unsigned["provider"],
            "budgets": unsigned["budgets"],
        }
        if self.schema_version >= 2:
            payload["result_policy_fingerprint"] = unsigned["result_policy_fingerprint"]
        return payload


@dataclass(frozen=True, slots=True)
class ExecutionPlanVerification:
    """Content-omitting proof that one plan matches one validated request."""

    plan: ExecutionPlan
    request_messages: int
    request_context_items: int
    request_context_bytes: int
    request_estimated_input_tokens: int

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ExecutionPlan):
            raise ArtifactError("execution plan verification requires a validated plan")
        _require_integer(
            self.request_messages,
            label="execution plan verification request messages",
            minimum=1,
            maximum=MAX_ARTIFACT_MESSAGES,
        )
        _require_integer(
            self.request_context_items,
            label="execution plan verification request context items",
            minimum=0,
            maximum=MAX_ARTIFACT_CONTEXT_ITEMS,
        )
        _require_integer(
            self.request_context_bytes,
            label="execution plan verification request context bytes",
            minimum=0,
        )
        _require_integer(
            self.request_estimated_input_tokens,
            label="execution plan verification estimated input tokens",
            minimum=1,
            maximum=MAX_ESTIMATED_INPUT_TOKENS,
        )
        if self.request_estimated_input_tokens > self.plan.max_estimated_input_tokens:
            raise ArtifactError("execution plan verification exceeds its estimated-input budget")

    @property
    def remaining_estimated_input_tokens(self) -> int:
        """Return the transparent plan budget remaining after this request."""

        return self.plan.max_estimated_input_tokens - self.request_estimated_input_tokens

    def to_payload(self) -> dict[str, Any]:
        """Return a stable verification without prompt contents or credentials."""

        return {
            "schema_version": EXECUTION_PLAN_VERIFICATION_SCHEMA_VERSION,
            "plan_fingerprint": self.plan.fingerprint,
            "result_policy_fingerprint": self.plan.result_policy_fingerprint,
            "request": {
                "fingerprint": self.plan.request_fingerprint,
                "messages": self.request_messages,
                "context_items": self.request_context_items,
                "context_bytes": self.request_context_bytes,
                "estimated_input_tokens": self.request_estimated_input_tokens,
            },
            "provider": {
                "endpoint": self.plan.endpoint,
                "model": self.plan.model,
                "timeout_seconds": self.plan.timeout_seconds,
                "max_output_tokens": self.plan.max_output_tokens,
            },
            "budgets": {
                "max_estimated_input_tokens": self.plan.max_estimated_input_tokens,
                "remaining_estimated_input_tokens": self.remaining_estimated_input_tokens,
            },
        }


class _DuplicatePlanKeyError(ValueError):
    """Internal signal for an ambiguous plan JSON object."""


def create_execution_plan(
    artifact: RequestArtifact,
    config: ProviderConfig,
    *,
    max_estimated_input_tokens: int | None = None,
    result_policy_fingerprint: str | None = None,
) -> ExecutionPlan:
    """Bind one validated request to canonical provider settings without credentials."""

    if not isinstance(artifact, RequestArtifact):
        raise ArtifactError("execution plan creation requires a validated request artifact")
    if not isinstance(config, ProviderConfig):
        raise ArtifactError("execution plan creation requires validated provider configuration")
    limit = (
        artifact.estimated_input_tokens
        if max_estimated_input_tokens is None
        else max_estimated_input_tokens
    )
    plan = ExecutionPlan(
        request_fingerprint=artifact.fingerprint,
        endpoint=config.endpoint,
        model=config.model,
        timeout_seconds=_exact_timeout(config.timeout_seconds),
        max_output_tokens=config.max_output_tokens,
        max_estimated_input_tokens=limit,
        result_policy_fingerprint=result_policy_fingerprint,
    )
    if artifact.estimated_input_tokens > plan.max_estimated_input_tokens:
        raise ArtifactError(
            f"request estimate is {artifact.estimated_input_tokens:,} tokens; "
            "the execution-plan limit is "
            f"{plan.max_estimated_input_tokens:,}"
        )
    return plan


def parse_execution_plan(raw: str | bytes) -> ExecutionPlan:
    """Parse and authenticate the internal digest of one strict plan document."""

    text = _decode_plan_document(raw)
    try:
        decoded: Any = json.loads(text, object_pairs_hook=_reject_duplicate_plan_keys)
    except _DuplicatePlanKeyError as exc:
        raise ArtifactError(str(exc)) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        message = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
        raise ArtifactError(f"execution plan is not valid JSON: {message}") from exc
    if not isinstance(decoded, dict):
        raise ArtifactError("execution plan must be a JSON object")
    schema_version = decoded.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version not in SUPPORTED_EXECUTION_PLAN_SCHEMA_VERSIONS
    ):
        raise ArtifactError(
            f"unsupported execution plan schema: {schema_version!r}; "
            f"expected one of {sorted(SUPPORTED_EXECUTION_PLAN_SCHEMA_VERSIONS)}"
        )
    required_fields = {
        "schema_version",
        "plan_fingerprint",
        "request_fingerprint",
        "provider",
        "budgets",
    }
    if schema_version >= 2:
        required_fields.add("result_policy_fingerprint")
    if set(decoded) != required_fields:
        raise ArtifactError(f"execution plan fields do not match schema version {schema_version}")

    provider = decoded.get("provider")
    budgets = decoded.get("budgets")
    if not isinstance(provider, dict) or set(provider) != {
        "endpoint",
        "model",
        "timeout_seconds",
        "max_output_tokens",
    }:
        raise ArtifactError("execution plan provider fields do not match schema version 1")
    if not isinstance(budgets, dict) or set(budgets) != {"max_estimated_input_tokens"}:
        raise ArtifactError("execution plan budget fields do not match schema version 1")

    plan = ExecutionPlan(
        request_fingerprint=cast(str, decoded.get("request_fingerprint")),
        endpoint=cast(str, provider.get("endpoint")),
        model=cast(str, provider.get("model")),
        timeout_seconds=cast(int, provider.get("timeout_seconds")),
        max_output_tokens=cast(int, provider.get("max_output_tokens")),
        max_estimated_input_tokens=cast(int, budgets.get("max_estimated_input_tokens")),
        result_policy_fingerprint=(
            cast(str | None, decoded.get("result_policy_fingerprint"))
            if schema_version >= 2
            else None
        ),
        schema_version=schema_version,
    )
    fingerprint = decoded.get("plan_fingerprint")
    if not isinstance(fingerprint, str) or not _is_sha256(fingerprint):
        raise ArtifactError("execution plan contains an invalid plan fingerprint")
    if not hmac.compare_digest(plan.fingerprint, fingerprint):
        raise ArtifactError("execution plan fingerprint does not match its canonical content")
    return plan


def render_execution_plan(plan: ExecutionPlan) -> str:
    """Render one validated execution plan deterministically."""

    if not isinstance(plan, ExecutionPlan):
        raise ArtifactError("execution plan rendering requires a validated plan")
    rendered = json.dumps(plan.to_payload(), ensure_ascii=False, indent=2) + "\n"
    try:
        rendered_size = len(rendered.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ArtifactError("execution plan is not valid Unicode") from exc
    if rendered_size > MAX_EXECUTION_PLAN_BYTES:
        raise ArtifactError(
            f"execution plan exceeds the {MAX_EXECUTION_PLAN_BYTES:,}-byte safety limit"
        )
    return rendered


def load_execution_plan(path: str | Path) -> ExecutionPlan:
    """Load one explicitly selected bounded execution-plan file."""

    try:
        plan_path = Path(path)
        if not plan_path.is_file():
            raise ArtifactError(f"execution plan is not a regular file: {path}")
        if plan_path.stat().st_size > MAX_EXECUTION_PLAN_BYTES:
            raise ArtifactError(
                f"execution plan exceeds the {MAX_EXECUTION_PLAN_BYTES:,}-byte safety limit"
            )
        with plan_path.open("rb") as handle:
            raw = handle.read(MAX_EXECUTION_PLAN_BYTES + 1)
    except ArtifactError:
        raise
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"cannot read execution plan {path}: {exc}") from exc
    return parse_execution_plan(raw)


def verify_execution_plan(
    artifact: RequestArtifact,
    plan: ExecutionPlan,
    *,
    expected_plan_fingerprint: str | None = None,
) -> ExecutionPlanVerification:
    """Verify request linkage, an optional approval digest, and the input budget."""

    if not isinstance(artifact, RequestArtifact):
        raise ArtifactError("execution plan verification requires a validated request artifact")
    if not isinstance(plan, ExecutionPlan):
        raise ArtifactError("execution plan verification requires a validated plan")
    if not hmac.compare_digest(artifact.fingerprint, plan.request_fingerprint):
        raise ArtifactError("execution plan does not reference the supplied request artifact")
    if expected_plan_fingerprint is not None:
        if not _is_sha256(expected_plan_fingerprint):
            raise ArtifactError(
                "--expect-plan-fingerprint must be a sha256:<64 lowercase hex> value"
            )
        if not hmac.compare_digest(plan.fingerprint, expected_plan_fingerprint):
            raise ArtifactError(
                "execution plan does not match the fingerprint approved by the operator"
            )
    if artifact.estimated_input_tokens > plan.max_estimated_input_tokens:
        raise ArtifactError(
            f"request estimate is {artifact.estimated_input_tokens:,} tokens; "
            f"the execution-plan limit is {plan.max_estimated_input_tokens:,}"
        )
    return ExecutionPlanVerification(
        plan=plan,
        request_messages=len(artifact.messages),
        request_context_items=len(artifact.context),
        request_context_bytes=artifact.context_bytes,
        request_estimated_input_tokens=artifact.estimated_input_tokens,
    )


def provider_config_from_execution_plan(
    plan: ExecutionPlan,
    *,
    api_key: str | None = None,
) -> ProviderConfig:
    """Create the exact runtime provider config; credentials remain external."""

    if not isinstance(plan, ExecutionPlan):
        raise ArtifactError("provider configuration requires a validated execution plan")
    return ProviderConfig(
        endpoint=plan.endpoint,
        model=plan.model,
        api_key=api_key,
        timeout_seconds=plan.timeout_seconds,
        max_output_tokens=plan.max_output_tokens,
    )


def require_execution_plan_result_policy(
    plan: ExecutionPlan,
    result_policy: ExecutionResultPolicy | None,
) -> str | None:
    """Require an exact policy file when a reviewed plan binds its fingerprint."""

    if not isinstance(plan, ExecutionPlan):
        raise ArtifactError("result policy verification requires a validated execution plan")
    expected = plan.result_policy_fingerprint
    if expected is None:
        if (
            result_policy is not None
            and result_policy.expected_model is not None
            and result_policy.expected_model != plan.model
        ):
            raise ArtifactError(
                "result policy expected model does not match the execution-plan model"
            )
        return None
    if result_policy is None:
        raise ArtifactError("execution plan requires its bound result policy")
    actual = fingerprint_execution_result_policy(result_policy)
    if not hmac.compare_digest(actual, expected):
        raise ArtifactError(
            "result policy does not match the fingerprint bound by the execution plan"
        )
    if result_policy.expected_model is not None and result_policy.expected_model != plan.model:
        raise ArtifactError("result policy expected model does not match the execution-plan model")
    return actual


def render_execution_plan_verification(
    verification: ExecutionPlanVerification,
    *,
    output_format: str = "text",
) -> str:
    """Render content-omitting plan/request linkage and executable settings."""

    if not isinstance(verification, ExecutionPlanVerification):
        raise ArtifactError("execution plan verification rendering requires validated evidence")
    if output_format == "json":
        return json.dumps(verification.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if output_format == "fingerprint":
        return verification.plan.fingerprint + "\n"
    if output_format != "text":
        raise ArtifactError("execution plan verification format must be text, json, or fingerprint")

    plan = verification.plan
    lines = [
        "Execution plan references the supplied validated request.",
        f"Plan: {plan.fingerprint}",
        (
            "Result policy: unbound"
            if plan.result_policy_fingerprint is None
            else f"Result policy: {plan.result_policy_fingerprint} (bound)"
        ),
        f"Request: {plan.request_fingerprint}",
        f"Request messages: {verification.request_messages:,}",
        (
            "Request context: "
            f"{verification.request_context_items:,} item(s), "
            f"{verification.request_context_bytes:,} bytes"
        ),
        (
            "Estimated input: "
            f"~{verification.request_estimated_input_tokens:,} / "
            f"{plan.max_estimated_input_tokens:,} tokens"
        ),
        f"Endpoint: {plan.endpoint}",
        f"Model: {plan.model}",
        f"Timeout: {plan.timeout_seconds:,} seconds",
        f"Maximum output: {plan.max_output_tokens:,} tokens",
    ]
    return "\n".join(lines) + "\n"


def _decode_plan_document(raw: str | bytes) -> str:
    if isinstance(raw, bytes):
        if len(raw) > MAX_EXECUTION_PLAN_BYTES:
            raise ArtifactError(
                f"execution plan exceeds the {MAX_EXECUTION_PLAN_BYTES:,}-byte safety limit"
            )
        if b"\x00" in raw:
            raise ArtifactError("binary execution plans are not supported")
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArtifactError("execution plan is not valid UTF-8") from exc
    if not isinstance(raw, str):
        raise ArtifactError("execution plan input must be UTF-8 text or bytes")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ArtifactError("execution plan text is not valid Unicode") from exc
    if len(encoded) > MAX_EXECUTION_PLAN_BYTES:
        raise ArtifactError(
            f"execution plan exceeds the {MAX_EXECUTION_PLAN_BYTES:,}-byte safety limit"
        )
    if "\x00" in raw:
        raise ArtifactError("binary execution plans are not supported")
    return raw


def _reject_duplicate_plan_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicatePlanKeyError(f"execution plan contains a duplicate JSON field: {key}")
        decoded[key] = value
    return decoded


def _exact_timeout(value: float) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactError("execution plans require an integer timeout in seconds")
    if isinstance(value, float):
        if not value.is_integer():
            raise ArtifactError("execution plans require an integer timeout in seconds")
        return int(value)
    return value


def _require_integer(
    value: object,
    *,
    label: str,
    minimum: int,
    maximum: int | None = None,
) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        if maximum is None:
            raise ArtifactError(f"{label} must be at least {minimum:,}")
        raise ArtifactError(f"{label} must be between {minimum:,} and {maximum:,}")


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return FINGERPRINT_PREFIX + hashlib.sha256(canonical).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith(FINGERPRINT_PREFIX) or len(value) != len(FINGERPRINT_PREFIX) + 64:
        return False
    return all(character in "0123456789abcdef" for character in value[len(FINGERPRINT_PREFIX) :])
