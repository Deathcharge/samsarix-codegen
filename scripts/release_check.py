#!/usr/bin/env python3
# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed source and distribution checks for a Samsarix Codegen release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Sequence
from datetime import date
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_NAME = "samsarix-codegen"
DIST_NAME = "samsarix_codegen"
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SOURCE_VERSION_PATTERN = re.compile(r'^__version__\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
PROJECT_BLOCK_PATTERN = re.compile(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
PROJECT_VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
CHANGELOG_PATTERN = re.compile(r"^## \[([^]]+)] - (.+)$", re.MULTILINE)

REQUIRED_SCHEMAS = (
    "artifact-comparison-v1.schema.json",
    "context-manifest-v1.schema.json",
    "execution-plan-v1.schema.json",
    "execution-plan-v2.schema.json",
    "execution-plan-verification-v1.schema.json",
    "execution-plan-verification-v2.schema.json",
    "execution-evidence-verification-v1.schema.json",
    "execution-evidence-verification-v2.schema.json",
    "execution-evidence-verification-v3.schema.json",
    "execution-result-v1.schema.json",
    "execution-result-v2.schema.json",
    "execution-result-comparison-v1.schema.json",
    "execution-result-comparison-v2.schema.json",
    "execution-result-inspection-v1.schema.json",
    "execution-result-inspection-v2.schema.json",
    "execution-result-policy-v1.schema.json",
    "execution-result-policy-v2.schema.json",
    "execution-result-verification-v1.schema.json",
    "execution-result-verification-v2.schema.json",
    "provider-check-v1.schema.json",
    "request-artifact-v2.schema.json",
    "self-check-v1.schema.json",
)
REQUIRED_SDIST_PATHS = (
    ".gitattributes",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.in",
    "NOTICE",
    "README.md",
    "ROADMAP.md",
    "SECURITY.md",
    "SUPPORT.md",
    "docs/COMPETITIVE_STRATEGY.md",
    "docs/CONTEXT_MANIFEST.md",
    "docs/EXECUTION_PLAN.md",
    "docs/PILOT.md",
    "docs/pilot-decision-v1.schema.json",
    "docs/pilot-kit-v1.schema.json",
    "docs/pilot-record-v1.schema.json",
    "docs/PRODUCTIZATION.md",
    "docs/RELEASING.md",
    "docs/REQUEST_ARTIFACT.md",
    "docs/RESULT_POLICY.md",
    "docs/SELF_CHECK.md",
    "examples/README.md",
    "examples/execution-plan-v1.json",
    "examples/execution-plan-v2.json",
    "examples/execution-request-v2.json",
    "examples/execution-result-v2.json",
    "examples/pilot-record-v1.json",
    "examples/execution-evidence-v1.json",
    "examples/execution-evidence-v2.json",
    "examples/execution-evidence-v3.json",
    "examples/execution-evidence-policy-v1.json",
    "examples/review-context-v1.json",
    "examples/result-policy-v1.json",
    "examples/structured-execution-result-v2.json",
    "examples/structured-result-policy-v2.json",
    "pyproject.toml",
    "scripts/release_check.py",
    "scripts/installed_plan_smoke.py",
    "scripts/pilot_bundle.py",
    "scripts/pilot_check.py",
    "src/samsarix_codegen/__init__.py",
    "src/samsarix_codegen/execution_plan.py",
    "src/samsarix_codegen/execution_evidence.py",
    "src/samsarix_codegen/provider_check.py",
    "src/samsarix_codegen/self_check.py",
    "src/samsarix_codegen/py.typed",
    "tests/test_release.py",
    "tests/test_self_check.py",
    "tests/test_pilot_check.py",
    "tests/test_pilot_bundle.py",
)
REQUIRED_WHEEL_PATHS = (
    "samsarix_codegen/__init__.py",
    "samsarix_codegen/execution_evidence.py",
    "samsarix_codegen/provider_check.py",
    "samsarix_codegen/self_check.py",
    "samsarix_codegen/py.typed",
)


class ReleaseCheckError(Exception):
    """A release input or artifact is inconsistent or unsafe."""


def verify_source(
    root: Path,
    expected_version: str,
    *,
    tag: str | None = None,
    allow_unreleased: bool = False,
    require_clean: bool = False,
) -> dict[str, Any]:
    """Verify version, changelog, tag, and optional worktree invariants."""

    _validate_version(expected_version)
    root = root.resolve()
    pyproject_version = _read_project_version(root / "pyproject.toml")
    package_version = _read_source_version(root / "src/samsarix_codegen/__init__.py")
    if pyproject_version != expected_version:
        raise ReleaseCheckError(
            f"pyproject version is {pyproject_version!r}, expected {expected_version!r}"
        )
    if package_version != expected_version:
        raise ReleaseCheckError(
            f"package version is {package_version!r}, expected {expected_version!r}"
        )

    if tag is not None and tag != f"v{expected_version}":
        raise ReleaseCheckError(f"tag must be exactly v{expected_version}, got {tag!r}")
    if tag is not None and allow_unreleased:
        raise ReleaseCheckError("--allow-unreleased cannot be combined with a release tag")

    changelog_state = _read_changelog_state(root / "CHANGELOG.md", expected_version)
    if changelog_state == "Unreleased":
        if not allow_unreleased:
            raise ReleaseCheckError(
                f"CHANGELOG.md must replace [{expected_version}] - Unreleased with an ISO date"
            )
    else:
        try:
            released_on = date.fromisoformat(changelog_state)
        except ValueError as exc:
            raise ReleaseCheckError(
                f"changelog release value must be Unreleased or YYYY-MM-DD, got {changelog_state!r}"
            ) from exc
        if released_on > date.today():
            raise ReleaseCheckError("changelog release date cannot be in the future")

    if require_clean:
        _require_clean_worktree(root)

    return {
        "check": "source",
        "status": "passed",
        "version": expected_version,
        "tag": tag,
        "changelog": changelog_state,
        "clean_worktree_required": require_clean,
    }


def verify_artifacts(
    dist_dir: Path,
    expected_version: str,
    *,
    write_checksums: Path | None = None,
) -> dict[str, Any]:
    """Verify the exact sdist/wheel pair and optionally write its SHA-256 manifest."""

    _validate_version(expected_version)
    dist_dir = dist_dir.resolve()
    if not dist_dir.is_dir():
        raise ReleaseCheckError(f"distribution directory does not exist: {dist_dir}")

    sdist = dist_dir / f"{DIST_NAME}-{expected_version}.tar.gz"
    wheel = dist_dir / f"{DIST_NAME}-{expected_version}-py3-none-any.whl"
    allowed = {sdist.name, wheel.name, "SHA256SUMS"}
    unexpected = sorted(path.name for path in dist_dir.iterdir() if path.name not in allowed)
    if unexpected:
        raise ReleaseCheckError(
            "distribution directory contains unexpected entries: " + ", ".join(unexpected)
        )
    for artifact in (sdist, wheel):
        if not artifact.is_file():
            raise ReleaseCheckError(f"required distribution is missing: {artifact.name}")

    _verify_sdist(sdist, expected_version)
    _verify_wheel(wheel, expected_version)
    digests = {artifact.name: _sha256(artifact) for artifact in (sdist, wheel)}

    if write_checksums is not None:
        checksum_path = write_checksums.resolve()
        if checksum_path.parent != dist_dir:
            raise ReleaseCheckError("SHA256SUMS must be written inside the distribution directory")
        if checksum_path.name != "SHA256SUMS":
            raise ReleaseCheckError("checksum manifest must be named SHA256SUMS")
        checksum_path.write_text(
            "".join(f"{digest}  {name}\n" for name, digest in sorted(digests.items())),
            encoding="utf-8",
            newline="\n",
        )

    return {
        "check": "artifacts",
        "status": "passed",
        "version": expected_version,
        "artifacts": [
            {"filename": name, "sha256": digest} for name, digest in sorted(digests.items())
        ],
        "checksums": str(write_checksums.resolve()) if write_checksums is not None else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser("source", help="verify source version and release metadata")
    source.add_argument("--version", required=True, help="expected X.Y.Z version")
    source.add_argument("--tag", help="expected tag; must be vVERSION")
    source.add_argument(
        "--allow-unreleased",
        action="store_true",
        help="allow an Unreleased changelog entry for a non-publishing dry run",
    )
    source.add_argument(
        "--require-clean",
        action="store_true",
        help="fail if the git worktree has tracked or untracked changes",
    )
    source.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)

    artifacts = subparsers.add_parser(
        "artifacts", help="verify an exact sdist/wheel pair and its metadata"
    )
    artifacts.add_argument("--version", required=True, help="expected X.Y.Z version")
    artifacts.add_argument("--dist-dir", type=Path, default=Path("dist"))
    artifacts.add_argument("--write-checksums", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "source":
            evidence = verify_source(
                args.root,
                args.version,
                tag=args.tag,
                allow_unreleased=args.allow_unreleased,
                require_clean=args.require_clean,
            )
        else:
            evidence = verify_artifacts(
                args.dist_dir,
                args.version,
                write_checksums=args.write_checksums,
            )
    except ReleaseCheckError as exc:
        print(f"release check failed: {exc}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


def _validate_version(version: str) -> None:
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ReleaseCheckError(
            f"release version must use X.Y.Z without a v prefix, got {version!r}"
        )


def _read_project_version(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseCheckError(f"cannot read {path}") from exc
    block = PROJECT_BLOCK_PATTERN.search(text)
    match = PROJECT_VERSION_PATTERN.search(block.group(1)) if block is not None else None
    if match is None:
        raise ReleaseCheckError("pyproject.toml has no literal [project] version")
    return match.group(1)


def _read_source_version(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseCheckError(f"cannot read {path}") from exc
    match = SOURCE_VERSION_PATTERN.search(text)
    if match is None:
        raise ReleaseCheckError(f"cannot find __version__ in {path}")
    return match.group(1)


def _read_changelog_state(path: Path, version: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseCheckError(f"cannot read {path}") from exc
    matches = [
        state.strip() for found, state in CHANGELOG_PATTERN.findall(text) if found == version
    ]
    if len(matches) != 1:
        raise ReleaseCheckError(f"CHANGELOG.md must contain exactly one [{version}] heading")
    return matches[0]


def _require_clean_worktree(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseCheckError("cannot inspect git worktree state") from exc
    if result.stdout.strip():
        raise ReleaseCheckError("git worktree is not clean")


def _verify_sdist(path: Path, version: str) -> None:
    expected_root = f"{DIST_NAME}-{version}"
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = {member.name for member in members}
            if len(names) != len(members):
                raise ReleaseCheckError("sdist contains duplicate archive members")
            _validate_archive_names(names, expected_root)
            for member in members:
                if not (member.isfile() or member.isdir()):
                    raise ReleaseCheckError(
                        f"sdist contains a non-regular archive member: {member.name}"
                    )
            required = {f"{expected_root}/{name}" for name in REQUIRED_SDIST_PATHS}
            required.update(
                f"{expected_root}/src/samsarix_codegen/schemas/{name}" for name in REQUIRED_SCHEMAS
            )
            missing = sorted(required - names)
            if missing:
                raise ReleaseCheckError("sdist is missing required files: " + ", ".join(missing))

            pyproject = _read_tar_text(archive, f"{expected_root}/pyproject.toml")
            package_init = _read_tar_text(
                archive, f"{expected_root}/src/samsarix_codegen/__init__.py"
            )
    except (OSError, tarfile.TarError) as exc:
        raise ReleaseCheckError(f"cannot inspect sdist {path.name}") from exc

    project_block = PROJECT_BLOCK_PATTERN.search(pyproject)
    project_match = (
        PROJECT_VERSION_PATTERN.search(project_block.group(1))
        if project_block is not None
        else None
    )
    source_match = SOURCE_VERSION_PATTERN.search(package_init)
    if project_match is None or project_match.group(1) != version:
        raise ReleaseCheckError("sdist pyproject version does not match the release")
    if source_match is None or source_match.group(1) != version:
        raise ReleaseCheckError("sdist package version does not match the release")


def _verify_wheel(path: Path, version: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            member_names = archive.namelist()
            names = set(member_names)
            if len(names) != len(member_names):
                raise ReleaseCheckError("wheel contains duplicate archive members")
            _validate_archive_names(names, None)
            required = set(REQUIRED_WHEEL_PATHS)
            required.update(f"samsarix_codegen/schemas/{name}" for name in REQUIRED_SCHEMAS)
            missing = sorted(required - names)
            if missing:
                raise ReleaseCheckError("wheel is missing required files: " + ", ".join(missing))

            metadata_names = sorted(name for name in names if name.endswith(".dist-info/METADATA"))
            if len(metadata_names) != 1:
                raise ReleaseCheckError("wheel must contain exactly one METADATA file")
            dist_info = metadata_names[0].removesuffix("METADATA")
            expected_dist_info = f"{DIST_NAME}-{version}.dist-info/"
            if dist_info != expected_dist_info:
                raise ReleaseCheckError(
                    f"wheel dist-info directory is {dist_info!r}, expected {expected_dist_info!r}"
                )
            allowed_roots = {"samsarix_codegen", dist_info.removesuffix("/")}
            unexpected_roots = sorted(
                {PurePosixPath(name).parts[0] for name in names} - allowed_roots
            )
            if unexpected_roots:
                raise ReleaseCheckError(
                    "wheel contains unexpected top-level paths: " + ", ".join(unexpected_roots)
                )
            legal_files = {f"{dist_info}licenses/LICENSE", f"{dist_info}licenses/NOTICE"}
            missing_legal = sorted(legal_files - names)
            if missing_legal:
                raise ReleaseCheckError(
                    "wheel is missing packaged legal files: " + ", ".join(missing_legal)
                )
            metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
            package_init = archive.read("samsarix_codegen/__init__.py").decode("utf-8")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ReleaseCheckError(f"cannot inspect wheel {path.name}") from exc

    expected_metadata = {
        "Name": PROJECT_NAME,
        "Version": version,
        "License-Expression": "Apache-2.0",
    }
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            raise ReleaseCheckError(
                f"wheel metadata {key} is {metadata.get(key)!r}, expected {expected!r}"
            )
    if metadata.get("Requires-Python") != ">=3.10":
        raise ReleaseCheckError("wheel Requires-Python must be >=3.10")
    dependencies = metadata.get_all("Requires-Dist", [])
    unconditional = [value for value in dependencies if "extra ==" not in value]
    if unconditional:
        raise ReleaseCheckError(
            "wheel unexpectedly declares runtime dependencies: " + ", ".join(unconditional)
        )

    source_match = SOURCE_VERSION_PATTERN.search(package_init)
    if source_match is None or source_match.group(1) != version:
        raise ReleaseCheckError("wheel package version does not match the release")


def _validate_archive_names(names: set[str], expected_root: str | None) -> None:
    for name in names:
        if "\\" in name:
            raise ReleaseCheckError(f"archive member uses a backslash: {name}")
        parts = PurePosixPath(name).parts
        if not parts or PurePosixPath(name).is_absolute() or ".." in parts:
            raise ReleaseCheckError(f"archive member has an unsafe path: {name}")
        if expected_root is not None and parts[0] != expected_root:
            raise ReleaseCheckError(f"sdist member is outside {expected_root}: {name}")


def _read_tar_text(archive: tarfile.TarFile, name: str) -> str:
    extracted = archive.extractfile(name)
    if extracted is None:
        raise ReleaseCheckError(f"sdist member is not a readable file: {name}")
    try:
        return extracted.read().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseCheckError(f"sdist member is not UTF-8: {name}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
