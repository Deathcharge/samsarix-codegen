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

CLI_TIMEOUT_SECONDS = 120
FIXTURE_RESPONSE = json.dumps(
    {
        "diagnosis": "Private fixture diagnosis",
        "evidence": ["Private fixture trace"],
        "next_step": "Private fixture action",
    },
    separators=(",", ":"),
)


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
                "model": "fixture-model-2026-08",
                "choices": [{"message": {"content": FIXTURE_RESPONSE}}],
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
        timeout=CLI_TIMEOUT_SECONDS,
    )
    if result.returncode != expected_exit:
        raise AssertionError(
            f"CLI exited {result.returncode}, expected {expected_exit}: "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )
    return result


def require(condition: bool, message: str) -> None:
    """Raise even under optimized Python when one smoke invariant fails."""

    if not condition:
        raise AssertionError(message)


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
            result_path = root / "result.json"
            policy_path = root / "result-policy.json"
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment["PYTHONNOUSERSITE"] = "1"
            policy_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "expected_model": "fixture-model",
                        "max_response_bytes": 256,
                        "max_total_tokens": 25,
                        "response_format": "json-object",
                        "required_json_keys": ["diagnosis", "evidence", "next_step"],
                        "allowed_json_keys": ["diagnosis", "evidence", "next_step"],
                        "json_key_types": {
                            "diagnosis": "string",
                            "evidence": "array",
                            "next_step": "string",
                        },
                    }
                ),
                encoding="utf-8",
            )
            fingerprinted_policy = run_cli(
                ["fingerprint-policy", str(policy_path)],
                cwd=root,
                environment=environment,
            )
            policy_fingerprint = fingerprinted_policy.stdout.decode().strip()
            require(
                policy_fingerprint.startswith("sha256:") and len(policy_fingerprint) == 71,
                "result policy fingerprint is not canonical sha256",
            )

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
            require(
                b"Private fixture instruction" not in verification.stdout,
                "plan verification disclosed the private instruction",
            )
            require(
                b"enabled = True" not in verification.stdout,
                "plan verification disclosed selected context",
            )

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
            rejected_orphaned_policy_approval = run_cli(
                [
                    "execute",
                    str(request_path),
                    "--plan",
                    str(plan_path),
                    "--expect-policy-fingerprint",
                    policy_fingerprint,
                ],
                cwd=root,
                environment=execution_environment,
                expected_exit=2,
            )
            require(
                rejected_orphaned_policy_approval.stdout == b"",
                "orphaned policy approval produced normal output",
            )
            require(
                len(FixtureHandler.requests) == 0,
                "orphaned policy approval caused a provider request",
            )
            rejected_policy_approval = run_cli(
                [
                    "execute",
                    str(request_path),
                    "--plan",
                    str(plan_path),
                    "--policy",
                    str(policy_path),
                    "--expect-policy-fingerprint",
                    "sha256:" + "0" * 64,
                ],
                cwd=root,
                environment=execution_environment,
                expected_exit=5,
            )
            require(
                rejected_policy_approval.stdout == b"",
                "unapproved result policy produced normal output",
            )
            require(
                len(FixtureHandler.requests) == 0,
                "unapproved result policy caused a provider request",
            )
            executed = run_cli(
                [
                    "execute",
                    str(request_path),
                    "--plan",
                    str(plan_path),
                    "--expect-plan-fingerprint",
                    plan_fingerprint,
                    "--policy",
                    str(policy_path),
                    "--expect-policy-fingerprint",
                    policy_fingerprint,
                    "--format",
                    "json",
                ],
                cwd=root,
                environment=execution_environment,
            )
            result = json.loads(executed.stdout)
            result_path.write_bytes(executed.stdout)
            require(result["schema_version"] == 2, "result did not use schema version 2")
            require(
                result["request_fingerprint"] == request_fingerprint,
                "result does not reference the exact request",
            )
            require(
                result["plan_fingerprint"] == plan_fingerprint,
                "result does not reference the exact execution plan",
            )
            require(result["model"] == "fixture-model", "result model does not match the plan")
            require(
                result["response_model"] == "fixture-model-2026-08",
                "result omitted the provider-reported model",
            )
            require(
                result["response"]["text"] == FIXTURE_RESPONSE,
                "provider response was not normalized",
            )
            require(result["usage"]["total_tokens"] == 25, "provider usage was not normalized")
            require(
                b"fixture-secret" not in executed.stdout + executed.stderr,
                "API key appeared in CLI output",
            )
            require(len(FixtureHandler.requests) == 1, "expected exactly one provider request")

            evidence = run_cli(
                [
                    "verify-execution",
                    str(request_path),
                    str(plan_path),
                    str(result_path),
                    "--expect-plan-fingerprint",
                    plan_fingerprint,
                    "--policy",
                    str(policy_path),
                    "--expect-policy-fingerprint",
                    policy_fingerprint,
                    "--format",
                    "json",
                ],
                cwd=root,
                environment=environment,
            )
            evidence_payload = json.loads(evidence.stdout)
            require(evidence_payload["schema_version"] == 3, "evidence did not use version 3")
            require(
                evidence_payload["plan_fingerprint"] == plan_fingerprint,
                "execution evidence does not reference the exact plan",
            )
            require(
                evidence_payload["provider"]["response_model"] == "fixture-model-2026-08",
                "execution evidence omitted the provider-reported model",
            )
            require(
                evidence_payload["result_policy"]["fingerprint"] == policy_fingerprint,
                "execution evidence does not identify the exact result policy",
            )
            require(
                evidence_payload["result_policy"]["rules"]["max_total_tokens"] == 25,
                "execution evidence omitted the enforced result-policy rule",
            )
            require(
                evidence_payload["result"]["response_structure"]
                == {"format": "json-object", "top_level_keys": 3},
                "execution evidence omitted the validated response structure",
            )
            require(
                b"Private fixture instruction" not in evidence.stdout,
                "execution evidence disclosed the private instruction",
            )
            require(
                FIXTURE_RESPONSE.encode() not in evidence.stdout,
                "execution evidence disclosed the provider response",
            )
            for private_value in (
                b"Private fixture diagnosis",
                b"Private fixture trace",
                b"Private fixture action",
            ):
                require(
                    private_value not in evidence.stdout,
                    "execution evidence disclosed a provider response value",
                )

            failing_policy_path = root / "failing-result-policy.json"
            failing_policy_path.write_text(
                json.dumps({"schema_version": 1, "max_total_tokens": 24}),
                encoding="utf-8",
            )
            rejected_policy = run_cli(
                [
                    "verify-execution",
                    str(request_path),
                    str(plan_path),
                    str(result_path),
                    "--policy",
                    str(failing_policy_path),
                ],
                cwd=root,
                environment=environment,
                expected_exit=5,
            )
            require(rejected_policy.stdout == b"", "failed result policy produced normal output")
            require(
                len(FixtureHandler.requests) == 1,
                "offline result-policy failure caused an additional provider request",
            )

            failing_structure_path = root / "failing-structure-policy.json"
            failing_structure_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "response_format": "json-object",
                        "required_json_keys": ["missing_key"],
                    }
                ),
                encoding="utf-8",
            )
            rejected_structure = run_cli(
                [
                    "verify-execution",
                    str(request_path),
                    str(plan_path),
                    str(result_path),
                    "--policy",
                    str(failing_structure_path),
                ],
                cwd=root,
                environment=environment,
                expected_exit=5,
            )
            require(
                rejected_structure.stdout == b"",
                "failed response-structure policy produced normal output",
            )
            require(
                len(FixtureHandler.requests) == 1,
                "offline response-structure failure caused an additional provider request",
            )

            received = FixtureHandler.requests[0]
            require(
                received["path"] == "/v1/chat/completions",
                "provider request used the wrong path",
            )
            require(
                received["authorization"] == "Bearer fixture-secret",
                "provider request omitted the external bearer credential",
            )
            require(
                received["payload"]["model"] == "fixture-model",
                "provider request did not use the planned model",
            )
            require(
                received["payload"]["max_tokens"] == 64,
                "provider request did not use the planned output limit",
            )
            require(received["payload"]["stream"] is False, "provider request enabled streaming")
            require(
                "Private fixture instruction" in received["payload"]["messages"][1]["content"],
                "provider request omitted the reviewed instruction",
            )
            require(
                "enabled = True" in received["payload"]["messages"][1]["content"],
                "provider request omitted the reviewed context",
            )

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
            require(rejected_tamper.stdout == b"", "tampered plan produced normal output")
            require(
                len(FixtureHandler.requests) == 1,
                "tampered plan caused an additional provider request",
            )

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
            require(rejected_override.stdout == b"", "plan override produced normal output")
            require(
                len(FixtureHandler.requests) == 1,
                "plan override caused an additional provider request",
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    print("installed execution-evidence smoke passed (1 provider request)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
