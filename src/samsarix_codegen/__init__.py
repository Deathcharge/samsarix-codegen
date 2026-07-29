# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Public API for Samsarix Codegen."""

__version__ = "0.1.0"

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
    "ContextFile",
    "OpenAIChatClient",
    "PromptRequest",
    "ProviderConfig",
    "Task",
    "build_messages",
    "estimate_tokens",
    "load_context_files",
    "render_markdown",
]
