"""Safe, explicit loading of source context from one project root."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from helix_codegen.errors import ContextError
from helix_codegen.models import ContextFile

DEFAULT_MAX_FILES = 20
DEFAULT_MAX_TOTAL_BYTES = 200_000
DEFAULT_MAX_FILE_BYTES = 100_000


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
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = project_root / candidate

        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ContextError(f"cannot resolve context file {raw_path!s}: {exc}") from exc

        try:
            relative = resolved.relative_to(project_root)
        except ValueError as exc:
            raise ContextError(f"context file escapes the project root: {raw_path!s}") from exc

        if resolved in seen:
            continue
        if not resolved.is_file():
            raise ContextError(f"context path is not a regular file: {raw_path!s}")

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


def _resolve_root(root: str | Path) -> Path:
    try:
        resolved = Path(root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContextError(f"cannot resolve project root {root!s}: {exc}") from exc
    if not resolved.is_dir():
        raise ContextError(f"project root is not a directory: {root!s}")
    return resolved
