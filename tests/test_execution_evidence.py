# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json

import pytest

from samsarix_codegen import (
    ExecutionEvidenceVerification,
    fingerprint_execution_result_policy,
    render_execution_evidence_verification,
    verify_execution_evidence,
)
from samsarix_codegen.artifact import (
    ExecutionResult,
    ExecutionResultPolicy,
    create_request_artifact,
    parse_execution_result,
    render_execution_result,
)
from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.execution_plan import create_execution_plan, verify_execution_plan
from samsarix_codegen.models import ChatResult, PromptRequest, ProviderConfig, Task
from samsarix_codegen.prompt import build_messages


def make_chain(
    *,
    result_model: str = "requested-model",
    response_model: str | None = "served-model-2026-08",
    completion_tokens: int | None = 12,
    response_text: str = "Private provider response",
    bound_policy: ExecutionResultPolicy | None = None,
):
    artifact = create_request_artifact(
        build_messages(PromptRequest(Task.REVIEW, "Private review instruction")),
        (),
    )
    plan = create_execution_plan(
        artifact,
        ProviderConfig(
            "https://models.example.com/v1",
            "requested-model",
            timeout_seconds=45,
            max_output_tokens=64,
        ),
        max_estimated_input_tokens=artifact.estimated_input_tokens + 100,
        result_policy_fingerprint=(
            None if bound_policy is None else fingerprint_execution_result_policy(bound_policy)
        ),
    )
    result = parse_execution_result(
        render_execution_result(
            artifact,
            ChatResult(
                response_text,
                prompt_tokens=30,
                completion_tokens=completion_tokens,
                total_tokens=None if completion_tokens is None else 30 + completion_tokens,
                response_model=response_model,
            ),
            model=result_model,
            plan_fingerprint=plan.fingerprint,
        )
    )
    return artifact, plan, result


def test_execution_evidence_links_chain_without_contents_and_allows_model_alias() -> None:
    artifact, plan, result = make_chain()

    evidence = verify_execution_evidence(
        artifact,
        plan,
        result,
        expected_plan_fingerprint=plan.fingerprint,
    )
    text = render_execution_evidence_verification(evidence)
    rendered = render_execution_evidence_verification(evidence, output_format="json")
    payload = json.loads(rendered)

    assert isinstance(evidence, ExecutionEvidenceVerification)
    assert payload["schema_version"] == 3
    assert payload["plan_fingerprint"] == plan.fingerprint
    assert payload["result_policy"] is None
    assert payload["request"]["fingerprint"] == artifact.fingerprint
    assert payload["provider"] == {
        "endpoint": plan.endpoint,
        "requested_model": "requested-model",
        "response_model": "served-model-2026-08",
        "timeout_seconds": 45,
        "max_output_tokens": 64,
    }
    assert payload["budgets"]["remaining_estimated_input_tokens"] == 100
    assert payload["budgets"]["reported_completion_tokens"] == 12
    assert payload["budgets"]["remaining_reported_output_tokens"] == 52
    assert payload["result"]["response"]["sha256"].startswith("sha256:")
    assert payload["result"]["response_structure"] is None
    assert "Response structure: not evaluated" in text
    assert "consistent local evidence chain" in text
    for private in ("Private review instruction", "Private provider response"):
        assert private not in text
        assert private not in rendered


def test_execution_evidence_enforces_and_identifies_the_exact_result_policy() -> None:
    artifact, plan, result = make_chain()
    policy = ExecutionResultPolicy(
        expected_model="requested-model",
        max_response_bytes=100,
        max_completion_tokens=12,
    )
    policy_fingerprint = fingerprint_execution_result_policy(policy)

    evidence = verify_execution_evidence(
        artifact,
        plan,
        result,
        result_policy=policy,
        expected_policy_fingerprint=policy_fingerprint,
    )
    payload = evidence.to_payload()
    text = render_execution_evidence_verification(evidence)

    assert evidence.result_policy_fingerprint == policy_fingerprint
    assert payload["result_policy"] == {
        "fingerprint": policy_fingerprint,
        "rules": {
            "schema_version": 1,
            "expected_model": "requested-model",
            "max_response_bytes": 100,
            "max_completion_tokens": 12,
        },
    }
    assert f"Result policy: {policy_fingerprint} (passed)" in text
    assert payload["result"]["response_structure"] is None


