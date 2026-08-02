# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import pytest

from samsarix_codegen.errors import ConfigurationError
from samsarix_codegen.models import MAX_ENDPOINT_CHARS, PromptRequest, ProviderConfig, Task


def test_prompt_request_normalizes_instruction_and_language() -> None:
    request = PromptRequest(Task.EXPLAIN, "  explain this  ", language=" Python ")

    assert request.instruction == "explain this"
    assert request.language == "Python"


@pytest.mark.parametrize("instruction", ["", "   "])
def test_prompt_request_rejects_blank_instruction(instruction: str) -> None:
    with pytest.raises(ConfigurationError, match="cannot be empty"):
        PromptRequest(Task.GENERATE, instruction)


@pytest.mark.parametrize(
    "endpoint",
    [
        "ftp://localhost/v1",
        "http://models.example.com/v1",
        "https://user:secret@example.com/v1",
        "https://example.com/v1?token=secret",
        "https://example.com/v1#fragment",
    ],
)
def test_provider_config_rejects_unsafe_endpoint_forms(endpoint: str) -> None:
    with pytest.raises(ConfigurationError):
        ProviderConfig(endpoint=endpoint, model="test-model")


def test_provider_config_allows_https_and_loopback_http() -> None:
    remote = ProviderConfig(endpoint="https://models.example.com/v1/", model="remote")
    local = ProviderConfig(endpoint="http://127.0.0.1:11434/v1", model="local")

    assert remote.chat_completions_url == "https://models.example.com/v1/chat/completions"
    assert local.chat_completions_url == "http://127.0.0.1:11434/v1/chat/completions"


def test_provider_config_accepts_explicit_full_endpoint() -> None:
    config = ProviderConfig(
        endpoint="https://models.example.com/v1/chat/completions", model="remote"
    )

    assert config.chat_completions_url == config.endpoint


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"endpoint": 1, "model": "model"}, "endpoint must be text"),
        ({"endpoint": "https://example.com/v1", "model": 1}, "model name must be text"),
        ({"endpoint": "https://example.com\n/v1", "model": "model"}, "control"),
        ({"endpoint": "https://example.com/v1", "model": "bad\nmodel"}, "control"),
        ({"endpoint": "https://example.com/v1", "model": "\ud800"}, "valid Unicode"),
        ({"endpoint": "https://[broken/v1", "model": "model"}, "URL is invalid"),
        (
            {"endpoint": "https://example.com/" + "x" * MAX_ENDPOINT_CHARS, "model": "model"},
            "exceeds",
        ),
        (
            {"endpoint": "https://example.com/v1", "model": "model", "timeout_seconds": True},
            "timeout",
        ),
        (
            {"endpoint": "https://example.com/v1", "model": "model", "max_output_tokens": True},
            "output tokens",
        ),
    ],
)
def test_provider_config_public_values_fail_closed(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ConfigurationError, match=match):
        ProviderConfig(**kwargs)  # type: ignore[arg-type]
