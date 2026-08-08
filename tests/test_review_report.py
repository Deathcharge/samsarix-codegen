# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import json

import pytest

from samsarix_codegen.artifact import (
    create_request_artifact,
    parse_execution_result,
    render_execution_result,
)
from samsarix_codegen.cli import main
from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.models import ChatResult, ContextFile, PromptRequest, Task
from samsarix_codegen.prompt import build_messages
from samsarix_codegen.review_report import (
    MAX_REVIEW_FINDINGS,
    MAX_REVIEW_RESPONSE_BYTES,
    ReviewFinding,
    ReviewReport,
    ReviewResponse,
    parse_review_response,
    render_review_report,
    render_review_sarif,
    verify_review_result,
)


def _artifact(path: str = "src/app.py"):
    source = "def divide(left: int, right: int) -> float:\n    return left / right\n"
    context = ContextFile(path, source, len(source.encode("utf-8")))
    request = PromptRequest(
        Task.REVIEW_REPORT,
        "Find concrete issues and cite their exact source ranges.",
        files=(context,),
    )
    return create_request_artifact(build_messages(request), request.files)


def _response_payload(path: str = "src/app.py") -> dict[str, object]:
    return {
        "schema_version": 1,
        "summary": "One reliability issue needs attention.",
        "findings": [
            {
                "category": "reliability",
                "severity": "warning",
                "title": "Division by zero is not handled",
                "message": "A zero right operand raises an exception without domain context.",
                "path": path,
                "start_line": 2,
                "end_line": 2,
            }
        ],
    }


def _result(artifact, payload: dict[str, object], *, plan_fingerprint: str | None = None):
    return parse_execution_result(
        render_execution_result(
            artifact,
            ChatResult(json.dumps(payload, ensure_ascii=False)),
            model="fixture-review-model",
            plan_fingerprint=plan_fingerprint,
        )
    )


def test_review_report_task_requests_the_strict_contract() -> None:
    messages = build_messages(
        PromptRequest(Task.REVIEW_REPORT, "Review this", files=(_context("src/app.py"),))
    )

    prompt = messages[1]["content"]
    assert "Task: review-report" in prompt
    assert "Return exactly one JSON object with schema_version 1" in prompt
    assert "Path must exactly match an explicitly included context path" in prompt
    assert "Do not use Markdown fences or add fields" in prompt


def test_verify_review_result_links_provenance_and_renders_sarif() -> None:
    artifact = _artifact("src/space name.py")
    plan_fingerprint = "sha256:" + "1" * 64
    result = _result(
        artifact,
        _response_payload("src/space name.py"),
        plan_fingerprint=plan_fingerprint,
    )

    report = verify_review_result(
        artifact,
        result,
        expected_request_fingerprint=artifact.fingerprint,
        expected_plan_fingerprint=plan_fingerprint,
    )
    payload = json.loads(render_review_report(report))
    sarif = json.loads(render_review_sarif(report, tool_version="0.2.0"))

    assert payload["provenance"]["request_fingerprint"] == artifact.fingerprint
    assert payload["provenance"]["plan_fingerprint"] == plan_fingerprint
    assert payload["provenance"]["response_sha256"].startswith("sha256:")
    assert payload["review"] == _response_payload("src/space name.py")
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["version"] == "0.2.0"
    assert run["properties"]["samsarix.requestFingerprint"] == artifact.fingerprint
    assert run["properties"]["samsarix.aiGenerated"] is True
    result_payload = run["results"][0]
    assert result_payload["ruleId"] == "samsarix-ai-review/reliability"
    assert result_payload["ruleIndex"] == 2
    assert result_payload["level"] == "warning"
    assert result_payload["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == (
        "src/space%20name.py"
    )
    assert "partialFingerprints" not in result_payload


