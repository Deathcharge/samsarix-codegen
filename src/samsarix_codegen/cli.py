# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Command-line interface for inspectable, bounded coding requests."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import BinaryIO, cast

from samsarix_codegen import __version__
from samsarix_codegen.artifact import (
    MAX_ARTIFACT_BYTES,
    MAX_RESULT_BYTES,
    ExecutionResult,
    RequestArtifact,
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    parse_execution_result,
    parse_request_artifact,
    render_artifact_comparison,
    render_artifact_summary,
    render_execution_result,
    render_execution_result_comparison,
    render_request_artifact,
    require_fingerprint,
)
from samsarix_codegen.context import DEFAULT_MAX_FILES, load_context_files, load_stream_context
from samsarix_codegen.errors import ArtifactError, ConfigurationError, ContextError, SamsarixError
from samsarix_codegen.models import PromptRequest, ProviderConfig, Task
from samsarix_codegen.prompt import build_messages, render_markdown
from samsarix_codegen.provider import OpenAIChatClient
from samsarix_codegen.provider_check import (
    DEFAULT_PROVIDER_CHECK_OUTPUT_TOKENS,
    MAX_PROVIDER_CHECK_OUTPUT_TOKENS,
    PROVIDER_CHECK_MESSAGES,
    check_provider,
    render_provider_check,
)
from samsarix_codegen.schema import ContractSchema, render_contract_schema

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1"
DEFAULT_MAX_CONTEXT_BYTES = 200_000
MAX_ESTIMATED_INPUT_TOKENS = 2_000_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samsarix-codegen",
        description=(
            "Compile inspectable coding requests locally or send one bounded request to an "
            "OpenAI-compatible endpoint. Samsarix Codegen never edits files or runs generated code."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_command = subparsers.add_parser(
        "build", help="compile a prompt or deterministic request artifact without network access"
    )
    _add_request_arguments(build_command)
    build_command.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="markdown prompt or executable JSON request artifact (default: markdown)",
    )

    run_command = subparsers.add_parser(
        "run", help="compile and send one request to a chat-completions endpoint"
    )
    _add_request_arguments(run_command)
    _add_provider_arguments(run_command)

    provider_check_command = subparsers.add_parser(
        "provider-check",
        help="send one small, content-free request to verify provider compatibility",
    )
    _add_provider_arguments(provider_check_command, provider_check=True)

    schema_command = subparsers.add_parser(
        "schema", help="print a bundled versioned JSON Schema without network access"
    )
    schema_command.add_argument(
        "contract",
        choices=tuple(item.value for item in ContractSchema),
        help="contract schema to print",
    )

    inspect_command = subparsers.add_parser(
        "inspect", help="validate and summarize a stored request artifact without network access"
    )
    inspect_command.add_argument("artifact", metavar="PATH", help="artifact path, or - for stdin")
    inspect_command.add_argument(
        "--format",
        choices=("text", "json", "fingerprint", "markdown"),
        default="text",
        help="summary, fingerprint, or exact stored prompt format (default: text)",
    )

    compare_command = subparsers.add_parser(
        "compare", help="compare two validated request artifacts without showing prompt contents"
    )
    compare_command.add_argument("base", metavar="BASE", help="base artifact path, or - for stdin")
    compare_command.add_argument(
        "target", metavar="TARGET", help="target artifact path, or - for stdin"
    )
    compare_command.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="comparison output format (default: text)",
    )

    compare_results_command = subparsers.add_parser(
        "compare-results",
        help="compare two same-request execution results without showing response contents",
    )
    compare_results_command.add_argument(
        "base", metavar="BASE", help="base execution-result path, or - for stdin"
    )
    compare_results_command.add_argument(
        "target", metavar="TARGET", help="target execution-result path, or - for stdin"
    )
    compare_results_command.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="comparison output format (default: text)",
    )

    execute_command = subparsers.add_parser(
        "execute", help="send exactly the messages in a validated request artifact"
    )
    execute_command.add_argument("artifact", metavar="PATH", help="artifact path, or - for stdin")
    execute_command.add_argument(
        "--expect-fingerprint",
        help="fail unless the artifact matches this previously approved sha256 fingerprint",
    )
    _add_estimated_input_budget(execute_command)
    _add_provider_arguments(execute_command)

    return parser


