#!/usr/bin/env python3
# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Exercise fresh-source review export using only the installed CLI and synthetic output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from samsarix_codegen import ChatResult, parse_request_artifact, render_execution_result


def require(condition: bool, message: str) -> None:
    """Keep smoke assertions active even under optimized Python."""

    if not condition:
        raise AssertionError(message)


def run_cli(root: Path, *args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[bytes]:
    """Run the installed module outside the checkout with bounded subprocess execution."""

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "samsarix_codegen", *args],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=120,
        check=False,
    )
    require(
        completed.returncode == expected_exit,
        f"review CLI exited {completed.returncode}, expected {expected_exit}: "
        + completed.stderr.decode("utf-8", errors="replace"),
    )
    return completed


def main() -> int:
    """Prove the copy-paste journey and stale-source rejection without a provider call."""

    with tempfile.TemporaryDirectory(prefix="samsarix-review-") as temporary:
        root = Path(temporary)
        source = root / "sample.py"
        source.write_bytes(b"def divide(a, b):\n    return a / b\n")
        built = run_cli(
            root,
            "build",
            "Review division",
            "--task",
            "review-report",
            "--file",
            "sample.py",
            "--format",
            "json",
        )
        artifact = parse_request_artifact(built.stdout)
        (root / "request.json").write_bytes(built.stdout)
        response = {
            "schema_version": 1,
            "summary": "Synthetic fixture, not a provider review.",
            "findings": [
                {
                    "category": "reliability",
                    "severity": "warning",
                    "title": "Check zero divisors",
                    "message": "Verify the intended failure behavior.",
                    "path": "sample.py",
                    "start_line": 2,
                    "end_line": 2,
                }
            ],
        }
        (root / "result.json").write_text(
            render_execution_result(
                artifact, ChatResult(json.dumps(response)), model="synthetic-review-fixture"
            ),
            encoding="utf-8",
        )
        arguments = ("export-review", "request.json", "result.json")
        for output_format in ("json", "sarif"):
            baseline = run_cli(root, *arguments, "--format", output_format)
            checked = run_cli(root, *arguments, "--format", output_format, "--source-root", ".")
            require(checked.stdout == baseline.stdout, "source check changed the report contract")
            require(not checked.stderr, "successful export wrote unexpected diagnostics")
            decoded = json.loads(checked.stdout)
            if output_format == "json":
                require(decoded["review"] == response, "review report lost the synthetic finding")
            else:
                location = decoded["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
                require(location["region"]["startLine"] == 2, "SARIF lost the source location")

        # Same bytes/line counts; the content hash must catch this change.
        source.write_bytes(b"def divide(a, b):\n    return a * b\n")
        for output_format in ("json", "sarif"):
            rejected = run_cli(
                root,
                *arguments,
                "--format",
                output_format,
                "--source-root",
                ".",
                expected_exit=5,
            )
            require(not rejected.stdout, "stale source leaked normal output")
            require(b"source changed" in rejected.stderr, "stale source was not diagnosed")
            run_cli(root, *arguments, "--format", output_format)
        source.unlink()
        for output_format in ("json", "sarif"):
            missing = run_cli(
                root,
                *arguments,
                "--format",
                output_format,
                "--source-root",
                ".",
                expected_exit=5,
            )
            require(not missing.stdout, "missing source leaked normal output")
            require(
                b"review source verification failed" in missing.stderr,
                "missing source was not diagnosed",
            )
            run_cli(root, *arguments, "--format", output_format)
    print("installed review-source smoke passed (0 provider requests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
