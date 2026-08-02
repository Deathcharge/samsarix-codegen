# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from scripts.release_check import (
    REQUIRED_SCHEMAS,
    REQUIRED_SDIST_PATHS,
    REQUIRED_WHEEL_PATHS,
    ReleaseCheckError,
    verify_artifacts,
    verify_source,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"


def test_source_check_accepts_current_unreleased_dry_run() -> None:
    evidence = verify_source(REPOSITORY_ROOT, VERSION, allow_unreleased=True)

    assert evidence["status"] == "passed"
    assert evidence["version"] == VERSION
    assert evidence["changelog"] == "Unreleased"


def test_source_check_rejects_tag_while_changelog_is_unreleased() -> None:
    with pytest.raises(ReleaseCheckError, match="replace.*Unreleased"):
        verify_source(REPOSITORY_ROOT, VERSION, tag=f"v{VERSION}")


def test_source_check_rejects_allow_unreleased_with_tag() -> None:
    with pytest.raises(ReleaseCheckError, match="cannot be combined"):
        verify_source(
            REPOSITORY_ROOT,
            VERSION,
            tag=f"v{VERSION}",
            allow_unreleased=True,
        )


def test_source_check_rejects_version_drift() -> None:
    with pytest.raises(ReleaseCheckError, match="pyproject version"):
        verify_source(REPOSITORY_ROOT, "0.2.1", allow_unreleased=True)


def test_release_workflow_is_pinned_and_manual_runs_cannot_publish() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    action_refs = re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, flags=re.MULTILINE)

    assert "workflow_dispatch:" in workflow
    assert "push:\n    tags:" in workflow
    assert action_refs
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in action_refs)
    assert workflow.count("github.event_name == 'push' && github.ref_type == 'tag'") == 2
    assert "environment:\n      name: pypi" in workflow
    assert 'tag_commit="$(git rev-list -n 1 "${GITHUB_REF_NAME}")"' in workflow
    assert 'git merge-base --is-ancestor "${tag_commit}"' in workflow
    assert "secrets." not in workflow


def test_artifact_check_validates_pair_and_writes_deterministic_manifest(tmp_path: Path) -> None:
    _write_distribution_pair(tmp_path)
    manifest = tmp_path / "SHA256SUMS"

    evidence = verify_artifacts(tmp_path, VERSION, write_checksums=manifest)

    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert evidence["status"] == "passed"
    assert [item["filename"] for item in evidence["artifacts"]] == [
        "samsarix_codegen-0.2.0-py3-none-any.whl",
        "samsarix_codegen-0.2.0.tar.gz",
    ]
    assert len(lines) == 2
    assert lines[0].endswith("  samsarix_codegen-0.2.0-py3-none-any.whl")
    assert lines[1].endswith("  samsarix_codegen-0.2.0.tar.gz")
    assert all(len(line.split()[0]) == 64 for line in lines)


def test_artifact_check_rejects_unconditional_runtime_dependency(tmp_path: Path) -> None:
    _write_distribution_pair(tmp_path, dependency="requests>=2")

    with pytest.raises(ReleaseCheckError, match="runtime dependencies"):
        verify_artifacts(tmp_path, VERSION)


def test_artifact_check_rejects_unexpected_distribution_entry(tmp_path: Path) -> None:
    _write_distribution_pair(tmp_path)
    (tmp_path / "unexpected.zip").write_bytes(b"not a release artifact")

    with pytest.raises(ReleaseCheckError, match="unexpected entries"):
        verify_artifacts(tmp_path, VERSION)


def test_artifact_check_rejects_misnamed_checksum_manifest(tmp_path: Path) -> None:
    _write_distribution_pair(tmp_path)

    with pytest.raises(ReleaseCheckError, match="named SHA256SUMS"):
        verify_artifacts(tmp_path, VERSION, write_checksums=tmp_path / "hashes.txt")


def test_artifact_check_rejects_duplicate_wheel_member(tmp_path: Path) -> None:
    _write_distribution_pair(tmp_path)
    wheel = tmp_path / f"samsarix_codegen-{VERSION}-py3-none-any.whl"
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(wheel, mode="a") as archive,
    ):
        archive.writestr("samsarix_codegen/__init__.py", f'__version__ = "{VERSION}"\n')

    with pytest.raises(ReleaseCheckError, match="duplicate archive members"):
        verify_artifacts(tmp_path, VERSION)


def test_artifact_check_rejects_unexpected_wheel_package(tmp_path: Path) -> None:
    _write_distribution_pair(tmp_path)
    wheel = tmp_path / f"samsarix_codegen-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, mode="a") as archive:
        archive.writestr("legacy_package/__init__.py", "legacy = True\n")

    with pytest.raises(ReleaseCheckError, match="unexpected top-level paths: legacy_package"):
        verify_artifacts(tmp_path, VERSION)


def _write_distribution_pair(dist_dir: Path, *, dependency: str | None = None) -> None:
    root = f"samsarix_codegen-{VERSION}"
    sdist_path = dist_dir / f"{root}.tar.gz"
    sdist_content = {path: "fixture\n" for path in REQUIRED_SDIST_PATHS}
    sdist_content["pyproject.toml"] = (
        f'[project]\nname = "samsarix-codegen"\nversion = "{VERSION}"\n'
    )
    sdist_content["src/samsarix_codegen/__init__.py"] = f'__version__ = "{VERSION}"\n'
    for schema in REQUIRED_SCHEMAS:
        sdist_content[f"src/samsarix_codegen/schemas/{schema}"] = "{}\n"
    with tarfile.open(sdist_path, mode="w:gz") as archive:
        for name, content in sorted(sdist_content.items()):
            _add_tar_text(archive, f"{root}/{name}", content)

    wheel_path = dist_dir / f"{root}-py3-none-any.whl"
    dist_info = f"{root}.dist-info"
    metadata = (
        "Metadata-Version: 2.4\n"
        "Name: samsarix-codegen\n"
        f"Version: {VERSION}\n"
        "License-Expression: Apache-2.0\n"
        "Requires-Python: >=3.10\n"
    )
    if dependency is not None:
        metadata += f"Requires-Dist: {dependency}\n"
    with zipfile.ZipFile(wheel_path, mode="w") as archive:
        for name in REQUIRED_WHEEL_PATHS:
            content = (
                f'__version__ = "{VERSION}"\n' if name.endswith("__init__.py") else "fixture\n"
            )
            archive.writestr(name, content)
        for schema in REQUIRED_SCHEMAS:
            archive.writestr(f"samsarix_codegen/schemas/{schema}", "{}\n")
        archive.writestr(f"{dist_info}/METADATA", metadata)
        archive.writestr(f"{dist_info}/licenses/LICENSE", "Apache License 2.0\n")
        archive.writestr(f"{dist_info}/licenses/NOTICE", "Samsarix Codegen\n")


def _add_tar_text(archive: tarfile.TarFile, name: str, content: str) -> None:
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    archive.addfile(info, BytesIO(data))
