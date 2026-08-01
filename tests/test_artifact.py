# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from samsarix_codegen.artifact import (
    MAX_ARTIFACT_BYTES,
    create_request_artifact,
    parse_request_artifact,
    render_artifact_summary,
    render_execution_result,
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
