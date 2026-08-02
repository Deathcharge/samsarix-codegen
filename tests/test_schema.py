# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from samsarix_codegen.artifact import (
    MAX_ARTIFACT_CONTEXT_ITEMS,
    MAX_ARTIFACT_MESSAGES,
    MAX_RESULT_BYTES,
    MAX_RESULT_POLICY_TOKENS,
    ExecutionResultPolicy,
    compare_execution_results,
    compare_request_artifacts,
    create_request_artifact,
    inspect_execution_result,
    parse_execution_result,
    parse_request_artifact,
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
from samsarix_codegen.execution_evidence import verify_execution_evidence
from samsarix_codegen.execution_plan import (
    create_execution_plan,
    parse_execution_plan,
    render_execution_plan,
    render_execution_plan_verification,
    verify_execution_plan,
)
from samsarix_codegen.models import (
    MAX_ENDPOINT_CHARS,
    MAX_ESTIMATED_INPUT_TOKENS,
    MAX_PROVIDER_OUTPUT_TOKENS,
    MAX_PROVIDER_TIMEOUT_SECONDS,
    ChatResult,
    ContextFile,
    PromptRequest,
    ProviderConfig,
    Task,
)
from samsarix_codegen.prompt import build_messages
from samsarix_codegen.provider_check import ProviderCheckReport, render_provider_check
from samsarix_codegen.result_policy import (
    fingerprint_execution_result_policy,
    load_execution_result_policy,
    render_execution_result_policy,
)
from samsarix_codegen.schema import ContractSchema, load_contract_schema, render_contract_schema
from samsarix_codegen.self_check import run_self_check


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
    result_policy_payload = json.loads(
        render_execution_result_policy(
            ExecutionResultPolicy(
                expected_model="local-model",
                max_response_bytes=100_000,
                max_total_tokens=1_000,
                schema_version=2,
            )
        )
    )
    execution_plan = create_execution_plan(
        base,
        ProviderConfig(
            "https://models.example.com/v1",
            "local-model",
            timeout_seconds=45,
            max_output_tokens=512,
        ),
        max_estimated_input_tokens=1_000,
    )
    execution_plan_payload = json.loads(render_execution_plan(execution_plan))
    execution_plan_verification_payload = json.loads(
        render_execution_plan_verification(
            verify_execution_plan(base, execution_plan), output_format="json"
        )
    )
    plan_bound_result = parse_execution_result(
        render_execution_result(
            base,
            ChatResult(
                "Plan-bound review",
                100,
                20,
                120,
                response_model="served-model",
            ),
            model=execution_plan.model,
            plan_fingerprint=execution_plan.fingerprint,
        )
    )
    execution_evidence_payload = verify_execution_evidence(
        base, execution_plan, plan_bound_result
    ).to_payload()
    self_check_payload = run_self_check().to_dict()

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
    Draft202012Validator(load_contract_schema("result-policy")).validate(result_policy_payload)
    Draft202012Validator(load_contract_schema("execution-plan")).validate(execution_plan_payload)
    Draft202012Validator(load_contract_schema("execution-plan-verification")).validate(
        execution_plan_verification_payload
    )
    Draft202012Validator(load_contract_schema("execution-evidence")).validate(
        execution_evidence_payload
    )
    Draft202012Validator(load_contract_schema("self-check")).validate(self_check_payload)


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


def test_result_policy_schema_limits_match_runtime() -> None:
    schema = load_contract_schema("result-policy")

    assert schema["properties"]["max_response_bytes"]["maximum"] == MAX_RESULT_BYTES
    for field in ("max_prompt_tokens", "max_completion_tokens", "max_total_tokens"):
        assert schema["properties"][field]["maximum"] == MAX_RESULT_POLICY_TOKENS


@pytest.mark.parametrize("contract", ["execution-plan", "execution-plan-verification"])
def test_execution_plan_schema_limits_match_runtime(contract: str) -> None:
    schema = load_contract_schema(contract)
    provider = schema["$defs"]["provider"]["properties"]
    budgets = schema["properties"]["budgets"]["properties"]

    assert provider["endpoint"]["maxLength"] == MAX_ENDPOINT_CHARS
    assert provider["timeout_seconds"]["maximum"] == MAX_PROVIDER_TIMEOUT_SECONDS
    assert provider["max_output_tokens"]["maximum"] == MAX_PROVIDER_OUTPUT_TOKENS
    assert budgets["max_estimated_input_tokens"]["maximum"] == MAX_ESTIMATED_INPUT_TOKENS


