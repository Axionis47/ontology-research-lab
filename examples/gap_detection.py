"""Demonstrate a reproducible gap report against a declared max-count contract.

This uses synthetic source evidence. It does not call an LLM or a live source,
implement SHACL, establish source truth, or diagnose an ontology defect.
"""

import argparse
import hashlib
import json
from pathlib import Path


class GapProtocolError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def required_string(record, key):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GapProtocolError("INVALID_INPUT", "Missing or invalid string: " + key)
    return value


def detect(fixture):
    """Evaluate only the specified maximum cardinality, returning a receipt.

    Context and acquisition metadata are supplied by a trusted runtime in a
    real implementation. They are test fixtures here, not authenticated claims.
    """
    for key in ("context", "ontology", "mapping", "evidence"):
        if not isinstance(fixture.get(key), dict):
            raise GapProtocolError("INVALID_INPUT", "Missing object: " + key)
    context = fixture["context"]
    ontology = fixture["ontology"]
    mapping = fixture["mapping"]
    evidence = fixture["evidence"]

    if evidence.get("access") != "granted":
        raise GapProtocolError("ACCESS_DENIED", "Source access was not granted.")
    if evidence.get("operation_status") != "succeeded":
        raise GapProtocolError("SOURCE_UNAVAILABLE", "The acquisition did not succeed.")
    if evidence.get("scope_complete") is not True:
        raise GapProtocolError("NEEDS_SCOPE", "The declared query scope is incomplete.")

    for key in ("run_id", "work_unit_id", "requirement_id", "environment_id", "scope_lease_id"):
        required_string(context, key)
    for key in ("source_id", "source_revision", "observed_at", "acquisition", "query"):
        required_string(evidence, key)
    required_string(ontology, "version")
    required_string(mapping, "version")
    shape = ontology.get("shape")
    record = evidence.get("record")
    if not isinstance(shape, dict) or not isinstance(record, dict):
        raise GapProtocolError("INVALID_INPUT", "A shape and source record are required.")

    shape_id = required_string(shape, "id")
    target_type = required_string(shape, "target_type")
    predicate = required_string(shape, "path")
    subject = required_string(record, "id")
    source_field = required_string(mapping, "source_field")
    if record.get("type") != target_type or mapping.get("target_path") != predicate:
        raise GapProtocolError("MAPPING_MISMATCH", "Mapping or target type does not match the declared check.")
    allowed = context.get("allowed_predicates")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise GapProtocolError("INVALID_INPUT", "An explicit predicate allowlist is required.")
    if predicate not in allowed:
        raise GapProtocolError("NEEDS_SCOPE", "Predicate is outside the scope lease.")

    maximum = shape.get("max_count")
    if type(maximum) is not int or maximum < 0:
        raise GapProtocolError("INVALID_INPUT", "max_count must be a nonnegative integer.")
    if source_field not in record:
        raise GapProtocolError("MISSING_DATA", "The mapped source field is absent.")
    values = record[source_field]
    if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
        raise GapProtocolError("INVALID_INPUT", "The mapped field must be a list of resolved entity IDs.")
    distinct_values = sorted(set(values))

    escaped_field = source_field.replace("~", "~0").replace("/", "~1")
    check = {
        "id": "active-lead-max-count",
        "version": "1",
        "operator": "distinct-count-less-than-or-equal",
        "shape_id": shape_id,
        "focus_entity": subject,
        "relationship": predicate,
        "expected": {"max_count": maximum},
        "observed": {"distinct_count": len(distinct_values), "values": distinct_values},
    }
    pins = {
        "context": dict(context),
        "ontology_version": ontology["version"],
        "ontology_hash": digest(ontology),
        "mapping_version": mapping["version"],
        "mapping_hash": digest(mapping),
        "evidence": {
            "source_id": evidence["source_id"],
            "source_revision": evidence["source_revision"],
            "observed_at": evidence["observed_at"],
            "content_hash": digest(evidence),
            "locator": "/record/" + escaped_field,
        },
    }
    violated = len(distinct_values) > maximum
    return {
        "example_only": True,
        "protocol_version": "gap-report/0.1",
        "receipt_id": digest({"pins": pins, "check": check}),
        "status": "GAP_DETECTED" if violated else "CHECK_PASSED",
        "diagnostic": "CONSTRAINT_VIOLATION" if violated else "NO_MAX_COUNT_VIOLATION",
        "root_cause": "UNDETERMINED" if violated else None,
        "pins": pins,
        "check": check,
        "next_action": "REPRODUCE_AND_TRIAGE" if violated else "CONTINUE_OTHER_REQUIRED_CHECKS",
        "schema_change_authorized": False,
    }


def reproduces(fixture, submitted_receipt):
    """Recompute against pinned inputs. Reproduction does not prove source truth."""
    try:
        return detect(fixture) == submitted_receipt
    except (GapProtocolError, TypeError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", type=Path,
                        default=Path(__file__).with_name("atlas-gap-fixture.json"))
    args = parser.parse_args()
    try:
        fixture = json.loads(args.fixture.read_text())
        result = detect(fixture)
    except GapProtocolError as error:
        print(json.dumps({"status": "BLOCKED", "code": error.code, "message": str(error)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
