# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from samsarix_codegen.artifact import (
    compare_request_artifacts,
    create_request_artifact,
    render_artifact_comparison,
    render_execution_result,
    render_request_artifact,
)
from samsarix_codegen.cli import main
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

    Draft202012Validator(load_contract_schema("request")).validate(request_payload)
    Draft202012Validator(load_contract_schema("result")).validate(result_payload)
    Draft202012Validator(load_contract_schema("comparison")).validate(comparison_payload)
    Draft202012Validator(load_contract_schema("provider-check")).validate(provider_check_payload)


def test_request_schema_rejects_contract_drift() -> None:
    payload = json.loads(render_request_artifact(make_artifact("Review this")))
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema("request")).validate(payload)


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
