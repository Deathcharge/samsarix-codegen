# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from samsarix_codegen import create_execution_plan as public_create_execution_plan
from samsarix_codegen import parse_execution_plan as public_parse_execution_plan
from samsarix_codegen import render_execution_plan as public_render_execution_plan
from samsarix_codegen import verify_execution_plan as public_verify_execution_plan
from samsarix_codegen.artifact import create_request_artifact
from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.execution_plan import (
    MAX_EXECUTION_PLAN_BYTES,
    ExecutionPlan,
    ExecutionPlanVerification,
    create_execution_plan,
    load_execution_plan,
    parse_execution_plan,
    provider_config_from_execution_plan,
    render_execution_plan,
    render_execution_plan_verification,
    verify_execution_plan,
)
from samsarix_codegen.models import PromptRequest, ProviderConfig, Task
from samsarix_codegen.prompt import build_messages


def make_artifact(instruction: str = "Review the selected change"):
    request = PromptRequest(Task.REVIEW, instruction)
    return create_request_artifact(build_messages(request), request.files)


def make_plan() -> ExecutionPlan:
    return create_execution_plan(
        make_artifact(),
        ProviderConfig(
            "https://models.example.com/v1/",
            "model-a",
            api_key="must-not-be-serialized",
            timeout_seconds=45,
            max_output_tokens=512,
        ),
        max_estimated_input_tokens=10_000,
    )


def test_execution_plan_round_trips_and_excludes_credentials() -> None:
    plan = make_plan()

    rendered = render_execution_plan(plan)
    payload = json.loads(rendered)
    reparsed = parse_execution_plan(rendered.encode())

    assert reparsed == plan
    assert payload == {
        "schema_version": 1,
        "plan_fingerprint": plan.fingerprint,
        "request_fingerprint": plan.request_fingerprint,
        "provider": {
            "endpoint": "https://models.example.com/v1",
            "model": "model-a",
            "timeout_seconds": 45,
            "max_output_tokens": 512,
        },
        "budgets": {"max_estimated_input_tokens": 10_000},
    }
    assert "must-not-be-serialized" not in rendered
    assert (
        public_create_execution_plan(
            make_artifact(), ProviderConfig("https://models.example.com/v1", "model-a")
        ).request_fingerprint
        == make_artifact().fingerprint
    )
    assert public_parse_execution_plan(rendered) == plan
    assert public_render_execution_plan(plan) == rendered


def test_execution_plan_fingerprint_changes_with_every_executable_choice() -> None:
    plan = make_plan()
    variants = (
        ExecutionPlan(
            plan.request_fingerprint,
            "https://other.example.com/v1",
            plan.model,
            plan.timeout_seconds,
            plan.max_output_tokens,
            plan.max_estimated_input_tokens,
        ),
        ExecutionPlan(
            plan.request_fingerprint,
            plan.endpoint,
            "model-b",
            plan.timeout_seconds,
            plan.max_output_tokens,
            plan.max_estimated_input_tokens,
        ),
        ExecutionPlan(
            plan.request_fingerprint,
            plan.endpoint,
            plan.model,
            46,
            plan.max_output_tokens,
            plan.max_estimated_input_tokens,
        ),
        ExecutionPlan(
            plan.request_fingerprint,
            plan.endpoint,
            plan.model,
            plan.timeout_seconds,
            513,
            plan.max_estimated_input_tokens,
        ),
        ExecutionPlan(
            plan.request_fingerprint,
            plan.endpoint,
            plan.model,
            plan.timeout_seconds,
            plan.max_output_tokens,
            10_001,
        ),
    )

    assert len({plan.fingerprint, *(variant.fingerprint for variant in variants)}) == 6


