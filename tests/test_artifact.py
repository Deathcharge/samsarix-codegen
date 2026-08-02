# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from samsarix_codegen import (
    inspect_execution_result as public_inspect_execution_result,
)
from samsarix_codegen import (
    render_execution_result as public_render_execution_result,
)
from samsarix_codegen.artifact import (
    MAX_ARTIFACT_BYTES,
    MAX_RESULT_BYTES,
    ExecutionResult,
    ExecutionResultComparison,
    ExecutionResultInspection,
    ExecutionResultSummary,
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    inspect_execution_result,
    parse_execution_result,
    parse_request_artifact,
    render_artifact_comparison,
    render_artifact_summary,
    render_execution_result,
    render_execution_result_comparison,
    render_execution_result_inspection,
    render_request_artifact,
    require_fingerprint,
)
from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.models import ChatResult, ContextFile, PromptRequest, Task
from samsarix_codegen.prompt import build_messages


def make_artifact():
    context = ContextFile("src/app.py", "print('hello')\n", 15)
    request = PromptRequest(Task.REVIEW, "Review this", files=(context,))
    return create_request_artifact(build_messages(request), request.files)


def test_artifact_is_deterministic_and_round_trips() -> None:
    first = make_artifact()
    second = make_artifact()

    rendered = render_request_artifact(first)
    parsed = parse_request_artifact(rendered)

    assert first == second
    assert parsed == first
    assert first.fingerprint.startswith("sha256:")
    assert first.context[0].name == "src/app.py"
    assert first.context[0].content_sha256.startswith("sha256:")
    assert json.loads(rendered)["schema_version"] == 2


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "tool", "content": "no"}],
        [{"role": "user"}],
        [{"role": "user", "content": 3}],
    ],
)
def test_artifact_creation_rejects_invalid_public_inputs(messages) -> None:
    with pytest.raises(ArtifactError):
        create_request_artifact(messages, ())


def test_artifact_creation_rejects_invalid_context_metadata() -> None:
    messages = [{"role": "user", "content": "Review"}]

    with pytest.raises(ArtifactError, match="invalid name"):
        create_request_artifact(messages, (ContextFile("bad\nname", "text", 4),))
    with pytest.raises(ArtifactError, match="non-negative"):
        create_request_artifact(messages, (ContextFile("good.txt", "text", -1),))


def test_artifact_supports_printable_unicode_context_names() -> None:
    artifact = create_request_artifact(
        [{"role": "user", "content": "Review"}],
        (ContextFile("src/naïve.py", "text", 4),),
    )

    assert parse_request_artifact(render_request_artifact(artifact)) == artifact


def test_artifact_renderer_enforces_read_compatible_size_limit() -> None:
    artifact = create_request_artifact(
        [{"role": "user", "content": "x" * MAX_ARTIFACT_BYTES}],
        (),
    )

    with pytest.raises(ArtifactError, match="safety limit"):
        render_request_artifact(artifact)


def test_artifact_fingerprint_detects_content_drift() -> None:
    payload = json.loads(render_request_artifact(make_artifact()))
    payload["messages"][1]["content"] += "tampered"

    with pytest.raises(ArtifactError, match="fingerprint does not match"):
        parse_request_artifact(json.dumps(payload))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(schema_version=1),
        lambda payload: payload["estimate"].update(input_tokens=1),
        lambda payload: payload["context"].update(total_bytes=999),
        lambda payload: payload.update(extra=True),
    ],
)
def test_artifact_rejects_invalid_schema_even_if_json(mutation) -> None:
    payload = json.loads(render_request_artifact(make_artifact()))
    mutation(payload)

    with pytest.raises(ArtifactError):
        parse_request_artifact(json.dumps(payload))


def test_expected_fingerprint_pins_reviewed_artifact() -> None:
    artifact = make_artifact()

    require_fingerprint(artifact, artifact.fingerprint)
    with pytest.raises(ArtifactError, match="approved by the operator"):
        require_fingerprint(artifact, "sha256:" + "0" * 64)


def test_summary_does_not_expose_prompt_content() -> None:
    artifact = make_artifact()

    text = render_artifact_summary(artifact)
    summary = json.loads(render_artifact_summary(artifact, output_format="json"))

    assert "print('hello')" not in text
    assert artifact.fingerprint in text
    assert summary["context_items"] == 1
    assert (
        render_artifact_summary(artifact, output_format="fingerprint").strip()
        == artifact.fingerprint
    )


