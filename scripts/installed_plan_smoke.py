#!/usr/bin/env python3
# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Exercise the installed execution-plan journey against one local HTTP fixture."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


class FixtureHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        type(self).requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "payload": json.loads(raw),
            }
        )
        response = json.dumps(
            {
                "choices": [{"message": {"content": "Fixture response"}}],
                "usage": {
                    "prompt_tokens": 23,
                    "completion_tokens": 2,
                    "total_tokens": 25,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_cli(
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    stdin: bytes | None = None,
    expected_exit: int = 0,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        [sys.executable, "-m", "samsarix_codegen", *arguments],
        cwd=cwd,
        env=environment,
        input=stdin,
        capture_output=True,
        check=False,
    )
    if result.returncode != expected_exit:
        raise AssertionError(
            f"CLI exited {result.returncode}, expected {expected_exit}: "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )
    return result


def main() -> int:
    FixtureHandler.requests = []
    server = HTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="samsarix-installed-plan-") as directory:
            root = Path(directory)
            request_path = root / "request.json"
            plan_path = root / "execution-plan.json"
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment["PYTHONNOUSERSITE"] = "1"

            built = run_cli(
                [
                    "build",
                    "Private fixture instruction",
                    "--task",
                    "review",
                    "--stdin-name",
                    "staged.diff",
                    "--format",
                    "json",
                ],
                cwd=root,
                environment=environment,
                stdin=b"diff --git a/app.py b/app.py\n+enabled = True\n",
            )
            request_path.write_bytes(built.stdout)
            inspected = run_cli(
                ["inspect", str(request_path), "--format", "fingerprint"],
                cwd=root,
                environment=environment,
            )
            request_fingerprint = inspected.stdout.decode().strip()

            endpoint = f"http://127.0.0.1:{server.server_port}/v1"
            created = run_cli(
                [
                    "create-plan",
                    str(request_path),
                    "--expect-fingerprint",
                    request_fingerprint,
                    "--endpoint",
                    endpoint,
                    "--model",
                    "fixture-model",
                    "--timeout",
                    "10",
                    "--max-output-tokens",
                    "64",
                    "--max-estimated-input-tokens",
                    "10000",
                ],
                cwd=root,
                environment=environment,
            )
            plan_path.write_bytes(created.stdout)
            approved = run_cli(
                [
                    "verify-plan",
                    str(request_path),
                    str(plan_path),
                    "--format",
                    "fingerprint",
                ],
                cwd=root,
                environment=environment,
            )
            plan_fingerprint = approved.stdout.decode().strip()
            verification = run_cli(
                [
                    "verify-plan",
                    str(request_path),
                    str(plan_path),
                    "--expect-plan-fingerprint",
                    plan_fingerprint,
                    "--format",
                    "json",
                ],
                cwd=root,
                environment=environment,
            )
            assert b"Private fixture instruction" not in verification.stdout
            assert b"enabled = True" not in verification.stdout

            execution_environment = environment.copy()
            execution_environment.update(
                {
                    "SAMSARIX_API_KEY": "fixture-secret",
                    "SAMSARIX_API_BASE": "http://remote.example.invalid/v1",
                    "SAMSARIX_MODEL": "environment-model",
                    "SAMSARIX_TIMEOUT": "not-an-integer",
                    "SAMSARIX_MAX_OUTPUT_TOKENS": "not-an-integer",
                    "SAMSARIX_MAX_ESTIMATED_INPUT_TOKENS": "not-an-integer",
                }
            )
            executed = run_cli(
                [
                    "execute",
                    str(request_path),
                    "--plan",
                    str(plan_path),
                    "--expect-plan-fingerprint",
                    plan_fingerprint,
                    "--format",
                    "json",
                ],
                cwd=root,
                environment=execution_environment,
            )
            result = json.loads(executed.stdout)
            assert result["request_fingerprint"] == request_fingerprint
            assert result["model"] == "fixture-model"
            assert result["response"]["text"] == "Fixture response"
            assert result["usage"]["total_tokens"] == 25
            assert b"fixture-secret" not in executed.stdout + executed.stderr
            assert len(FixtureHandler.requests) == 1

            received = FixtureHandler.requests[0]
            assert received["path"] == "/v1/chat/completions"
            assert received["authorization"] == "Bearer fixture-secret"
            assert received["payload"]["model"] == "fixture-model"
            assert received["payload"]["max_tokens"] == 64
            assert received["payload"]["stream"] is False
            assert "Private fixture instruction" in received["payload"]["messages"][1]["content"]
            assert "enabled = True" in received["payload"]["messages"][1]["content"]

            tampered_path = root / "tampered-plan.json"
            tampered = json.loads(plan_path.read_text(encoding="utf-8"))
            tampered["provider"]["model"] = "tampered-model"
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            rejected_tamper = run_cli(
                ["execute", str(request_path), "--plan", str(tampered_path)],
                cwd=root,
                environment=execution_environment,
                expected_exit=5,
            )
            assert rejected_tamper.stdout == b""
            assert len(FixtureHandler.requests) == 1

            rejected_override = run_cli(
                [
                    "execute",
                    str(request_path),
                    "--plan",
                    str(plan_path),
                    "--model",
                    "override-model",
                ],
                cwd=root,
                environment=execution_environment,
                expected_exit=2,
            )
            assert rejected_override.stdout == b""
            assert len(FixtureHandler.requests) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    print("installed execution-plan smoke passed (1 provider request)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
