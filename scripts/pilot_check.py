#!/usr/bin/env python3
# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Validate a privacy-minimal pilot record and evaluate its adoption gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

PILOT_RECORD_SCHEMA_VERSION = 1
PILOT_DECISION_SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 256 * 1024
MAX_SESSIONS = 40

_WHEEL_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_PILOT_ID = re.compile(r"^pilot-[0-9a-f]{12}$")
_PYTHON_VERSION = re.compile(r"^3\.(?:10|11|12|13|14)(?:\.[0-9]+)?$")
_OS_FAMILIES = {"linux", "macos", "windows", "other"}
_WORKFLOWS = {"log-triage", "staged-review"}
_PROVIDER_MODES = {"hosted", "local", "offline-only"}
_RUN_STATUSES = {"failed", "not-run", "passed"}
_EVIDENCE_STATUSES = {"failed", "not-run", "passed"}
_COMPLETION_STAGES = {
    "request-built",
    "request-inspected",
    "plan-created",
    "plan-verified",
    "provider-checked",
    "executed",
    "evidence-verified",
}
_PLAN_REVIEWED_STAGES = {
    "plan-verified",
    "provider-checked",
    "executed",
    "evidence-verified",
}
_REUSE_VALUES = {"maybe", "no", "yes"}
_FRICTION_CODES = {
    "context-selection",
    "documentation",
    "evidence-verification",
    "execution",
    "none",
    "other",
    "plan-review",
    "prompt-review",
    "provider-preflight",
    "setup",
}
_SAFETY_FIELDS = {
    "credential_exposure",
    "samsarix_content_collection",
    "unintended_file_access",
    "unreviewed_context_sent",
}


class PilotRecordError(Exception):
    """A pilot record is malformed, ambiguous, or outside its privacy boundary."""


def load_pilot_record(path: Path) -> dict[str, Any]:
    """Load one strict, bounded UTF-8 JSON pilot record."""

    try:
        if not path.is_file():
            raise PilotRecordError(f"pilot record is not a regular file: {path}")
        size = path.stat().st_size
        if size > MAX_RECORD_BYTES:
            raise PilotRecordError(
                f"pilot record exceeds the {MAX_RECORD_BYTES:,}-byte safety limit"
            )
        raw = path.read_bytes()
    except OSError as exc:
        raise PilotRecordError(f"cannot read pilot record: {path}") from exc

    if b"\x00" in raw:
        raise PilotRecordError("pilot record contains a NUL byte")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PilotRecordError("pilot record must be UTF-8") from exc
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_fields)
    except (json.JSONDecodeError, PilotRecordError) as exc:
        if isinstance(exc, PilotRecordError):
            raise
        raise PilotRecordError(f"pilot record is not valid JSON: {exc.msg}") from exc
    return validate_pilot_record(payload)


def validate_pilot_record(payload: object) -> dict[str, Any]:
    """Validate the portable record shape and cross-field invariants."""

    record = _strict_object(
        payload,
        "$",
        required={"schema_version", "wheel_sha256", "commit", "sessions"},
    )
    _exact_integer(record["schema_version"], "$.schema_version", PILOT_RECORD_SCHEMA_VERSION)
    _matching_string(record["wheel_sha256"], "$.wheel_sha256", _WHEEL_DIGEST)
    _matching_string(record["commit"], "$.commit", _COMMIT)

    sessions = record["sessions"]
    if not isinstance(sessions, list):
        _fail("$.sessions", "must be an array")
    if not 1 <= len(sessions) <= MAX_SESSIONS:
        _fail("$.sessions", f"must contain between 1 and {MAX_SESSIONS} sessions")

    seen: set[tuple[str, str]] = set()
    for index, value in enumerate(sessions):
        path = f"$.sessions[{index}]"
        session = _validate_session(value, path)
        identity = (session["pilot_id"], session["workflow"])
        if identity in seen:
            _fail(path, "duplicates an existing pilot_id/workflow pair")
        seen.add(identity)
    return record