def test_execution_result_is_machine_readable_and_omits_endpoint() -> None:
    artifact = make_artifact()
    result = ChatResult("Looks good", prompt_tokens=10, completion_tokens=2, total_tokens=12)

    payload = json.loads(render_execution_result(artifact, result, model="local-model"))

    assert payload["request_fingerprint"] == artifact.fingerprint
    assert payload["model"] == "local-model"
    assert payload["response"]["text"] == "Looks good"
    assert payload["usage"]["total_tokens"] == 12
    assert "endpoint" not in payload


@pytest.mark.parametrize(
    ("result", "model", "match"),
    [
        (ChatResult(""), "local", "text cannot be empty"),
        (ChatResult("ok", total_tokens=-1), "local", "non-negative integer"),
        (ChatResult("ok", prompt_tokens=True), "local", "non-negative integer"),
        (ChatResult("ok"), " ", "model cannot be empty"),
        (ChatResult("ok"), "m" * 201, "200-character limit"),
    ],
)
def test_execution_result_rejects_values_outside_its_public_contract(
    result: ChatResult,
    model: str,
    match: str,
) -> None:
    with pytest.raises(ArtifactError, match=match):
        render_execution_result(make_artifact(), result, model=model)


def test_execution_result_round_trips_as_a_strict_envelope() -> None:
    artifact = make_artifact()
    rendered = render_execution_result(
        artifact,
        ChatResult("Reviewed response", prompt_tokens=10, completion_tokens=3, total_tokens=13),
        model="local-model",
    )

    parsed = parse_execution_result(b"\xef\xbb\xbf" + rendered.encode("utf-8"))

    assert parsed.request_fingerprint == artifact.fingerprint
    assert parsed.model == "local-model"
    assert parsed.response_text == "Reviewed response"
    assert parsed.prompt_tokens == 10
    assert parsed.completion_tokens == 3
    assert parsed.total_tokens == 13
    assert parsed.to_payload() == json.loads(rendered)
    assert public_render_execution_result is render_execution_result


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda payload: payload.update(schema_version=True), "unsupported.*schema"),
        (lambda payload: payload.update(unexpected=True), "fields do not match"),
        (lambda payload: payload.update(model=" local "), "surrounding whitespace"),
        (lambda payload: payload["usage"].update(total_tokens=True), "non-negative integer"),
        (lambda payload: payload["response"].update(text="\ud800"), "not valid UTF-8"),
    ],
)
def test_execution_result_parser_rejects_contract_drift(mutate, match: str) -> None:
    rendered = render_execution_result(
        make_artifact(), ChatResult("Reviewed response"), model="local"
    )
    payload = json.loads(rendered)
    mutate(payload)

    with pytest.raises(ArtifactError, match=match):
        parse_execution_result(json.dumps(payload))


def test_execution_result_enforces_bounded_utf8_and_safe_model_labels() -> None:
    with pytest.raises(ArtifactError, match="byte safety limit"):
        parse_execution_result(b" " * (MAX_RESULT_BYTES + 1))

    with pytest.raises(ArtifactError, match="control character"):
        render_execution_result(make_artifact(), ChatResult("ok"), model="unsafe\nmodel")

    fingerprint = make_artifact().fingerprint
    with pytest.raises(ArtifactError, match="response exceeds"):
        ExecutionResult(fingerprint, "model", "x" * (MAX_RESULT_BYTES + 1), None, None, None)


def test_execution_result_comparison_public_values_fail_closed() -> None:
    fingerprint = make_artifact().fingerprint
    with pytest.raises(ArtifactError, match="response characters"):
        ExecutionResultSummary("model", True, 1, fingerprint, None, None, None)
    summary = ExecutionResultSummary("model", 1, 1, fingerprint, None, None, None)
    with pytest.raises(ArtifactError, match="invalid request fingerprint"):
        ExecutionResultComparison("invalid", summary, summary)

    with pytest.raises(ArtifactError, match="invalid request fingerprint"):
        ExecutionResultInspection("invalid", summary)


def test_execution_result_inspection_is_typed_content_omitting_metadata() -> None:
    artifact = make_artifact()
    result = parse_execution_result(
        render_execution_result(
            artifact,
            ChatResult("secret α", prompt_tokens=10, completion_tokens=None, total_tokens=12),
            model="model-a",
        )
    )

    inspection = inspect_execution_result(result)
    text = render_execution_result_inspection(inspection)
    payload = json.loads(render_execution_result_inspection(inspection, output_format="json"))

    assert inspection == public_inspect_execution_result(result)
    assert payload["request_fingerprint"] == artifact.fingerprint
    assert payload["summary"]["model"] == "model-a"
    assert payload["summary"]["response"]["chars"] == len("secret α")
    assert payload["summary"]["response"]["bytes"] == len("secret α".encode())
    assert payload["summary"]["response"]["sha256"].startswith("sha256:")
    assert payload["summary"]["usage"]["completion_tokens"] is None
    assert "Completion tokens: not reported" in text
    assert "secret α" not in text
    assert "secret α" not in json.dumps(payload, ensure_ascii=False)

    with pytest.raises(ArtifactError, match="requires a validated execution result"):
        inspect_execution_result(object())  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="format must be"):
        render_execution_result_inspection(inspection, output_format="yaml")