def test_execution_plan_schemas_share_the_same_provider_contract() -> None:
    plan_provider = load_contract_schema("execution-plan")["$defs"]["provider"]
    verification_provider = load_contract_schema("execution-plan-verification")["$defs"]["provider"]

    assert verification_provider == plan_provider


def test_execution_plan_example_is_schema_valid_and_internally_consistent() -> None:
    example = Path(__file__).resolve().parents[1] / "examples" / "execution-plan-v1.json"
    payload = json.loads(example.read_text(encoding="utf-8"))

    Draft202012Validator(load_contract_schema("execution-plan")).validate(payload)
    plan = parse_execution_plan(example.read_bytes())
    assert plan.fingerprint == payload["plan_fingerprint"]


def test_checked_in_execution_chain_is_runnable_and_matches_evidence(capsys) -> None:
    repository = Path(__file__).resolve().parents[1]
    examples = repository / "examples"
    request_path = examples / "execution-request-v2.json"
    plan_path = examples / "execution-plan-v1.json"
    result_path = examples / "structured-execution-result-v2.json"
    policy_path = examples / "structured-result-policy-v2.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    evidence = json.loads((examples / "execution-evidence-v3.json").read_text(encoding="utf-8"))
    policy = load_execution_result_policy(policy_path)

    Draft202012Validator(load_contract_schema("request")).validate(request)
    Draft202012Validator(load_contract_schema("execution-plan")).validate(plan)
    Draft202012Validator(load_contract_schema("result")).validate(result)
    Draft202012Validator(load_contract_schema("execution-evidence")).validate(evidence)

    build_exit_code = main(
        [
            "build",
            "Review greet for correctness, edge cases, and maintainability. "
            "Return concise findings.",
            "--task",
            "review",
            "--root",
            str(repository),
            "--file",
            "examples/sample.py",
            "--max-estimated-input-tokens",
            "5000",
            "--format",
            "json",
        ]
    )
    build_output = capsys.readouterr()
    assert build_exit_code == 0
    assert build_output.err == ""
    assert json.loads(build_output.out) == request

    artifact = parse_request_artifact(request_path.read_bytes())
    parsed_plan = parse_execution_plan(plan_path.read_bytes())
    parsed_result = parse_execution_result(result_path.read_bytes())
    verification = verify_execution_evidence(
        artifact,
        parsed_plan,
        parsed_result,
        expected_plan_fingerprint=plan["plan_fingerprint"],
        result_policy=policy,
        expected_policy_fingerprint=fingerprint_execution_result_policy(policy),
    )
    assert verification.to_payload() == evidence

    exit_code = main(
        [
            "verify-execution",
            str(request_path),
            str(plan_path),
            str(result_path),
            "--expect-plan-fingerprint",
            plan["plan_fingerprint"],
            "--policy",
            str(policy_path),
            "--expect-policy-fingerprint",
            fingerprint_execution_result_policy(policy),
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == evidence
    response = result["response"]["text"]
    assert evidence["result"]["response"]["sha256"] == (
        "sha256:" + hashlib.sha256(response.encode("utf-8")).hexdigest()
    )

    legacy_schema = json.loads(
        (
            repository
            / "src/samsarix_codegen/schemas/execution-evidence-verification-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    legacy_evidence = json.loads(
        (examples / "execution-evidence-v1.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(legacy_schema)
    Draft202012Validator(legacy_schema).validate(legacy_evidence)
    evidence_v2_schema = json.loads(
        (
            repository
            / "src/samsarix_codegen/schemas/execution-evidence-verification-v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    evidence_v2 = json.loads((examples / "execution-evidence-v2.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(evidence_v2_schema)
    Draft202012Validator(evidence_v2_schema).validate(evidence_v2)
    policy_v1_schema = json.loads(
        (
            repository / "src/samsarix_codegen/schemas/execution-result-policy-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    policy_v1 = json.loads((examples / "result-policy-v1.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(policy_v1_schema)
    Draft202012Validator(policy_v1_schema).validate(policy_v1)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.update(unexpected=True),
        lambda payload: payload["provider"].update(model=" model-a"),
        lambda payload: payload["provider"].update(endpoint="http://remote.example.com/v1"),
        lambda payload: payload["provider"].update(endpoint="http://127.evil.com/v1"),
        lambda payload: payload["provider"].update(
            endpoint="https://user:pass@models.example.com/v1"
        ),
        lambda payload: payload["provider"].update(timeout_seconds=0),
        lambda payload: payload["provider"].update(max_output_tokens=32_769),
        lambda payload: payload["budgets"].update(max_estimated_input_tokens=2_000_001),
    ],
)
def test_execution_plan_schema_rejects_contract_drift(mutator) -> None:
    artifact = make_artifact("Review")
    plan = create_execution_plan(
        artifact, ProviderConfig("https://models.example.com/v1", "model-a")
    )
    payload = json.loads(render_execution_plan(plan))
    mutator(payload)

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema("execution-plan")).validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2},
        {"schema_version": 2, "unexpected": True},
        {"schema_version": 2, "expected_model": None},
        {"schema_version": 2, "expected_model": " model-a"},
        {"schema_version": 2, "max_response_bytes": 0},
        {"schema_version": 2, "max_response_bytes": MAX_RESULT_BYTES + 1},
        {"schema_version": 2, "max_total_tokens": -1},
        {"schema_version": 2, "max_total_tokens": True},
        {"schema_version": 2, "max_total_tokens": MAX_RESULT_POLICY_TOKENS + 1},
        {"schema_version": 2, "response_format": "json"},
        {"schema_version": 2, "required_json_keys": ["answer"]},
        {"schema_version": 2, "response_format": "json-object", "required_json_keys": []},
        {
            "schema_version": 2,
            "response_format": "json-object",
            "required_json_keys": ["answer", "answer"],
        },
        {"schema_version": 2, "response_format": "json-object", "json_key_types": {}},
        {
            "schema_version": 2,
            "response_format": "json-object",
            "json_key_types": {"answer": "date"},
        },
    ],
)
def test_result_policy_schema_rejects_contract_drift(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema("result-policy")).validate(payload)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.pop("result_policy"),
        lambda payload: payload.update(result_policy={}),
        lambda payload: payload["result_policy"].pop("fingerprint"),
        lambda payload: payload["result_policy"]["rules"].update(unexpected=True),
        lambda payload: payload["result_policy"]["rules"].update(expected_model=None),
        lambda payload: payload["result"].pop("response_structure"),
        lambda payload: payload["result"]["response_structure"].update(format="json"),
        lambda payload: payload["result"]["response_structure"].update(top_level_keys=257),
    ],
)
def test_execution_evidence_schema_rejects_policy_contract_drift(mutator) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (repository / "examples/execution-evidence-v3.json").read_text(encoding="utf-8")
    )
    mutator(payload)

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema("execution-evidence")).validate(payload)


