# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from scripts.pilot_check import (
    PilotRecordError,
    evaluate_pilot,
    load_pilot_record,
    main,
    validate_pilot_record,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = REPOSITORY_ROOT / "examples/pilot-record-v1.json"
SCHEMA_PATH = REPOSITORY_ROOT / "docs/pilot-record-v1.schema.json"


def test_example_is_valid_but_intentionally_not_ready(capsys: pytest.CaptureFixture[str]) -> None:
    record = load_pilot_record(EXAMPLE_PATH)

    exit_code = main([str(EXAMPLE_PATH)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["decision"] == "not-ready"
    assert output["participants"] == 1
    assert output["workflows"] == ["staged-review"]
    assert output["record_sha256"].startswith("sha256:")
    assert "context" not in output
    assert evaluate_pilot(record) == output


def test_malformed_record_returns_invalid_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{}", encoding="utf-8")

    exit_code = main([str(path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "pilot check failed:" in captured.err


def test_three_participants_and_both_workflows_pass() -> None:
    record = _passing_record()

    evidence = evaluate_pilot(validate_pilot_record(record))

    assert evidence["decision"] == "passed"
    assert evidence["participants"] == 3
    assert evidence["sessions"] == 4
    assert evidence["qualified_participants"] == 3
    assert all(evidence["requirements"].values())


def test_successful_execution_requires_passing_evidence() -> None:
    record = _passing_record()
    session = record["sessions"][0]
    session["provider_mode"] = "local"
    session["execution"] = {
        "status": "passed",
        "attempts": 1,
        "exit_code": 0,
        "evidence_status": "failed",
    }
    session["completion_stage"] = "executed"

    evidence = evaluate_pilot(validate_pilot_record(record))

    assert evidence["decision"] == "not-ready"
    assert not evidence["requirements"]["successful_executions_have_passing_evidence"]


def test_safety_event_is_preserved_and_fails_decision() -> None:
    record = _passing_record()
    record["sessions"][0]["safety"]["credential_exposure"] = True

    evidence = evaluate_pilot(validate_pilot_record(record))

    assert evidence["decision"] == "not-ready"
    assert not evidence["requirements"]["safety_boundary_preserved"]


def test_every_participant_must_complete_staged_review() -> None:
    record = _passing_record()
    record["sessions"][2]["workflow"] = "log-triage"

    evidence = evaluate_pilot(validate_pilot_record(record))

    assert evidence["decision"] == "not-ready"
    assert not evidence["requirements"]["every_participant_completed_staged_review"]


def test_offline_session_rejects_provider_attempt() -> None:
    record = _passing_record()
    record["sessions"][0]["provider_check"] = {
        "status": "passed",
        "attempts": 1,
        "exit_code": 0,
    }

    with pytest.raises(PilotRecordError, match="offline-only"):
        validate_pilot_record(record)


def test_completion_stage_must_match_execution_outcome() -> None:
    record = _passing_record()
    record["sessions"][0]["completion_stage"] = "evidence-verified"

    with pytest.raises(PilotRecordError, match="requires a passing execution"):
        validate_pilot_record(record)


def test_duplicate_participant_workflow_is_rejected() -> None:
    record = _passing_record()
    duplicate = copy.deepcopy(record["sessions"][0])
    record["sessions"].append(duplicate)

    with pytest.raises(PilotRecordError, match="duplicates"):
        validate_pilot_record(record)


def test_unknown_free_form_field_is_rejected() -> None:
    record = _passing_record()
    record["sessions"][0]["notes"] = "do not collect this"

    with pytest.raises(PilotRecordError, match="unknown fields: notes"):
        validate_pilot_record(record)


def test_duplicate_json_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":1,"schema_version":1,"wheel_sha256":"'
        + "0" * 64
        + '","commit":"'
        + "0" * 40
        + '","sessions":[]}',
        encoding="utf-8",
    )

    with pytest.raises(PilotRecordError, match="duplicate field 'schema_version'"):
        load_pilot_record(path)


def test_portable_schema_is_valid_and_accepts_example() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    decision_schema = json.loads(
        (REPOSITORY_ROOT / "docs/pilot-decision-v1.schema.json").read_text(encoding="utf-8")
    )
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    Draft202012Validator.check_schema(decision_schema)
    Draft202012Validator(decision_schema).validate(evaluate_pilot(validate_pilot_record(example)))


def _passing_record() -> dict[str, Any]:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    first = example["sessions"][0]
    sessions = []
    for pilot_id in ("pilot-111111111111", "pilot-222222222222", "pilot-333333333333"):
        session = copy.deepcopy(first)
        session["pilot_id"] = pilot_id
        sessions.append(session)
    log_session = copy.deepcopy(first)
    log_session["pilot_id"] = "pilot-111111111111"
    log_session["workflow"] = "log-triage"
    sessions.append(log_session)
    return {
        "schema_version": 1,
        "wheel_sha256": "a" * 64,
        "commit": "b" * 40,
        "sessions": sessions,
    }
