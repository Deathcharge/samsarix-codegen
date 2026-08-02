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
    MAX_RESULT_POLICY_TOKENS,
    ExecutionResult,
    ExecutionResultPolicy,
    RequestArtifact,
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    enforce_execution_result_policy,
    inspect_execution_result,
    parse_execution_result,
    parse_request_artifact,
    render_artifact_comparison,
    render_artifact_summary,
    render_execution_result,
    render_execution_result_comparison,
    render_execution_result_inspection,
    render_execution_result_verification,
    render_request_artifact,
    require_fingerprint,
    verify_execution_result,
)
from samsarix_codegen.context import (
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_MANIFESTS,
    load_context_files,
    load_context_manifest,
    load_stream_context,
)
from samsarix_codegen.errors import ArtifactError, ConfigurationError, ContextError, SamsarixError
from samsarix_codegen.execution_evidence import (
    render_execution_evidence_verification,
    verify_execution_evidence,
)
from samsarix_codegen.execution_plan import (
    ExecutionPlan,
    create_execution_plan,
    load_execution_plan,
    provider_config_from_execution_plan,
    render_execution_plan,
    render_execution_plan_verification,
    verify_execution_plan,
)
from samsarix_codegen.models import (
    MAX_ESTIMATED_INPUT_TOKENS,
    MAX_PROVIDER_OUTPUT_TOKENS,
    MAX_PROVIDER_TIMEOUT_SECONDS,
    PromptRequest,
    ProviderConfig,
    Task,
)
from samsarix_codegen.prompt import build_messages, render_markdown
from samsarix_codegen.provider import OpenAIChatClient
from samsarix_codegen.provider_check import (
    DEFAULT_PROVIDER_CHECK_OUTPUT_TOKENS,
    MAX_PROVIDER_CHECK_OUTPUT_TOKENS,
    PROVIDER_CHECK_MESSAGES,
    check_provider,
    render_provider_check,
)
from samsarix_codegen.result_policy import (
    fingerprint_execution_result_policy,
    load_execution_result_policy,
    require_execution_result_policy_fingerprint,
)
from samsarix_codegen.schema import ContractSchema, render_contract_schema
from samsarix_codegen.self_check import render_self_check, run_self_check

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1"
DEFAULT_MAX_CONTEXT_BYTES = 200_000


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

    self_check_command = subparsers.add_parser(
        "self-check",
        help="verify the installed package and offline evidence path without network access",
    )
    self_check_command.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="self-check evidence output format (default: text)",
    )

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

    create_plan_command = subparsers.add_parser(
        "create-plan",
        help="bind a validated request to credential-free provider settings without network access",
    )
    create_plan_command.add_argument(
        "artifact", metavar="PATH", help="request-artifact path, or - for stdin"
    )
    create_plan_command.add_argument(
        "--expect-fingerprint",
        help="fail unless the artifact matches this previously approved sha256 fingerprint",
    )
    create_plan_command.add_argument(
        "--max-estimated-input-tokens",
        type=_bounded_int(1, MAX_ESTIMATED_INPUT_TOKENS, "max estimated input tokens"),
        metavar="TOKENS",
        help="plan input ceiling (default: the supplied artifact's exact estimate)",
    )
    _add_provider_arguments(create_plan_command, include_format=False)

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

    inspect_result_command = subparsers.add_parser(
        "inspect-result",
        help="validate and summarize one execution result without showing its response",
    )
    inspect_result_command.add_argument(
        "result", metavar="PATH", help="execution-result path, or - for stdin"
    )
    inspect_result_command.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="content-omitting inspection output format (default: text)",
    )
    _add_result_policy_arguments(inspect_result_command)

    verify_result_command = subparsers.add_parser(
        "verify-result",
        help="verify one result against a request artifact without showing their contents",
    )
    verify_result_command.add_argument(
        "artifact", metavar="REQUEST", help="request-artifact path, or - for stdin"
    )
    verify_result_command.add_argument(
        "result", metavar="RESULT", help="execution-result path, or - for stdin"
    )
    verify_result_command.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="content-omitting verification output format (default: text)",
    )
    _add_result_policy_arguments(verify_result_command)

    verify_plan_command = subparsers.add_parser(
        "verify-plan",
        help="verify an execution plan against a request without showing prompt contents",
    )
    verify_plan_command.add_argument(
        "artifact", metavar="REQUEST", help="request-artifact path, or - for stdin"
    )
    verify_plan_command.add_argument(
        "plan", metavar="PLAN", help="explicit execution-plan file path"
    )
    verify_plan_command.add_argument(
        "--expect-plan-fingerprint",
        help="fail unless the plan matches this previously approved sha256 fingerprint",
    )
    verify_plan_command.add_argument(
        "--format",
        choices=("text", "json", "fingerprint"),
        default="text",
        help="verification record or plan fingerprint (default: text)",
    )

    verify_execution_command = subparsers.add_parser(
        "verify-execution",
        help="verify a request, reviewed plan, and result as one offline evidence chain",
    )
    verify_execution_command.add_argument(
        "artifact", metavar="REQUEST", help="request-artifact path, or - for stdin"
    )
    verify_execution_command.add_argument(
        "plan", metavar="PLAN", help="explicit execution-plan file path"
    )
    verify_execution_command.add_argument(
        "result", metavar="RESULT", help="execution-result path, or - for stdin"
    )
    verify_execution_command.add_argument(
        "--expect-plan-fingerprint",
        help="fail unless the plan matches this previously approved sha256 fingerprint",
    )
    verify_execution_command.add_argument(
        "--policy",
        metavar="PATH",
        help="enforce and record one explicit versioned result-policy file",
    )
    verify_execution_command.add_argument(
        "--expect-policy-fingerprint",
        help="fail unless the result policy matches this previously approved sha256 fingerprint",
    )
    verify_execution_command.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="content-omitting evidence output format (default: text)",
    )

    fingerprint_policy_command = subparsers.add_parser(
        "fingerprint-policy",
        help="validate and fingerprint one explicit result-policy file without network access",
    )
    fingerprint_policy_command.add_argument(
        "policy", metavar="POLICY", help="explicit execution-result-policy file path"
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
    execute_command.add_argument(
        "--plan",
        metavar="PATH",
        help="use one explicit versioned execution plan; provider overrides are refused",
    )
    execute_command.add_argument(
        "--expect-plan-fingerprint",
        help="fail unless --plan matches this previously approved sha256 fingerprint",
    )
    execute_command.add_argument(
        "--policy",
        metavar="PATH",
        help="enforce one explicit versioned result-policy before emitting the response",
    )
    execute_command.add_argument(
        "--expect-policy-fingerprint",
        help="fail unless --policy matches this previously approved sha256 fingerprint",
    )
    _add_estimated_input_budget(execute_command, defer_default=True)
    _add_provider_arguments(execute_command, defer_defaults=True)

    return parser


def main(argv: Sequence[str] | None = None, *, stdin: BinaryIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_stream = stdin if stdin is not None else cast(BinaryIO, sys.stdin.buffer)
    try:
        if args.command == "self-check":
            _write_stdout(render_self_check(run_self_check(), output_format=args.format))
            return 0
        if args.command in {"build", "run"}:
            return _handle_request_command(args, input_stream)
        if args.command == "provider-check":
            return _handle_provider_check(args)
        if args.command == "create-plan":
            artifact = _read_artifact(args.artifact, input_stream)
            require_fingerprint(artifact, args.expect_fingerprint)
            config = _provider_config_from_args(args, include_api_key=False)
            plan = create_execution_plan(
                artifact,
                config,
                max_estimated_input_tokens=args.max_estimated_input_tokens,
            )
            _write_stdout(render_execution_plan(plan))
            return 0
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
        if args.command == "inspect-result":
            result = _read_execution_result(args.result, input_stream)
            _enforce_result_policy(result, args)
            inspection = inspect_execution_result(result)
            _write_stdout(render_execution_result_inspection(inspection, output_format=args.format))
            return 0
        if args.command == "verify-result":
            if args.artifact == "-" and args.result == "-":
                raise ArtifactError("REQUEST and RESULT cannot both read from stdin")
            artifact = _read_artifact(args.artifact, input_stream)
            result = _read_execution_result(args.result, input_stream)
            verification = verify_execution_result(artifact, result)
            _enforce_result_policy(result, args)
            _write_stdout(
                render_execution_result_verification(verification, output_format=args.format)
            )
            return 0
        if args.command == "verify-plan":
            plan = _load_execution_plan(args.plan)
            artifact = _read_artifact(args.artifact, input_stream)
            plan_verification = verify_execution_plan(
                artifact,
                plan,
                expected_plan_fingerprint=args.expect_plan_fingerprint,
            )
            _write_stdout(
                render_execution_plan_verification(plan_verification, output_format=args.format)
            )
            return 0
        if args.command == "verify-execution":
            if args.artifact == "-" and args.result == "-":
                raise ArtifactError("REQUEST and RESULT cannot both read from stdin")
            plan = _load_execution_plan(args.plan)
            artifact = _read_artifact(args.artifact, input_stream)
            result = _read_execution_result(args.result, input_stream)
            policy = _load_explicit_result_policy(
                args.policy,
                args.expect_policy_fingerprint,
            )
            evidence = verify_execution_evidence(
                artifact,
                plan,
                result,
                expected_plan_fingerprint=args.expect_plan_fingerprint,
                result_policy=policy,
                expected_policy_fingerprint=args.expect_policy_fingerprint,
            )
            _write_stdout(
                render_execution_evidence_verification(evidence, output_format=args.format)
            )
            return 0
        if args.command == "fingerprint-policy":
            policy = load_execution_result_policy(args.policy)
            _write_stdout(fingerprint_execution_result_policy(policy) + "\n")
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
            result_policy = _load_explicit_result_policy(
                args.policy,
                args.expect_policy_fingerprint,
            )
            plan_fingerprint: str | None = None
            if args.plan is not None:
                _reject_execution_plan_overrides(args)
                plan = _load_execution_plan(args.plan)
                plan_verification = verify_execution_plan(
                    artifact,
                    plan,
                    expected_plan_fingerprint=args.expect_plan_fingerprint,
                )
                print(
                    f"Execution plan {plan_verification.plan.fingerprint} matches the request.",
                    file=sys.stderr,
                )
                config = provider_config_from_execution_plan(
                    plan,
                    api_key=os.environ.get("SAMSARIX_API_KEY"),
                )
                plan_fingerprint = plan.fingerprint
            else:
                if args.expect_plan_fingerprint is not None:
                    raise ConfigurationError("--expect-plan-fingerprint requires --plan")
                require_fingerprint(artifact, args.expect_fingerprint)
                _enforce_estimated_input_budget(
                    artifact,
                    _resolve_estimated_input_budget(args.max_estimated_input_tokens),
                )
                config = _provider_config_from_args(args)
            return _execute_artifact(
                artifact,
                config,
                output_format=args.format,
                plan_fingerprint=plan_fingerprint,
                result_policy=result_policy,
            )
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
    return _execute_artifact(
        artifact,
        _provider_config_from_args(args),
        output_format=args.format,
    )


def _execute_artifact(
    artifact: RequestArtifact,
    config: ProviderConfig,
    *,
    output_format: str,
    plan_fingerprint: str | None = None,
    result_policy: ExecutionResultPolicy | None = None,
) -> int:
    print(
        f"Request {artifact.fingerprint}: ~{artifact.estimated_input_tokens:,} input tokens, "
        f"up to {config.max_output_tokens:,} output tokens, "
        f"{len(artifact.context)} context item(s).",
        file=sys.stderr,
    )
    result = OpenAIChatClient(config).complete(artifact.messages)
    rendered_result: str | None = None
    if output_format == "json" or result_policy is not None:
        rendered_result = render_execution_result(
            artifact,
            result,
            model=config.model,
            plan_fingerprint=plan_fingerprint,
        )
    if result_policy is not None:
        if rendered_result is None:
            raise AssertionError("policy enforcement requires a rendered execution result")
        execution_result = parse_execution_result(rendered_result)
        enforce_execution_result_policy(execution_result, result_policy)
    if output_format == "json":
        if rendered_result is None:
            raise AssertionError("JSON output requires a rendered execution result")
        _write_stdout(rendered_result)
    else:
        _write_stdout(result.text.rstrip() + "\n")
    if result.total_tokens is not None:
        print(f"Provider usage: {result.total_tokens:,} total tokens.", file=sys.stderr)
    return 0


def _handle_provider_check(args: argparse.Namespace) -> int:
    config = _provider_config_from_args(args)
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
        "--context-manifest",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "versioned JSON file allowlist within --root; repeat to compose explicit context sets"
        ),
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


def _add_estimated_input_budget(
    parser: argparse.ArgumentParser,
    *,
    defer_default: bool = False,
) -> None:
    default = None if defer_default else os.environ.get("SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS")
    parser.add_argument(
        "--max-estimated-input-tokens",
        type=_bounded_int(1, MAX_ESTIMATED_INPUT_TOKENS, "max estimated input tokens"),
        default=default,
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
    defer_defaults: bool = False,
    include_format: bool = True,
) -> None:
    endpoint_default = (
        None if defer_defaults else os.environ.get("SAMSARIX_API_BASE", DEFAULT_ENDPOINT)
    )
    parser.add_argument(
        "--endpoint",
        default=endpoint_default,
        help=(f"API base URL (default: SAMSARIX_API_BASE or local endpoint {DEFAULT_ENDPOINT})"),
    )
    model_default = None if defer_defaults else os.environ.get("SAMSARIX_MODEL")
    parser.add_argument(
        "--model",
        default=model_default,
        help="model name (default: SAMSARIX_MODEL; required)",
    )
    timeout_default = None if defer_defaults else os.environ.get("SAMSARIX_TIMEOUT", "60")
    parser.add_argument(
        "--timeout",
        type=_bounded_int(1, MAX_PROVIDER_TIMEOUT_SECONDS, "timeout"),
        default=timeout_default,
        metavar="SECONDS",
        help=(f"network timeout from 1 to {MAX_PROVIDER_TIMEOUT_SECONDS} seconds (default: 60)"),
    )
    maximum_output_tokens = (
        MAX_PROVIDER_CHECK_OUTPUT_TOKENS if provider_check else MAX_PROVIDER_OUTPUT_TOKENS
    )
    default_output_tokens = (
        str(DEFAULT_PROVIDER_CHECK_OUTPUT_TOKENS)
        if provider_check
        else (None if defer_defaults else os.environ.get("SAMSARIX_MAX_OUTPUT_TOKENS", "1024"))
    )
    parser.add_argument(
        "--max-output-tokens",
        type=_bounded_int(1, maximum_output_tokens, "max output tokens"),
        default=default_output_tokens,
        metavar="TOKENS",
        help=(
            f"provider output cap from 1 to {maximum_output_tokens:,} tokens "
            f"(default: {'environment or 1,024' if defer_defaults else default_output_tokens})"
        ),
    )
    if include_format:
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="response output format (default: text)",
        )