def evaluate_pilot(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return content-free, deterministic evidence for the documented pilot gate."""

    sessions = record["sessions"]
    participant_ids = {session["pilot_id"] for session in sessions}
    staged_ids = {
        session["pilot_id"] for session in sessions if session["workflow"] == "staged-review"
    }
    workflows = {session["workflow"] for session in sessions}
    review_chain_passed = all(
        all(session["review_checks"].values())
        and session["completion_stage"] in _PLAN_REVIEWED_STAGES
        for session in sessions
    )
    execution_policy_passed = all(_execution_is_acceptable(session) for session in sessions)
    safety_passed = all(not any(session["safety"].values()) for session in sessions)
    qualified_ids = {
        session["pilot_id"]
        for session in sessions
        if session["clarity_score"] >= 4
        and session["usefulness_score"] >= 4
        and session["reuse"] in {"yes", "maybe"}
    }

    requirements = {
        "at_least_three_participants": len(participant_ids) >= 3,
        "every_participant_completed_staged_review": participant_ids == staged_ids,
        "both_workflows_exercised": workflows == _WORKFLOWS,
        "review_chain_completed": review_chain_passed,
        "successful_executions_have_passing_evidence": execution_policy_passed,
        "at_least_two_qualified_participants": len(qualified_ids) >= 2,
        "safety_boundary_preserved": safety_passed,
    }
    decision = "passed" if all(requirements.values()) else "not-ready"
    fingerprint = hashlib.sha256(_canonical_json(record)).hexdigest()
    return {
        "schema_version": PILOT_DECISION_SCHEMA_VERSION,
        "decision": decision,
        "record_sha256": f"sha256:{fingerprint}",
        "wheel_sha256": record["wheel_sha256"],
        "commit": record["commit"],
        "participants": len(participant_ids),
        "sessions": len(sessions),
        "workflows": sorted(workflows),
        "qualified_participants": len(qualified_ids),
        "requirements": requirements,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="privacy-minimal pilot-record-v1 JSON file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        record = load_pilot_record(args.record)
        evidence = evaluate_pilot(record)
    except PilotRecordError as exc:
        print(f"pilot check failed: {exc}", file=sys.stderr, flush=True)
        return 2
    except Exception as exc:
        print(
            f"pilot check failed: unexpected {type(exc).__name__}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["decision"] == "passed" else 1


def _validate_session(value: object, path: str) -> dict[str, Any]:
    session = _strict_object(
        value,
        path,
        required={
            "pilot_id",
            "platform",
            "workflow",
            "provider_mode",
            "provider_check",
            "context",
            "review_checks",
            "execution",
            "completion_stage",
            "review_minutes",
            "clarity_score",
            "usefulness_score",
            "reuse",
            "friction_codes",
            "safety",
        },
    )
    _matching_string(session["pilot_id"], f"{path}.pilot_id", _PILOT_ID)
    _validate_platform(session["platform"], f"{path}.platform")
    _enum(session["workflow"], f"{path}.workflow", _WORKFLOWS)
    provider_mode = _enum(session["provider_mode"], f"{path}.provider_mode", _PROVIDER_MODES)
    provider_check = _validate_run(
        session["provider_check"], f"{path}.provider_check", allow_evidence=False
    )
    _validate_context(session["context"], f"{path}.context")
    _validate_review_checks(session["review_checks"], f"{path}.review_checks")
    execution = _validate_run(session["execution"], f"{path}.execution", allow_evidence=True)
    completion_stage = _enum(
        session["completion_stage"], f"{path}.completion_stage", _COMPLETION_STAGES
    )
    _bounded_integer(session["review_minutes"], f"{path}.review_minutes", 0, 480)
    _bounded_integer(session["clarity_score"], f"{path}.clarity_score", 1, 5)
    _bounded_integer(session["usefulness_score"], f"{path}.usefulness_score", 1, 5)
    _enum(session["reuse"], f"{path}.reuse", _REUSE_VALUES)
    _validate_friction_codes(session["friction_codes"], f"{path}.friction_codes")
    _validate_safety(session["safety"], f"{path}.safety")

    if provider_mode == "offline-only" and provider_check["status"] != "not-run":
        _fail(f"{path}.provider_check", "must be not-run when provider_mode is offline-only")
    if provider_mode == "offline-only" and execution["status"] != "not-run":
        _fail(f"{path}.execution", "must be not-run when provider_mode is offline-only")
    _validate_completion_stage(
        completion_stage,
        provider_check,
        execution,
        f"{path}.completion_stage",
    )
    return session


def _validate_platform(value: object, path: str) -> None:
    platform = _strict_object(value, path, required={"os_family", "python_version"})
    _enum(platform["os_family"], f"{path}.os_family", _OS_FAMILIES)
    _matching_string(platform["python_version"], f"{path}.python_version", _PYTHON_VERSION)


def _validate_context(value: object, path: str) -> None:
    context = _strict_object(
        value,
        path,
        required={"items", "bytes", "estimated_input_tokens"},
    )
    _bounded_integer(context["items"], f"{path}.items", 0, 20)
    _bounded_integer(context["bytes"], f"{path}.bytes", 0, 5_000_000)
    _bounded_integer(
        context["estimated_input_tokens"],
        f"{path}.estimated_input_tokens",
        1,
        2_000_000,
    )


def _validate_review_checks(value: object, path: str) -> None:
    fields = {
        "exact_prompt_inspected",
        "plan_fingerprint_captured",
        "plan_settings_reviewed",
        "request_fingerprint_captured",
    }
    checks = _strict_object(value, path, required=fields)
    for field in sorted(fields):
        _boolean(checks[field], f"{path}.{field}")


def _validate_run(value: object, path: str, *, allow_evidence: bool) -> dict[str, Any]:
    required = {"status", "attempts", "exit_code"}
    if allow_evidence:
        required.add("evidence_status")
    run = _strict_object(value, path, required=required)
    status = _enum(run["status"], f"{path}.status", _RUN_STATUSES)
    attempts = _bounded_integer(run["attempts"], f"{path}.attempts", 0, 1)
    exit_code = _nullable_exit_code(run["exit_code"], f"{path}.exit_code")

    if status == "not-run":
        if attempts != 0 or exit_code is not None:
            _fail(path, "not-run requires attempts 0 and exit_code null")
    elif status == "passed":
        if attempts != 1 or exit_code != 0:
            _fail(path, "passed requires attempts 1 and exit_code 0")
    elif attempts != 1 or exit_code in {None, 0}:
        _fail(path, "failed requires attempts 1 and a nonzero exit_code")

    if allow_evidence:
        evidence = _enum(run["evidence_status"], f"{path}.evidence_status", _EVIDENCE_STATUSES)
        if status == "not-run" and evidence != "not-run":
            _fail(path, "an unattempted execution cannot have evidence")
        if status == "failed" and evidence == "passed":
            _fail(path, "a failed execution cannot have passing evidence")
        if status == "passed" and evidence == "not-run":
            _fail(path, "a passing execution must retain passed or failed evidence verification")
    return run


def _validate_friction_codes(value: object, path: str) -> None:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    if not 1 <= len(value) <= 5:
        _fail(path, "must contain between 1 and 5 values")
    codes = [_enum(item, f"{path}[{index}]", _FRICTION_CODES) for index, item in enumerate(value)]
    if len(set(codes)) != len(codes):
        _fail(path, "must not contain duplicate values")
    if "none" in codes and len(codes) != 1:
        _fail(path, "none cannot be combined with another friction code")


def _validate_safety(value: object, path: str) -> None:
    safety = _strict_object(value, path, required=_SAFETY_FIELDS)
    for field in sorted(_SAFETY_FIELDS):
        _boolean(safety[field], f"{path}.{field}")


def _validate_completion_stage(
    stage: str,
    provider_check: Mapping[str, Any],
    execution: Mapping[str, Any],
    path: str,
) -> None:
    execution_status = execution["status"]
    evidence_status = execution["evidence_status"]
    if stage == "evidence-verified" and not (
        execution_status == "passed" and evidence_status == "passed"
    ):
        _fail(path, "evidence-verified requires a passing execution and evidence check")
    if stage == "executed" and execution_status != "passed":
        _fail(path, "executed requires a passing execution")
    if execution_status == "passed":
        expected = "evidence-verified" if evidence_status == "passed" else "executed"
        if stage != expected:
            _fail(path, f"must be {expected} for the recorded execution outcome")
    elif stage in {"executed", "evidence-verified"}:
        _fail(path, "cannot claim execution success for the recorded execution outcome")

    provider_status = provider_check["status"]
    if (
        execution_status == "not-run"
        and provider_status == "passed"
        and stage != "provider-checked"
    ):
        _fail(path, "must be provider-checked after a passing preflight without execution")
    if stage == "provider-checked" and provider_status != "passed":
        _fail(path, "provider-checked requires a passing provider preflight")
    if provider_status == "failed":
        if execution_status != "not-run":
            _fail(path, "a failed provider preflight must stop before execution")
        if stage != "plan-verified":
            _fail(path, "must remain plan-verified after a failed provider preflight")
    if execution_status == "failed":
        expected = "provider-checked" if provider_status == "passed" else "plan-verified"
        if stage != expected:
            _fail(path, f"must be {expected} after the recorded execution failure")


def _execution_is_acceptable(session: Mapping[str, Any]) -> bool:
    execution = session["execution"]
    if execution["attempts"] > 1:
        return False
    if execution["status"] == "passed":
        return execution["evidence_status"] == "passed"
    return execution["evidence_status"] != "passed"


def _strict_object(
    value: object,
    path: str,
    *,
    required: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(path, "must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        _fail(path, "is missing required fields: " + ", ".join(missing))
    if unknown:
        _fail(path, "contains unknown fields: " + ", ".join(unknown))
    return value


def _enum(value: object, path: str, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail(path, "must be one of: " + ", ".join(sorted(allowed)))
    return value


def _matching_string(value: object, path: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail(path, f"must match {pattern.pattern}")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "must be a boolean")
    return value


def _exact_integer(value: object, path: str, expected: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        _fail(path, f"must be exactly {expected}")
    return value


def _bounded_integer(value: object, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail(path, f"must be an integer from {minimum} through {maximum}")
    return value


def _nullable_exit_code(value: object, path: str) -> int | None:
    if value is None:
        return None
    return _bounded_integer(value, path, 0, 255)


def _reject_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PilotRecordError(f"pilot record contains duplicate field {key!r}")
        result[key] = value
    return result


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fail(path: str, message: str) -> NoReturn:
    raise PilotRecordError(f"{path} {message}")


if __name__ == "__main__":
    raise SystemExit(main())