@pytest.mark.parametrize(
    "contract",
    [
        "result",
        "result-inspection",
        "result-verification",
        "result-comparison",
        "execution-evidence",
    ],
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
    elif contract == "result-comparison":
        payload = compare_execution_results(result, result).to_payload()
        payload["base"]["model"] = " model "
    else:
        plan = create_execution_plan(
            artifact, ProviderConfig("https://models.example.com/v1", "model")
        )
        plan_result = parse_execution_result(
            render_execution_result(
                artifact,
                ChatResult("Reviewed", response_model="served-model"),
                model="model",
                plan_fingerprint=plan.fingerprint,
            )
        )
        payload = verify_execution_evidence(artifact, plan, plan_result).to_payload()
        payload["provider"]["response_model"] = " model "

    with pytest.raises(ValidationError):
        Draft202012Validator(load_contract_schema(contract)).validate(payload)


def test_schema_command_prints_standalone_machine_readable_contract(capsys) -> None:
    exit_code = main(["schema", "request"])

    captured = capsys.readouterr()
    schema = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert schema["properties"]["schema_version"]["const"] == 2


def test_schema_command_exports_latest_policy_and_evidence_versions(capsys) -> None:
    policy_exit = main(["schema", "result-policy"])
    policy_output = capsys.readouterr()
    evidence_exit = main(["schema", "execution-evidence"])
    evidence_output = capsys.readouterr()

    assert policy_exit == evidence_exit == 0
    assert policy_output.err == evidence_output.err == ""
    assert json.loads(policy_output.out)["properties"]["schema_version"]["const"] == 2
    assert json.loads(evidence_output.out)["properties"]["schema_version"]["const"] == 3


def test_unknown_library_schema_name_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="unknown contract schema"):
        load_contract_schema("future")
