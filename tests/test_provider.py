# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError

import pytest

from samsarix_codegen.errors import ConfigurationError, ProviderError
from samsarix_codegen.models import ProviderConfig
from samsarix_codegen.provider import OpenAIChatClient
from samsarix_codegen.provider_check import (
    PROVIDER_CHECK_MESSAGES,
    ProviderCheckReport,
    check_provider,
    render_provider_check,
)


@contextmanager
def chat_server(
    response: dict[str, object],
    *,
    status: int = 200,
    response_headers: dict[str, str] | None = None,
) -> Iterator[tuple[str, dict[str, object]]]:
    captured: dict[str, object] = {}
    captured["request_count"] = 0
    response_body = json.dumps(response).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            captured["request_count"] = int(captured["request_count"]) + 1
            captured["path"] = self.path
            captured["authorization"] = self.headers.get("Authorization")
            captured["user_agent"] = self.headers.get("User-Agent")
            captured["body"] = json.loads(self.rfile.read(length))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            for name, value in (response_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/v1", captured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_client_sends_bounded_request_and_normalizes_usage() -> None:
    response = {
        "choices": [{"message": {"content": "Model answer"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
    }
    with chat_server(response) as (endpoint, captured):
        config = ProviderConfig(
            endpoint=endpoint, model="test-model", api_key="test-key", max_output_tokens=77
        )
        result = OpenAIChatClient(config).complete([{"role": "user", "content": "Hello"}])

    assert result.text == "Model answer"
    assert result.total_tokens == 15
    assert captured["path"] == "/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["user_agent"] == "samsarix-codegen/0.2.0"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "test-model"
    assert body["max_tokens"] == 77
    assert body["stream"] is False


def test_provider_check_sends_exactly_one_content_free_bounded_request() -> None:
    response = {
        "choices": [{"message": {"content": "SAMSARIX_OK"}}],
        "usage": {"prompt_tokens": 21, "completion_tokens": 4, "total_tokens": 25},
    }
    with chat_server(response) as (endpoint, captured):
        config = ProviderConfig(
            endpoint=endpoint,
            model="check-model",
            api_key="check-key",
            max_output_tokens=64,
        )
        report = check_provider(config)

    assert captured["request_count"] == 1
    body = captured["body"]
    assert isinstance(body, dict)
    assert body == {
        "model": "check-model",
        "messages": list(PROVIDER_CHECK_MESSAGES),
        "max_tokens": 64,
        "stream": False,
    }
    payload = json.loads(render_provider_check(report, output_format="json"))
    assert payload["status"] == "passed"
    assert payload["request"]["source_context_items"] == 0
    assert payload["response"] == {"text_received": True, "text_chars": 11}
    assert payload["usage"]["total_tokens"] == 25
    assert endpoint not in json.dumps(payload)
    assert "check-key" not in json.dumps(payload)
    assert "SAMSARIX_OK" not in json.dumps(payload)


def test_provider_check_report_rejects_invalid_public_values() -> None:
    with pytest.raises(ConfigurationError, match="response characters"):
        ProviderCheckReport(model="model", max_output_tokens=64, response_chars=0)


def test_client_accepts_text_content_parts() -> None:
    response = {
        "choices": [{"message": {"content": [{"type": "text", "text": "one"}, {"text": " two"}]}}]
    }
    with chat_server(response) as (endpoint, _captured):
        result = OpenAIChatClient(ProviderConfig(endpoint, "model")).complete([])

    assert result.text == "one two"


def test_http_error_redacts_api_key() -> None:
    secret = "super-secret-key"
    with chat_server({"error": f"bad key {secret}"}, status=401) as (endpoint, _captured):
        client = OpenAIChatClient(ProviderConfig(endpoint, "model", api_key=secret))
        with pytest.raises(ProviderError) as caught:
            client.complete([])

    assert "HTTP 401" in str(caught.value)
    assert "[REDACTED]" in str(caught.value)
    assert secret not in str(caught.value)


def test_client_rejects_redirect_without_contacting_target() -> None:
    success = {"choices": [{"message": {"content": "must not be reached"}}]}
    with chat_server(success) as (target_endpoint, target_capture):
        target_url = f"{target_endpoint}/chat/completions"
        with chat_server({}, status=307, response_headers={"Location": target_url}) as (
            redirect_endpoint,
            redirect_capture,
        ):
            client = OpenAIChatClient(
                ProviderConfig(redirect_endpoint, "model", api_key="redirect-secret")
            )
            with pytest.raises(ProviderError, match="HTTP 307"):
                client.complete([{"role": "user", "content": "fixed"}])

    assert redirect_capture["request_count"] == 1
    assert redirect_capture["authorization"] == "Bearer redirect-secret"
    assert target_capture["request_count"] == 0


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, limit: int) -> bytes:
        return self.body[:limit]

    def close(self) -> None:
        return


def test_client_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "samsarix_codegen.provider._open_without_redirects",
        lambda request, timeout: FakeResponse(b"not-json"),
    )

    with pytest.raises(ProviderError, match="invalid UTF-8 JSON"):
        OpenAIChatClient(ProviderConfig("http://localhost:11434/v1", "model")).complete([])


def test_client_reports_unavailable_endpoint(monkeypatch) -> None:
    def unavailable(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("samsarix_codegen.provider._open_without_redirects", unavailable)

    with pytest.raises(ProviderError, match="endpoint is unavailable"):
        OpenAIChatClient(ProviderConfig("http://localhost:11434/v1", "model")).complete([])


def test_client_reports_timeout(monkeypatch) -> None:
    def timeout(request, timeout):
        raise TimeoutError

    monkeypatch.setattr("samsarix_codegen.provider._open_without_redirects", timeout)

    with pytest.raises(ProviderError, match="timed out after 2 seconds"):
        config = ProviderConfig("http://localhost:11434/v1", "model", timeout_seconds=2)
        OpenAIChatClient(config).complete([])


def test_client_enforces_response_byte_cap(monkeypatch) -> None:
    monkeypatch.setattr("samsarix_codegen.provider.MAX_RESPONSE_BYTES", 4)
    monkeypatch.setattr(
        "samsarix_codegen.provider._open_without_redirects",
        lambda request, timeout: FakeResponse(b"12345"),
    )

    with pytest.raises(ProviderError, match="response exceeds"):
        OpenAIChatClient(ProviderConfig("http://localhost:11434/v1", "model")).complete([])


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_client_rejects_missing_text(response: dict[str, object]) -> None:
    with chat_server(response) as (endpoint, _captured), pytest.raises(ProviderError):
        OpenAIChatClient(ProviderConfig(endpoint, "model")).complete([])