def _add_result_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--policy",
        metavar="PATH",
        help="load deterministic result limits from a versioned JSON policy file",
    )
    parser.add_argument(
        "--expect-model",
        help="fail unless the stored result has this exact model label",
    )
    parser.add_argument(
        "--max-response-bytes",
        type=_bounded_int(1, MAX_RESULT_BYTES, "maximum response bytes"),
        metavar="BYTES",
        help="fail when the UTF-8 response exceeds this byte count",
    )
    parser.add_argument(
        "--max-prompt-tokens",
        type=_bounded_int(0, MAX_RESULT_POLICY_TOKENS, "maximum prompt tokens"),
        metavar="TOKENS",
        help="fail when reported prompt usage exceeds this value or is missing",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=_bounded_int(0, MAX_RESULT_POLICY_TOKENS, "maximum completion tokens"),
        metavar="TOKENS",
        help="fail when reported completion usage exceeds this value or is missing",
    )
    parser.add_argument(
        "--max-total-tokens",
        type=_bounded_int(0, MAX_RESULT_POLICY_TOKENS, "maximum total tokens"),
        metavar="TOKENS",
        help="fail when reported total usage exceeds this value or is missing",
    )


def _enforce_result_policy(result: ExecutionResult, args: argparse.Namespace) -> None:
    inline_values = (
        args.expect_model,
        args.max_response_bytes,
        args.max_prompt_tokens,
        args.max_completion_tokens,
        args.max_total_tokens,
    )
    if args.policy is not None:
        policy = _load_result_policy_file(args.policy, inline_values=inline_values)
    else:
        policy = ExecutionResultPolicy(
            expected_model=args.expect_model,
            max_response_bytes=args.max_response_bytes,
            max_prompt_tokens=args.max_prompt_tokens,
            max_completion_tokens=args.max_completion_tokens,
            max_total_tokens=args.max_total_tokens,
        )
    enforce_execution_result_policy(result, policy)


