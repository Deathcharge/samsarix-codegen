# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""Strict AI review responses and provenance-linked CI exports."""

from __future__ import annotations

import hmac
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Final, cast
from urllib.parse import quote

from samsarix_codegen.artifact import ExecutionResult, RequestArtifact, verify_execution_result
from samsarix_codegen.errors import ArtifactError

REVIEW_RESPONSE_SCHEMA_VERSION = 1
REVIEW_REPORT_SCHEMA_VERSION = 1
MAX_REVIEW_RESPONSE_BYTES = 1024 * 1024
MAX_REVIEW_FINDINGS = 100
MAX_REVIEW_SUMMARY_CHARS = 4_000
MAX_REVIEW_TITLE_CHARS = 200
MAX_REVIEW_MESSAGE_CHARS = 4_000
MAX_REVIEW_PATH_CHARS = 4_096
MAX_REVIEW_LINE = 10_000_000
REVIEW_CATEGORIES: Final = (
    "correctness",
    "security",
    "reliability",
    "maintainability",
    "testing",
)
REVIEW_SEVERITIES: Final = ("error", "warning", "note")
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"

_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_RESPONSE_FIELDS = {"schema_version", "summary", "findings"}
_FINDING_FIELDS = {
    "category",
    "severity",
    "title",
    "message",
    "path",
    "start_line",
    "end_line",
}
_RULE_IDS = {category: f"samsarix-ai-review/{category}" for category in REVIEW_CATEGORIES}
_RULE_DESCRIPTIONS = {
    "correctness": "Potential correctness issue",
    "security": "Potential security issue",
    "reliability": "Potential reliability issue",
    "maintainability": "Potential maintainability issue",
    "testing": "Missing or inadequate test coverage",
}


