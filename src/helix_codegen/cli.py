"""Command-line interface for building and running bounded coding prompts."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence

from helix_codegen import __version__
from helix_codegen.context import DEFAULT_MAX_FILES, load_context_files
from helix_codegen.errors import HelixError
from helix_codegen.models import PromptRequest, ProviderConfig, Task
from helix_codegen.prompt import build_messages, estimate_tokens, render_json, render_markdown
from helix_codegen.provider import OpenAIChatClient

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1"
DEFAULT_MAX_CONTEXT_BYTES = 200_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="helix-codegen",
        description=(
            "Build inspectable coding prompts locally or send one bounded request to an "
            "OpenAI-compatible endpoint. Helix Codegen never edits files or runs generated code."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_command = subparsers.add_parser(
        "build", help="build a prompt locally without making a network request"
    )
    _add_request_arguments(build_command)
    build_command.add_argument(
        "--format", choices=("markdown", "json"), default="markdown", help="output format"
    )

    run_command = subparsers.add_parser(
        "run", help="send one request to an OpenAI-compatible chat-completions endpoint"
    )
    _add_request_arguments(run_command)
    run_command.add_argument(
        "--endpoint",
        default=os.environ.get("HELIX_API_BASE", DEFAULT_ENDPOINT),
        help=(f"API base URL (default: HELIX_API_BASE or local Ollama at {DEFAULT_ENDPOINT})"),
    )
    run_command.add_argument(
        "--model",
        default=os.environ.get("HELIX_MODEL"),
        help="model name (default: HELIX_MODEL; required)",
    )
    run_command.add_argument(
        "--timeout",
        type=_bounded_int(1, 300, "timeout"),
        default=os.environ.get("HELIX_TIMEOUT", "60"),
        metavar="SECONDS",
        help="network timeout from 1 to 300 seconds (default: 60)",
    )
    run_command.add_argument(
        "--max-output-tokens",
        type=_bounded_int(1, 32_768, "max output tokens"),
        default=os.environ.get("HELIX_MAX_OUTPUT_TOKENS", "1024"),
        metavar="TOKENS",
        help="provider output cap from 1 to 32,768 tokens (default: 1024)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        request, context_bytes = _request_from_args(args)
        messages = build_messages(request)

        if args.command == "build":
            if args.format == "json":
                output = render_json(
                    messages,
                    context_bytes=context_bytes,
                    context_files=len(request.files),
                )
            else:
                output = render_markdown(messages)
            sys.stdout.write(output)
            return 0

        config = ProviderConfig(
            endpoint=args.endpoint,
            model=args.model or "",
            api_key=os.environ.get("HELIX_API_KEY"),
            timeout_seconds=float(args.timeout),
            max_output_tokens=args.max_output_tokens,
        )
        estimate = estimate_tokens(messages)
        print(
            f"Request estimate: ~{estimate:,} input tokens, "
            f"up to {config.max_output_tokens:,} output tokens, "
            f"{len(request.files)} context file(s).",
            file=sys.stderr,
        )
        result = OpenAIChatClient(config).complete(messages)
        sys.stdout.write(result.text.rstrip() + "\n")
        if result.total_tokens is not None:
            print(f"Provider usage: {result.total_tokens:,} total tokens.", file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except HelixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


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
        help=f"UTF-8 context file within --root; repeat up to {DEFAULT_MAX_FILES} times",
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


def _request_from_args(args: argparse.Namespace) -> tuple[PromptRequest, int]:
    files = load_context_files(
        args.file,
        root=args.root,
        max_files=DEFAULT_MAX_FILES,
        max_total_bytes=args.max_context_bytes,
        max_file_bytes=args.max_context_bytes,
    )
    request = PromptRequest(
        task=Task(args.task),
        instruction=args.instruction,
        files=files,
        language=args.language,
    )
    return request, sum(context_file.size_bytes for context_file in files)


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