def main(argv: Sequence[str] | None = None, *, stdin: BinaryIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_stream = stdin if stdin is not None else cast(BinaryIO, sys.stdin.buffer)
    try:
        if args.command in {"build", "run"}:
            return _handle_request_command(args, input_stream)
        if args.command == "provider-check":
            return _handle_provider_check(args)
        if args.command == "schema":
            _write_stdout(render_contract_schema(args.contract))
            return 0
        if args.command == "inspect":
            artifact = _read_artifact(args.artifact, input_stream)
            if args.format == "markdown":
                _write_stdout(render_markdown(artifact.messages))
            else:
                _write_stdout(render_artifact_summary(artifact, output_format=args.format))
            return 0
        if args.command == "compare":
            if args.base == "-" and args.target == "-":
                raise ArtifactError("BASE and TARGET cannot both read from stdin")
            base = _read_artifact(args.base, input_stream)
            target = _read_artifact(args.target, input_stream)
            comparison = compare_request_artifacts(base, target)
            _write_stdout(render_artifact_comparison(comparison, output_format=args.format))
            return 0
        if args.command == "compare-results":
            if args.base == "-" and args.target == "-":
                raise ArtifactError("BASE and TARGET cannot both read from stdin")
            base_result = _read_execution_result(args.base, input_stream)
            target_result = _read_execution_result(args.target, input_stream)
            result_comparison = compare_execution_results(base_result, target_result)
            _write_stdout(
                render_execution_result_comparison(result_comparison, output_format=args.format)
            )
            return 0
        if args.command == "execute":
            artifact = _read_artifact(args.artifact, input_stream)
            require_fingerprint(artifact, args.expect_fingerprint)
            _enforce_estimated_input_budget(artifact, args.max_estimated_input_tokens)
            return _execute_artifact(artifact, args)
        raise AssertionError(f"unhandled command: {args.command}")
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except SamsarixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


def _handle_request_command(args: argparse.Namespace, stdin: BinaryIO) -> int:
    request = _request_from_args(args, stdin)
    messages = build_messages(request)
    artifact = create_request_artifact(messages, request.files)
    _enforce_estimated_input_budget(artifact, args.max_estimated_input_tokens)

    if args.command == "build":
        if args.format == "json":
            output = render_request_artifact(artifact)
        else:
            output = render_markdown(messages)
        _write_stdout(output)
        return 0
    return _execute_artifact(artifact, args)


def _execute_artifact(artifact: RequestArtifact, args: argparse.Namespace) -> int:
    config = ProviderConfig(
        endpoint=args.endpoint,
        model=args.model or "",
        api_key=os.environ.get("SAMSARIX_API_KEY"),
        timeout_seconds=float(args.timeout),
        max_output_tokens=args.max_output_tokens,
    )
    print(
        f"Request {artifact.fingerprint}: ~{artifact.estimated_input_tokens:,} input tokens, "
        f"up to {config.max_output_tokens:,} output tokens, "
        f"{len(artifact.context)} context item(s).",
        file=sys.stderr,
    )
    result = OpenAIChatClient(config).complete(artifact.messages)
    if args.format == "json":
        _write_stdout(render_execution_result(artifact, result, model=config.model))
    else:
        _write_stdout(result.text.rstrip() + "\n")
    if result.total_tokens is not None:
        print(f"Provider usage: {result.total_tokens:,} total tokens.", file=sys.stderr)
    return 0


def _handle_provider_check(args: argparse.Namespace) -> int:
    config = ProviderConfig(
        endpoint=args.endpoint,
        model=args.model or "",
        api_key=os.environ.get("SAMSARIX_API_KEY"),
        timeout_seconds=float(args.timeout),
        max_output_tokens=args.max_output_tokens,
    )
    print(
        f"Provider check will send one request containing {len(PROVIDER_CHECK_MESSAGES)} fixed "
        f"messages, no source context, and at most {config.max_output_tokens:,} output tokens. "
        "Provider charges may apply.",
        file=sys.stderr,
    )
    report = check_provider(config)
    _write_stdout(render_provider_check(report, output_format=args.format))
    return 0


def _add_request_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("instruction", help="the coding request")
    parser.add_argument(
        "--task",
        choices=tuple(task.value for task in Task),
        default=Task.GENERATE.value,
        help="workflow guidance (default: generate)",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="PATH",
        help=f"UTF-8 context file within --root; repeat up to {DEFAULT_MAX_FILES} total inputs",
    )
    parser.add_argument(
        "--stdin-name",
        metavar="NAME",
        help="read one bounded UTF-8 context item from stdin and label it stdin:NAME",
    )
    parser.add_argument(
        "--root",
        default=".",
        metavar="DIR",
        help="project root used to contain and label context files (default: current directory)",
    )
    parser.add_argument("--language", help="optional language or ecosystem hint")
    parser.add_argument(
        "--max-context-bytes",
        type=_bounded_int(1, 5_000_000, "max context bytes"),
        default=DEFAULT_MAX_CONTEXT_BYTES,
        metavar="BYTES",
        help=f"total context cap from 1 to 5,000,000 bytes (default: {DEFAULT_MAX_CONTEXT_BYTES})",
    )
    _add_estimated_input_budget(parser)


def _add_estimated_input_budget(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-estimated-input-tokens",
        type=_bounded_int(1, MAX_ESTIMATED_INPUT_TOKENS, "max estimated input tokens"),
        default=os.environ.get("SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS"),
        metavar="TOKENS",
        help=(
            "fail before a network request when the transparent estimate exceeds this budget "
            "(default: SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS or no additional cap)"
        ),
    )


def _add_provider_arguments(
    parser: argparse.ArgumentParser,
    *,
    provider_check: bool = False,
) -> None:
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("SAMSARIX_API_BASE", DEFAULT_ENDPOINT),
        help=(f"API base URL (default: SAMSARIX_API_BASE or local endpoint {DEFAULT_ENDPOINT})"),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SAMSARIX_MODEL"),
        help="model name (default: SAMSARIX_MODEL; required)",
    )
    parser.add_argument(
        "--timeout",
        type=_bounded_int(1, 300, "timeout"),
        default=os.environ.get("SAMSARIX_TIMEOUT", "60"),
        metavar="SECONDS",
        help="network timeout from 1 to 300 seconds (default: 60)",
    )
    maximum_output_tokens = MAX_PROVIDER_CHECK_OUTPUT_TOKENS if provider_check else 32_768
    default_output_tokens = (
        str(DEFAULT_PROVIDER_CHECK_OUTPUT_TOKENS)
        if provider_check
        else os.environ.get("SAMSARIX_MAX_OUTPUT_TOKENS", "1024")
    )
    parser.add_argument(
        "--max-output-tokens",
        type=_bounded_int(1, maximum_output_tokens, "max output tokens"),
        default=default_output_tokens,
        metavar="TOKENS",
        help=(
            f"provider output cap from 1 to {maximum_output_tokens:,} tokens "
            f"(default: {default_output_tokens})"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="response output format (default: text)",
    )


def _request_from_args(args: argparse.Namespace, stdin: BinaryIO) -> PromptRequest:
    input_count = len(args.file) + (1 if args.stdin_name is not None else 0)
    if input_count > DEFAULT_MAX_FILES:
        raise ContextError(f"at most {DEFAULT_MAX_FILES} total context items may be selected")

    files = list(
        load_context_files(
            args.file,
            root=args.root,
            max_files=DEFAULT_MAX_FILES,
            max_total_bytes=args.max_context_bytes,
            max_file_bytes=args.max_context_bytes,
        )
    )
    if args.stdin_name is not None:
        used_bytes = sum(context_file.size_bytes for context_file in files)
        files.append(
            load_stream_context(
                args.stdin_name,
                stdin,
                max_bytes=args.max_context_bytes - used_bytes,
            )
        )

    return PromptRequest(
        task=Task(args.task),
        instruction=args.instruction,
        files=tuple(files),
        language=args.language,
    )


def _read_artifact(path: str, stdin: BinaryIO) -> RequestArtifact:
    raw = _read_bounded_input(
        path,
        stdin,
        maximum=MAX_ARTIFACT_BYTES,
        label="request artifact",
    )
    return parse_request_artifact(raw)


def _read_execution_result(path: str, stdin: BinaryIO) -> ExecutionResult:
    raw = _read_bounded_input(
        path,
        stdin,
        maximum=MAX_RESULT_BYTES,
        label="execution result",
    )
    return parse_execution_result(raw)


def _read_bounded_input(
    path: str,
    stdin: BinaryIO,
    *,
    maximum: int,
    label: str,
) -> bytes:
    if path == "-":
        try:
            return stdin.read(maximum + 1)
        except OSError as exc:
            raise ArtifactError(f"cannot read {label} from stdin: {exc}") from exc

    input_path = Path(path)
    try:
        if not input_path.is_file():
            raise ArtifactError(f"{label} is not a regular file: {path}")
        if input_path.stat().st_size > maximum:
            raise ArtifactError(f"{label} exceeds the {maximum:,}-byte safety limit")
        with input_path.open("rb") as handle:
            return handle.read(maximum + 1)
    except ArtifactError:
        raise
    except OSError as exc:
        raise ArtifactError(f"cannot read {label} {path}: {exc}") from exc


def _enforce_estimated_input_budget(
    artifact: RequestArtifact,
    maximum: int | None,
) -> None:
    if maximum is not None and artifact.estimated_input_tokens > maximum:
        raise ConfigurationError(
            f"estimated input is {artifact.estimated_input_tokens:,} tokens; "
            f"the configured limit is {maximum:,}"
        )


def _write_stdout(value: str) -> None:
    """Write redirected output as UTF-8 while preserving native terminal text handling."""

    output_buffer = getattr(sys.stdout, "buffer", None)
    if output_buffer is not None and not sys.stdout.isatty():
        output_buffer.write(value.encode("utf-8"))
        output_buffer.flush()
        return
    sys.stdout.write(value)


def _bounded_int(minimum: int, maximum: int, label: str) -> Callable[[str], int]:
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(f"{label} must be between {minimum:,} and {maximum:,}")
        return parsed

    return parse
