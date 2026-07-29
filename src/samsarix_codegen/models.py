# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Validated value objects used by the prompt builder and provider client."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
from urllib.parse import SplitResult, urlsplit

from samsarix_codegen.errors import ConfigurationError

MAX_INSTRUCTION_CHARS = 20_000
MAX_LANGUAGE_CHARS = 64
MAX_MODEL_CHARS = 200


class Task(str, Enum):
    """Supported coding workflows."""

    GENERATE = "generate"
    EXPLAIN = "explain"
    DEBUG = "debug"
    REFACTOR = "refactor"
    TESTS = "tests"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class ContextFile:
    """One explicitly selected UTF-8 text file."""

    path: str
    content: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class PromptRequest:
    """A complete, provider-neutral coding request."""

    task: Task
    instruction: str
    files: tuple[ContextFile, ...] = ()
    language: str | None = None

    def __post_init__(self) -> None:
        instruction = self.instruction.strip()
        if not instruction:
            raise ConfigurationError("the instruction cannot be empty")
        if len(instruction) > MAX_INSTRUCTION_CHARS:
            raise ConfigurationError(
                f"the instruction exceeds the {MAX_INSTRUCTION_CHARS:,}-character limit"
            )
        object.__setattr__(self, "instruction", instruction)

        if self.language is not None:
            language = self.language.strip()
            if not language:
                raise ConfigurationError("--language cannot be blank")
            if len(language) > MAX_LANGUAGE_CHARS:
                raise ConfigurationError(
                    f"--language exceeds the {MAX_LANGUAGE_CHARS}-character limit"
                )
            object.__setattr__(self, "language", language)


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Bounded configuration for one OpenAI-compatible chat-completions call."""

    endpoint: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_output_tokens: int = 1_024

    def __post_init__(self) -> None:
        endpoint = self.endpoint.strip().rstrip("/")
        model = self.model.strip()
        if not endpoint:
            raise ConfigurationError("the model endpoint cannot be empty")
        if not model:
            raise ConfigurationError("a model is required; use --model or SAMSARIX_MODEL")
        if len(model) > MAX_MODEL_CHARS:
            raise ConfigurationError(f"the model name exceeds {MAX_MODEL_CHARS} characters")
        if not 1 <= self.timeout_seconds <= 300:
            raise ConfigurationError("the timeout must be between 1 and 300 seconds")
        if not 1 <= self.max_output_tokens <= 32_768:
            raise ConfigurationError("max output tokens must be between 1 and 32,768")

        parsed = urlsplit(endpoint)
        _validate_endpoint(parsed)

        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "model", model)

    @property
    def chat_completions_url(self) -> str:
        """Return the concrete endpoint without changing an explicit full URL."""

        suffix = "/chat/completions"
        if self.endpoint.endswith(suffix):
            return self.endpoint
        return f"{self.endpoint}{suffix}"


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Normalized text and optional usage from a provider response."""

    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


def _validate_endpoint(parsed: SplitResult) -> None:
    if parsed.scheme not in {"http", "https"}:
        raise ConfigurationError("the endpoint scheme must be http or https")
    if not parsed.hostname:
        raise ConfigurationError("the endpoint must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError("credentials are not allowed in the endpoint URL")
    if parsed.query or parsed.fragment:
        raise ConfigurationError("query strings and fragments are not allowed in the endpoint URL")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ConfigurationError("the endpoint contains an invalid port") from exc

    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise ConfigurationError(
            "unencrypted http endpoints are allowed only for localhost or loopback addresses"
        )


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
