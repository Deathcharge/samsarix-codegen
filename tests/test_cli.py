# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from io import BytesIO, TextIOWrapper
from pathlib import Path

from samsarix_codegen.artifact import (
    ExecutionResultPolicy,
    create_request_artifact,
    render_execution_result,
    render_request_artifact,
)
from samsarix_codegen.cli import main
from samsarix_codegen.models import ChatResult, PromptRequest, Task
from samsarix_codegen.prompt import build_messages
from samsarix_codegen.result_policy import render_execution_result_policy

EXPECTED_PROVIDER_CHECK_MESSAGES = (
    {
        "role": "system",
        "content": (
            "This is a provider compatibility check. Return a short plain-text acknowledgement."
        ),
    },
    {"role": "user", "content": "Reply with SAMSARIX_OK."},
)


def test_build_markdown_is_complete_local_journey(tmp_path: Path, capsys) -> None:
    source = tmp_path / "hello.py"
    source.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    exit_code = main(
        [
            "build",
            "Explain this function",
            "--task",
            "explain",
            "--root",
            str(tmp_path),
            "--file",
            "hello.py",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Task: explain" in captured.out
    assert "def hello" in captured.out


def test_build_json_is_machine_readable(capsys) -> None:
    exit_code = main(["build", "Write a parser", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["schema_version"] == 2
    assert payload["request_fingerprint"].startswith("sha256:")
    assert payload["context"]["items"] == []


def test_redirected_json_is_always_utf8(monkeypatch) -> None:
    output = BytesIO()
    redirected = TextIOWrapper(output, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", redirected)

    exit_code = main(["build", "Explain naïve 🚀 code", "--format", "json"])
    redirected.flush()
    payload = json.loads(output.getvalue().decode("utf-8"))

    assert exit_code == 0
    assert "naïve 🚀" in payload["messages"][1]["content"]


def test_context_failure_uses_stable_exit_code(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "build",
            "Explain",
            "--root",
            str(tmp_path),
            "--file",
            "missing.py",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert "error:" in captured.err
    assert "missing.py" in captured.err


def test_run_requires_model_before_network(capsys, monkeypatch) -> None:
    monkeypatch.delenv("SAMSARIX_MODEL", raising=False)

    exit_code = main(["run", "Explain this"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "a model is required" in captured.err


def test_run_prints_response_and_usage(capsys, monkeypatch) -> None:
    def fake_complete(self, messages):
        assert messages[1]["content"].startswith("Task: review")
        return ChatResult("Review result\n", total_tokens=42)

    monkeypatch.setattr("samsarix_codegen.cli.OpenAIChatClient.complete", fake_complete)

    exit_code = main(["run", "Review this", "--task", "review", "--model", "local"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "Review result\n"
    assert "Request sha256:" in captured.err
    assert "Provider usage: 42 total tokens." in captured.err


def test_run_uses_samsarix_environment_configuration(capsys, monkeypatch) -> None:
    def fake_complete(self, messages):
        assert self.config.model == "env-model"
        assert self.config.api_key == "env-key"
        assert self.config.timeout_seconds == 7
        assert self.config.max_output_tokens == 88
        return ChatResult("Environment configured\n")

    monkeypatch.setenv("SAMSARIX_MODEL", "env-model")
    monkeypatch.setenv("SAMSARIX_API_KEY", "env-key")
    monkeypatch.setenv("SAMSARIX_TIMEOUT", "7")
    monkeypatch.setenv("SAMSARIX_MAX_OUTPUT_TOKENS", "88")
    monkeypatch.setattr("samsarix_codegen.cli.OpenAIChatClient.complete", fake_complete)

    exit_code = main(["run", "Explain this"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "Environment configured\n"


def test_provider_check_reports_content_safe_machine_evidence(capsys, monkeypatch) -> None:
    calls = 0

    def fake_complete(self, messages):
        nonlocal calls
        calls += 1
        assert tuple(messages) == EXPECTED_PROVIDER_CHECK_MESSAGES
        assert self.config.model == "pilot-model"
        assert self.config.api_key == "secret-check-key"
        assert self.config.max_output_tokens == 64
        return ChatResult(
            "SAMSARIX_OK",
            prompt_tokens=18,
            completion_tokens=4,
            total_tokens=22,
        )

    monkeypatch.setenv("SAMSARIX_API_KEY", "secret-check-key")
    monkeypatch.setattr("samsarix_codegen.provider_check.OpenAIChatClient.complete", fake_complete)

    exit_code = main(["provider-check", "--model", "pilot-model", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert calls == 1
    assert payload["status"] == "passed"
    assert payload["request"] == {
        "message_count": 2,
        "source_context_items": 0,
        "max_output_tokens": 64,
        "stream": False,
    }
    assert payload["response"]["text_chars"] == 11
    assert payload["usage"]["total_tokens"] == 22
    assert "Provider charges may apply" in captured.err
    assert "secret-check-key" not in captured.out + captured.err
    assert "SAMSARIX_OK" not in captured.out + captured.err


def test_provider_check_requires_model_before_network(capsys, monkeypatch) -> None:
    monkeypatch.delenv("SAMSARIX_MODEL", raising=False)

    def fail_if_called(self, messages):
        raise AssertionError("provider must not be called")

    monkeypatch.setattr("samsarix_codegen.provider_check.OpenAIChatClient.complete", fail_if_called)

    exit_code = main(["provider-check"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "a model is required" in captured.err
    assert "Provider charges may apply" not in captured.err


def test_run_rejects_remote_plain_http(capsys) -> None:
    exit_code = main(
        [
            "run",
            "Explain this",
            "--model",
            "remote",
            "--endpoint",
            "http://models.example.com/v1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "unencrypted http" in captured.err


def test_build_accepts_explicit_bounded_stdin_context(capsys) -> None:
    exit_code = main(
        [
            "build",
            "Review the staged changes",
            "--task",
            "review",
            "--stdin-name",
            "staged.diff",
            "--format",
            "json",
        ],
        stdin=BytesIO(b"diff --git a/app.py b/app.py\n+safe = True\n"),
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["context"]["items"][0]["name"] == "stdin:staged.diff"
    assert "safe = True" in payload["messages"][1]["content"]


def test_build_composes_direct_files_and_repeated_context_manifests(tmp_path: Path, capsys) -> None:
    for name in ("direct.py", "shared.py", "tests.py"):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "core.json").write_text(
        json.dumps({"schema_version": 1, "files": ["direct.py", "shared.py"]}), encoding="utf-8"
    )
    (tmp_path / "tests.json").write_text(
        json.dumps({"schema_version": 1, "files": ["tests.py"]}), encoding="utf-8"
    )

    exit_code = main(
        [
            "build",
            "Review the selected project surface",
            "--root",
            str(tmp_path),
            "--file",
            "direct.py",
            "--context-manifest",
            "core.json",
            "--context-manifest",
            "tests.json",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert [item["name"] for item in payload["context"]["items"]] == [
        "direct.py",
        "shared.py",
        "tests.py",
    ]


def test_manifest_entries_share_the_total_context_item_limit(tmp_path: Path, capsys) -> None:
    manifest = {
        "schema_version": 1,
        "files": [f"src/file-{index}.py" for index in range(20)],
    }
    (tmp_path / "context.json").write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = main(
        [
            "build",
            "Review",
            "--root",
            str(tmp_path),
            "--context-manifest",
            "context.json",
            "--stdin-name",
            "extra.diff",
        ],
        stdin=BytesIO(b"diff"),
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert "at most 20 total context items" in captured.err


def test_direct_context_limit_fails_before_reading_a_manifest(tmp_path: Path, capsys) -> None:
    arguments = [
        "build",
        "Review",
        "--root",
        str(tmp_path),
        "--context-manifest",
        "missing-manifest.json",
    ]
    for index in range(21):
        arguments.extend(["--file", f"missing-{index}.py"])

    exit_code = main(arguments)

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert "at most 20 total context items" in captured.err
    assert "missing-manifest" not in captured.err


def test_invalid_context_manifest_fails_with_context_exit_code(tmp_path: Path, capsys) -> None:
    (tmp_path / "context.json").write_text(
        json.dumps({"schema_version": 1, "files": ["../secret.py"]}), encoding="utf-8"
    )

    exit_code = main(
        [
            "build",
            "Review",
            "--root",
            str(tmp_path),
            "--context-manifest",
            "context.json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert "parent segments" in captured.err


def test_estimated_input_budget_fails_before_network(capsys, monkeypatch) -> None:
    def fail_if_called(self, messages):
        raise AssertionError("provider must not be called")

    monkeypatch.setattr("samsarix_codegen.cli.OpenAIChatClient.complete", fail_if_called)

    exit_code = main(
        [
            "run",
            "Explain this",
            "--model",
            "local",
            "--max-estimated-input-tokens",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "estimated input is" in captured.err


def test_inspect_and_execute_reviewed_artifact(tmp_path: Path, capsys, monkeypatch) -> None:
    request = PromptRequest(Task.EXPLAIN, "Explain this contract")
    artifact = create_request_artifact(build_messages(request), request.files)
    artifact_path = tmp_path / "request.json"
    artifact_path.write_text(render_request_artifact(artifact), encoding="utf-8")

    inspect_exit = main(["inspect", str(artifact_path), "--format", "fingerprint"])
    inspected = capsys.readouterr()
    assert inspect_exit == 0
    assert inspected.out.strip() == artifact.fingerprint

    def fake_complete(self, messages):
        assert tuple(messages) == artifact.messages
        return ChatResult("Reviewed response", total_tokens=23)

    monkeypatch.setattr("samsarix_codegen.cli.OpenAIChatClient.complete", fake_complete)
    execute_exit = main(
        [
            "execute",
            str(artifact_path),
            "--expect-fingerprint",
            artifact.fingerprint,
            "--model",
            "local",
            "--format",
            "json",
        ]
    )

    executed = capsys.readouterr()
    payload = json.loads(executed.out)
    assert execute_exit == 0
    assert payload["request_fingerprint"] == artifact.fingerprint
    assert payload["response"]["text"] == "Reviewed response"
    assert payload["usage"]["total_tokens"] == 23


def test_execute_rejects_unapproved_or_tampered_artifact(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review this")
    artifact = create_request_artifact(build_messages(request), request.files)
    payload = json.loads(render_request_artifact(artifact))
    payload["messages"][1]["content"] += "tampered"
    artifact_path = tmp_path / "tampered.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["execute", str(artifact_path), "--model", "local"])

    captured = capsys.readouterr()
    assert exit_code == 5
    assert "fingerprint does not match" in captured.err


def test_inspect_reads_artifact_from_stdin(capsys) -> None:
    request = PromptRequest(Task.TESTS, "Suggest tests")
    artifact = create_request_artifact(build_messages(request), request.files)

    exit_code = main(
        ["inspect", "-", "--format", "json"],
        stdin=BytesIO(render_request_artifact(artifact).encode()),
    )

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert exit_code == 0
    assert summary["request_fingerprint"] == artifact.fingerprint


def test_inspect_renders_exact_stored_prompt_as_markdown(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.DEBUG, "Diagnose the exact failure")
    artifact = create_request_artifact(build_messages(request), request.files)
    artifact_path = tmp_path / "request.json"
    artifact_path.write_text(render_request_artifact(artifact), encoding="utf-8")

    exit_code = main(["inspect", str(artifact_path), "--format", "markdown"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Task: debug" in captured.out
    assert "Diagnose the exact failure" in captured.out


def test_compare_artifacts_is_machine_readable_and_content_safe(tmp_path: Path, capsys) -> None:
    base_request = PromptRequest(Task.REVIEW, "Review secret old behavior")
    target_request = PromptRequest(Task.REVIEW, "Review secret new behavior")
    base = create_request_artifact(build_messages(base_request), base_request.files)
    target = create_request_artifact(build_messages(target_request), target_request.files)
    base_path = tmp_path / "base.json"
    target_path = tmp_path / "target.json"
    base_path.write_text(render_request_artifact(base), encoding="utf-8")
    target_path.write_text(render_request_artifact(target), encoding="utf-8")

    exit_code = main(["compare", str(base_path), str(target_path), "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["changed"] is True
    assert payload["messages"]["changed_indices"] == [1]
    assert "secret old behavior" not in captured.out
    assert "secret new behavior" not in captured.out


def test_compare_rejects_two_stdin_inputs(capsys) -> None:
    exit_code = main(["compare", "-", "-"], stdin=BytesIO(b"{}"))

    captured = capsys.readouterr()
    assert exit_code == 5
    assert "cannot both read from stdin" in captured.err


def test_compare_results_is_machine_readable_and_omits_responses(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review provider behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    base_path = tmp_path / "result-a.json"
    target_path = tmp_path / "result-b.json"
    base_path.write_text(
        render_execution_result(
            artifact,
            ChatResult("secret response a", prompt_tokens=10, completion_tokens=2, total_tokens=12),
            model="model-a",
        ),
        encoding="utf-8",
    )
    target_path.write_text(
        render_execution_result(
            artifact,
            ChatResult("secret response b", prompt_tokens=10, completion_tokens=4, total_tokens=14),
            model="model-b",
        ),
        encoding="utf-8",
    )

    exit_code = main(["compare-results", str(base_path), str(target_path), "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert payload["request_fingerprint"] == artifact.fingerprint
    assert payload["model_changed"] is True
    assert payload["response_identical"] is False
    assert payload["delta"]["completion_tokens"] == 2
    assert "secret response a" not in captured.out
    assert "secret response b" not in captured.out


def test_inspect_result_validates_stdin_and_omits_response(capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review provider behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    rendered = render_execution_result(
        artifact,
        ChatResult("secret provider response", 10, 3, 13),
        model="model-a",
    )

    exit_code = main(
        [
            "inspect-result",
            "-",
            "--expect-model",
            "model-a",
            "--max-response-bytes",
            str(len(b"secret provider response")),
            "--max-prompt-tokens",
            "10",
            "--max-completion-tokens",
            "3",
            "--max-total-tokens",
            "13",
            "--format",
            "json",
        ],
        stdin=BytesIO(rendered.encode("utf-8")),
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert payload["request_fingerprint"] == artifact.fingerprint
    assert payload["summary"]["model"] == "model-a"
    assert payload["summary"]["response"]["chars"] == len("secret provider response")
    assert payload["summary"]["usage"]["total_tokens"] == 13
    assert "secret provider response" not in captured.out


def test_inspect_result_policy_fails_closed_for_missing_usage(capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review provider behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    rendered = render_execution_result(
        artifact,
        ChatResult("secret provider response"),
        model="model-a",
    )

    exit_code = main(
        ["inspect-result", "-", "--max-total-tokens", "13"],
        stdin=BytesIO(rendered.encode("utf-8")),
    )

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "total token usage was not reported" in captured.err
    assert "secret provider response" not in captured.err


def test_inspect_result_loads_a_policy_file_and_rejects_excess_usage(
    tmp_path: Path, capsys
) -> None:
    request = PromptRequest(Task.REVIEW, "Review provider behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    result_path = tmp_path / "result.json"
    policy_path = tmp_path / "result-policy.json"
    result_path.write_text(
        render_execution_result(
            artifact,
            ChatResult("secret provider response", 10, 3, 13),
            model="model-a",
        ),
        encoding="utf-8",
    )
    policy_path.write_text(
        render_execution_result_policy(ExecutionResultPolicy(max_total_tokens=12)),
        encoding="utf-8",
    )

    exit_code = main(["inspect-result", str(result_path), "--policy", str(policy_path)])

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "total token usage is 13" in captured.err
    assert "secret provider response" not in captured.err


def test_result_policy_file_cannot_mix_with_inline_rules(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review provider behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    result_path = tmp_path / "result.json"
    policy_path = tmp_path / "result-policy.json"
    result_path.write_text(
        render_execution_result(artifact, ChatResult("private"), model="model-a"),
        encoding="utf-8",
    )
    policy_path.write_text(
        render_execution_result_policy(ExecutionResultPolicy(expected_model="model-a")),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "inspect-result",
            str(result_path),
            "--policy",
            str(policy_path),
            "--expect-model",
            "model-a",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "cannot be combined" in captured.err


def test_result_policy_file_cannot_read_from_stdin(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review provider behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    result_path = tmp_path / "result.json"
    result_path.write_text(
        render_execution_result(artifact, ChatResult("private"), model="model-a"),
        encoding="utf-8",
    )

    exit_code = main(["inspect-result", str(result_path), "--policy", "-"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "requires a file path" in captured.err


def test_inspect_result_rejects_invalid_envelope(capsys) -> None:
    exit_code = main(["inspect-result", "-"], stdin=BytesIO(b"{}"))

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "fields do not match schema version 1" in captured.err


def test_verify_result_is_machine_readable_and_omits_contents(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review private behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    policy_path = tmp_path / "result-policy.json"
    request_path.write_text(render_request_artifact(artifact), encoding="utf-8")
    result_path.write_text(
        render_execution_result(
            artifact,
            ChatResult("private provider response", 10, 3, 13),
            model="model-a",
        ),
        encoding="utf-8",
    )
    policy_path.write_text(
        render_execution_result_policy(
            ExecutionResultPolicy(
                expected_model="model-a",
                max_response_bytes=len(b"private provider response"),
                max_prompt_tokens=10,
                max_completion_tokens=3,
                max_total_tokens=13,
            )
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "verify-result",
            str(request_path),
            str(result_path),
            "--policy",
            str(policy_path),
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert payload["request"]["fingerprint"] == artifact.fingerprint
    assert payload["result"]["model"] == "model-a"
    assert payload["result"]["usage"]["total_tokens"] == 13
    assert "Review private behavior" not in captured.out
    assert "private provider response" not in captured.out


def test_verify_result_policy_rejects_unexpected_model(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review private behavior")
    artifact = create_request_artifact(build_messages(request), request.files)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(render_request_artifact(artifact), encoding="utf-8")
    result_path.write_text(
        render_execution_result(
            artifact,
            ChatResult("private provider response", 10, 3, 13),
            model="model-a",
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "verify-result",
            str(request_path),
            str(result_path),
            "--expect-model",
            "model-b",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "does not match the expected model" in captured.err
    assert "private provider response" not in captured.err


def test_verify_result_rejects_mismatched_request(tmp_path: Path, capsys) -> None:
    request = PromptRequest(Task.REVIEW, "Review A")
    other_request = PromptRequest(Task.REVIEW, "Review B")
    artifact = create_request_artifact(build_messages(request), request.files)
    other_artifact = create_request_artifact(build_messages(other_request), other_request.files)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(render_request_artifact(artifact), encoding="utf-8")
    result_path.write_text(
        render_execution_result(other_artifact, ChatResult("private"), model="model-a"),
        encoding="utf-8",
    )

    exit_code = main(["verify-result", str(request_path), str(result_path)])

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "does not reference the supplied request" in captured.err


def test_verify_result_rejects_two_stdin_inputs(capsys) -> None:
    exit_code = main(["verify-result", "-", "-"], stdin=BytesIO(b"{}"))

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "cannot both read from stdin" in captured.err


def test_compare_results_rejects_different_requests(tmp_path: Path, capsys) -> None:
    base_request = PromptRequest(Task.REVIEW, "Review provider A")
    target_request = PromptRequest(Task.REVIEW, "Review provider B")
    base_artifact = create_request_artifact(build_messages(base_request), base_request.files)
    target_artifact = create_request_artifact(build_messages(target_request), target_request.files)
    base_path = tmp_path / "result-a.json"
    target_path = tmp_path / "result-b.json"
    base_path.write_text(
        render_execution_result(base_artifact, ChatResult("a"), model="model-a"),
        encoding="utf-8",
    )
    target_path.write_text(
        render_execution_result(target_artifact, ChatResult("b"), model="model-b"),
        encoding="utf-8",
    )

    exit_code = main(["compare-results", str(base_path), str(target_path)])

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "different request fingerprints" in captured.err


def test_compare_results_rejects_two_stdin_inputs(capsys) -> None:
    exit_code = main(["compare-results", "-", "-"], stdin=BytesIO(b"{}"))

    captured = capsys.readouterr()
    assert exit_code == 5
    assert captured.out == ""
    assert "cannot both read from stdin" in captured.err
