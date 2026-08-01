# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json
from io import BytesIO
from pathlib import Path

import pytest

from samsarix_codegen.context import (
    MAX_CONTEXT_MANIFEST_BYTES,
    ContextManifest,
    load_context_files,
    load_context_manifest,
    load_stream_context,
    parse_context_manifest,
    render_context_manifest,
)
from samsarix_codegen.errors import ContextError


def test_loads_utf8_context_relative_to_root(tmp_path: Path) -> None:
    source = tmp_path / "src" / "hello.py"
    source.parent.mkdir()
    source.write_bytes("print('héllo')\n".encode())

    files = load_context_files(["src/hello.py"], root=tmp_path)

    assert len(files) == 1
    assert files[0].path == "src/hello.py"
    assert files[0].content == "print('héllo')\n"
    assert files[0].size_bytes == len(source.read_bytes())


def test_duplicate_resolved_paths_are_loaded_once(tmp_path: Path) -> None:
    source = tmp_path / "hello.py"
    source.write_text("pass\n", encoding="utf-8")

    files = load_context_files(["hello.py", source], root=tmp_path)

    assert [item.path for item in files] == ["hello.py"]


def test_rejects_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("private", encoding="utf-8")

    with pytest.raises(ContextError, match="escapes the project root"):
        load_context_files([outside], root=root)


def test_rejects_binary_context(tmp_path: Path) -> None:
    source = tmp_path / "blob.bin"
    source.write_bytes(b"hello\x00world")

    with pytest.raises(ContextError, match="binary context"):
        load_context_files([source], root=tmp_path)


def test_rejects_invalid_utf8(tmp_path: Path) -> None:
    source = tmp_path / "legacy.txt"
    source.write_bytes(b"\xff\xfe")

    with pytest.raises(ContextError, match="not valid UTF-8"):
        load_context_files([source], root=tmp_path)


def test_enforces_per_file_and_total_limits(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("12345", encoding="utf-8")
    second.write_text("67890", encoding="utf-8")

    with pytest.raises(ContextError, match="per-file limit"):
        load_context_files([first], root=tmp_path, max_file_bytes=4)

    with pytest.raises(ContextError, match="total limit"):
        load_context_files([first, second], root=tmp_path, max_file_bytes=5, max_total_bytes=9)


def test_bounded_read_does_not_depend_only_on_stat_size(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "growing.txt"
    source.write_text("12345", encoding="utf-8")
    actual_mode = source.stat().st_mode

    class StaleStat:
        st_size = 1
        st_mode = actual_mode

    original_stat = Path.stat

    def stale_stat(self, *args, **kwargs):
        if self == source:
            return StaleStat()
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stale_stat)

    with pytest.raises(ContextError, match="while being read"):
        load_context_files([source], root=tmp_path, max_file_bytes=4)


def test_enforces_file_count_before_reading(tmp_path: Path) -> None:
    with pytest.raises(ContextError, match="at most 1"):
        load_context_files(["missing-a", "missing-b"], root=tmp_path, max_files=1)


def test_loads_bounded_utf8_stream_context() -> None:
    context = load_stream_context(
        "staged.diff", BytesIO("diff --git a/é b/é\n".encode()), max_bytes=50
    )

    assert context.path == "stdin:staged.diff"
    assert context.content == "diff --git a/é b/é\n"
    assert context.size_bytes == len(context.content.encode())


@pytest.mark.parametrize(
    ("name", "body", "match"),
    [
        ("", b"content", "cannot be blank"),
        ("bad\nname", b"content", "control characters"),
        ("empty", b"", "is empty"),
        ("binary", b"a\x00b", "binary"),
        ("legacy", b"\xff", "not valid UTF-8"),
    ],
)
def test_rejects_invalid_stream_context(name: str, body: bytes, match: str) -> None:
    with pytest.raises(ContextError, match=match):
        load_stream_context(name, BytesIO(body), max_bytes=20)


def test_enforces_stream_context_byte_limit() -> None:
    with pytest.raises(ContextError, match="remaining 4-byte limit"):
        load_stream_context("input", BytesIO(b"12345"), max_bytes=4)


def test_context_manifest_round_trips_as_an_exact_versioned_contract() -> None:
    manifest = ContextManifest(files=("src/app.py", "tests/test_app.py"))

    rendered = render_context_manifest(manifest)
    reparsed = parse_context_manifest(rendered.encode("utf-8"))

    assert reparsed == manifest
    assert json.loads(rendered) == {
        "schema_version": 1,
        "files": ["src/app.py", "tests/test_app.py"],
    }


def test_loads_context_manifest_relative_to_the_same_root(tmp_path: Path) -> None:
    manifest_path = tmp_path / "review-context.json"
    manifest_path.write_text(
        render_context_manifest(ContextManifest(files=("src/app.py",))), encoding="utf-8"
    )

    manifest = load_context_manifest("review-context.json", root=tmp_path)

    assert manifest.files == ("src/app.py",)


def test_context_manifest_must_be_contained_by_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "context.json"
    outside.write_text('{"schema_version": 1, "files": ["app.py"]}', encoding="utf-8")

    with pytest.raises(ContextError, match="context manifest escapes the project root"):
        load_context_manifest(outside, root=root)


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        (b"\xff", "not valid UTF-8"),
        (b"{}\x00", "binary context manifests"),
        ('{"schema_version": 1, "files": ["\ud800"]}', "not valid Unicode"),
        ("not json", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ('{"schema_version": 1}', "fields do not match"),
        (
            '{"schema_version": 1, "schema_version": 1, "files": ["app.py"]}',
            "duplicate JSON field",
        ),
        ('{"schema_version": true, "files": ["app.py"]}', "unsupported"),
        ('{"schema_version": 2, "files": ["app.py"]}', "unsupported"),
        ('{"schema_version": 1, "files": []}', "non-empty array"),
        ('{"schema_version": 1, "files": [1]}', "must be a string"),
        (
            '{"schema_version": 1, "files": ["app.py", "app.py"]}',
            "duplicate file path",
        ),
    ],
)
def test_rejects_invalid_context_manifest_documents(raw: str | bytes, match: str) -> None:
    with pytest.raises(ContextError, match=match):
        parse_context_manifest(raw)