def test_execution_evidence_requires_the_policy_bound_by_the_plan() -> None:
    policy = ExecutionResultPolicy(
        expected_model="requested-model",
        max_response_bytes=100,
        max_completion_tokens=12,
    )
    artifact, plan, result = make_chain(bound_policy=policy)

    evidence = verify_execution_evidence(artifact, plan, result, result_policy=policy)

    assert evidence.result_policy_fingerprint == plan.result_policy_fingerprint
    with pytest.raises(ArtifactError, match="requires its bound result policy"):
        verify_execution_evidence(artifact, plan, result)
    with pytest.raises(ArtifactError, match="fingerprint bound"):
        verify_execution_evidence(
            artifact,
            plan,
            result,
            result_policy=ExecutionResultPolicy(expected_model="requested-model"),
        )


def test_execution_evidence_records_structural_policy_without_response_values() -> None:
    private_response = json.dumps(
        {
            "diagnosis": "Private diagnosis",
            "evidence": ["Private trace"],
            "next_step": "Private action",
        },
        separators=(",", ":"),
    )
    artifact, plan, result = make_chain(response_text=private_response)
    policy = ExecutionResultPolicy(
        expected_model="requested-model",
        response_format="json-object",
        required_json_keys=("diagnosis", "evidence", "next_step"),
        allowed_json_keys=("diagnosis", "evidence", "next_step"),
        json_key_types=(
            ("diagnosis", "string"),
            ("evidence", "array"),
            ("next_step", "string"),
        ),
        schema_version=2,
    )
    policy_fingerprint = fingerprint_execution_result_policy(policy)

    evidence = verify_execution_evidence(
        artifact,
        plan,
        result,
        result_policy=policy,
        expected_policy_fingerprint=policy_fingerprint,
    )
    payload = evidence.to_payload()
    rendered = render_execution_evidence_verification(evidence, output_format="json")
    text = render_execution_evidence_verification(evidence)

    assert payload["result_policy"]["rules"]["schema_version"] == 2
    assert payload["result"]["response_structure"] == {
        "format": "json-object",
        "top_level_keys": 3,
    }
    assert "Response structure: JSON object, 3 top-level key(s)" in text
    for private in ("Private diagnosis", "Private trace", "Private action"):
        assert private not in rendered
        assert private not in text
        assert private not in repr(evidence)


def test_execution_evidence_rejects_structural_policy_failure() -> None:
    artifact, plan, result = make_chain(response_text='{"diagnosis": "Private"}')
    policy = ExecutionResultPolicy(
        response_format="json-object",
        required_json_keys=("diagnosis", "evidence"),
        schema_version=2,
    )

    with pytest.raises(ArtifactError, match="missing required keys: evidence"):
        verify_execution_evidence(artifact, plan, result, result_policy=policy)


def test_execution_evidence_rejects_policy_failure_or_unapproved_policy() -> None:
    artifact, plan, result = make_chain()
    passing_policy = ExecutionResultPolicy(expected_model="requested-model")

    with pytest.raises(ArtifactError, match="does not match the execution-plan model"):
        verify_execution_evidence(
            artifact,
            plan,
            result,
            result_policy=ExecutionResultPolicy(expected_model="other-model"),
        )
    with pytest.raises(ArtifactError, match="does not match the expected fingerprint"):
        verify_execution_evidence(
            artifact,
            plan,
            result,
            result_policy=passing_policy,
            expected_policy_fingerprint="sha256:" + "0" * 64,
        )
    with pytest.raises(ArtifactError, match="requires an explicit result policy"):
        verify_execution_evidence(
            artifact,
            plan,
            result,
            expected_policy_fingerprint=fingerprint_execution_result_policy(passing_policy),
        )
    with pytest.raises(ArtifactError, match="must configure at least one rule"):
        verify_execution_evidence(
            artifact,
            plan,
            result,
            result_policy=ExecutionResultPolicy(),
        )