class _DuplicateReviewKeyError(ValueError):
    """Internal signal for an ambiguous review-response JSON object."""


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """One bounded, source-located AI review finding."""

    category: str
    severity: str
    title: str
    message: str
    path: str
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if self.category not in REVIEW_CATEGORIES:
            raise ArtifactError(
                "review finding category must be one of: " + ", ".join(REVIEW_CATEGORIES)
            )
        if self.severity not in REVIEW_SEVERITIES:
            raise ArtifactError(
                "review finding severity must be one of: " + ", ".join(REVIEW_SEVERITIES)
            )
        title = _normalize_text(
            self.title,
            label="review finding title",
            maximum=MAX_REVIEW_TITLE_CHARS,
            single_line=True,
        )
        message = _normalize_text(
            self.message,
            label="review finding message",
            maximum=MAX_REVIEW_MESSAGE_CHARS,
        )
        path = _normalize_review_path(self.path)
        start_line = _require_line(self.start_line, label="review finding start_line")
        end_line = _require_line(self.end_line, label="review finding end_line")
        if end_line < start_line:
            raise ArtifactError("review finding end_line cannot precede start_line")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "path", path)

    def to_payload(self) -> dict[str, object]:
        """Return the strict provider-facing finding shape."""

        return {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass(frozen=True, slots=True)
class ReviewResponse:
    """A validated structured response returned by a coding model."""

    summary: str
    findings: tuple[ReviewFinding, ...]
    schema_version: int = REVIEW_RESPONSE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REVIEW_RESPONSE_SCHEMA_VERSION or isinstance(
            self.schema_version, bool
        ):
            raise ArtifactError(
                f"unsupported review response schema: {self.schema_version!r}; expected 1"
            )
        summary = _normalize_text(
            self.summary,
            label="review response summary",
            maximum=MAX_REVIEW_SUMMARY_CHARS,
        )
        if not isinstance(self.findings, tuple):
            raise ArtifactError("review response findings must be a tuple")
        if len(self.findings) > MAX_REVIEW_FINDINGS:
            raise ArtifactError(f"review response cannot exceed {MAX_REVIEW_FINDINGS:,} findings")
        if any(not isinstance(finding, ReviewFinding) for finding in self.findings):
            raise ArtifactError("review response contains an invalid finding")
        if len(set(self.findings)) != len(self.findings):
            raise ArtifactError("review response contains duplicate findings")
        object.__setattr__(self, "summary", summary)

    def to_payload(self) -> dict[str, object]:
        """Return the versioned provider-facing response contract."""

        return {
            "schema_version": self.schema_version,
            "summary": self.summary,
            "findings": [finding.to_payload() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class ReviewReport:
    """A structured review linked to the exact validated request and result."""

    request_fingerprint: str
    plan_fingerprint: str | None
    response_sha256: str
    review: ReviewResponse
    schema_version: int = REVIEW_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REVIEW_REPORT_SCHEMA_VERSION or isinstance(
            self.schema_version, bool
        ):
            raise ArtifactError(
                f"unsupported review report schema: {self.schema_version!r}; expected 1"
            )
        if _SHA256_PATTERN.fullmatch(self.request_fingerprint) is None:
            raise ArtifactError("review report request fingerprint is invalid")
        if (
            self.plan_fingerprint is not None
            and _SHA256_PATTERN.fullmatch(self.plan_fingerprint) is None
        ):
            raise ArtifactError("review report plan fingerprint is invalid")
        if _SHA256_PATTERN.fullmatch(self.response_sha256) is None:
            raise ArtifactError("review report response fingerprint is invalid")
        if not isinstance(self.review, ReviewResponse):
            raise ArtifactError("review report requires a validated review response")

    def to_payload(self) -> dict[str, object]:
        """Return a provenance-linked, machine-readable review report."""

        return {
            "schema_version": self.schema_version,
            "provenance": {
                "request_fingerprint": self.request_fingerprint,
                "plan_fingerprint": self.plan_fingerprint,
                "response_sha256": self.response_sha256,
            },
            "review": self.review.to_payload(),
        }


def parse_review_response(raw: str | bytes) -> ReviewResponse:
    """Parse a bounded, duplicate-free review-response version 1 document."""

    text = _decode_review_response(raw)
    try:
        decoded: Any = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_review_keys,
            parse_constant=_reject_nonfinite_number,
        )
    except _DuplicateReviewKeyError as exc:
        raise ArtifactError(str(exc)) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        message = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
        raise ArtifactError(f"review response is not valid JSON: {message}") from exc
    if not isinstance(decoded, dict):
        raise ArtifactError("review response must be a JSON object")
    if set(decoded) != _RESPONSE_FIELDS:
        raise ArtifactError("review response fields do not match schema version 1")
    if decoded.get("schema_version") != REVIEW_RESPONSE_SCHEMA_VERSION or isinstance(
        decoded.get("schema_version"), bool
    ):
        raise ArtifactError(
            f"unsupported review response schema: {decoded.get('schema_version')!r}; expected 1"
        )
    raw_findings = decoded.get("findings")
    if not isinstance(raw_findings, list):
        raise ArtifactError("review response findings must be a JSON array")
    if len(raw_findings) > MAX_REVIEW_FINDINGS:
        raise ArtifactError(f"review response cannot exceed {MAX_REVIEW_FINDINGS:,} findings")
    findings = tuple(_parse_finding(item, index=index) for index, item in enumerate(raw_findings))
    return ReviewResponse(
        summary=cast(str, decoded.get("summary")),
        findings=findings,
        schema_version=cast(int, decoded["schema_version"]),
    )


def verify_review_result(
    artifact: RequestArtifact,
    result: ExecutionResult,
    *,
    expected_request_fingerprint: str | None = None,
    expected_plan_fingerprint: str | None = None,
) -> ReviewReport:
    """Link and validate one structured review result against explicitly selected context."""

    verification = verify_execution_result(artifact, result)
    if expected_request_fingerprint is not None:
        if _SHA256_PATTERN.fullmatch(expected_request_fingerprint) is None:
            raise ArtifactError("expected review request fingerprint is not canonical sha256")
        if not hmac.compare_digest(artifact.fingerprint, expected_request_fingerprint):
            raise ArtifactError(
                "review request fingerprint does not match the expected fingerprint"
            )
    if expected_plan_fingerprint is not None:
        if _SHA256_PATTERN.fullmatch(expected_plan_fingerprint) is None:
            raise ArtifactError("expected review plan fingerprint is not canonical sha256")
        if result.plan_fingerprint is None:
            raise ArtifactError("review result does not record a reviewed execution plan")
        if not hmac.compare_digest(result.plan_fingerprint, expected_plan_fingerprint):
            raise ArtifactError("review plan fingerprint does not match the expected fingerprint")

    review = parse_review_response(result.response_text)
    selected_paths = {record.name for record in artifact.context}
    for finding in review.findings:
        if finding.path not in selected_paths:
            raise ArtifactError(
                f"review finding path was not explicitly selected in the request: {finding.path}"
            )
    return ReviewReport(
        request_fingerprint=artifact.fingerprint,
        plan_fingerprint=result.plan_fingerprint,
        response_sha256=verification.result.response_sha256,
        review=review,
    )


def render_review_report(report: ReviewReport) -> str:
    """Render one canonical provenance-linked review report."""

    if not isinstance(report, ReviewReport):
        raise ArtifactError("review report rendering requires a validated report")
    return json.dumps(report.to_payload(), ensure_ascii=False, indent=2) + "\n"


def render_review_sarif(report: ReviewReport, *, tool_version: str) -> str:
    """Render a review report as GitHub-compatible SARIF 2.1.0."""

    if not isinstance(report, ReviewReport):
        raise ArtifactError("SARIF rendering requires a validated review report")
    if not isinstance(tool_version, str) or _SEMVER_PATTERN.fullmatch(tool_version) is None:
        raise ArtifactError("SARIF tool version must use X.Y.Z")

    rules = [_sarif_rule(category) for category in REVIEW_CATEGORIES]
    rule_indices = {category: index for index, category in enumerate(REVIEW_CATEGORIES)}
    results = [
        _sarif_result(finding, rule_index=rule_indices[finding.category])
        for finding in report.review.findings
    ]
    payload = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Samsarix Codegen AI Review",
                        "informationUri": "https://github.com/Deathcharge/samsarix-codegen",
                        "version": tool_version,
                        "semanticVersion": tool_version,
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "samsarix.requestFingerprint": report.request_fingerprint,
                    "samsarix.planFingerprint": report.plan_fingerprint,
                    "samsarix.responseSha256": report.response_sha256,
                    "samsarix.reviewSummary": report.review.summary,
                    "samsarix.aiGenerated": True,
                },
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _parse_finding(value: object, *, index: int) -> ReviewFinding:
    if not isinstance(value, dict):
        raise ArtifactError(f"review finding {index} must be a JSON object")
    if set(value) != _FINDING_FIELDS:
        raise ArtifactError(f"review finding {index} fields do not match schema version 1")
    return ReviewFinding(
        category=cast(str, value.get("category")),
        severity=cast(str, value.get("severity")),
        title=cast(str, value.get("title")),
        message=cast(str, value.get("message")),
        path=cast(str, value.get("path")),
        start_line=cast(int, value.get("start_line")),
        end_line=cast(int, value.get("end_line")),
    )


def _decode_review_response(raw: str | bytes) -> str:
    if isinstance(raw, bytes):
        if len(raw) > MAX_REVIEW_RESPONSE_BYTES:
            raise ArtifactError(
                f"review response exceeds the {MAX_REVIEW_RESPONSE_BYTES:,}-byte safety limit"
            )
        if b"\x00" in raw:
            raise ArtifactError("binary review responses are not supported")
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArtifactError("review response is not valid UTF-8") from exc
    if not isinstance(raw, str):
        raise ArtifactError("review response must be text or bytes")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ArtifactError("review response text is not valid Unicode") from exc
    if len(encoded) > MAX_REVIEW_RESPONSE_BYTES:
        raise ArtifactError(
            f"review response exceeds the {MAX_REVIEW_RESPONSE_BYTES:,}-byte safety limit"
        )
    if "\x00" in raw:
        raise ArtifactError("binary review responses are not supported")
    return raw


def _normalize_text(value: object, *, label: str, maximum: int, single_line: bool = False) -> str:
    if not isinstance(value, str):
        raise ArtifactError(f"{label} must be text")
    normalized = value.strip()
    if not normalized:
        raise ArtifactError(f"{label} cannot be empty")
    if len(normalized) > maximum:
        raise ArtifactError(f"{label} exceeds {maximum:,} characters")
    if single_line and (
        normalized.splitlines() != [normalized]
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ArtifactError(f"{label} must be one line without control characters")
    for character in normalized:
        codepoint = ord(character)
        if (codepoint < 32 and character not in "\t\r\n") or codepoint == 127:
            raise ArtifactError(f"{label} contains a control character")
    return normalized


def _normalize_review_path(value: object) -> str:
    if not isinstance(value, str):
        raise ArtifactError("review finding path must be text")
    if not value or value != value.strip():
        raise ArtifactError("review finding path must be non-empty canonical text")
    if len(value) > MAX_REVIEW_PATH_CHARS:
        raise ArtifactError(f"review finding path exceeds {MAX_REVIEW_PATH_CHARS:,} characters")
    if "\\" in value or ":" in value:
        raise ArtifactError("review finding path must be a relative POSIX path")
    if value.splitlines() != [value] or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ArtifactError("review finding path contains a control character")
    path = PurePosixPath(value)
    if path.is_absolute() or value == "." or ".." in path.parts or path.as_posix() != value:
        raise ArtifactError("review finding path must be a canonical root-relative POSIX path")
    return value


def _require_line(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_REVIEW_LINE:
        raise ArtifactError(f"{label} must be between 1 and {MAX_REVIEW_LINE:,}")
    return value


def _reject_duplicate_review_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicateReviewKeyError(
                f"review response contains a duplicate JSON field: {key}"
            )
        decoded[key] = value
    return decoded


def _reject_nonfinite_number(value: str) -> None:
    raise ValueError(f"non-finite number {value} is not supported")


def _sarif_rule(category: str) -> dict[str, object]:
    description = _RULE_DESCRIPTIONS[category]
    return {
        "id": _RULE_IDS[category],
        "name": "AIReview" + "".join(part.title() for part in category.split("-")),
        "shortDescription": {"text": description},
        "fullDescription": {
            "text": (
                f"{description} reported by an AI model through the bounded Samsarix review "
                "contract. A developer must verify the finding before acting on it."
            )
        },
        "help": {
            "text": (
                "Treat model-generated review findings as untrusted suggestions and verify them."
            ),
            "markdown": (
                "Treat model-generated review findings as **untrusted suggestions** and verify "
                "them against the cited source and project tests before acting."
            ),
        },
        "defaultConfiguration": {"level": "warning"},
        "properties": {
            "tags": ["ai-generated", category],
            "precision": "low",
            "problem.severity": "warning",
        },
    }


def _sarif_result(finding: ReviewFinding, *, rule_index: int) -> dict[str, object]:
    title_suffix = "" if finding.title.endswith((".", "!", "?")) else "."
    message = f"{finding.title}{title_suffix} {finding.message}"
    return {
        "ruleId": _RULE_IDS[finding.category],
        "ruleIndex": rule_index,
        "level": finding.severity,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": quote(finding.path, safe="/-._~"),
                    },
                    "region": {
                        "startLine": finding.start_line,
                        "endLine": finding.end_line,
                    },
                }
            }
        ],
        "properties": {
            "samsarix.category": finding.category,
            "samsarix.aiGenerated": True,
        },
    }
