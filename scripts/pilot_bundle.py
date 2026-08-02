#!/usr/bin/env python3
# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Create and verify a deterministic, self-contained Samsarix Codegen pilot kit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

PILOT_KIT_SCHEMA_VERSION = 1
PACKAGE_NAME = "samsarix-codegen"
ARCHIVE_PREFIX = f"{PACKAGE_NAME}-pilot-kit-"
MANIFEST_NAME = "pilot-kit-v1.json"
CHECKSUMS_NAME = "SHA256SUMS"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_FILES = 32
MAX_MANIFEST_BYTES = 128 * 1024
MAX_PILOT_RECORD_BYTES = 256 * 1024
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

_VERSION = re.compile(r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")

_SOURCE_ASSETS = (
    "LICENSE",
    "NOTICE",
    "docs/PILOT.md",
    "docs/pilot-decision-v1.schema.json",
    "docs/pilot-kit-v1.schema.json",
    "docs/pilot-record-v1.schema.json",
    "examples/pilot-record-v1.json",
    "scripts/pilot_bundle.py",
    "scripts/pilot_check.py",
)


class PilotKitError(Exception):
    """A pilot kit is malformed, inconsistent, or outside its safety limits."""


def create_pilot_kit(
    *,
    version: str,
    commit: str,
    wheel: Path,
    output: Path,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Create one deterministic pilot kit and return its verified summary."""

    _validate_version(version)
    _matching_string(commit, "commit", _COMMIT)
    expected_wheel_name = _wheel_name(version)
    if wheel.name != expected_wheel_name:
        raise PilotKitError(f"wheel must be named {expected_wheel_name!r}, got {wheel.name!r}")
    root_name = f"{ARCHIVE_PREFIX}{version}"
    if output.name != f"{root_name}.zip":
        raise PilotKitError(f"output must be named {root_name}.zip")
    wheel_bytes = _read_regular_file(wheel, "wheel", MAX_UNCOMPRESSED_BYTES)
    if output.exists():
        raise PilotKitError(f"refusing to overwrite existing output: {output}")
    if not output.parent.is_dir():
        raise PilotKitError(f"output parent is not a directory: {output.parent}")

    wheel_path = f"package/{expected_wheel_name}"
    wheel_sha256 = _sha256(wheel_bytes)
    assets: dict[str, bytes] = {wheel_path: wheel_bytes}
    for relative in _SOURCE_ASSETS:
        source = repository_root / Path(relative)
        assets[relative] = _read_regular_file(source, relative, MAX_UNCOMPRESSED_BYTES)

    example = _load_json_file(
        repository_root / "examples/pilot-record-v1.json",
        "pilot record",
        maximum=MAX_PILOT_RECORD_BYTES,
    )
    if not isinstance(example, dict):
        raise PilotKitError("pilot record example must be a JSON object")
    example["wheel_sha256"] = wheel_sha256
    example["commit"] = commit
    assets["pilot-record.json"] = _pretty_json(example)
    assets["PILOT-START.md"] = _render_start(
        version=version,
        commit=commit,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
    )

    contents = [_content_record(path, data) for path, data in sorted(assets.items())]
    wheel_record = next(item for item in contents if item["path"] == wheel_path)
    manifest = {
        "schema_version": PILOT_KIT_SCHEMA_VERSION,
        "package": PACKAGE_NAME,
        "package_version": version,
        "source_commit": commit,
        "wheel": wheel_record,
        "contents": contents,
    }
    manifest_bytes = _pretty_json(manifest)
    files = {**assets, MANIFEST_NAME: manifest_bytes}
    checksum_bytes = _render_checksums(files)
    files[CHECKSUMS_NAME] = checksum_bytes

    try:
        with zipfile.ZipFile(
            output,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, data in sorted(files.items()):
                archive.writestr(_zip_info(f"{root_name}/{relative}"), data, compresslevel=9)
    except (OSError, zipfile.BadZipFile) as exc:
        with suppress(OSError):
            output.unlink()
        raise PilotKitError(f"cannot create pilot kit: {output}") from exc

    try:
        return verify_pilot_kit_archive(output)
    except PilotKitError:
        with suppress(OSError):
            output.unlink()
        raise


def verify_pilot_kit_archive(path: Path) -> dict[str, Any]:
    """Verify an unextracted pilot-kit ZIP without trusting archive paths."""

    try:
        if not path.is_file() or path.is_symlink():
            raise PilotKitError(f"pilot kit is not a regular file: {path}")
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise PilotKitError(f"pilot kit exceeds the {MAX_ARCHIVE_BYTES:,}-byte archive limit")
    except OSError as exc:
        raise PilotKitError(f"cannot inspect pilot kit: {path}") from exc

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_FILES:
                raise PilotKitError(f"pilot kit must contain between 1 and {MAX_FILES} files")
            names: set[str] = set()
            root_name: str | None = None
            total = 0
            for info in infos:
                name = _validate_archive_member(info)
                if name in names:
                    raise PilotKitError(f"pilot kit contains duplicate path: {name}")
                names.add(name)
                total += info.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise PilotKitError(
                        f"pilot kit exceeds the {MAX_UNCOMPRESSED_BYTES:,}-byte uncompressed limit"
                    )
                member_root = PurePosixPath(name).parts[0]
                if root_name is None:
                    root_name = member_root
                elif member_root != root_name:
                    raise PilotKitError("pilot kit must have exactly one top-level directory")
            assert root_name is not None
            payload = {
                str(PurePosixPath(info.filename).relative_to(root_name)): archive.read(info)
                for info in infos
            }
    except PilotKitError:
        raise
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise PilotKitError(f"cannot read pilot-kit ZIP: {path}") from exc

    return _verify_payload(payload, root_name=root_name, archive_name=path.name)


def verify_pilot_kit_directory(path: Path) -> dict[str, Any]:
    """Verify an extracted pilot-kit directory, including every regular file."""

    try:
        if not path.is_dir() or path.is_symlink():
            raise PilotKitError(f"pilot kit is not a regular directory: {path}")
        root = path.resolve(strict=True)
        payload: dict[str, bytes] = {}
        total = 0
        for candidate in root.rglob("*"):
            if candidate.is_symlink():
                raise PilotKitError(f"pilot kit contains a symbolic link: {candidate}")
            resolved = candidate.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise PilotKitError(f"pilot-kit path escapes its root: {candidate}") from exc
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise PilotKitError(f"pilot kit contains a non-regular file: {candidate}")
            relative = candidate.relative_to(root).as_posix()
            _validate_relative_path(relative, "directory path")
            data = _read_regular_file(candidate, relative, MAX_UNCOMPRESSED_BYTES)
            payload[relative] = data
            total += len(data)
            if len(payload) > MAX_FILES or total > MAX_UNCOMPRESSED_BYTES:
                raise PilotKitError("extracted pilot kit exceeds its file or size limit")
    except PilotKitError:
        raise
    except OSError as exc:
        raise PilotKitError(f"cannot inspect extracted pilot kit: {path}") from exc

    return _verify_payload(payload, root_name=root.name, archive_name=f"{root.name}.zip")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create and immediately verify a pilot kit")
    create.add_argument("--version", required=True)
    create.add_argument("--commit", required=True)
    create.add_argument("--wheel", required=True, type=Path)
    create.add_argument("--output", required=True, type=Path)

    verify = subparsers.add_parser("verify", help="verify a pilot-kit ZIP")
    verify.add_argument("archive", type=Path)

    verify_directory = subparsers.add_parser(
        "verify-directory", help="verify an extracted pilot-kit directory"
    )
    verify_directory.add_argument("directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            summary = create_pilot_kit(
                version=args.version,
                commit=args.commit,
                wheel=args.wheel,
                output=args.output,
            )
        elif args.command == "verify":
            summary = verify_pilot_kit_archive(args.archive)
        else:
            summary = verify_pilot_kit_directory(args.directory)
    except PilotKitError as exc:
        print(f"pilot kit check failed: {exc}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _verify_payload(
    payload: Mapping[str, bytes], *, root_name: str, archive_name: str
) -> dict[str, Any]:
    if MANIFEST_NAME not in payload or CHECKSUMS_NAME not in payload:
        raise PilotKitError(f"pilot kit must contain {MANIFEST_NAME} and {CHECKSUMS_NAME}")
    if len(payload[MANIFEST_NAME]) > MAX_MANIFEST_BYTES:
        raise PilotKitError("pilot-kit manifest exceeds its size limit")
    manifest = _load_json_bytes(payload[MANIFEST_NAME], "pilot-kit manifest")
    validated = _validate_manifest(manifest)
    version = validated["package_version"]
    expected_root = f"{ARCHIVE_PREFIX}{version}"
    if root_name != expected_root:
        raise PilotKitError(f"pilot-kit root must be {expected_root!r}, got {root_name!r}")
    if archive_name != f"{expected_root}.zip":
        raise PilotKitError(
            f"pilot-kit archive must be named {expected_root}.zip, got {archive_name!r}"
        )

    content_records = validated["contents"]
    expected_content_paths = {item["path"] for item in content_records}
    expected_paths = expected_content_paths | {MANIFEST_NAME, CHECKSUMS_NAME}
    actual_paths = set(payload)
    if actual_paths != expected_paths:
        _raise_path_difference(actual_paths, expected_paths)

    checksums = _parse_checksums(payload[CHECKSUMS_NAME])
    expected_checksum_paths = expected_paths - {CHECKSUMS_NAME}
    if set(checksums) != expected_checksum_paths:
        _raise_path_difference(set(checksums), expected_checksum_paths, label="checksum")
    for relative in sorted(expected_checksum_paths):
        actual = _sha256(payload[relative])
        if checksums[relative] != actual:
            raise PilotKitError(f"checksum mismatch for {relative}")

    by_path = {item["path"]: item for item in content_records}
    for relative in sorted(expected_content_paths):
        record = by_path[relative]
        data = payload[relative]
        if record["size_bytes"] != len(data) or record["sha256"] != _sha256(data):
            raise PilotKitError(f"manifest metadata mismatch for {relative}")

    wheel = validated["wheel"]
    if len(payload["pilot-record.json"]) > MAX_PILOT_RECORD_BYTES:
        raise PilotKitError("prefilled pilot record exceeds its size limit")
    record = _load_json_bytes(payload["pilot-record.json"], "prefilled pilot record")
    if not isinstance(record, dict):
        raise PilotKitError("prefilled pilot record must be a JSON object")
    if isinstance(record.get("schema_version"), bool) or record.get("schema_version") != 1:
        raise PilotKitError("prefilled pilot record must use schema_version 1")
    if record.get("wheel_sha256") != wheel["sha256"]:
        raise PilotKitError("prefilled pilot record does not match the bundled wheel")
    if record.get("commit") != validated["source_commit"]:
        raise PilotKitError("prefilled pilot record does not match the source commit")
    if not isinstance(record.get("sessions"), list) or not record["sessions"]:
        raise PilotKitError("prefilled pilot record must include an editable example session")

    expected_start = _render_start(
        version=version,
        commit=validated["source_commit"],
        wheel_path=wheel["path"],
        wheel_sha256=wheel["sha256"],
    )
    if payload["PILOT-START.md"] != expected_start:
        raise PilotKitError("PILOT-START.md does not match the manifest")

    return {
        "schema_version": PILOT_KIT_SCHEMA_VERSION,
        "status": "verified",
        "package": PACKAGE_NAME,
        "package_version": version,
        "source_commit": validated["source_commit"],
        "wheel_path": wheel["path"],
        "wheel_sha256": wheel["sha256"],
        "files": len(payload),
    }


def _validate_manifest(value: object) -> dict[str, Any]:
    manifest = _strict_object(
        value,
        "manifest",
        required={
            "schema_version",
            "package",
            "package_version",
            "source_commit",
            "wheel",
            "contents",
        },
    )
    if (
        isinstance(manifest["schema_version"], bool)
        or manifest["schema_version"] != PILOT_KIT_SCHEMA_VERSION
    ):
        raise PilotKitError(f"manifest.schema_version must be {PILOT_KIT_SCHEMA_VERSION}")
    if manifest["package"] != PACKAGE_NAME:
        raise PilotKitError(f"manifest.package must be {PACKAGE_NAME!r}")
    version = _validate_version(manifest["package_version"])
    _matching_string(manifest["source_commit"], "manifest.source_commit", _COMMIT)
    wheel = _validate_content_record(manifest["wheel"], "manifest.wheel")
    expected_wheel_path = f"package/{_wheel_name(version)}"
    if wheel["path"] != expected_wheel_path:
        raise PilotKitError(f"manifest.wheel.path must be {expected_wheel_path!r}")

    values = manifest["contents"]
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_FILES - 2:
        raise PilotKitError("manifest.contents must be a bounded, non-empty array")
    contents = [
        _validate_content_record(item, f"manifest.contents[{index}]")
        for index, item in enumerate(values)
    ]
    paths = [item["path"] for item in contents]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise PilotKitError("manifest.contents paths must be unique and sorted")
    expected_paths = set(_SOURCE_ASSETS) | {
        "PILOT-START.md",
        "pilot-record.json",
        expected_wheel_path,
    }
    if set(paths) != expected_paths:
        _raise_path_difference(set(paths), expected_paths, label="manifest")
    wheel_copy = next(item for item in contents if item["path"] == expected_wheel_path)
    if wheel != wheel_copy:
        raise PilotKitError("manifest.wheel must exactly match its contents record")
    return manifest


def _validate_content_record(value: object, path: str) -> dict[str, Any]:
    record = _strict_object(value, path, required={"path", "sha256", "size_bytes"})
    relative = record["path"]
    if not isinstance(relative, str):
        raise PilotKitError(f"{path}.path must be a string")
    _validate_relative_path(relative, f"{path}.path")
    _matching_string(record["sha256"], f"{path}.sha256", _SHA256)
    size_bytes = record["size_bytes"]
    if (
        isinstance(size_bytes, bool)
        or not isinstance(size_bytes, int)
        or not 0 <= size_bytes <= MAX_UNCOMPRESSED_BYTES
    ):
        raise PilotKitError(f"{path}.size_bytes is outside its safety limit")
    return record


def _validate_archive_member(info: zipfile.ZipInfo) -> str:
    name = info.filename
    _validate_relative_path(name, "archive path", require_root=True)
    if info.is_dir() or name.endswith("/"):
        raise PilotKitError(f"pilot kit contains an explicit directory entry: {name}")
    if info.flag_bits & 0x1:
        raise PilotKitError(f"pilot kit contains an encrypted entry: {name}")
    unix_mode = info.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)
    if file_type not in {0, stat.S_IFREG}:
        raise PilotKitError(f"pilot kit contains a non-regular entry: {name}")
    if info.file_size < 0 or info.file_size > MAX_UNCOMPRESSED_BYTES:
        raise PilotKitError(f"pilot-kit member exceeds its size limit: {name}")
    return name


def _validate_relative_path(value: str, label: str, *, require_root: bool = False) -> None:
    if not value or "\\" in value or "\x00" in value:
        raise PilotKitError(f"{label} is empty or non-canonical: {value!r}")
    path = PurePosixPath(value)
    parts = path.parts
    minimum_parts = 2 if require_root else 1
    if (
        path.is_absolute()
        or len(parts) < minimum_parts
        or re.match(r"^[A-Za-z]:", parts[0]) is not None
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or any(part in {"", ".", ".."} for part in parts)
        or path.as_posix() != value
    ):
        raise PilotKitError(f"{label} is unsafe or non-canonical: {value!r}")


def _parse_checksums(raw: bytes) -> dict[str, str]:
    text = _decode_utf8(raw, CHECKSUMS_NAME)
    if not text.endswith("\n"):
        raise PilotKitError(f"{CHECKSUMS_NAME} must end with a newline")
    result: dict[str, str] = {}
    paths: list[str] = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise PilotKitError(f"invalid {CHECKSUMS_NAME} line {index}")
        digest, relative = match.groups()
        _validate_relative_path(relative, f"{CHECKSUMS_NAME} line {index}")
        if relative in result:
            raise PilotKitError(f"duplicate checksum path: {relative}")
        result[relative] = digest
        paths.append(relative)
    if not result or paths != sorted(paths):
        raise PilotKitError(f"{CHECKSUMS_NAME} paths must be non-empty and sorted")
    return result


def _render_checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(f"{_sha256(files[path])}  {path}\n" for path in sorted(files)).encode("utf-8")


def _render_start(*, version: str, commit: str, wheel_path: str, wheel_sha256: str) -> bytes:
    text = f"""# Start the Samsarix Codegen pilot

This kit pins Samsarix Codegen `{version}` to source commit `{commit}`.
Its wheel SHA-256 is `{wheel_sha256}`.

## 1. Verify this extracted kit

From this directory, run:

```console
python scripts/pilot_bundle.py verify-directory .
```

The command verifies the strict manifest, every checksum, the bundled wheel, and the prefilled
record linkage. It establishes internal integrity; use GitHub artifact-attestation verification
before extraction to establish build provenance.

## 2. Install the exact wheel

```console
python -m pip install \"{wheel_path}\"
samsarix-codegen self-check
```

Use a fresh virtual environment if another Samsarix Codegen version is already installed.

## 3. Run the protocol

Follow `docs/PILOT.md`. Edit `pilot-record.json` without adding prompts, responses, source code,
paths, logs, credentials, names, email addresses, or other free-form content. The wheel digest and
source commit are already filled in.

Validate the record from this directory:

```console
python scripts/pilot_check.py pilot-record.json > pilot-decision.json
```

Exit code 0 means the adoption gate passed, 1 means the record is valid but not ready, and 2 means
the record is invalid. An initial exit code 1 is expected until all three developers complete the
protocol.
"""
    return text.encode("utf-8")


def _content_record(path: str, data: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": _sha256(data), "size_bytes": len(data)}


def _wheel_name(version: str) -> str:
    return f"samsarix_codegen-{version}-py3-none-any.whl"


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _read_regular_file(path: Path, label: str, maximum: int) -> bytes:
    try:
        if not path.is_file() or path.is_symlink():
            raise PilotKitError(f"{label} is not a regular file: {path}")
        size = path.stat().st_size
        if size > maximum:
            raise PilotKitError(f"{label} exceeds its {maximum:,}-byte safety limit")
        return path.read_bytes()
    except PilotKitError:
        raise
    except OSError as exc:
        raise PilotKitError(f"cannot read {label}: {path}") from exc


def _load_json_file(path: Path, label: str, *, maximum: int = MAX_MANIFEST_BYTES) -> object:
    return _load_json_bytes(_read_regular_file(path, label, maximum), label)


def _load_json_bytes(raw: bytes, label: str) -> object:
    text = _decode_utf8(raw, label)
    try:
        return json.loads(text, object_pairs_hook=lambda pairs: _reject_duplicates(pairs, label))
    except PilotKitError:
        raise
    except json.JSONDecodeError as exc:
        raise PilotKitError(f"{label} is not valid JSON: {exc.msg}") from exc


def _reject_duplicates(pairs: list[tuple[str, Any]], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PilotKitError(f"{label} contains duplicate field {key!r}")
        result[key] = value
    return result


def _decode_utf8(raw: bytes, label: str) -> str:
    if b"\x00" in raw:
        raise PilotKitError(f"{label} contains a NUL byte")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PilotKitError(f"{label} must be UTF-8") from exc


def _pretty_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_version(value: object) -> str:
    return _matching_string(value, "version", _VERSION)


def _matching_string(value: object, path: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise PilotKitError(f"{path} must match {pattern.pattern}")
    return value


def _strict_object(value: object, path: str, *, required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PilotKitError(f"{path} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise PilotKitError(f"{path} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise PilotKitError(f"{path} contains unknown fields: {', '.join(unknown)}")
    return value


def _raise_path_difference(
    actual: set[str], expected: set[str], *, label: str = "pilot-kit"
) -> NoReturn:
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append("missing: " + ", ".join(missing))
    if unexpected:
        details.append("unexpected: " + ", ".join(unexpected))
    raise PilotKitError(f"{label} paths do not match ({'; '.join(details)})")


if __name__ == "__main__":
    raise SystemExit(main())
