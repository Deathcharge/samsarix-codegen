# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from samsarix_codegen.artifact import (
    MAX_ARTIFACT_CONTEXT_ITEMS,
    MAX_ARTIFACT_MESSAGES,
    MAX_RESULT_BYTES,
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    inspect_execution_result,
    parse_execution_result,
    render_artifact_comparison,
    render_execution_result,
    render_execution_result_comparison,
    render_execution_result_inspection,
    render_execution_result_verification,
    render_request_artifact,
    verify_execution_result,
)
from samsarix_codegen.cli import main
from samsarix_codegen.context import ContextManifest
from samsarix_codegen.errors import ConfigurationError
from samsarix_codegen.models import ChatResult, ContextFile, PromptRequest, Task
from samsarix_codegen.prompt import build_messages
from samsarix_codegen.provider_check import ProviderCheckReport, render_provider_check
from samsarix_codegen.schema import ContractSchema, load_contract_schema, render_contract_schema


def make_artifact(instruction: str, content: str = "print('hello')\n"):
    context = ContextFile("src/app.py", content, len(content.encode()))
    request = PromptRequest(Task.REVIEW, instruction, files=(context,))
    return create_request_artifact(build_messages(request), request.files)


@pytest.mark.parametrize("kind", list(ContractSchema))
def test_bundled_contract_schemas_are_valid_draft_2020_12(kind: ContractSchema) -> None:
    schema = load_contract_schema(kind)

    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert json.loads(render_contract_schema(kind)) == schema


def test_real_outputs_conform_to_bundled_contract_schemas() -> None:
    base = make_artifact("Review the original")
    target = make_artifact("Review the revision", "print('revised')\n")
    result = ChatResult("Review complete", 100, 20, 120)

    request_payload = json.loads(render_request_artifact(base))
    result_payload = json.loads(render_execution_result(base, result, model="local-model"))
    base_execution_result = parse_execution_result(
        render_execution_result(base, result, model="local-model")
    )
    target_execution_result = parse_execution_result(
        render_execution_result(
            base,
            ChatResult("Different review", 101, 22, 123),
            model="other-model",
        )
    )
    result_comparison_payload = json.loads(
        render_execution_result_comparison(
            compare_execution_results(base_execution_result, target_execution_result),
            output_format="json",
        )
    )
    result_inspection_payload = json.loads(
        render_execution_result_inspection(
            inspect_execution_result(base_execution_result),
            output_format="json",
        )
    )
    result_verification_payload = json.loads(
        render_execution_result_verification(
            verify_execution_result(base, base_execution_result),
            output_format="json",
        )
    )
    comparison_payload = json.loads(
        render_artifact_comparison(
            compare_request_artifacts(base, target),
            output_format="json",
        )
    )
    provider_check_payload = json.loads(
        render_provider_check(
            ProviderCheckReport(
                model="local-model",
                max_output_tokens=64,
                response_chars=11,
                prompt_tokens=12,
                completion_tokens=3,
                total_tokens=15,
            ),
            output_format="json",
        )
    )
    context_manifest_payload = ContextManifest(
        files=("src/app.py", "tests/test_app.py")
    ).to_payload()

    Draft202012Validator(load_contract_schema("request")).validate(request_payload)
    Draft202012Validator(load_contract_schema("result")).validate(result_payload)
    Draft202012Validator(load_contract_schema("result-inspection")).validate(
        result_inspection_payload
    )
    Draft202012Validator(load_contract_schema("result-verification")).validate(
        result_verification_payload
    )
    Draft202012Validator(load_contract_schema("comparison")).validate(comparison_payload)
    Draft202012Validator(load_contract_schema("result-comparison")).validate(
        result_comparison_payload
    )
    Draft202012Validator(load_contract_schema("provider-check")).validate(provider_check_payload)
    Draft202012Validator(load_contract_schema("context-manifest")).validate(
        context_manifest_payload
    )


@pytest.mark.parametrize(
    "files",
    [
        ["src/app.py", "src/app.py"],
        ["../secret.py"],
        ["src\\app.py"],
        ["/absolute.py"],
    ],
)
def test_context_manifest_schema_rejects_unsafe_or_duplicate_paths(files: list[str]) -> None:
    payload = {"schema_version": 1, "files": files}

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema("context-manifest")).validate(payload)


def test_request_schema_rejects_contract_drift() -> None:
    payload = json.loads(render_request_artifact(make_artifact("Review this")))
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema("request")).validate(payload)


def test_result_verification_schema_limits_match_runtime() -> None:
    schema = load_contract_schema("result-verification")
    request_properties = schema["properties"]["request"]["properties"]
    result_response_properties = schema["$defs"]["result_summary"]["properties"]["response"][
        "properties"
    ]

    assert request_properties["messages"]["maximum"] == MAX_ARTIFACT_MESSAGES
    assert request_properties["context_items"]["maximum"] == MAX_ARTIFACT_CONTEXT_ITEMS
    assert result_response_properties["chars"]["maximum"] == MAX_RESULT_BYTES
    assert result_response_properties["bytes"]["maximum"] == MAX_RESULT_BYTES


@pytest.mark.parametrize(
    "contract",
    ["result", "result-inspection", "result-verification", "result-comparison"],
)
def test_result_schemas_reject_noncanonical_model_labels(contract: str) -> None:
    artifact = make_artifact("Review this")
    result = parse_execution_result(
        render_execution_result(artifact, ChatResult("Reviewed"), model="model")
    )
    if contract == "result":
        payload = result.to_payload()
        payload["model"] = " model "
    elif contract == "result-inspection":
        payload = inspect_execution_result(result).to_payload()
        payload["summary"]["model"] = " model "
    elif contract == "result-verification":
        payload = verify_execution_result(artifact, result).to_payload()
        payload["result"]["model"] = " model "
    else:
        payload = compare_execution_results(result, result).to_payload()
        payload["base"]["model"] = " model "

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema(contract)).validate(payload)


def test_schema_command_prints_standalone_machine_readable_contract(capsys) -> None:
    exit_code = main(["schema", "request"])

    captured = capsys.readouterr()
    schema = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert schema["properties"]["schema_version"]["const"] == 2


def test_unknown_library_schema_name_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="unknown contract schema"):
        load_contract_schema("future")
