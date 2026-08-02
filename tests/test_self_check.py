# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from samsarix_codegen import __version__
from samsarix_codegen.cli import main
from samsarix_codegen.schema import load_contract_schema
from samsarix_codegen.self_check import (
    EXPECTED_PLAN_FINGERPRINT,
    EXPECTED_POLICY_FINGERPRINT,
    EXPECTED_REQUEST_FINGERPRINT,
    EXPECTED_RESPONSE_FINGERPRINT,
    SELF_CHECK_SOURCE,
    SelfCheckError,
    SelfCheckReport,
    render_self_check,
    run_self_check,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_self_check_matches_the_checked_in_offline_chain(monkeypatch) -> None:
    def fail_if_called(self, messages):
        raise AssertionError("self-check must not call a provider")

    monkeypatch.setattr("samsarix_codegen.provider.OpenAIChatClient.complete", fail_if_called)

    report = run_self_check()
    payload = report.to_dict()
    example_request = json.loads(
        (REPOSITORY_ROOT / "examples/execution-request-v2.json").read_text(encoding="utf-8")
    )
    example_plan = json.loads(
        (REPOSITORY_ROOT / "examples/execution-plan-v1.json").read_text(encoding="utf-8")
    )
    example_evidence = json.loads(
        (REPOSITORY_ROOT / "examples/execution-evidence-v2.json").read_text(encoding="utf-8")
    )

    assert (
        SELF_CHECK_SOURCE.encode("utf-8") == (REPOSITORY_ROOT / "examples/sample.py").read_bytes()
    )
    assert report.package_version == __version__
    assert report.request_fingerprint == example_request["request_fingerprint"]
    assert report.request_fingerprint == EXPECTED_REQUEST_FINGERPRINT
    assert report.plan_fingerprint == example_plan["plan_fingerprint"]
    assert report.plan_fingerprint == EXPECTED_PLAN_FINGERPRINT
    assert example_evidence["result_policy"]["fingerprint"] == EXPECTED_POLICY_FINGERPRINT
    assert report.response_fingerprint == example_evidence["result"]["response"]["sha256"]
    assert report.response_fingerprint == EXPECTED_RESPONSE_FINGERPRINT
    assert payload["network"] == {"attempted": False, "provider_called": False}
    Draft202012Validator(load_contract_schema("self-check")).validate(payload)


def test_self_check_renderers_are_content_omitting() -> None:
    report = run_self_check()

    rendered_text = render_self_check(report)
    rendered_json = render_self_check(report, output_format="json")

    assert "self-check passed" in rendered_text
    assert "Network: not attempted; no provider called." in rendered_text
    assert SELF_CHECK_SOURCE not in rendered_text + rendered_json
    assert "Synthetic offline fixture" not in rendered_text + rendered_json
    assert json.loads(rendered_json) == report.to_dict()


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_self_check_cli_succeeds_without_configuration(output_format: str, capsys) -> None:
    exit_code = main(["self-check", "--format", output_format])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    if output_format == "json":
        assert json.loads(captured.out)["status"] == "passed"
    else:
        assert captured.out.startswith("Samsarix Codegen self-check passed.")


def test_self_check_fails_cleanly_on_deterministic_drift(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "samsarix_codegen.self_check.EXPECTED_REQUEST_FINGERPRINT",
        "sha256:" + ("0" * 64),
    )

    exit_code = main(["self-check"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "error: installed-package self-check request fingerprint does not match" in captured.err


def test_self_check_fails_when_the_contract_registry_drifts(monkeypatch, capsys) -> None:
    monkeypatch.setattr("samsarix_codegen.self_check.EXPECTED_CONTRACTS", ("request",))

    exit_code = main(["self-check"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "error: installed-package self-check contract registry does not match" in captured.err


def test_self_check_rejects_invalid_renderer_inputs() -> None:
    with pytest.raises(SelfCheckError, match="validated report"):
        render_self_check(object())  # type: ignore[arg-type]
    with pytest.raises(SelfCheckError, match="text or json"):
        render_self_check(run_self_check(), output_format="yaml")  # type: ignore[arg-type]


def test_self_check_report_rejects_invalid_machine_fields() -> None:
    with pytest.raises(SelfCheckError, match="contract count"):
        SelfCheckReport(
            package_version="0.2.0",
            python_implementation="CPython",
            python_version="3.14.0",
            contract_count=True,
            request_fingerprint=EXPECTED_REQUEST_FINGERPRINT,
            plan_fingerprint=EXPECTED_PLAN_FINGERPRINT,
            response_fingerprint=EXPECTED_RESPONSE_FINGERPRINT,
        )
