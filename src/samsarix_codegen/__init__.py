# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Public API for Samsarix Codegen."""

__version__ = "0.2.0"

from samsarix_codegen.artifact import (
    ContextRecord,
    RequestArtifact,
    create_request_artifact,
    parse_request_artifact,
    render_artifact_summary,
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

__all__ = [
    "ChatResult",
    "ContextRecord",
    "ContextFile",
    "OpenAIChatClient",
    "PromptRequest",
    "ProviderConfig",
    "RequestArtifact",
    "Task",
    "build_messages",
    "create_request_artifact",
    "estimate_tokens",
    "load_context_files",
    "parse_request_artifact",
    "render_artifact_summary",
    "render_markdown",
    "render_request_artifact",
    "require_fingerprint",
]
