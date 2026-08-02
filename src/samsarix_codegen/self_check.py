# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Deterministic, network-free verification of an installed package."""

from __future__ import annotations

import json
import platform
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from samsarix_codegen import __version__
from samsarix_codegen.artifact import (
    ExecutionResultPolicy,
    create_request_artifact,
    parse_execution_result,
    parse_request_artifact,
    render_execution_result,
    render_request_artifact,
)
from samsarix_codegen.errors import SamsarixError
from samsarix_codegen.execution_evidence import verify_execution_evidence
from samsarix_codegen.execution_plan import (
    create_execution_plan,
    parse_execution_plan,
    render_execution_plan,
)
from samsarix_codegen.models import ChatResult, ContextFile, PromptRequest, ProviderConfig, Task
from samsarix_codegen.prompt import build_messages
from samsarix_codegen.result_policy import fingerprint_execution_result_policy
from samsarix_codegen.schema import ContractSchema, load_contract_schema

SELF_CHECK_SCHEMA_VERSION = 1
SELF_CHECK_SOURCE = (
    "# Copyright 2026 Samsarix LLC\n"
    "# SPDX-License-Identifier: Apache-2.0\n"
    "\n"
    '"""Small input used by the README and package smoke test."""\n'
    "\n"
    "\n"
    "def greet(name: str) -> str:\n"
    '    """Return a friendly greeting."""\n'
    "\n"
    "    cleaned_name = name.strip()\n"
    "    if not cleaned_name:\n"
    '        raise ValueError("name cannot be blank")\n'
    '    return f"Hello, {cleaned_name}!"\n'
)
SELF_CHECK_INSTRUCTION = (
    "Review greet for correctness, edge cases, and maintainability. Return concise findings."
)
SELF_CHECK_RESPONSE = (
    '{"diagnosis":"Null dereference","evidence":["trace line 42"],'
    '"next_step":"Guard the optional value"}'
)
EXPECTED_REQUEST_FINGERPRINT = (
    "sha256:4c04cb6a6352ef10b09403b8f5b7da03e71dbfd278606fc25edb5274c3399d59"
)
EXPECTED_PLAN_FINGERPRINT = (
    "sha256:cbcaf0102a11fc20d056d9a3fdb1ab5e40822ed53852cbf181cb90c80a68a1d9"
)
EXPECTED_RESPONSE_FINGERPRINT = (
    "sha256:d10517f83c16d86209750ef9c9101cf06770a9df1b8f7a8386293921f7c3f7e5"
)
EXPECTED_POLICY_FINGERPRINT = (
    "sha256:56f31e83efb5caa3e806b0eba3735009ac1387003fa5888b9a78e774a6218578"
)
EXPECTED_CONTRACTS = (
    "request",
    "result",
    "comparison",
    "result-inspection",
    "result-verification",
    "result-comparison",
    "provider-check",
    "context-manifest",
    "result-policy",
    "execution-plan",
    "execution-plan-verification",
    "execution-evidence",
    "self-check",
)
_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_PYTHON_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+")
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class SelfCheckError(SamsarixError):
    """The installed package did not reproduce its deterministic evidence chain."""