def test_execution_result_comparison_is_same_request_and_content_omitting() -> None:
    artifact = make_artifact()
    base = parse_execution_result(
        render_execution_result(
            artifact,
            ChatResult("secret α", prompt_tokens=10, completion_tokens=2, total_tokens=12),
            model="model-a",
        )
    )
    target = parse_execution_result(
        render_execution_result(
            artifact,
            ChatResult(
                "different secret", prompt_tokens=11, completion_tokens=None, total_tokens=15
            ),
            model="model-b",
        )
    )

    comparison = compare_execution_results(base, target)
    text = render_execution_result_comparison(comparison)
    payload = json.loads(render_execution_result_comparison(comparison, output_format="json"))

    assert comparison.model_changed
    assert not comparison.response_identical
    assert payload["request_fingerprint"] == artifact.fingerprint
    assert payload["base"]["response"]["chars"] == len("secret α")
    assert payload["base"]["response"]["bytes"] == len("secret α".encode())
    assert payload["delta"]["prompt_tokens"] == 1
    assert payload["delta"]["completion_tokens"] is None
    assert payload["base"]["response"]["sha256"].startswith("sha256:")
    assert "secret α" not in text
    assert "different secret" not in text
    assert "secret α" not in json.dumps(payload, ensure_ascii=False)
    assert "different secret" not in json.dumps(payload, ensure_ascii=False)


def test_execution_result_comparison_rejects_different_requests() -> None:
    base = parse_execution_result(
        render_execution_result(make_artifact(), ChatResult("base"), model="model-a")
    )
    other_request = PromptRequest(Task.REVIEW, "Review something else")
    other_artifact = create_request_artifact(build_messages(other_request), other_request.files)
    target = parse_execution_result(
        render_execution_result(other_artifact, ChatResult("target"), model="model-b")
    )

    with pytest.raises(ArtifactError, match="different request fingerprints"):
        compare_execution_results(base, target)


def test_execution_result_comparison_reports_identical_responses() -> None:
    artifact = make_artifact()
    base = parse_execution_result(
        render_execution_result(artifact, ChatResult("same"), model="model-a")
    )
    target = parse_execution_result(
        render_execution_result(artifact, ChatResult("same"), model="model-a")
    )

    comparison = compare_execution_results(base, target)

    assert comparison.response_identical
    assert not comparison.model_changed
    assert "Responses: identical" in render_execution_result_comparison(comparison)
    with pytest.raises(ArtifactError, match="format must be"):
        render_execution_result_comparison(comparison, output_format="yaml")


def test_comparison_identifies_message_and_context_changes_without_prompt_content() -> None:
    base_request = PromptRequest(
        Task.REVIEW,
        "Review the old behavior",
        files=(ContextFile("src/app.py", "secret old value", 16),),
    )
    target_request = PromptRequest(
        Task.REVIEW,
        "Review the new behavior",
        files=(ContextFile("src/app.py", "secret new value", 16),),
    )
    base = create_request_artifact(build_messages(base_request), base_request.files)
    target = create_request_artifact(build_messages(target_request), target_request.files)

    comparison = compare_request_artifacts(base, target)
    text = render_artifact_comparison(comparison)
    payload = json.loads(render_artifact_comparison(comparison, output_format="json"))

    assert comparison.changed
    assert comparison.changed_message_indices == (1,)
    assert len(comparison.added_context) == 1
    assert len(comparison.removed_context) == 1
    assert "secret old value" not in text
    assert "secret new value" not in text
    assert payload["changed"] is True
    assert payload["messages"]["changed_indices"] == [1]
    assert payload["context"]["added"][0]["name"] == "src/app.py"


def test_comparison_reports_identical_artifacts() -> None:
    artifact = make_artifact()

    comparison = compare_request_artifacts(artifact, artifact)

    assert not comparison.changed
    assert comparison.changed_message_indices == ()
    assert comparison.added_context == ()
    assert comparison.removed_context == ()
    assert render_artifact_comparison(comparison).startswith("Request artifacts are identical.")


def test_comparison_renderer_rejects_unknown_format() -> None:
    comparison = compare_request_artifacts(make_artifact(), make_artifact())

    with pytest.raises(ArtifactError, match="format must be"):
        render_artifact_comparison(comparison, output_format="yaml")
