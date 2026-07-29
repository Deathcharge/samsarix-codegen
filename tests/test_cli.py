# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

from samsarix_codegen.cli import main
from samsarix_codegen.models import ChatResult


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
    assert payload["schema_version"] == 1
    assert payload["estimate"]["context_files"] == 0


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
    assert "Request estimate:" in captured.err
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
