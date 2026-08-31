# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from samsarix_codegen import (
    ChatResult,
    ContextFile,
    create_request_artifact,
    load_context_files,
    parse_execution_result,
    parse_request_artifact,
    render_execution_result,
    render_request_artifact,
    verify_review_result,
)
from samsarix_codegen.artifact import MAX_ARTIFACT_BYTES
from samsarix_codegen.cli import main
from samsarix_codegen.errors import ArtifactError


def _artifact(root: Path, raw: bytes = b"value = 1\n", *, path: str = "app.py"):
    source = root / path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(raw)
    return create_request_artifact(
        [{"role": "user", "content": "Review the selected source"}],
        load_context_files([path], root=root),
        include_line_counts=True,
    )


def _result(artifact):
    return parse_execution_result(
        render_execution_result(
            artifact,
            ChatResult('{"schema_version":1,"summary":"No issues found.","findings":[]}'),
            model="synthetic-review-fixture",
        )
    )


@pytest.mark.parametrize(
    "raw", [b"", b"one\ntwo\n", b"one\r\ntwo\r\n", b"\xef\xbb\xbftext\n", "naïve\n".encode()]
)
def test_source_verification_preserves_loader_encoding_and_line_endings(tmp_path, raw):
    artifact = _artifact(tmp_path, raw, path="src/naïve file.py")
    result = _result(artifact)

    assert verify_review_result(artifact, result, source_root=tmp_path) == verify_review_result(
        artifact, result
    )


@pytest.mark.parametrize(
    "raw", [b"value = 2\n", b"short", b"value = 1\nmore", b"\xff" * 10, b"\x00" * 10]
)
def test_changed_source_fails_even_for_an_empty_review(tmp_path, raw):
    artifact = _artifact(tmp_path)
    (tmp_path / "app.py").write_bytes(raw)

    with pytest.raises(ArtifactError, match="review source"):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)


@pytest.mark.parametrize("missing", [True, False])
def test_deleted_source_or_directory_fails(tmp_path, missing):
    artifact = _artifact(tmp_path)
    (tmp_path / "app.py").unlink()
    if not missing:
        (tmp_path / "app.py").mkdir()
    with pytest.raises(ArtifactError, match="review source verification failed"):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)


def test_default_export_never_loads_source(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)

    def unexpected_read(*args, **kwargs):
        raise AssertionError("artifact-only verification must not read source")

    monkeypatch.setattr("samsarix_codegen.review_report.load_context_files", unexpected_read)
    verify_review_result(artifact, _result(artifact))


@pytest.mark.parametrize(
    "path",
    [
        "../secret.txt",
        "/secret.txt",
        "C:/secret.txt",
        "stdin:diff",
        "NUL",
        "dir/file.",
        "dir\\file",
        "dir/*.py",
    ],
)
def test_all_paths_are_validated_before_any_source_read(tmp_path, monkeypatch, path):
    artifact = create_request_artifact(
        [{"role": "user", "content": "Review"}],
        (ContextFile("valid.py", "x", 1), ContextFile(path, "x", 1)),
        include_line_counts=True,
    )

    def unexpected_read(*args, **kwargs):
        raise AssertionError("unsafe artifact must be rejected before source loading")

    monkeypatch.setattr("samsarix_codegen.review_report.load_context_files", unexpected_read)
    with pytest.raises(ArtifactError):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)


def test_directly_constructed_artifact_drift_is_rejected_before_source_reads(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)
    tampered = replace(artifact, context=(replace(artifact.context[0], name="other.py"),))

    def unexpected_read(*args, **kwargs):
        raise AssertionError("fingerprint must be checked before source loading")

    monkeypatch.setattr("samsarix_codegen.review_report.load_context_files", unexpected_read)
    with pytest.raises(ArtifactError, match="fingerprint does not match"):
        verify_review_result(tampered, _result(tampered), source_root=tmp_path)


def test_oversized_declared_context_fails_before_source_reads(tmp_path, monkeypatch):
    artifact = create_request_artifact(
        [{"role": "user", "content": "Review"}],
        (ContextFile("large.py", "x", MAX_ARTIFACT_BYTES + 1),),
        include_line_counts=True,
    )

    def unexpected_read(*args, **kwargs):
        raise AssertionError("resource limits must be checked before source loading")

    monkeypatch.setattr("samsarix_codegen.review_report.load_context_files", unexpected_read)
    with pytest.raises(ArtifactError, match="safety limit"):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)