def _load_explicit_result_policy(
    policy_path: str | None,
    expected_fingerprint: str | None,
) -> ExecutionResultPolicy | None:
    if policy_path is None:
        if expected_fingerprint is not None:
            raise ConfigurationError("--expect-policy-fingerprint requires --policy")
        return None
    policy = _load_result_policy_file(policy_path)
    if expected_fingerprint is not None:
        require_execution_result_policy_fingerprint(policy, expected_fingerprint)
    return policy


def _load_result_policy_file(
    policy_path: str,
    *,
    inline_values: Sequence[object] = (),
) -> ExecutionResultPolicy:
    if policy_path == "-":
        raise ConfigurationError("--policy requires a file path and cannot read from stdin")
    if any(value is not None for value in inline_values):
        raise ConfigurationError("--policy cannot be combined with inline result-policy flags")
    return load_execution_result_policy(policy_path)


def _provider_config_from_args(
    args: argparse.Namespace,
    *,
    include_api_key: bool = True,
) -> ProviderConfig:
    endpoint = (
        args.endpoint
        if args.endpoint is not None
        else os.environ.get("SAMSARIX_API_BASE", DEFAULT_ENDPOINT)
    )
    model = args.model if args.model is not None else os.environ.get("SAMSARIX_MODEL", "")
    timeout = (
        args.timeout
        if args.timeout is not None
        else _environment_bounded_int(
            "SAMSARIX_TIMEOUT",
            default=60,
            minimum=1,
            maximum=MAX_PROVIDER_TIMEOUT_SECONDS,
            label="timeout",
        )
    )
    max_output_tokens = (
        args.max_output_tokens
        if args.max_output_tokens is not None
        else _environment_bounded_int(
            "SAMSARIX_MAX_OUTPUT_TOKENS",
            default=1_024,
            minimum=1,
            maximum=MAX_PROVIDER_OUTPUT_TOKENS,
            label="max output tokens",
        )
    )
    return ProviderConfig(
        endpoint=endpoint,
        model=model,
        api_key=os.environ.get("SAMSARIX_API_KEY") if include_api_key else None,
        timeout_seconds=timeout,
        max_output_tokens=max_output_tokens,
    )