@dataclass(frozen=True, slots=True)
class SelfCheckReport:
    """Content-omitting evidence from one successful installed-package self-check."""

    package_version: str
    python_implementation: str
    python_version: str
    contract_count: int
    request_fingerprint: str
    plan_fingerprint: str
    response_fingerprint: str
    schema_version: ClassVar[int] = SELF_CHECK_SCHEMA_VERSION
    status: ClassVar[Literal["passed"]] = "passed"

    def __post_init__(self) -> None:
        if not _VERSION_PATTERN.fullmatch(self.package_version):
            raise SelfCheckError("self-check package version is invalid")
        if not self.python_implementation:
            raise SelfCheckError("self-check Python implementation is empty")
        if not _PYTHON_VERSION_PATTERN.match(self.python_version):
            raise SelfCheckError("self-check Python version is invalid")
        if (
            not isinstance(self.contract_count, int)
            or isinstance(self.contract_count, bool)
            or not 1 <= self.contract_count <= 1_000
        ):
            raise SelfCheckError("self-check contract count must be between 1 and 1,000")
        for label, value in (
            ("request fingerprint", self.request_fingerprint),
            ("plan fingerprint", self.plan_fingerprint),
            ("response fingerprint", self.response_fingerprint),
        ):
            if not _SHA256_PATTERN.fullmatch(value):
                raise SelfCheckError(f"self-check {label} is invalid")

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned, content-omitting report envelope."""

        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "package_version": self.package_version,
            "runtime": {
                "python_implementation": self.python_implementation,
                "python_version": self.python_version,
            },
            "checks": {
                "bundled_contracts": {
                    "status": "passed",
                    "count": self.contract_count,
                },
                "request_round_trip": {
                    "status": "passed",
                    "fingerprint": self.request_fingerprint,
                },
                "plan_round_trip": {
                    "status": "passed",
                    "fingerprint": self.plan_fingerprint,
                },
                "result_round_trip": {
                    "status": "passed",
                    "response_sha256": self.response_fingerprint,
                },
                "execution_evidence": {"status": "passed"},
            },
            "network": {
                "attempted": False,
                "provider_called": False,
            },
        }


def run_self_check() -> SelfCheckReport:
    """Exercise bundled contracts and the core evidence path without user input or network."""

    try:
        contract_count = _check_bundled_contract_resources()

        source_bytes = SELF_CHECK_SOURCE.encode("utf-8")
        context = ContextFile(
            path="examples/sample.py",
            content=SELF_CHECK_SOURCE,
            size_bytes=len(source_bytes),
        )
        request = PromptRequest(
            task=Task.REVIEW,
            instruction=SELF_CHECK_INSTRUCTION,
            files=(context,),
        )
        artifact = create_request_artifact(build_messages(request), request.files)
        _require_equal(
            artifact.fingerprint,
            EXPECTED_REQUEST_FINGERPRINT,
            label="request fingerprint",
        )
        parsed_artifact = parse_request_artifact(render_request_artifact(artifact))
        _require_equal(
            parsed_artifact.to_payload(),
            artifact.to_payload(),
            label="request round trip",
        )

        config = ProviderConfig(
            endpoint="http://127.0.0.1:11434/v1",
            model="example-review-model",
            timeout_seconds=45,
            max_output_tokens=256,
        )
        result_policy = ExecutionResultPolicy(
            expected_model="example-review-model",
            max_response_bytes=256,
            response_format="json-object",
            required_json_keys=("diagnosis", "evidence", "next_step"),
            allowed_json_keys=("diagnosis", "evidence", "next_step"),
            json_key_types=(
                ("diagnosis", "string"),
                ("evidence", "array"),
                ("next_step", "string"),
            ),
            schema_version=2,
        )
        plan = create_execution_plan(
            parsed_artifact,
            config,
            max_estimated_input_tokens=5000,
            result_policy_fingerprint=fingerprint_execution_result_policy(result_policy),
        )
        _require_equal(plan.fingerprint, EXPECTED_PLAN_FINGERPRINT, label="plan fingerprint")
        parsed_plan = parse_execution_plan(render_execution_plan(plan))
        _require_equal(parsed_plan.to_payload(), plan.to_payload(), label="plan round trip")

        rendered_result = render_execution_result(
            parsed_artifact,
            ChatResult(text=SELF_CHECK_RESPONSE),
            model=config.model,
            plan_fingerprint=parsed_plan.fingerprint,
        )
        result = parse_execution_result(rendered_result)
        _require_equal(
            result.to_payload(),
            json.loads(rendered_result),
            label="result round trip",
        )
        evidence = verify_execution_evidence(
            parsed_artifact,
            parsed_plan,
            result,
            expected_plan_fingerprint=EXPECTED_PLAN_FINGERPRINT,
            result_policy=result_policy,
        )
        _require_equal(
            evidence.result_policy_fingerprint,
            EXPECTED_POLICY_FINGERPRINT,
            label="result policy fingerprint",
        )
        _require_equal(
            evidence.result.response_sha256,
            EXPECTED_RESPONSE_FINGERPRINT,
            label="response fingerprint",
        )
        _require_equal(
            evidence.response_structure,
            {"format": "json-object", "top_level_keys": 3},
            label="response structure",
        )
    except SelfCheckError:
        raise
    except (RuntimeError, SamsarixError) as exc:
        raise SelfCheckError(f"installed-package self-check failed: {exc}") from exc

    return SelfCheckReport(
        package_version=__version__,
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        contract_count=contract_count,
        request_fingerprint=artifact.fingerprint,
        plan_fingerprint=plan.fingerprint,
        response_fingerprint=evidence.result.response_sha256,
    )


def render_self_check(
    report: SelfCheckReport,
    *,
    output_format: Literal["text", "json"] = "text",
) -> str:
    """Render successful self-check evidence without prompt or response contents."""

    if not isinstance(report, SelfCheckReport):
        raise SelfCheckError("self-check rendering requires a validated report")
    if output_format == "json":
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if output_format != "text":
        raise SelfCheckError("self-check format must be text or json")

    return (
        "Samsarix Codegen self-check passed.\n"
        f"Package: {report.package_version}\n"
        f"Runtime: {report.python_implementation} {report.python_version}\n"
        f"Bundled contracts: {report.contract_count:,} loaded.\n"
        f"Request: {report.request_fingerprint}\n"
        f"Plan: {report.plan_fingerprint}\n"
        f"Response: {report.response_fingerprint}\n"
        "Execution evidence: passed.\n"
        "Network: not attempted; no provider called.\n"
    )


def _check_bundled_contract_resources() -> int:
    """Check package resources without adding a runtime JSON Schema dependency.

    Full Draft 2020-12 meta-schema validation is intentionally a development and CI gate using the
    optional ``jsonschema`` dependency. The installed-package path stays dependency-free and checks
    that the exact registry is present, every resource parses, and each root declares the expected
    draft and object shape.
    """

    registered = tuple(contract.value for contract in ContractSchema)
    _require_equal(registered, EXPECTED_CONTRACTS, label="contract registry")
    for contract in ContractSchema:
        schema = load_contract_schema(contract)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise SelfCheckError(
                f"bundled {contract.value} contract does not declare Draft 2020-12"
            )
        if schema.get("type") != "object":
            raise SelfCheckError(f"bundled {contract.value} contract is not an object schema")
    return len(registered)


def _require_equal(actual: object, expected: object, *, label: str) -> None:
    if actual != expected:
        raise SelfCheckError(f"installed-package self-check {label} does not match")
