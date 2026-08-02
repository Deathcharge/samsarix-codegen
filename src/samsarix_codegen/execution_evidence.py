# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Offline verification of a request, reviewed plan, and stored provider result."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from typing import Any

from samsarix_codegen.artifact import (
    ExecutionResult,
    ExecutionResultPolicy,
    ExecutionResultSummary,
    RequestArtifact,
    enforce_execution_result_summary_policy,
    inspect_execution_result,
    verify_execution_result,
)
from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.execution_plan import (
    ExecutionPlan,
    ExecutionPlanVerification,
    require_execution_plan_result_policy,
    verify_execution_plan,
)
from samsarix_codegen.result_policy import (
    fingerprint_execution_result_policy,
    render_execution_result_policy,
    require_execution_result_policy_fingerprint,
)

EXECUTION_EVIDENCE_SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class ExecutionEvidenceVerification:
    """Content-omitting evidence for one internally consistent execution chain."""

    plan_verification: ExecutionPlanVerification
    result: ExecutionResultSummary
    result_request_fingerprint: str
    result_policy: ExecutionResultPolicy | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan_verification, ExecutionPlanVerification):
            raise ArtifactError("execution evidence requires a validated plan verification")
        if not isinstance(self.result, ExecutionResultSummary):
            raise ArtifactError("execution evidence requires a validated result summary")

        plan = self.plan_verification.plan
        if not _is_sha256(self.result_request_fingerprint):
            raise ArtifactError("execution evidence contains an invalid result request fingerprint")
        if not hmac.compare_digest(plan.request_fingerprint, self.result_request_fingerprint):
            raise ArtifactError("execution result does not reference the supplied request artifact")
        if self.result.plan_fingerprint is None:
            raise ArtifactError("execution result does not record a reviewed execution plan")
        if not hmac.compare_digest(plan.fingerprint, self.result.plan_fingerprint):
            raise ArtifactError("execution result does not reference the supplied execution plan")
        if plan.model != self.result.model:
            raise ArtifactError(
                "execution result requested model does not match the execution plan"
            )
        if (
            self.result.completion_tokens is not None
            and self.result.completion_tokens > plan.max_output_tokens
        ):
            raise ArtifactError(
                "execution result completion usage exceeds the execution-plan output limit"
            )
        if self.result_policy is not None:
            if not isinstance(self.result_policy, ExecutionResultPolicy):
                raise ArtifactError("execution evidence requires a validated result policy")
            fingerprint_execution_result_policy(self.result_policy)
            enforce_execution_result_summary_policy(self.result, self.result_policy)
        require_execution_plan_result_policy(plan, self.result_policy)

    @property
    def result_policy_fingerprint(self) -> str | None:
        """Return the exact applied policy fingerprint, if policy enforcement was requested."""

        if self.result_policy is None:
            return None
        return fingerprint_execution_result_policy(self.result_policy)

    @property
    def remaining_reported_output_tokens(self) -> int | None:
        """Return remaining output headroom when the provider reported completion usage."""

        if self.result.completion_tokens is None:
            return None
        return self.plan_verification.plan.max_output_tokens - self.result.completion_tokens

    @property
    def response_structure(self) -> dict[str, object] | None:
        """Return non-value JSON-object evidence only when a structural rule passed."""

        if self.result_policy is None or self.result_policy.response_format is None:
            return None
        if self.result.response_json_key_hash_types is None:
            raise ArtifactError("execution evidence is missing validated response structure")
        return {
            "format": self.result_policy.response_format,
            "top_level_keys": len(self.result.response_json_key_hash_types),
        }

    def to_payload(self) -> dict[str, Any]:
        """Return portable linkage evidence without prompt or response contents."""

        plan = self.plan_verification.plan
        result_payload = self.result.to_payload()
        policy_payload = (
            None
            if self.result_policy is None
            else {
                "fingerprint": self.result_policy_fingerprint,
                "rules": json.loads(render_execution_result_policy(self.result_policy)),
            }
        )
        return {
            "schema_version": EXECUTION_EVIDENCE_SCHEMA_VERSION,
            "plan_fingerprint": plan.fingerprint,
            "result_policy": policy_payload,
            "request": {
                "fingerprint": plan.request_fingerprint,
                "messages": self.plan_verification.request_messages,
                "context_items": self.plan_verification.request_context_items,
                "context_bytes": self.plan_verification.request_context_bytes,
                "estimated_input_tokens": (self.plan_verification.request_estimated_input_tokens),
            },
            "provider": {
                "endpoint": plan.endpoint,
                "requested_model": plan.model,
                "response_model": self.result.response_model,
                "timeout_seconds": plan.timeout_seconds,
                "max_output_tokens": plan.max_output_tokens,
            },
            "budgets": {
                "max_estimated_input_tokens": plan.max_estimated_input_tokens,
                "remaining_estimated_input_tokens": (
                    self.plan_verification.remaining_estimated_input_tokens
                ),
                "reported_completion_tokens": self.result.completion_tokens,
                "remaining_reported_output_tokens": self.remaining_reported_output_tokens,
            },
            "result": {
                "response": result_payload["response"],
                "response_structure": self.response_structure,
                "usage": result_payload["usage"],
            },
        }