def test_empty_review_is_valid_and_emits_no_sarif_results() -> None:
    artifact = _artifact()
    payload = {"schema_version": 1, "summary": "No source-located issues found.", "findings": []}
    report = verify_review_result(artifact, _result(artifact, payload))

    assert report.review.findings == ()
    assert json.loads(render_review_sarif(report, tool_version="0.2.0"))["runs"][0]["results"] == []


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ("[]", "must be a JSON object"),
        ('{"schema_version":1,"summary":"ok","findings":[],"extra":true}', "fields"),
        ('{"schema_version":true,"summary":"ok","findings":[]}', "unsupported"),
        ('{"schema_version":1,"summary":"ok","findings":{}}', "JSON array"),
        (
            '{"schema_version":1,"summary":"first","summary":"second","findings":[]}',
            "duplicate JSON field",
        ),
        ('{"schema_version":1,"summary":"ok","findings":[NaN]}', "non-finite"),
    ],
)
def test_parser_rejects_ambiguous_or_invalid_documents(raw: str, match: str) -> None:
    with pytest.raises(ArtifactError, match=match):
        parse_review_response(raw)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("category", "style", "category"),
        ("severity", "critical", "severity"),
        ("title", " ", "cannot be empty"),
        ("title", "first\nsecond", "one line"),
        ("title", "first\u2028second", "one line"),
        ("message", "\x00hidden", "control character"),
        ("path", "../secret.py", "canonical root-relative"),
        ("path", "src\\app.py", "relative POSIX"),
        ("path", "src/first\u2028second.py", "control character"),
        ("path", "/src/app.py", "canonical root-relative"),
        ("path", "C:/src/app.py", "relative POSIX"),
        ("start_line", 0, "between 1"),
        ("start_line", True, "between 1"),
        ("end_line", 1, "cannot precede"),
    ],
)
def test_parser_rejects_invalid_finding_fields(field: str, value: object, match: str) -> None:
    payload = _response_payload()
    finding = payload["findings"][0]
    assert isinstance(finding, dict)
    if field == "end_line":
        finding["start_line"] = 2
    finding[field] = value

    with pytest.raises(ArtifactError, match=match):
        parse_review_response(json.dumps(payload))


def test_parser_rejects_duplicate_findings_and_resource_overflow() -> None:
    payload = _response_payload()
    finding = payload["findings"][0]
    payload["findings"] = [finding, finding]
    with pytest.raises(ArtifactError, match="duplicate findings"):
        parse_review_response(json.dumps(payload))

    payload["findings"] = [finding] * (MAX_REVIEW_FINDINGS + 1)
    with pytest.raises(ArtifactError, match="cannot exceed"):
        parse_review_response(json.dumps(payload))
    with pytest.raises(ArtifactError, match="safety limit"):
        parse_review_response(b" " * (MAX_REVIEW_RESPONSE_BYTES + 1))


def test_verify_review_result_rejects_unselected_path_and_wrong_approvals() -> None:
    artifact = _artifact()
    result = _result(artifact, _response_payload("src/unselected.py"))
    with pytest.raises(ArtifactError, match="not explicitly selected"):
        verify_review_result(artifact, result)

    selected_result = _result(artifact, _response_payload())
    with pytest.raises(ArtifactError, match="request fingerprint does not match"):
        verify_review_result(
            artifact,
            selected_result,
            expected_request_fingerprint="sha256:" + "2" * 64,
        )
    with pytest.raises(ArtifactError, match="does not record a reviewed execution plan"):
        verify_review_result(
            artifact,
            selected_result,
            expected_plan_fingerprint="sha256:" + "3" * 64,
        )


def test_public_value_objects_reject_invalid_construction_and_sarif_version() -> None:
    finding = ReviewFinding(
        "correctness",
        "error",
        "Wrong result",
        "The branch returns the wrong value.",
        "src/app.py",
        1,
        1,
    )
    response = ReviewResponse("One issue.", (finding,))
    report = ReviewReport("sha256:" + "0" * 64, None, "sha256:" + "1" * 64, response)

    with pytest.raises(ArtifactError, match="tuple"):
        ReviewResponse("One issue.", [finding])  # type: ignore[arg-type]
    with pytest.raises(ArtifactError, match="X.Y.Z"):
        render_review_sarif(report, tool_version="dev")


def test_export_review_cli_emits_json_and_sarif(tmp_path, capsys) -> None:
    artifact = _artifact()
    result = _result(artifact, _response_payload())
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(artifact.to_payload()), encoding="utf-8")
    result_path.write_text(json.dumps(result.to_payload()), encoding="utf-8")

    json_exit = main(
        [
            "export-review",
            str(request_path),
            str(result_path),
            "--expect-fingerprint",
            artifact.fingerprint,
            "--format",
            "json",
        ]
    )
    json_output = capsys.readouterr()
    sarif_exit = main(["export-review", str(request_path), str(result_path), "--format", "sarif"])
    sarif_output = capsys.readouterr()

    assert json_exit == sarif_exit == 0
    assert json_output.err == sarif_output.err == ""
    assert json.loads(json_output.out)["review"] == _response_payload()
    assert json.loads(sarif_output.out)["version"] == "2.1.0"


def test_export_review_cli_rejects_two_stdin_inputs_and_suppresses_output(capsys) -> None:
    exit_code = main(
        ["export-review", "-", "-"],
        stdin=io.BytesIO(b"{}"),
    )

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "cannot both read from stdin" in captured.err


def _context(path: str) -> ContextFile:
    content = "value = 1\n"
    return ContextFile(path, content, len(content.encode("utf-8")))
