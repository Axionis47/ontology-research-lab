"""Attributed requirements and structural coverage checks for construction.

The application derives obligations from literal construction inputs. Models
may interpret those obligations and propose function mappings, but cannot turn
a mapping into evidence of task success. These checks establish references and
accounting only; execution and independent outcome evaluation stay separate.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from oak.task_context import QuerySpec, StrictContract

ObligationID = Annotated[str, Field(pattern=r"^r_[0-9a-f]{18}$")]


class RequirementObligation(StrictContract):
    """One literal request or public requirement, identified by the application."""

    obligation_id: ObligationID
    case_id: str = Field(min_length=1)
    kind: Literal["query", "public_requirement"]
    text: str = Field(min_length=1)
    requirement_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_origin(self) -> RequirementObligation:
        """Keep source positions unambiguous without changing the source text."""
        if not self.case_id.strip() or not self.text.strip():
            raise ValueError("obligations require nonempty case IDs and source text")
        if (self.kind == "public_requirement") != (self.requirement_index is not None):
            raise ValueError("requirement_index is required only for public requirements")
        return self


class RequirementInterpretation(StrictContract):
    """Model interpretation of a supplied obligation, not an evaluation result."""

    obligation_id: ObligationID
    case_id: str = Field(min_length=1)
    interpretation: str = Field(min_length=1)
    required_outputs: list[str] = Field(min_length=1)
    capability_ids: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

    @field_validator("case_id", "interpretation")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        """Reject whitespace-only model descriptions without rewriting them."""
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value

    @field_validator("required_outputs", "capability_ids", "gaps")
    @classmethod
    def nonempty_items(cls, value: list[str]) -> list[str]:
        """Every listed output, reference, or gap must contain actual text."""
        if any(not item.strip() for item in value):
            raise ValueError("list entries must contain non-whitespace characters")
        return value


class RequirementAnalysis(StrictContract):
    """Focused requirement-stage output with explicit unmeasured interpretations."""

    scope_summary: str = Field(min_length=1)
    interpretations: list[RequirementInterpretation] = Field(min_length=1)
    gaps: list[str] = Field(default_factory=list)

    @field_validator("scope_summary")
    @classmethod
    def nonempty_scope(cls, value: str) -> str:
        """A whitespace-only scope cannot explain a construction target."""
        if not value.strip():
            raise ValueError("scope_summary must contain non-whitespace characters")
        return value

    @field_validator("gaps")
    @classmethod
    def nonempty_gaps(cls, value: list[str]) -> list[str]:
        """An unresolved gap must contain a description."""
        if any(not item.strip() for item in value):
            raise ValueError("gaps must contain non-whitespace characters")
        return value


class FunctionCoverage(StrictContract):
    """Proposed function references or an explicit unsupported obligation.

    Semantic matching is model-proposed. The deterministic report checks the
    references and rejects missing, contradictory, or duplicate declarations.
    """

    obligation_id: ObligationID
    function_names: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None


class CoverageCounts(StrictContract):
    """Counts of obligations and mapping entries, with no inferred success rate."""

    obligations: int = Field(ge=0)
    mapped: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    missing: int = Field(ge=0)
    invalid: int = Field(ge=0)
    function_count: int = Field(ge=0)


class CoverageReport(StrictContract):
    """Application-produced mapping audit, explicitly distinct from task scoring."""

    format_version: Literal[1] = 1
    valid: bool
    structurally_complete: bool
    outcome_status: Literal["not_checked"] = "not_checked"
    mappings: list[FunctionCoverage]
    gaps: list[str]
    counts: CoverageCounts
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Function mappings do not establish semantic coverage, executability, or task correctness.",
            "This report covers only the supplied construction obligations, not an entire task family.",
        ]
    )


def requirement_inputs(queries: Sequence[QuerySpec]) -> list[RequirementObligation]:
    """Derive stable short IDs and exact source obligations from selected cases.

    An input query is always an obligation, even when no separate public
    requirements were supplied. The function rejects every non-construction
    query rather than silently dropping it. It neither reads evaluator labels
    nor generates additional cases. IDs are independent of case-list ordering.
    """
    selected = [QuerySpec.model_validate(query.model_dump(mode="json")) for query in queries]
    if not selected:
        raise ValueError("requirement analysis requires at least one construction query")
    if any(query.split != "construction" for query in selected):
        raise ValueError("requirement analysis accepts construction queries only")
    if len({query.id for query in selected}) != len(selected):
        raise ValueError("construction query IDs must be unique")
    obligations: list[RequirementObligation] = []
    for query in sorted(selected, key=lambda item: item.id):
        sources = [("query", None, query.query)] + [
            ("public_requirement", index, text) for index, text in enumerate(query.requirements)
        ]
        for kind, index, text in sources:
            origin = {
                "case_id": query.id,
                "kind": kind,
                "text": text,
                "requirement_index": index,
            }
            encoded = json.dumps(origin, sort_keys=True, ensure_ascii=False).encode("utf-8")
            identity = f"r_{hashlib.sha256(encoded).hexdigest()[:18]}"
            obligations.append(RequirementObligation(obligation_id=identity, **origin))
    _obligation_index(obligations)
    return obligations


def _obligation_index(
    obligations: Sequence[RequirementObligation],
) -> dict[str, RequirementObligation]:
    """Reject ambiguous obligation input instead of losing an item in a map."""
    indexed = {item.obligation_id: item for item in obligations}
    if not indexed or len(indexed) != len(obligations):
        raise ValueError("obligation IDs must be nonempty and unique")
    return indexed


def validate_requirement_analysis(
    analysis: RequirementAnalysis | dict[str, Any],
    obligations: Sequence[RequirementObligation],
    capability_ids: Sequence[str],
) -> RequirementAnalysis:
    """Validate complete source attribution and authorized capability references.

    Passing checks confirms that the model addressed each declared obligation
    exactly once. It cannot establish that the interpretation is semantically
    correct or that the supplied task scope is complete.
    """
    result = RequirementAnalysis.model_validate(analysis)
    expected = _obligation_index(obligations)
    counts = Counter(item.obligation_id for item in result.interpretations)
    if set(counts) != set(expected) or any(count != 1 for count in counts.values()):
        raise ValueError("analysis must interpret every supplied obligation exactly once")
    allowed = set(capability_ids)
    for item in result.interpretations:
        if item.case_id != expected[item.obligation_id].case_id:
            raise ValueError(f"analysis references the wrong case for {item.obligation_id}")
        if not set(item.capability_ids).issubset(allowed):
            raise ValueError(f"analysis references an unknown capability for {item.obligation_id}")
        if len(item.capability_ids) != len(set(item.capability_ids)):
            raise ValueError(f"analysis repeats a capability for {item.obligation_id}")
    return result


def validate_function_coverage(
    coverage: Sequence[FunctionCoverage | dict[str, Any]],
    obligations: Sequence[RequirementObligation],
    functions: Sequence[Mapping[str, Any]],
) -> CoverageReport:
    """Audit proposed mappings without treating them as successful executions.

    Missing, duplicate, unknown, and contradictory mappings return an invalid
    inspectable report. Explicitly unsupported obligations are valid reports
    but not structurally complete candidates. Callers persist the report and
    decide whether to repair or reject; this function never starts execution.
    """
    mappings = [FunctionCoverage.model_validate(item) for item in coverage]
    expected = _obligation_index(obligations)
    names = [item["name"] for item in functions]
    known = set(names)
    counts = Counter(item.obligation_id for item in mappings)
    missing = sorted(set(expected) - set(counts))
    gaps = [f"No function mapping for obligation {identity}" for identity in missing]
    catalog_valid = len(names) == len(known) and all(
        isinstance(name, str) and name for name in names
    )
    if not catalog_valid:
        gaps.append("Function catalog names must be nonempty and unique")
    mapped, unsupported, invalid = 0, 0, 0
    for item in mappings:
        errors: list[str] = []
        if item.obligation_id not in expected:
            errors.append("unknown obligation")
        if counts[item.obligation_id] != 1:
            errors.append("duplicate obligation mapping")
        if len(item.function_names) != len(set(item.function_names)):
            errors.append("duplicate function references")
        if any(not name.strip() or name not in known for name in item.function_names):
            errors.append("unknown or empty function reference")
        has_reason = item.unsupported_reason is not None
        if has_reason and not item.unsupported_reason.strip():
            errors.append("unsupported reason is empty")
        if bool(item.function_names) == has_reason:
            errors.append("provide function references or an unsupported reason, exclusively")
        if errors:
            invalid += 1
            gaps.append(f"Invalid mapping for {item.obligation_id}: {'; '.join(errors)}")
        elif item.function_names:
            mapped += 1
        else:
            unsupported += 1
            gaps.append(f"Unsupported obligation {item.obligation_id}: {item.unsupported_reason}")
    valid = catalog_valid and not missing and not invalid
    return CoverageReport(
        valid=valid,
        structurally_complete=valid and not unsupported,
        mappings=mappings,
        gaps=gaps,
        counts=CoverageCounts(
            obligations=len(expected),
            mapped=mapped,
            unsupported=unsupported,
            missing=len(missing),
            invalid=invalid,
            function_count=len(functions),
        ),
    )
