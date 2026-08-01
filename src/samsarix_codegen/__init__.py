# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Public API for Samsarix Codegen."""

__version__ = "0.2.0"

from samsarix_codegen.artifact import (
    ContextRecord,
    ExecutionResult,
    ExecutionResultComparison,
    ExecutionResultSummary,
    RequestArtifact,
    RequestArtifactComparison,
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    parse_execution_result,
    parse_request_artifact,
    render_artifact_comparison,
    render_artifact_summary,
    render_execution_result_comparison,
    render_request_artifact,
    require_fingerprint,
)
from samsarix_codegen.context import load_context_files
from samsarix_codegen.models import (
    ChatResult,
    ContextFile,
    PromptRequest,
    ProviderConfig,
    Task,
)
from samsarix_codegen.prompt import build_messages, estimate_tokens, render_markdown
from samsarix_codegen.provider import OpenAIChatClient
from samsarix_codegen.provider_check import (
    ProviderCheckReport,
    check_provider,
    render_provider_check,
)
from samsarix_codegen.schema import ContractSchema, load_contract_schema, render_contract_schema

__all__ = [
    "ChatResult",
    "ContextRecord",
    "ContextFile",
    "ContractSchema",
    "ExecutionResult",
    "ExecutionResultComparison",
    "ExecutionResultSummary",
    "OpenAIChatClient",
    "PromptRequest",
    "ProviderConfig",
    "ProviderCheckReport",
    "RequestArtifact",
    "RequestArtifactComparison",
    "Task",
    "build_messages",
    "check_provider",
    "compare_execution_results",
    "compare_request_artifacts",
    "create_request_artifact",
    "estimate_tokens",
    "load_context_files",
    "load_contract_schema",
    "parse_execution_result",
    "parse_request_artifact",
    "render_artifact_comparison",
    "render_artifact_summary",
    "render_execution_result_comparison",
    "render_markdown",
    "render_provider_check",
    "render_request_artifact",
    "render_contract_schema",
    "require_fingerprint",
]
