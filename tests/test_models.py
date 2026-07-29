# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import pytest

from samsarix_codegen.errors import ConfigurationError
from samsarix_codegen.models import PromptRequest, ProviderConfig, Task


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
