# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Cost-bounded conformance check for the supported provider wire contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from samsarix_codegen.errors import ConfigurationError
from samsarix_codegen.models import ChatResult, ProviderConfig
from samsarix_codegen.provider import OpenAIChatClient

PROVIDER_CHECK_SCHEMA_VERSION = 1
DEFAULT_PROVIDER_CHECK_OUTPUT_TOKENS = 64
MAX_PROVIDER_CHECK_OUTPUT_TOKENS = 256
PROVIDER_CHECK_MESSAGES = (
    {
        "role": "system",
        "content": (
            "This is a provider compatibility check. Return a short plain-text acknowledgement."
        ),
    },
    {"role": "user", "content": "Reply with SAMSARIX_OK."},
)


@dataclass(frozen=True, slots=True)
class ProviderCheckReport:
    """Content-safe evidence that one provider request satisfied the supported contract."""

    model: str
    max_output_tokens: int
    response_chars: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    schema_version: ClassVar[int] = PROVIDER_CHECK_SCHEMA_VERSION
    status: ClassVar[Literal["passed"]] = "passed"
    transport: ClassVar[Literal["openai_chat_completions"]] = "openai_chat_completions"

    def __post_init__(self) -> None:
        model = self.model.strip()
        if not model:
            raise ConfigurationError("the provider check model cannot be empty")
        if len(model) > 200:
            raise ConfigurationError("the provider check model exceeds 200 characters")
        if (
            not isinstance(self.max_output_tokens, int)
            or isinstance(self.max_output_tokens, bool)
            or not 1 <= self.max_output_tokens <= MAX_PROVIDER_CHECK_OUTPUT_TOKENS
        ):
            raise ConfigurationError(
                "provider check output tokens must be between 1 and "
                f"{MAX_PROVIDER_CHECK_OUTPUT_TOKENS}"
            )
        if (
            not isinstance(self.response_chars, int)
            or isinstance(self.response_chars, bool)
            or self.response_chars < 1
        ):
            raise ConfigurationError("provider check response characters must be positive")
        for label, value in (
            ("prompt tokens", self.prompt_tokens),
            ("completion tokens", self.completion_tokens),
            ("total tokens", self.total_tokens),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ConfigurationError(f"provider check {label} must be a non-negative integer")
        object.__setattr__(self, "model", model)

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned, endpoint- and content-free report envelope."""

        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "transport": self.transport,
            "model": self.model,
            "request": {
                "message_count": len(PROVIDER_CHECK_MESSAGES),
                "source_context_items": 0,
                "max_output_tokens": self.max_output_tokens,
                "stream": False,
            },
            "response": {
                "text_received": True,
                "text_chars": self.response_chars,
            },
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
        }


def check_provider(config: ProviderConfig) -> ProviderCheckReport:
    """Make one small request that exercises the same contract as ``run`` and ``execute``."""

    if config.max_output_tokens > MAX_PROVIDER_CHECK_OUTPUT_TOKENS:
        raise ConfigurationError(
            f"provider check output tokens must not exceed {MAX_PROVIDER_CHECK_OUTPUT_TOKENS}"
        )

    result = OpenAIChatClient(config).complete(PROVIDER_CHECK_MESSAGES)
    return _report_from_result(config, result)


def render_provider_check(
    report: ProviderCheckReport,
    *,
    output_format: Literal["text", "json"] = "text",
) -> str:
    """Render provider-check evidence without endpoint, credentials, or response content."""

    if output_format == "json":
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if output_format != "text":
        raise ConfigurationError("provider check format must be text or json")

    usage = _render_usage(report)
    return (
        "Provider check passed.\n"
        "Transport: OpenAI-compatible Chat Completions\n"
        f"Model: {report.model}\n"
        f"Request: {len(PROVIDER_CHECK_MESSAGES)} fixed messages, no source context, "
        f"non-streaming, up to {report.max_output_tokens:,} output tokens.\n"
        f"Response: non-empty text received ({report.response_chars:,} characters).\n"
        f"Usage: {usage}\n"
    )


def _report_from_result(config: ProviderConfig, result: ChatResult) -> ProviderCheckReport:
    return ProviderCheckReport(
        model=config.model,
        max_output_tokens=config.max_output_tokens,
        response_chars=len(result.text),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
    )


def _render_usage(report: ProviderCheckReport) -> str:
    if report.total_tokens is None:
        return "not reported by provider."
    return f"{report.total_tokens:,} total tokens reported by provider."
