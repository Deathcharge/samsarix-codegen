# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest

from samsarix_codegen import (
    load_execution_result_policy as public_load_execution_result_policy,
)
from samsarix_codegen import (
    parse_execution_result_policy as public_parse_execution_result_policy,
)
from samsarix_codegen import (
    render_execution_result_policy as public_render_execution_result_policy,
)
from samsarix_codegen.artifact import (
    MAX_RESULT_BYTES,
    MAX_RESULT_POLICY_TOKENS,
    ExecutionResultPolicy,
)
from samsarix_codegen.errors import ArtifactError
from samsarix_codegen.result_policy import (
    MAX_RESULT_POLICY_BYTES,
    load_execution_result_policy,
    parse_execution_result_policy,
    render_execution_result_policy,
)


def make_policy() -> ExecutionResultPolicy:
    return ExecutionResultPolicy(
        expected_model="model-a",
        max_response_bytes=100_000,
        max_prompt_tokens=10_000,
        max_completion_tokens=2_000,
        max_total_tokens=12_000,
    )


def test_result_policy_round_trips_as_an_exact_versioned_contract() -> None:
    policy = make_policy()

    rendered = render_execution_result_policy(policy)
    reparsed = parse_execution_result_policy(rendered.encode())

    assert reparsed == policy
    assert json.loads(rendered) == {
        "schema_version": 1,
        "expected_model": "model-a",
        "max_response_bytes": 100_000,
        "max_prompt_tokens": 10_000,
        "max_completion_tokens": 2_000,
        "max_total_tokens": 12_000,
    }
    assert public_parse_execution_result_policy(rendered) == policy
    assert public_render_execution_result_policy(policy) == rendered


def test_loads_result_policy_from_an_explicit_file(tmp_path: Path) -> None:
    policy_path = tmp_path / "result-policy.json"
    policy_path.write_text(render_execution_result_policy(make_policy()), encoding="utf-8")

    assert load_execution_result_policy(policy_path) == make_policy()
    assert public_load_execution_result_policy(policy_path) == make_policy()


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        (b"\xff", "not valid UTF-8"),
        (b"{}\x00", "binary execution result policies"),
        ('{"schema_version": 1, "expected_model": "\ud800"}', "not valid Unicode"),
        ("not json", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ('{"expected_model": "model-a"}', "fields do not match"),
        ('{"schema_version": 1, "unexpected": true}', "fields do not match"),
        (
            '{"schema_version": 1, "schema_version": 1, "expected_model": "model-a"}',
            "duplicate JSON field",
        ),
        ('{"schema_version": true, "expected_model": "model-a"}', "unsupported"),
        ('{"schema_version": 2, "expected_model": "model-a"}', "unsupported"),
        ('{"schema_version": 1}', "at least one rule"),
        ('{"schema_version": 1, "expected_model": null}', "cannot be null"),
        ('{"schema_version": 1, "expected_model": " model-a"}', "surrounding whitespace"),
        ('{"schema_version": 1, "max_response_bytes": 0}', "between"),
        (
            f'{{"schema_version": 1, "max_response_bytes": {MAX_RESULT_BYTES + 1}}}',
            "between",
        ),
        ('{"schema_version": 1, "max_prompt_tokens": true}', "between 0"),
        ('{"schema_version": 1, "max_completion_tokens": -1}', "between 0"),
        ('{"schema_version": 1, "max_total_tokens": "12"}', "between 0"),
        (
            f'{{"schema_version": 1, "max_total_tokens": {MAX_RESULT_POLICY_TOKENS + 1}}}',
            "between 0",
        ),
    ],
)
def test_rejects_invalid_result_policy_documents(raw: str | bytes, match: str) -> None:
    with pytest.raises(ArtifactError, match=match):
        parse_execution_result_policy(raw)


def test_result_policy_document_byte_limit_applies_before_json_decode() -> None:
    with pytest.raises(ArtifactError, match="byte safety limit"):
        parse_execution_result_policy(b" " * (MAX_RESULT_POLICY_BYTES + 1))


def test_result_policy_rendering_rejects_empty_or_unvalidated_values() -> None:
    with pytest.raises(ArtifactError, match="at least one rule"):
        render_execution_result_policy(ExecutionResultPolicy())
    with pytest.raises(ArtifactError, match="requires a validated policy"):
        render_execution_result_policy(object())  # type: ignore[arg-type]


def test_policy_bounded_read_does_not_depend_only_on_stat_size(tmp_path: Path, monkeypatch) -> None:
    policy_path = tmp_path / "growing.json"
    policy_path.write_bytes(b" " * (MAX_RESULT_POLICY_BYTES + 1))
    actual_mode = policy_path.stat().st_mode

    class StaleStat:
        st_size = 1
        st_mode = actual_mode

    original_stat = Path.stat

    def stale_stat(self, *args, **kwargs):
        if self == policy_path:
            return StaleStat()
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stale_stat)

    with pytest.raises(ArtifactError, match="byte safety limit"):
        load_execution_result_policy(policy_path)


def test_policy_loader_rejects_a_missing_or_oversized_file(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="not a regular file"):
        load_execution_result_policy(tmp_path / "missing.json")

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_RESULT_POLICY_BYTES + 1))
    with pytest.raises(ArtifactError, match="byte safety limit"):
        load_execution_result_policy(oversized)


def test_policy_loader_converts_invalid_path_value_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy_path = tmp_path / "invalid.json"
    original_is_file = Path.is_file

    def invalid_is_file(self: Path) -> bool:
        if self == policy_path:
            raise ValueError("embedded null character in path")
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", invalid_is_file)

    with pytest.raises(ArtifactError, match="cannot read execution result policy"):
        load_execution_result_policy(policy_path)