def test_execution_evidence_accepts_missing_provider_usage_and_response_model() -> None:
    artifact, plan, result = make_chain(response_model=None, completion_tokens=None)

    evidence = verify_execution_evidence(artifact, plan, result)
    payload = evidence.to_payload()

    assert evidence.remaining_reported_output_tokens is None
    assert payload["provider"]["response_model"] is None
    assert payload["budgets"]["reported_completion_tokens"] is None
    assert payload["budgets"]["remaining_reported_output_tokens"] is None


def test_execution_evidence_rejects_unbound_or_wrong_plan_results() -> None:
    artifact, plan, result = make_chain()
    unbound = ExecutionResult(
        artifact.fingerprint,
        plan.model,
        result.response_text,
        result.prompt_tokens,
        result.completion_tokens,
        result.total_tokens,
    )
    other_plan = create_execution_plan(
        artifact,
        ProviderConfig(plan.endpoint, plan.model, max_output_tokens=65),
    )
    other_artifact = create_request_artifact(
        build_messages(PromptRequest(Task.REVIEW, "Different request")), ()
    )
    wrong_request = parse_execution_result(
        render_execution_result(
            other_artifact,
            ChatResult("private"),
            model=plan.model,
            plan_fingerprint=plan.fingerprint,
        )
    )

    with pytest.raises(ArtifactError, match="does not record a reviewed execution plan"):
        verify_execution_evidence(artifact, plan, unbound)
    with pytest.raises(ArtifactError, match="does not reference the supplied execution plan"):
        verify_execution_evidence(artifact, other_plan, result)
    with pytest.raises(ArtifactError, match="does not reference the supplied request"):
        verify_execution_evidence(artifact, plan, wrong_request)


def test_execution_evidence_rejects_requested_model_or_reported_usage_drift() -> None:
    artifact, plan, wrong_model = make_chain(result_model="other-requested-model")
    _, _, over_budget = make_chain(completion_tokens=65)

    with pytest.raises(ArtifactError, match="requested model does not match"):
        verify_execution_evidence(artifact, plan, wrong_model)
    with pytest.raises(ArtifactError, match="completion usage exceeds"):
        verify_execution_evidence(artifact, plan, over_budget)


def test_execution_evidence_public_values_and_renderer_fail_closed() -> None:
    artifact, plan, result = make_chain()
    plan_verification = verify_execution_plan(artifact, plan)
    summary = verify_execution_evidence(artifact, plan, result).result

    with pytest.raises(ArtifactError, match="validated plan verification"):
        ExecutionEvidenceVerification(object(), result, artifact.fingerprint)  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="validated result summary"):
        ExecutionEvidenceVerification(  # type: ignore[arg-type]
            plan_verification, object(), artifact.fingerprint
        )
    with pytest.raises(ArtifactError, match="validated result policy"):
        ExecutionEvidenceVerification(  # type: ignore[arg-type]
            plan_verification, summary, artifact.fingerprint, object()
        )
    with pytest.raises(ArtifactError, match="invalid result request fingerprint"):
        ExecutionEvidenceVerification(plan_verification, summary, "invalid")
    with pytest.raises(ArtifactError, match="does not reference the supplied request"):
        ExecutionEvidenceVerification(plan_verification, summary, "sha256:" + "0" * 64)
    with pytest.raises(ArtifactError, match="validated evidence"):
        render_execution_evidence_verification(object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="format must be"):
        render_execution_evidence_verification(
            verify_execution_evidence(artifact, plan, result), output_format="yaml"
        )
