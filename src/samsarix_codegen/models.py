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
MAX_ENDPOINT_CHARS = 2_048
MAX_PROVIDER_TIMEOUT_SECONDS = 300
MAX_PROVIDER_OUTPUT_TOKENS = 32_768
MAX_ESTIMATED_INPUT_TOKENS = 2_000_000


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
        if not isinstance(self.endpoint, str):
            raise ConfigurationError("the model endpoint must be text")
        if not isinstance(self.model, str):
            raise ConfigurationError("the model name must be text")
        endpoint = self.endpoint.strip().rstrip("/")
        model = self.model.strip()
        if not endpoint:
            raise ConfigurationError("the model endpoint cannot be empty")
        if len(endpoint) > MAX_ENDPOINT_CHARS:
            raise ConfigurationError(
                f"the model endpoint exceeds {MAX_ENDPOINT_CHARS:,} characters"
            )
        if any(ord(character) < 32 or ord(character) == 127 for character in endpoint):
            raise ConfigurationError("the model endpoint contains a control character")
        if not model:
            raise ConfigurationError("a model is required; use --model or SAMSARIX_MODEL")
        if len(model) > MAX_MODEL_CHARS:
            raise ConfigurationError(f"the model name exceeds {MAX_MODEL_CHARS} characters")
        if any(ord(character) < 32 or ord(character) == 127 for character in model):
            raise ConfigurationError("the model name contains a control character")
        try:
            endpoint.encode("utf-8")
            model.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ConfigurationError("the endpoint and model must be valid Unicode") from exc
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or not 1 <= self.timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS
        ):
            raise ConfigurationError(
                f"the timeout must be between 1 and {MAX_PROVIDER_TIMEOUT_SECONDS} seconds"
            )
        if (
            not isinstance(self.max_output_tokens, int)
            or isinstance(self.max_output_tokens, bool)
            or not 1 <= self.max_output_tokens <= MAX_PROVIDER_OUTPUT_TOKENS
        ):
            raise ConfigurationError(
                f"max output tokens must be between 1 and {MAX_PROVIDER_OUTPUT_TOKENS:,}"
            )

        try:
            parsed = urlsplit(endpoint)
        except ValueError as exc:
            raise ConfigurationError("the endpoint URL is invalid") from exc
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
    response_model: str | None = None


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
