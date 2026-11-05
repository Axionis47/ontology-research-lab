"""Portable checks of actual Lean, independent of benchmark installations.

The input is an authored formal program contract, not fabricated task evidence,
an MCP reply, or a claimed model generation. No graph or provider is simulated.
"""

from __future__ import annotations

import os
from copy import deepcopy

import pytest

from oak.preservation import check_lean, lower_function


def _formal_plans():
    schema = {
        "name": "ProofContract",
        "entity_types": {
            "Record": {
                "primary_key": "key",
                "properties": {"key": {"type": "string", "required": True}},
            }
        },
        "relations": {},
    }
    before = {
        "name": "lookup_record",
        "description": "Formal contract used to check compiler-preservation templates.",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "array"},
        "steps": [
            {"id": "records", "operator": "lookup_entities", "args": {"entity_types": ["Record"]}}
        ],
        "result": {"$step": "records"},
    }
    after = deepcopy(before)
    after["steps"][0]["id"] = "renamed_records"
    after["result"]["$step"] = "renamed_records"
    return lower_function(before, schema), lower_function(after, schema)


def test_actual_pinned_lean_checks_instantiated_preservation():
    before, after = _formal_plans()
    receipt = check_lean({"renamed_lookup": {"before": before, "after": after}})
    if receipt["status"] != "checked" and os.environ.get("OAK_REQUIRE_LEAN") != "1":
        if receipt.get("reason") in {
            "Pinned Lean checker is unavailable",
            "Lean version does not match the pinned toolchain",
        }:
            pytest.skip(receipt["reason"])
    assert receipt["status"] == "checked", receipt
    assert receipt["toolchain"] == "leanprover/lean4:v4.35.0"
    assert receipt["axioms"] == []
    assert receipt["module_exit_code"] == receipt["exit_code"] == 0
    assert "canonical_preservation" in receipt["source"]

    # A genuinely different term cannot be accepted by the fixed equality
    # template. This invokes the real checker again, not a stubbed response.
    unequal = after.model_copy(deep=True)
    unequal.steps[0].arguments["top_k"] = 1
    rejected = check_lean({"changed_lookup": {"before": before, "after": unequal}})
    assert rejected["status"] == "unknown"
    assert rejected["exit_code"] != 0
    assert rejected["reason"] == "Proof compilation or dependency audit failed"