def test_source_root_must_exist_as_a_directory(tmp_path):
    artifact = _artifact(tmp_path)
    for root in (tmp_path / "missing", tmp_path / "app.py"):
        with pytest.raises(ArtifactError, match="review source verification failed"):
            verify_review_result(artifact, _result(artifact), source_root=root)


def test_wrong_approval_is_rejected_before_source_reads(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)

    def unexpected_read(*args, **kwargs):
        raise AssertionError("approval must be checked before source loading")

    monkeypatch.setattr("samsarix_codegen.review_report.load_context_files", unexpected_read)
    with pytest.raises(ArtifactError, match="expected fingerprint"):
        verify_review_result(
            artifact,
            _result(artifact),
            source_root=tmp_path,
            expected_request_fingerprint="sha256:" + "0" * 64,
        )


def test_legacy_or_absent_source_metadata_cannot_claim_freshness(tmp_path):
    artifact = create_request_artifact(
        [{"role": "user", "content": "Review"}], (ContextFile("app.py", "x", 1),)
    )
    with pytest.raises(ArtifactError, match="recorded line counts"):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)
    empty = create_request_artifact([{"role": "user", "content": "Review"}], ())
    with pytest.raises(ArtifactError, match="at least one source file"):
        verify_review_result(empty, _result(empty), source_root=tmp_path)


def test_inconsistent_fingerprinted_line_count_is_rejected(tmp_path):
    artifact = _artifact(tmp_path)
    payload = artifact.to_payload()
    payload["context"]["items"][0]["line_count"] = 2
    del payload["request_fingerprint"]
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["request_fingerprint"] = "sha256:" + digest
    artifact = parse_request_artifact(json.dumps(payload))
    with pytest.raises(ArtifactError, match="source changed"):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)


def test_more_than_one_manifest_of_context_files_is_supported(tmp_path):
    paths = [f"file-{index}.py" for index in range(21)]
    for path in paths:
        (tmp_path / path).write_bytes(b"x\n")
    artifact = create_request_artifact(
        [{"role": "user", "content": "Review"}],
        load_context_files(paths, root=tmp_path, max_files=21),
        include_line_counts=True,
    )
    verify_review_result(artifact, _result(artifact), source_root=tmp_path)
    (tmp_path / paths[-1]).write_bytes(b"y\n")
    with pytest.raises(ArtifactError, match="source changed"):
        verify_review_result(artifact, _result(artifact), source_root=tmp_path)


@pytest.mark.parametrize("destination", ["outside", "alias", "duplicate"])
def test_symlink_escape_and_changed_source_identity_fail(tmp_path, destination):
    root = tmp_path / "project"
    root.mkdir()
    artifact = _artifact(root)
    target = tmp_path / "outside.py" if destination == "outside" else root / "target.py"
    target.write_bytes(b"value = 1\n")
    if destination == "duplicate":
        artifact = create_request_artifact(
            artifact.messages,
            load_context_files(["app.py", "target.py"], root=root),
            include_line_counts=True,
        )
    (root / "app.py").unlink()
    try:
        (root / "app.py").symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ArtifactError, match="escapes|canonically|duplicate"):
        verify_review_result(artifact, _result(artifact), source_root=root)


@pytest.mark.parametrize("output_format", ["json", "sarif"])
def test_cli_source_root_success_and_failure_stdout_contract(tmp_path, capsys, output_format):
    artifact = _artifact(tmp_path)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(render_request_artifact(artifact), encoding="utf-8")
    result_path.write_text(json.dumps(_result(artifact).to_payload()), encoding="utf-8")
    args = ["export-review", str(request_path), str(result_path), "--format", output_format]
    assert main(args + ["--source-root", str(tmp_path)]) == 0
    checked = capsys.readouterr()
    assert checked.err == ""
    (tmp_path / "app.py").write_bytes(b"value = 2\n")
    assert main(args + ["--source-root", str(tmp_path)]) == 5
    rejected = capsys.readouterr()
    assert rejected.out == ""
    assert "source changed" in rejected.err
    assert "value = 2" not in rejected.err
    assert main(args) == 0
    assert capsys.readouterr().out == checked.out
