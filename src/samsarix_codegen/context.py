# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Safe, explicit loading of source context from one project root."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, ClassVar

from samsarix_codegen.errors import ContextError
from samsarix_codegen.models import ContextFile

DEFAULT_MAX_FILES = 20
DEFAULT_MAX_MANIFESTS = 20
DEFAULT_MAX_TOTAL_BYTES = 200_000
DEFAULT_MAX_FILE_BYTES = 100_000
CONTEXT_MANIFEST_SCHEMA_VERSION = 1
MAX_CONTEXT_MANIFEST_BYTES = 64 * 1024
MAX_CONTEXT_PATH_CHARS = 4_096
MAX_STDIN_NAME_CHARS = 200


class _DuplicateManifestKeyError(ValueError):
    """Internal signal for an ambiguous JSON object."""


@dataclass(frozen=True, slots=True)
class ContextManifest:
    """A portable, explicitly invoked allowlist of context files."""

    files: tuple[str, ...]
    schema_version: ClassVar[int] = CONTEXT_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.files, tuple) or not self.files:
            raise ContextError("context manifest files must be a non-empty tuple")
        if len(self.files) > DEFAULT_MAX_FILES:
            raise ContextError(f"context manifest may contain at most {DEFAULT_MAX_FILES} files")
        seen: set[str] = set()
        for index, path in enumerate(self.files):
            if not isinstance(path, str):
                raise ContextError(f"context manifest file {index} must be a string")
            _validate_manifest_path(path, index=index)
            if path in seen:
                raise ContextError(f"context manifest contains duplicate file path: {path}")
            seen.add(path)
        rendered_size = len(
            json.dumps(
                {"schema_version": self.schema_version, "files": list(self.files)},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if rendered_size > MAX_CONTEXT_MANIFEST_BYTES:
            raise ContextError(
                f"context manifest exceeds the {MAX_CONTEXT_MANIFEST_BYTES:,}-byte limit"
            )

    def to_payload(self) -> dict[str, object]:
        """Return the stable JSON-compatible manifest payload."""

        return {"schema_version": self.schema_version, "files": list(self.files)}


def parse_context_manifest(raw: str | bytes) -> ContextManifest:
    """Parse one bounded, exact context-manifest version 1 document."""

    if isinstance(raw, bytes):
        if len(raw) > MAX_CONTEXT_MANIFEST_BYTES:
            raise ContextError(
                f"context manifest exceeds the {MAX_CONTEXT_MANIFEST_BYTES:,}-byte limit"
            )
        if b"\x00" in raw:
            raise ContextError("binary context manifests are not supported")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ContextError("context manifest is not valid UTF-8") from exc
    else:
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ContextError("context manifest text is not valid Unicode") from exc
        if len(encoded) > MAX_CONTEXT_MANIFEST_BYTES:
            raise ContextError(
                f"context manifest exceeds the {MAX_CONTEXT_MANIFEST_BYTES:,}-byte limit"
            )
        text = raw

    try:
        decoded: Any = json.loads(text, object_pairs_hook=_reject_duplicate_manifest_keys)
    except _DuplicateManifestKeyError as exc:
        raise ContextError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise ContextError(f"context manifest is not valid JSON: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ContextError("context manifest must be a JSON object")
    if set(decoded) != {"schema_version", "files"}:
        raise ContextError("context manifest fields do not match schema version 1")

    schema_version = decoded.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != CONTEXT_MANIFEST_SCHEMA_VERSION
    ):
        raise ContextError(
            f"unsupported context manifest schema: {schema_version!r}; "
            f"expected {CONTEXT_MANIFEST_SCHEMA_VERSION}"
        )

    files = decoded.get("files")
    if not isinstance(files, list) or not files:
        raise ContextError("context manifest files must be a non-empty array")
    if len(files) > DEFAULT_MAX_FILES:
        raise ContextError(f"context manifest may contain at most {DEFAULT_MAX_FILES} files")

    return ContextManifest(files=tuple(files))


def render_context_manifest(manifest: ContextManifest) -> str:
    """Render a context manifest deterministically."""

    return json.dumps(manifest.to_payload(), ensure_ascii=False, indent=2) + "\n"


def load_context_manifest(
    path: str | Path,
    *,
    root: str | Path = ".",
) -> ContextManifest:
    """Load a bounded context manifest that resolves within ``root``."""

    project_root = _resolve_root(root)
    resolved, relative = _resolve_contained_file(path, project_root, label="context manifest")
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise ContextError(f"cannot inspect context manifest {relative.as_posix()}: {exc}") from exc
    if size > MAX_CONTEXT_MANIFEST_BYTES:
        raise ContextError(
            f"context manifest {relative.as_posix()} is {size:,} bytes; "
            f"the limit is {MAX_CONTEXT_MANIFEST_BYTES:,}"
        )
    try:
        with resolved.open("rb") as handle:
            raw = handle.read(MAX_CONTEXT_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise ContextError(f"cannot read context manifest {relative.as_posix()}: {exc}") from exc
    if len(raw) > MAX_CONTEXT_MANIFEST_BYTES:
        raise ContextError(
            f"context manifest {relative.as_posix()} exceeds the "
            f"{MAX_CONTEXT_MANIFEST_BYTES:,}-byte limit while being read"
        )
    return parse_context_manifest(raw)


def load_context_files(
    paths: Iterable[str | Path],
    *,
    root: str | Path = ".",
    max_files: int = DEFAULT_MAX_FILES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> tuple[ContextFile, ...]:
    """Load explicitly named UTF-8 files that resolve within ``root``.

    Symlinks are resolved before the containment check. Duplicate resolved paths are
    included once, in first-seen order.
    """

    if max_files < 1:
        raise ContextError("max_files must be at least 1")
    if max_total_bytes < 1 or max_file_bytes < 1:
        raise ContextError("context byte limits must be positive")

    project_root = _resolve_root(root)
    requested = list(paths)
    if len(requested) > max_files:
        raise ContextError(f"at most {max_files} context files may be selected")

    loaded: list[ContextFile] = []
    seen: set[Path] = set()
    total_bytes = 0

    for raw_path in requested:
        resolved, relative = _resolve_contained_file(raw_path, project_root, label="context file")

        if resolved in seen:
            continue

        try:
            size = resolved.stat().st_size
        except OSError as exc:
            raise ContextError(f"cannot inspect context file {relative.as_posix()}: {exc}") from exc
        if size > max_file_bytes:
            raise ContextError(
                f"context file {relative.as_posix()} is {size:,} bytes; "
                f"the per-file limit is {max_file_bytes:,}"
            )
        if total_bytes + size > max_total_bytes:
            raise ContextError(f"selected context exceeds the {max_total_bytes:,}-byte total limit")

        try:
            with resolved.open("rb") as handle:
                raw = handle.read(max_file_bytes + 1)
        except OSError as exc:
            raise ContextError(f"cannot read context file {relative.as_posix()}: {exc}") from exc
        if len(raw) > max_file_bytes:
            raise ContextError(
                f"context file {relative.as_posix()} exceeds the "
                f"{max_file_bytes:,}-byte per-file limit while being read"
            )
        if total_bytes + len(raw) > max_total_bytes:
            raise ContextError(
                f"selected context exceeds the {max_total_bytes:,}-byte total limit "
                "while being read"
            )
        if b"\x00" in raw:
            raise ContextError(f"binary context is not supported: {relative.as_posix()}")
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ContextError(f"context file is not valid UTF-8: {relative.as_posix()}") from exc

        actual_size = len(raw)
        total_bytes += actual_size
        seen.add(resolved)
        loaded.append(
            ContextFile(path=relative.as_posix(), content=content, size_bytes=actual_size)
        )

    return tuple(loaded)


def load_stream_context(
    name: str,
    stream: BinaryIO,
    *,
    max_bytes: int,
) -> ContextFile:
    """Load one explicitly requested, bounded UTF-8 context item from a binary stream."""

    label = name.strip()
    if not label:
        raise ContextError("--stdin-name cannot be blank")
    if len(label) > MAX_STDIN_NAME_CHARS:
        raise ContextError(f"--stdin-name exceeds the {MAX_STDIN_NAME_CHARS}-character limit")
    if any(not character.isprintable() for character in label):
        raise ContextError("--stdin-name cannot contain control characters")
    if max_bytes < 1:
        raise ContextError("no context byte budget remains for stdin")

    try:
        raw = stream.read(max_bytes + 1)
    except OSError as exc:
        raise ContextError(f"cannot read stdin context: {exc}") from exc
    if len(raw) > max_bytes:
        raise ContextError(f"stdin context exceeds the remaining {max_bytes:,}-byte limit")
    if not raw:
        raise ContextError("stdin context is empty")
    if b"\x00" in raw:
        raise ContextError("binary stdin context is not supported")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ContextError("stdin context is not valid UTF-8") from exc
    return ContextFile(path=f"stdin:{label}", content=content, size_bytes=len(raw))


def _resolve_root(root: str | Path) -> Path:
    try:
        resolved = Path(root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContextError(f"cannot resolve project root {root!s}: {exc}") from exc
    if not resolved.is_dir():
        raise ContextError(f"project root is not a directory: {root!s}")
    return resolved


def _resolve_contained_file(
    path: str | Path,
    project_root: Path,
    *,
    label: str,
) -> tuple[Path, Path]:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContextError(f"cannot resolve {label} {path!s}: {exc}") from exc
    try:
        relative = resolved.relative_to(project_root)
    except ValueError as exc:
        raise ContextError(f"{label} escapes the project root: {path!s}") from exc
    if not resolved.is_file():
        raise ContextError(f"{label} is not a regular file: {path!s}")
    return resolved, relative


def _validate_manifest_path(path: str, *, index: int) -> None:
    label = f"context manifest file {index}"
    if not path:
        raise ContextError(f"{label} cannot be blank")
    if len(path) > MAX_CONTEXT_PATH_CHARS:
        raise ContextError(f"{label} exceeds the {MAX_CONTEXT_PATH_CHARS:,}-character limit")
    if path != path.strip():
        raise ContextError(f"{label} cannot have leading or trailing whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        raise ContextError(f"{label} cannot contain control characters")
    try:
        path.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContextError(f"{label} must be valid Unicode") from exc
    if "\\" in path:
        raise ContextError(f"{label} must use forward slashes")
    if path.startswith("/"):
        raise ContextError(f"{label} must be relative to --root")
    if any(character in '<>:"|?*' for character in path):
        raise ContextError(f"{label} contains a path character that is not portable")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ContextError(f"{label} cannot contain empty, dot, or parent segments")
    if any(part.endswith((" ", ".")) for part in parts):
        raise ContextError(f"{label} contains a segment with a non-portable ending")
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{value}" for value in range(1, 10)),
        *(f"LPT{value}" for value in range(1, 10)),
    }
    if any(part.split(".", 1)[0].upper() in reserved for part in parts):
        raise ContextError(f"{label} contains a reserved path segment")


def _reject_duplicate_manifest_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicateManifestKeyError(
                f"context manifest contains a duplicate JSON field: {key}"
            )
        decoded[key] = value
    return decoded