def test_execution_plan_verification_links_request_and_exposes_no_prompt() -> None:
    artifact = make_artifact("Private review instruction")
    plan = create_execution_plan(
        artifact,
        ProviderConfig("http://127.0.0.1:11434/v1", "local-model"),
        max_estimated_input_tokens=artifact.estimated_input_tokens + 20,
    )

    verification = verify_execution_plan(
        artifact,
        plan,
        expected_plan_fingerprint=plan.fingerprint,
    )
    rendered = render_execution_plan_verification(verification, output_format="json")
    payload = json.loads(rendered)

    assert verification.remaining_estimated_input_tokens == 20
    assert payload["plan_fingerprint"] == plan.fingerprint
    assert payload["request"]["fingerprint"] == artifact.fingerprint
    assert payload["request"]["estimated_input_tokens"] == artifact.estimated_input_tokens
    assert payload["provider"]["model"] == "local-model"
    assert payload["budgets"]["remaining_estimated_input_tokens"] == 20
    assert "Private review instruction" not in rendered
    assert public_verify_execution_plan(artifact, plan) == verification
    assert (
        render_execution_plan_verification(verification, output_format="fingerprint")
        == plan.fingerprint + "\n"
    )


def test_execution_plan_rejects_mismatched_request_approval_and_budget() -> None:
    artifact = make_artifact("First")
    other = make_artifact("Second")
    plan = create_execution_plan(artifact, ProviderConfig("http://localhost:11434/v1", "local"))

    with pytest.raises(ArtifactError, match="does not reference"):
        verify_execution_plan(other, plan)
    with pytest.raises(ArtifactError, match="approved by the operator"):
        verify_execution_plan(
            artifact,
            plan,
            expected_plan_fingerprint="sha256:" + "0" * 64,
        )
    with pytest.raises(ArtifactError, match="must be a sha256"):
        verify_execution_plan(artifact, plan, expected_plan_fingerprint="invalid")

    undersized = ExecutionPlan(
        artifact.fingerprint,
        plan.endpoint,
        plan.model,
        plan.timeout_seconds,
        plan.max_output_tokens,
        artifact.estimated_input_tokens - 1,
    )
    with pytest.raises(ArtifactError, match="execution-plan limit"):
        verify_execution_plan(artifact, undersized)
    with pytest.raises(ArtifactError, match="execution-plan limit"):
        create_execution_plan(
            artifact,
            ProviderConfig("http://localhost:11434/v1", "local"),
            max_estimated_input_tokens=artifact.estimated_input_tokens - 1,
        )


def test_provider_config_from_execution_plan_adds_only_external_credential() -> None:
    plan = make_plan()

    config = provider_config_from_execution_plan(plan, api_key="external-secret")

    assert config.endpoint == plan.endpoint
    assert config.model == plan.model
    assert config.timeout_seconds == plan.timeout_seconds
    assert config.max_output_tokens == plan.max_output_tokens
    assert config.api_key == "external-secret"


def test_execution_plan_parser_rejects_ambiguous_or_tampered_documents() -> None:
    rendered = render_execution_plan(make_plan())
    payload = json.loads(rendered)

    tampered = json.loads(rendered)
    tampered["provider"]["model"] = "model-b"
    unknown = json.loads(rendered)
    unknown["unexpected"] = True
    wrong_provider = json.loads(rendered)
    wrong_provider["provider"]["unexpected"] = True
    wrong_budgets = json.loads(rendered)
    wrong_budgets["budgets"]["unexpected"] = True
    wrong_version = json.loads(rendered)
    wrong_version["schema_version"] = 2
    bad_fingerprint = json.loads(rendered)
    bad_fingerprint["plan_fingerprint"] = "invalid"

    cases = (
        ("[]", "fields do not match"),
        (json.dumps(unknown), "fields do not match"),
        (json.dumps(wrong_provider), "provider fields"),
        (json.dumps(wrong_budgets), "budget fields"),
        (json.dumps(wrong_version), "unsupported"),
        (json.dumps(bad_fingerprint), "invalid plan fingerprint"),
        (json.dumps(tampered), "does not match its canonical content"),
        (
            rendered.replace('"model": "model-a"', '"model": "model-a", "model": "model-a"'),
            "duplicate JSON field",
        ),
        (json.dumps({**payload, "schema_version": True}), "unsupported"),
    )
    for raw, match in cases:
        with pytest.raises(ArtifactError, match=match):
            parse_execution_plan(raw)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("request_fingerprint", "invalid", "request fingerprint"),
        ("endpoint", "http://remote.example.com/v1", "unencrypted http"),
        ("endpoint", "https://models.example.com/v1/", "canonical"),
        ("model", " model-a", "canonical"),
        ("model", "model\n", "canonical"),
        ("timeout_seconds", True, "timeout_seconds"),
        ("timeout_seconds", 301, "timeout_seconds"),
        ("max_output_tokens", 0, "max_output_tokens"),
        ("max_output_tokens", 32_769, "max_output_tokens"),
        ("max_estimated_input_tokens", 0, "max_estimated_input_tokens"),
        ("max_estimated_input_tokens", 2_000_001, "max_estimated_input_tokens"),
    ],
)
def test_execution_plan_values_fail_closed(field: str, value: object, match: str) -> None:
    values: dict[str, object] = {
        "request_fingerprint": "sha256:" + "a" * 64,
        "endpoint": "https://models.example.com/v1",
        "model": "model-a",
        "timeout_seconds": 60,
        "max_output_tokens": 1_024,
        "max_estimated_input_tokens": 10_000,
    }
    values[field] = value

    with pytest.raises(ArtifactError, match=match):
        ExecutionPlan(**values)  # type: ignore[arg-type]


