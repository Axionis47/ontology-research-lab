"""Lossless encoding checks using genuine retained construction evidence.

No model or service runs here. The composition sizing case assembles real
retained components for a size bound, without claiming they form a new kernel.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from oak.bootstrap import FunctionProposal, receipt_documents
from oak.construction_context import compact_construction_context, expand_construction_context
from oak.construction_prompts import stage_prompt
from oak.functions import FunctionSpec
from oak.ontology import schema_json_schema
from oak.operators import operator_contracts
from oak.store import canonical

PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT / ".local/artifacts"
PORTABLE = PROJECT / "tests/fixtures/observer/weather/artifacts"
TASK_IR = "707a8313cc574d60f4ffdcc61c75771338964e51ce4c02b7df6b6e13cca42537"
BEHAVIOR_BANK = "a17f396566ec4e450f60add977fe9f00eb5bcfc171123f2dc0b460d23f441d0f"
REQUIREMENT_INPUTS = "2ec9e760169dedf2dca31bea233d7a3f6022cd67e04c800037daf3b77ab3281a"
RECEIPTS = (
    "25277a2c49c90c254bc627f23341bec9ee5c89b800ea42419a7d713cd3f9914c",
    "b95c36eb06a67e52b7c07dce615456f404a0873a825dde46cb3cf97f9a20ac18",
)


@pytest.fixture
def evidence():
    """Verify immutable source hashes both before and after every test."""
    originals = {}

    def read(identity, root=ARTIFACTS):
        path = root / f"{identity}.json"
        if not path.is_file():
            pytest.skip("Genuine semantic campaign evidence is unavailable")
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == identity
        originals[path] = raw
        return json.loads(raw)["data"]

    yield read
    for path, raw in originals.items():
        assert path.read_bytes() == raw


@pytest.fixture
def schema_inputs(evidence):
    task = evidence(TASK_IR)
    requirements = evidence(REQUIREMENT_INPUTS)
    receipts = [{**evidence(identity), "evidence_id": identity} for identity in RECEIPTS]
    return {
        "surface": requirements["surface"],
        "obligations": requirements["obligations"],
        "requirements": evidence(task["analysis_id"]),
        "task_ir": task,
        "behavior_bank": evidence(BEHAVIOR_BANK),
        "capabilities": requirements["capabilities"],
        "observations": [item for receipt in receipts for item in receipt_documents(receipt)],
        "previous_schema": None,
        "validation_feedback": None,
    }


def request_size(inputs, *, stage="schema.0", prompt="schema", output=None):
    return len(
        canonical(
            {
                "stage": stage,
                "instruction": stage_prompt(prompt),
                "inputs": inputs,
                "output_schema": schema_json_schema() if output is None else output,
            }
        )
    )


def test_exact_failed_schema_payload_roundtrips_below_existing_limit(schema_inputs):
    original_bytes = canonical(schema_inputs)
    compact = compact_construction_context(schema_inputs)
    assert canonical(schema_inputs) == original_bytes
    assert canonical(expand_construction_context(compact)) == original_bytes
    assert request_size(schema_inputs) > 120_000
    assert request_size(compact) < 120_000
    assert request_size(compact) < request_size(schema_inputs) * 0.6
    assert {key: len(value) for key, value in compact["definitions"].items()} == {
        "programs": 70,
        "fields": 3,
        "operations": 20,
        "input_domains": 1,
    }
    # All non-program obligation/behavior metadata, including IDs and frozen
    # denominators, stays inline and identical rather than being summarized.
    for name, collection in (("task_ir", "obligations"), ("behavior_bank", "behaviors")):
        before = schema_inputs[name]
        after = compact["inputs"][name]
        assert {key: value for key, value in before.items() if key != collection} == {
            key: value for key, value in after.items() if key != collection
        }
        assert len(before[collection]) == len(after[collection])
        for original, projected in zip(before[collection], after[collection], strict=True):
            assert {key: value for key, value in original.items() if key != "program"} == {
                key: value for key, value in projected.items() if key != "program"
            }


def test_genuine_composition_components_fit_without_contract_or_graph_elision(
    schema_inputs, evidence
):
    kernel = evidence("2c112be392425277cf1d469ab6c7fd4a98546c3e520452a40802d6ac43c6eaad", PORTABLE)
    graph = evidence("3d22ea885e705dc8d46186e4f3f795653a9182ab7c8142876facb99633e658da", PORTABLE)
    components = {
        **schema_inputs,
        "schema": kernel["schema"],
        "graph": graph,
        "parent_functions": kernel["functions"],
        "operators": operator_contracts(),
        "function_contract": FunctionSpec.model_json_schema(),
        "obligations": [
            item for item in schema_inputs["task_ir"]["obligations"] if item["mandatory"]
        ],
    }
    compact = compact_construction_context(components)
    assert expand_construction_context(compact) == components
    size_args = {
        "stage": "compose.0",
        "prompt": "functions",
        "output": FunctionProposal.model_json_schema(),
    }
    assert request_size(components, **size_args) > 120_000
    assert request_size(compact, **size_args) < 120_000
    for key in ("schema", "graph", "parent_functions", "operators", "function_contract"):
        assert compact["inputs"][key] == components[key]


def test_shared_program_objects_and_input_order_do_not_change_definitions(schema_inputs):
    program = schema_inputs["requirements"]["interpretations"][0]["program"]
    assert program is not None
    payload = {
        "obligations": [{"program": program}, {"program": program}],
        "surface": schema_inputs["surface"],
    }
    original = canonical(payload)
    compact = compact_construction_context(payload)
    assert canonical(payload) == original
    assert canonical(expand_construction_context(compact)) == original
    assert len(compact["definitions"]["programs"]) == 1
    assert (
        compact["inputs"]["obligations"][0]["program"]
        == compact["inputs"]["obligations"][1]["program"]
    )
    reordered = dict(reversed(list(payload.items())))
    assert compact_construction_context(reordered) == compact
    expanded = expand_construction_context(compact)
    expanded["obligations"][0]["program"]["fields"][0]["description"] = "Changed inspection copy"
    assert canonical(payload) == original
    assert canonical(expand_construction_context(compact)) == original


def test_task_program_shaped_source_content_is_never_reinterpreted(schema_inputs):
    program = schema_inputs["requirements"]["interpretations"][0]["program"]
    # Copy a real program into unrelated evidence slots. Its coincidental
    # shape does not authorize interpreting it as a task-semantic container.
    payload = {
        "observations": [{"program": program}],
        "capabilities": [{"input_schema": program}],
        "schema": {"properties": program},
        "validation_feedback": {"task_ir": schema_inputs["task_ir"]},
    }
    compact = compact_construction_context(payload)
    assert all(not value for value in compact["definitions"].values())
    assert compact["inputs"] == payload
    assert expand_construction_context(compact) == payload


def test_changed_or_missing_definitions_fail_expansion(schema_inputs):
    compact = compact_construction_context(schema_inputs)
    damaged = deepcopy(compact)
    identity = next(iter(damaged["definitions"]["fields"]))
    damaged["definitions"]["fields"][identity]["description"] += " changed"
    with pytest.raises(ValueError, match="Changed field definition"):
        expand_construction_context(damaged)
    damaged = deepcopy(compact)
    del damaged["definitions"]["fields"][identity]
    with pytest.raises(ValueError, match="Missing field definition"):
        expand_construction_context(damaged)
    with pytest.raises(ValueError, match="Unsupported construction context encoding"):
        expand_construction_context({**compact, "version": 2})
