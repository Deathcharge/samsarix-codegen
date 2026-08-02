# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from samsarix_codegen.artifact import (
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    parse_execution_result,
    render_artifact_comparison,
    render_execution_result,
    render_execution_result_comparison,
    render_request_artifact,
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


@pytest.mark.parametrize("contract", ["result", "result-comparison"])
def test_result_schemas_reject_noncanonical_model_labels(contract: str) -> None:
    artifact = make_artifact("Review this")
    result = parse_execution_result(
        render_execution_result(artifact, ChatResult("Reviewed"), model="model")
    )
    if contract == "result":
        payload = result.to_payload()
        payload["model"] = " model "
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
