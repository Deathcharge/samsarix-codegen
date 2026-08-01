# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from io import BytesIO, TextIOWrapper
from pathlib import Path

from samsarix_codegen.artifact import create_request_artifact, render_request_artifact
from samsarix_codegen.cli import main
from samsarix_codegen.models import ChatResult, PromptRequest, Task
from samsarix_codegen.prompt import build_messages


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