def verify_execution_evidence(
    artifact: RequestArtifact,
    plan: ExecutionPlan,
    result: ExecutionResult,
    *,
    expected_plan_fingerprint: str | None = None,
    result_policy: ExecutionResultPolicy | None = None,
    expected_policy_fingerprint: str | None = None,
) -> ExecutionEvidenceVerification:
    """Validate every local linkage in one request-plan-result evidence chain."""

    plan_verification = verify_execution_plan(
        artifact,
        plan,
        expected_plan_fingerprint=expected_plan_fingerprint,
    )
    verify_execution_result(artifact, result)
    if expected_policy_fingerprint is not None:
        if result_policy is None:
            raise ArtifactError(
                "an expected result policy fingerprint requires an explicit result policy"
            )
        require_execution_result_policy_fingerprint(result_policy, expected_policy_fingerprint)
    require_execution_plan_result_policy(plan, result_policy)
    return ExecutionEvidenceVerification(
        plan_verification=plan_verification,
        result=inspect_execution_result(result).summary,
        result_request_fingerprint=result.request_fingerprint,
        result_policy=result_policy,
    )


def render_execution_evidence_verification(
    verification: ExecutionEvidenceVerification,
    *,
    output_format: str = "text",
) -> str:
    """Render content-omitting execution-chain evidence as text or JSON."""

    if not isinstance(verification, ExecutionEvidenceVerification):
        raise ArtifactError("execution evidence rendering requires validated evidence")
    if output_format == "json":
        return json.dumps(verification.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if output_format != "text":
        raise ArtifactError("execution evidence format must be text or json")

    plan = verification.plan_verification.plan
    result = verification.result
    lines = [
        "Request, execution plan, and result form a consistent local evidence chain.",
        f"Plan: {plan.fingerprint}",
        (
            "Result policy: not applied"
            if verification.result_policy is None
            else f"Result policy: {verification.result_policy_fingerprint} (passed)"
        ),
        f"Request: {plan.request_fingerprint}",
        (
            "Request context: "
            f"{verification.plan_verification.request_context_items:,} item(s), "
            f"{verification.plan_verification.request_context_bytes:,} bytes"
        ),
        (
            "Estimated input: "
            f"~{verification.plan_verification.request_estimated_input_tokens:,} / "
            f"{plan.max_estimated_input_tokens:,} tokens"
        ),
        f"Endpoint: {plan.endpoint}",
        f"Requested model: {plan.model}",
        f"Response model: {result.response_model or 'not reported'}",
        f"Timeout: {plan.timeout_seconds:,} seconds",
        (
            "Reported completion: "
            f"{_format_optional(result.completion_tokens)} / "
            f"{plan.max_output_tokens:,} tokens"
        ),
        f"Response characters: {result.response_chars:,}",
        f"Response bytes: {result.response_bytes:,}",
        (
            "Response structure: not evaluated"
            if verification.response_structure is None
            else (
                "Response structure: JSON object, "
                f"{len(result.response_json_key_hash_types or ()):,} top-level key(s)"
            )
        ),
        f"Response: {result.response_sha256}",
        f"Prompt tokens: {_format_optional(result.prompt_tokens)}",
        f"Total tokens: {_format_optional(result.total_tokens)}",
    ]
    return "\n".join(lines) + "\n"


def _format_optional(value: int | None) -> str:
    return "not reported" if value is None else f"{value:,}"


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        return False
    return all(character in "0123456789abcdef" for character in value[7:])
