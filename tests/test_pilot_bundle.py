# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.pilot_bundle import (
    PilotKitError,
    create_pilot_kit,
    main,
    verify_pilot_kit_archive,
    verify_pilot_kit_directory,
)
from scripts.pilot_check import evaluate_pilot, load_pilot_record

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
COMMIT = "1234567890abcdef1234567890abcdef12345678"
ARCHIVE_NAME = f"samsarix-codegen-pilot-kit-{VERSION}.zip"
ROOT_NAME = f"samsarix-codegen-pilot-kit-{VERSION}"
WHEEL_NAME = f"samsarix_codegen-{VERSION}-py3-none-any.whl"


def _create(tmp_path: Path, slot: str = "first") -> Path:
    directory = tmp_path / slot
    directory.mkdir()
    wheel = directory / WHEEL_NAME
    wheel.write_bytes(b"deterministic test wheel\n")
    archive = directory / ARCHIVE_NAME
    create_pilot_kit(
        version=VERSION,
        commit=COMMIT,
        wheel=wheel,
        output=archive,
        repository_root=ROOT,
    )
    return archive


def test_create_is_deterministic_and_both_verifiers_accept_it(tmp_path: Path) -> None:
    first = _create(tmp_path, "first")
    second = _create(tmp_path, "second")

    assert first.read_bytes() == second.read_bytes()
    summary = verify_pilot_kit_archive(first)
    assert summary == {
        "schema_version": 1,
        "status": "verified",
        "package": "samsarix-codegen",
        "package_version": VERSION,
        "source_commit": COMMIT,
        "wheel_path": f"package/{WHEEL_NAME}",
        "wheel_sha256": hashlib.sha256(b"deterministic test wheel\n").hexdigest(),
        "files": 21,
    }

    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(first) as archive:
        archive.extractall(extracted)
    assert verify_pilot_kit_directory(extracted / ROOT_NAME) == summary


def test_manifest_matches_schema_and_record_is_valid_but_not_ready(tmp_path: Path) -> None:
    archive_path = _create(tmp_path)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extracted)
    root = extracted / ROOT_NAME

    start = (root / "PILOT-START.md").read_text(encoding="utf-8")
    assert "Exercise the offline review export" in start
    assert (root / "docs/REVIEW_REPORT.md").is_file()
    assert (root / "examples/review-report-v1.json").is_file()

    manifest = json.loads((root / "pilot-kit-v1.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "docs/pilot-kit-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(manifest)
    path_schema = schema["$defs"]["content"]["properties"]["path"]
    path_validator = Draft202012Validator(path_schema)
    unsafe_paths = (
        "../escape.txt",
        ".",
        "..",
        "/absolute.txt",
        "root/../escape.txt",
        "root/.",
        "root/..",
        "C:/drive.txt",
        "root//double.txt",
        "root\\backslash.txt",
        "root/bad\nname",
        "directory/",
    )
    assert all(not path_validator.is_valid(path) for path in unsafe_paths)
    record = load_pilot_record(root / "pilot-record.json")
    assert record["wheel_sha256"] == manifest["wheel"]["sha256"]
    assert record["commit"] == manifest["source_commit"]
    assert evaluate_pilot(record)["decision"] == "not-ready"


def test_verify_rejects_tampered_content(tmp_path: Path) -> None:
    original = _create(tmp_path)
    tampered = tmp_path / ARCHIVE_NAME
    with (
        zipfile.ZipFile(original) as source,
        zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            data = source.read(info)
            if info.filename.endswith("/pilot-record.json"):
                data = data.replace(COMMIT.encode(), ("f" * 40).encode())
            target.writestr(info, data)

    with pytest.raises(PilotKitError, match="checksum mismatch for pilot-record.json"):
        verify_pilot_kit_archive(tampered)


@pytest.mark.parametrize(
    "member",
    ["../escape.txt", "/absolute.txt", "root/../escape.txt", "C:/drive.txt", "root/bad\nname"],
)
def test_verify_rejects_unsafe_archive_paths(tmp_path: Path, member: str) -> None:
    archive_path = tmp_path / ARCHIVE_NAME
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(member, b"unsafe")

    with pytest.raises(PilotKitError, match="unsafe or non-canonical"):
        verify_pilot_kit_archive(archive_path)


def test_verify_rejects_duplicate_archive_paths(tmp_path: Path) -> None:
    archive_path = tmp_path / ARCHIVE_NAME
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(archive_path, "w") as archive,
    ):
        archive.writestr(f"{ROOT_NAME}/duplicate.txt", b"first")
        archive.writestr(f"{ROOT_NAME}/duplicate.txt", b"second")

    with pytest.raises(PilotKitError, match="duplicate path"):
        verify_pilot_kit_archive(archive_path)


def test_verify_rejects_non_regular_archive_entry(tmp_path: Path) -> None:
    archive_path = tmp_path / ARCHIVE_NAME
    info = zipfile.ZipInfo(f"{ROOT_NAME}/link")
    info.create_system = 3
    info.external_attr = (0o120777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(info, b"target")

    with pytest.raises(PilotKitError, match="non-regular entry"):
        verify_pilot_kit_archive(archive_path)


def test_verify_directory_rejects_unexpected_file(tmp_path: Path) -> None:
    archive_path = _create(tmp_path)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extracted)
    root = extracted / ROOT_NAME
    (root / "unexpected.txt").write_text("not declared", encoding="utf-8")

    with pytest.raises(PilotKitError, match="unexpected: unexpected.txt"):
        verify_pilot_kit_directory(root)


def test_verify_directory_rejects_symlink(tmp_path: Path) -> None:
    archive_path = _create(tmp_path)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extracted)
    root = extracted / ROOT_NAME
    link = root / "linked-start.md"
    try:
        link.symlink_to("PILOT-START.md")
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(PilotKitError, match="contains a symbolic link"):
        verify_pilot_kit_directory(root)


def test_create_rejects_ambiguous_inputs_and_overwrite(tmp_path: Path) -> None:
    wheel = tmp_path / WHEEL_NAME
    wheel.write_bytes(b"wheel")
    output = tmp_path / ARCHIVE_NAME
    output.write_bytes(b"existing")

    with pytest.raises(PilotKitError, match="refusing to overwrite"):
        create_pilot_kit(
            version=VERSION,
            commit=COMMIT,
            wheel=wheel,
            output=output,
            repository_root=ROOT,
        )
    with pytest.raises(PilotKitError, match="wheel must be named"):
        create_pilot_kit(
            version=VERSION,
            commit=COMMIT,
            wheel=tmp_path / "wrong.whl",
            output=tmp_path / "unused.zip",
            repository_root=ROOT,
        )
    with pytest.raises(PilotKitError, match="output must be named"):
        create_pilot_kit(
            version=VERSION,
            commit=COMMIT,
            wheel=wheel,
            output=tmp_path / "wrong-name.zip",
            repository_root=ROOT,
        )
    with pytest.raises(PilotKitError, match="commit must match"):
        create_pilot_kit(
            version=VERSION,
            commit="not-a-commit",
            wheel=wheel,
            output=tmp_path / "unused.zip",
            repository_root=ROOT,
        )


def test_cli_reports_verified_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archive_path = _create(tmp_path)

    assert main(["verify", str(archive_path)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "verified"
    assert captured.err == ""