def test_execution_plan_requires_integer_timeout_when_created_from_config() -> None:
    with pytest.raises(ArtifactError, match="integer timeout"):
        create_execution_plan(
            make_artifact(),
            ProviderConfig("https://models.example.com/v1", "model-a", timeout_seconds=1.5),
        )


def test_execution_plan_document_and_render_limits() -> None:
    with pytest.raises(ArtifactError, match="UTF-8 text or bytes"):
        parse_execution_plan(object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="byte safety limit"):
        parse_execution_plan(b" " * (MAX_EXECUTION_PLAN_BYTES + 1))
    with pytest.raises(ArtifactError, match="binary execution plans"):
        parse_execution_plan(b"{}\x00")
    with pytest.raises(ArtifactError, match="not valid UTF-8"):
        parse_execution_plan(b"\xff")
    with pytest.raises(ArtifactError, match="not valid Unicode"):
        parse_execution_plan('{"model": "\ud800"}')
    with pytest.raises(ArtifactError, match="requires a validated plan"):
        render_execution_plan(object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="must be text, json, or fingerprint"):
        render_execution_plan_verification(
            verify_execution_plan(
                make_artifact(),
                create_execution_plan(
                    make_artifact(), ProviderConfig("http://localhost:11434/v1", "local")
                ),
            ),
            output_format="yaml",
        )


def test_execution_plan_text_verification_is_useful_and_content_omitting() -> None:
    artifact = make_artifact("Private prompt content")
    plan = create_execution_plan(
        artifact,
        ProviderConfig("http://127.0.0.1:11434/v1", "reviewed-model"),
        max_estimated_input_tokens=artifact.estimated_input_tokens + 100,
    )

    rendered = render_execution_plan_verification(verify_execution_plan(artifact, plan))

    assert plan.fingerprint in rendered
    assert artifact.fingerprint in rendered
    assert plan.endpoint in rendered
    assert plan.model in rendered
    assert "Private prompt content" not in rendered


def test_execution_plan_loader_is_bounded_and_converts_path_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(render_execution_plan(make_plan()), encoding="utf-8")
    assert load_execution_plan(plan_path) == make_plan()

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_EXECUTION_PLAN_BYTES + 1))
    with pytest.raises(ArtifactError, match="byte safety limit"):
        load_execution_plan(oversized)
    with pytest.raises(ArtifactError, match="not a regular file"):
        load_execution_plan(tmp_path / "missing.json")

    original_is_file = Path.is_file

    def invalid_is_file(self: Path) -> bool:
        if self == plan_path:
            raise ValueError("embedded null character in path")
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", invalid_is_file)
    with pytest.raises(ArtifactError, match="cannot read execution plan"):
        load_execution_plan(plan_path)


def test_execution_plan_public_values_reject_wrong_objects() -> None:
    with pytest.raises(ArtifactError, match="validated request artifact"):
        create_execution_plan(object(), ProviderConfig("http://localhost:11434/v1", "local"))  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="validated provider configuration"):
        create_execution_plan(make_artifact(), object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="validated execution plan"):
        provider_config_from_execution_plan(object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="validated plan"):
        verify_execution_plan(make_artifact(), object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="validated plan"):
        ExecutionPlanVerification(object(), 1, 0, 0, 1)  # type: ignore[arg-type]