@pytest.mark.parametrize(
    ("path", "match"),
    [
        ("", "cannot be blank"),
        (" app.py", "leading or trailing whitespace"),
        ("app.py ", "leading or trailing whitespace"),
        ("src\\app.py", "forward slashes"),
        ("/src/app.py", "relative to --root"),
        ("C:/src/app.py", "not portable"),
        ("src/../secret.txt", "parent segments"),
        ("src/./app.py", "dot"),
        ("src//app.py", "empty"),
        ("src/app?.py", "not portable"),
        ("src/trailing./app.py", "non-portable ending"),
        ("src/NUL.txt", "reserved path segment"),
        ("src/line\nbreak.py", "control characters"),
        ("\ud800", "valid Unicode"),
    ],
)
def test_rejects_nonportable_manifest_paths(path: str, match: str) -> None:
    raw = json.dumps({"schema_version": 1, "files": [path]})

    with pytest.raises(ContextError, match=match):
        parse_context_manifest(raw)


def test_context_manifest_byte_limit_applies_before_json_decode() -> None:
    raw = b" " * (MAX_CONTEXT_MANIFEST_BYTES + 1)

    with pytest.raises(ContextError, match="byte limit"):
        parse_context_manifest(raw)


def test_manifest_bounded_read_does_not_depend_only_on_stat_size(
    tmp_path: Path, monkeypatch
) -> None:
    manifest_path = tmp_path / "growing.json"
    manifest_path.write_bytes(b" " * (MAX_CONTEXT_MANIFEST_BYTES + 1))
    actual_mode = manifest_path.stat().st_mode

    class StaleStat:
        st_size = 1
        st_mode = actual_mode

    original_stat = Path.stat

    def stale_stat(self, *args, **kwargs):
        if self == manifest_path:
            return StaleStat()
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stale_stat)

    with pytest.raises(ContextError, match="while being read"):
        load_context_manifest(manifest_path, root=tmp_path)