def _resolve_estimated_input_budget(value: int | None) -> int | None:
    if value is not None:
        return value
    raw = os.environ.get("SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS")
    if raw is None:
        return None
    return _parse_configuration_int(
        raw,
        minimum=1,
        maximum=MAX_ESTIMATED_INPUT_TOKENS,
        label="max estimated input tokens",
        source="SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS",
    )


def _reject_execution_plan_overrides(args: argparse.Namespace) -> None:
    if args.plan == "-":
        raise ConfigurationError("--plan requires a file path and cannot read from stdin")
    overrides = (
        args.expect_fingerprint,
        args.max_estimated_input_tokens,
        args.endpoint,
        args.model,
        args.timeout,
        args.max_output_tokens,
    )
    if any(value is not None for value in overrides):
        raise ConfigurationError(
            "--plan cannot be combined with request, provider, or budget override flags"
        )


def _load_execution_plan(path: str) -> ExecutionPlan:
    if path == "-":
        raise ConfigurationError("execution plans require a file path and cannot read from stdin")
    return load_execution_plan(path)


def _environment_bounded_int(
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
    label: str,
) -> int:
    return _parse_configuration_int(
        os.environ.get(name, str(default)),
        minimum=minimum,
        maximum=maximum,
        label=label,
        source=name,
    )


def _parse_configuration_int(
    value: str,
    *,
    minimum: int,
    maximum: int,
    label: str,
    source: str,
) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{source} {label} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigurationError(f"{source} {label} must be between {minimum:,} and {maximum:,}")
    return parsed


def _request_from_args(args: argparse.Namespace, stdin: BinaryIO) -> PromptRequest:
    if len(args.context_manifest) > DEFAULT_MAX_MANIFESTS:
        raise ContextError(f"at most {DEFAULT_MAX_MANIFESTS} context manifests may be selected")

    selected_paths = list(args.file)
    input_count = len(selected_paths) + (1 if args.stdin_name is not None else 0)
    if input_count > DEFAULT_MAX_FILES:
        raise ContextError(f"at most {DEFAULT_MAX_FILES} total context items may be selected")
    for manifest_path in args.context_manifest:
        manifest = load_context_manifest(manifest_path, root=args.root)
        selected_paths.extend(manifest.files)
        input_count += len(manifest.files)
        if input_count > DEFAULT_MAX_FILES:
            raise ContextError(f"at most {DEFAULT_MAX_FILES} total context items may be selected")

    files = list(
        load_context_files(
            selected_paths,
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
