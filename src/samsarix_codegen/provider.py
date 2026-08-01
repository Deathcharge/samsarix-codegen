# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Minimal bounded client for OpenAI-compatible chat-completions endpoints."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextlib import closing
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from samsarix_codegen import __version__
from samsarix_codegen.errors import ProviderError
from samsarix_codegen.models import ChatResult, ProviderConfig

MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_ERROR_BYTES = 8 * 1024


class OpenAIChatClient:
    """Execute one non-streaming chat-completions request."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    def complete(self, messages: Sequence[Mapping[str, str]]) -> ChatResult:
        """Send ``messages`` and normalize the first text response."""

        payload = {
            "model": self.config.model,
            "messages": list(messages),
            "max_tokens": self.config.max_output_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"samsarix-codegen/{__version__}",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = Request(
            self.config.chat_completions_url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with closing(_open_without_redirects(request, self.config.timeout_seconds)) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            detail = _read_http_error(exc, self.config.api_key)
            raise ProviderError(f"model endpoint returned HTTP {exc.code}: {detail}") from exc
        except TimeoutError as exc:
            raise ProviderError(
                f"model request timed out after {self.config.timeout_seconds:g} seconds"
            ) from exc
        except URLError as exc:
            reason = _redact(str(exc.reason), self.config.api_key)
            raise ProviderError(f"model endpoint is unavailable: {reason}") from exc
        except OSError as exc:
            detail = _redact(str(exc), self.config.api_key)
            raise ProviderError(f"model request failed: {detail}") from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError(
                f"model response exceeds the {MAX_RESPONSE_BYTES:,}-byte safety limit"
            )

        try:
            decoded: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("model endpoint returned invalid UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise ProviderError("model endpoint returned a JSON value instead of an object")

        text = _extract_text(decoded)
        usage = decoded.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        return ChatResult(
            text=text,
            prompt_tokens=_optional_nonnegative_int(usage.get("prompt_tokens")),
            completion_tokens=_optional_nonnegative_int(usage.get("completion_tokens")),
            total_tokens=_optional_nonnegative_int(usage.get("total_tokens")),
        )


def _extract_text(decoded: dict[str, Any]) -> str:
    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("model response does not contain choices[0]")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ProviderError("model response does not contain choices[0].message")
    content = message.get("content")
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") not in {None, "text"}:
                continue
            part = item.get("text")
            if isinstance(part, str):
                parts.append(part)
        text = "".join(parts)
        if text:
            return text
    raise ProviderError("model response contains no text content")


class _RejectRedirects(HTTPRedirectHandler):
    """Fail closed so bearer credentials cannot follow a provider-controlled redirect."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise HTTPError(req.full_url, code, "redirects are not allowed", headers, fp)


def _open_without_redirects(request: Request, timeout: float) -> Any:
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


def _optional_nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _read_http_error(error: HTTPError, api_key: str | None) -> str:
    try:
        raw = error.read(MAX_ERROR_BYTES)
        detail = raw.decode("utf-8", errors="replace").strip()
    except OSError:
        detail = ""
    detail = _redact(detail, api_key)
    return detail or error.reason or "request rejected"


def _redact(value: str, api_key: str | None) -> str:
    if api_key:
        return value.replace(api_key, "[REDACTED]")
    return value
