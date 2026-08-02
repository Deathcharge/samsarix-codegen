# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Access to the versioned JSON Schemas shipped with Samsarix Codegen."""

from __future__ import annotations

import json
from enum import Enum
from importlib.resources import files
from typing import Any, cast

from samsarix_codegen.errors import ConfigurationError


class ContractSchema(str, Enum):
    """Public machine-readable contract schemas."""

    REQUEST = "request"
    RESULT = "result"
    COMPARISON = "comparison"
    RESULT_INSPECTION = "result-inspection"
    RESULT_VERIFICATION = "result-verification"
    RESULT_COMPARISON = "result-comparison"
    PROVIDER_CHECK = "provider-check"
    CONTEXT_MANIFEST = "context-manifest"
    RESULT_POLICY = "result-policy"
    EXECUTION_PLAN = "execution-plan"
    EXECUTION_PLAN_VERIFICATION = "execution-plan-verification"
    EXECUTION_EVIDENCE = "execution-evidence"


_SCHEMA_FILES = {
    ContractSchema.REQUEST: "request-artifact-v2.schema.json",
    ContractSchema.RESULT: "execution-result-v2.schema.json",
    ContractSchema.COMPARISON: "artifact-comparison-v1.schema.json",
    ContractSchema.RESULT_INSPECTION: "execution-result-inspection-v2.schema.json",
    ContractSchema.RESULT_VERIFICATION: "execution-result-verification-v2.schema.json",
    ContractSchema.RESULT_COMPARISON: "execution-result-comparison-v2.schema.json",
    ContractSchema.PROVIDER_CHECK: "provider-check-v1.schema.json",
    ContractSchema.CONTEXT_MANIFEST: "context-manifest-v1.schema.json",
    ContractSchema.RESULT_POLICY: "execution-result-policy-v1.schema.json",
    ContractSchema.EXECUTION_PLAN: "execution-plan-v1.schema.json",
    ContractSchema.EXECUTION_PLAN_VERIFICATION: "execution-plan-verification-v1.schema.json",
    ContractSchema.EXECUTION_EVIDENCE: "execution-evidence-verification-v1.schema.json",
}


def load_contract_schema(kind: ContractSchema | str) -> dict[str, Any]:
    """Load one bundled JSON Schema as a new dictionary."""

    try:
        selected = kind if isinstance(kind, ContractSchema) else ContractSchema(kind)
    except ValueError as exc:
        choices = ", ".join(item.value for item in ContractSchema)
        raise ConfigurationError(f"unknown contract schema {kind!r}; choose {choices}") from exc

    resource = files("samsarix_codegen.schemas").joinpath(_SCHEMA_FILES[selected])
    try:
        decoded = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"bundled {selected.value} contract schema is unavailable") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"bundled {selected.value} contract schema is not a JSON object")
    return cast(dict[str, Any], decoded)


def render_contract_schema(kind: ContractSchema | str) -> str:
    """Render a bundled JSON Schema deterministically."""

    return json.dumps(load_contract_schema(kind), ensure_ascii=False, indent=2) + "\n"
