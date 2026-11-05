"""Offline, inherited regression over actual executions and shared revision adapters.

Proposal is an explicit construction operation. The replay functions below have
no model or transport dependency and execute current functions, never answers.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
from copy import deepcopy
from pathlib import Path

import owlready2
from pydantic import Field

from oak.functions import execute_function, validate_functions
from oak.migration import MigrationSpec, migrate_graph
from oak.ontology import parse_schema, validate_ontology
from oak.preservation import runtime_dependencies
from oak.regression import AdapterSpec, validate_adapter
from oak.replay_contracts import (
    ComparisonContract,
    FirstDifference,
    RecordedCall,
    ReplayBank,
    ReplayBankReport,
    ReplayCase,
    ReplayContract,
    ReplayReport,
)
from oak.store import canonical


class ReplayGap(ValueError):
    """Retained evidence does not support the requested offline computation."""


class AdapterEdge(ReplayContract):
    """One shared M/A/B package bound to the actual parent-child revision edge."""

    parent_id: str
    child_id: str
    migration: MigrationSpec = Field(default_factory=MigrationSpec)
    call_adapter: AdapterSpec
    step_mappings: dict[str, dict[str, str]] = Field(default_factory=dict)
    proposal_ref: str | None = None


def execution_dependencies() -> dict[str, str]:
    """Only code and packages that define executed computation pin baselines."""
    return {
        k: v
        for k, v in runtime_dependencies().items()
        if k in {"executor", "operators", "ontology", "runtime_lock"}
    }


def replay_dependencies() -> dict[str, str]:
    pins = execution_dependencies()
    for name in ("historical_replay.py", "migration.py", "regression.py", "replay_contracts.py"):
        pins[name] = hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    root = Path(__file__).resolve().parents[2]
    lock = root / "toolchain-java.lock.json"
    pins["java_lock"] = (
        hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else "missing"
    )
    try:
        config = json.loads(lock.read_text())
        java = root / config["install_directory"] / config["java_relative_path"]
        pins["java_binary"] = hashlib.sha256(java.read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError):
        pins["java_binary"] = "unavailable"
    jar = Path(owlready2.__file__).parent / "hermit" / "HermiT.jar"
    pins["hermit_jar"] = (
        hashlib.sha256(jar.read_bytes()).hexdigest() if jar.is_file() else "missing"
    )
    return pins


def _init(store):
    with store.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS replay_banks (kernel_id TEXT PRIMARY KEY, bank_id TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS replay_edges (child_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, edge_id TEXT NOT NULL)"
        )


def _kernel(store, identity):
    return {**store.get(identity), "id": identity}


def _bank(store, kernel_id):
    _init(store)
    rows = store.rows("SELECT bank_id FROM replay_banks WHERE kernel_id=?", (kernel_id,))
    if not rows:
        raise ReplayGap(f"Kernel {kernel_id} has no sealed protected bank")
    identity = rows[0]["bank_id"]
    bank = ReplayBank.model_validate(store.get(identity))
    if bank.kernel_id != kernel_id:
        raise ReplayGap("Protected bank belongs to another kernel")
    return identity, bank


def _validated_receipt(store, kernel, receipt_id, inputs):
    """Authenticate an actual retained receipt against its frozen source request."""
    receipt = store.get(receipt_id)
    contracts = [
        tool
        for tool in kernel.get("catalog", {}).get("tools", [])
        if tool.get("id") == inputs["capability"]
    ]
    if (
        len(contracts) != 1
        or receipt.get("status") != "completed"
        or receipt.get("tool_call_attempted") is not True
        or receipt.get("capability_id") != inputs["capability"]
        or canonical(receipt.get("args")) != canonical(inputs["arguments"])
        or not receipt.get("contract_id")
        or receipt["contract_id"] != contracts[0].get("contract_id")
        or receipt.get("observed_contract_id", receipt["contract_id"]) != receipt["contract_id"]
        or not receipt.get("started_at")
        or not receipt.get("finished_at")
        or "output" not in receipt
    ):
        raise ReplayGap("Retained receipt arguments, capability contract or attribution differ")
    refs = [receipt_id]
    for name in ("dispatch_evidence_id", "live_catalog_evidence_id"):
        if receipt.get(name):
            evidence = store.get(receipt[name])
            if name == "dispatch_evidence_id" and any(
                canonical(evidence.get(key)) != canonical(receipt.get(key))
                for key in (
                    "capability_id",
                    "args",
                    "contract_id",
                    "observed_contract_id",
                    "started_at",
                )
            ):
                raise ReplayGap("Completed receipt differs from its actual saved dispatch")
            if name == "live_catalog_evidence_id":
                observed = [
                    tool
                    for tool in evidence.get("tools", [])
                    if tool.get("id") == inputs["capability"]
                ]
                if len(observed) != 1 or observed[0].get("contract_id") != receipt["contract_id"]:
                    raise ReplayGap("Receipt contract differs from its saved live contract check")
            refs.append(receipt[name])
    return receipt, refs


def _receipt_at_boundary(store, kernel, step):
    """Authenticate retained acquisition inputs without dispatching a tool."""
    inputs, output = step.get("inputs", {}), step.get("output", {})
    if step.get("operator") != "invoke_capability" or set(inputs) != {"capability", "arguments"}:
        raise ReplayGap("Retained acquisition requires its exact capability and arguments")
    if not isinstance(output, dict) or set(output) != {
        "entities",
        "entities_by_type",
        "receipt_id",
    }:
        raise ReplayGap("Unsupported historical acquisition output contract")
    receipt, refs = _validated_receipt(store, kernel, output["receipt_id"], inputs)
    after = store.get(step["graph_after_ref"])
    by_id = {node["id"]: node for node in after["nodes"]}
    entities = output["entities"]
    if not isinstance(entities, list) or any(
        canonical(by_id.get(node.get("id"))) != canonical(node) for node in entities
    ):
        raise ReplayGap("Acquisition records do not match their retained materialized graph")
    grouped = {
        name: [node for node in entities if node["type"] == name]
        for name in kernel["schema"]["entity_types"]
    }
    if canonical(grouped) != canonical(output["entities_by_type"]):
        raise ReplayGap("Acquisition type grouping differs from its actual retained records")
    return receipt, refs


def _capture_source_refs(store, capture, kernel):
    """Follow immutable source attribution, without rediscovering live evidence.

    Older cases can rely on references already pinned by their origin kernel.
    New seals also retain these references directly for inspection.
    """
    refs, documents = [], {}
    for container in (kernel, kernel.get("evidence", {})):
        for field in ("corpus_id", "documents_id"):
            identity = container.get(field)
            if not identity:
                continue
            data = store.get(identity)
            refs.append(identity)
            if field == "documents_id":
                if not isinstance(data, list):
                    raise ReplayGap("Frozen documents reference is not a document collection")
                for document in data:
                    key = document.get("document_id", document.get("id"))
                    if not isinstance(key, str) or not key:
                        raise ReplayGap("Frozen source document lacks its recorded identity")
                    if key in documents and canonical(documents[key]) != canonical(document):
                        raise ReplayGap("Frozen source document identities conflict")
                    documents[key] = document

    explicit_sources = set()
    for step in capture["steps"]:
        if step["operator"] == "invoke_capability":
            for entity in step["output"]["entities"]:
                explicit_sources.update(canonical(source) for source in entity.get("sources", []))
    graph_refs = {capture["initial_graph_ref"], capture["final_graph_ref"]}
    for step in capture["steps"]:
        graph_refs.update(
            step[key]
            for key in ("input_graph_ref", "graph_after_ref", "before_materialization_graph_ref")
            if step.get(key)
        )
    sources = {}
    for identity in graph_refs:
        graph = store.get(identity)
        for record in [*graph["nodes"], *graph["edges"]]:
            for source in record.get("sources", []):
                if str(source.get("source_ref", "")).startswith("mcp:"):
                    sources[canonical(source)] = source
        for document_id in graph.get("source_document_ids", []):
            document = documents.get(document_id)
            if document and str(document.get("locator", "")).startswith("mcp:"):
                source = {"document_id": document_id, "source_ref": document["locator"]}
                sources[canonical(source)] = source
            elif not document and kernel.get("acquisition_bindings"):
                match = re.fullmatch(r"([0-9a-f]{64})-([0-9]+)", document_id)
                if not match:
                    raise ReplayGap("Demand source document lacks supported receipt attribution")
                receipt = store.get(match[1])
                offset = int(match[2])
                source = {
                    "document_id": document_id,
                    "source_ref": f"mcp:{receipt.get('capability_id')}#characters={offset}:{offset + 2500}",
                }
                sources[canonical(source)] = source

    from oak.bootstrap import receipt_documents
    from oak.materialization import prepare_bound_materialization

    function = next(item for item in kernel["functions"] if item["name"] == capture["function"])
    requests = (
        prepare_bound_materialization(
            kernel["schema"],
            function,
            capture["args"],
            kernel.get("acquisition_bindings", []),
            kernel.get("catalog", {}).get("tools", []),
        ).acquisitions
        if kernel.get("acquisition_bindings")
        else []
    )
    matched_requests = set()
    for encoded, source in sources.items():
        if encoded in explicit_sources:
            continue
        document = documents.get(source["document_id"])
        receipt_id = document.get("source_id") if document else None
        if not receipt_id:
            match = re.fullmatch(r"([0-9a-f]{64})-([0-9]+)", source["document_id"])
            if not match:
                raise ReplayGap("MCP materialization lacks an exact retained source receipt")
            receipt_id = match[1]
        receipt = store.get(receipt_id)
        receipt, receipt_refs = _validated_receipt(
            store,
            kernel,
            receipt_id,
            {"capability": receipt.get("capability_id"), "arguments": receipt.get("args")},
        )
        generated = receipt_documents({**receipt, "evidence_id": receipt_id})
        matching = [
            item
            for item in generated
            if item["document_id"] == source["document_id"]
            and item["locator"] == source["source_ref"]
        ]
        if len(matching) != 1 or (document and canonical(document) != canonical(matching[0])):
            raise ReplayGap(
                "Materialized source provenance differs from its actual receipt document"
            )
        refs.extend(receipt_refs)
        for index, request in enumerate(requests):
            if (
                request.capability == receipt["capability_id"]
                and canonical(request.arguments) == canonical(receipt["args"])
                and request.contract_id == receipt["contract_id"]
            ):
                matched_requests.add(index)
    if len(matched_requests) != len(requests):
        raise ReplayGap(
            "Demand materialization lacks retained receipts matching its frozen requests"
        )
    return list(dict.fromkeys(refs))


def _validated_capture(store, capture_id, kernel, *, include_source_refs=False):
    """Check immutable boundary records and their graph/function attribution."""
    capture = store.get(capture_id)
    if capture.get("status") != "completed" or "value" not in capture:
        raise ReplayGap("Only successful captured computations can be sealed or replayed")
    input_keys = (
        "format_version",
        "function",
        "args",
        "schema_ref",
        "functions_ref",
        "initial_graph_ref",
        "runtime_dependencies",
    )
    if canonical(store.get(capture["input_manifest_ref"])) != canonical(
        {key: capture[key] for key in input_keys}
    ):
        raise ReplayGap("Capture differs from the inputs persisted before execution")
    if canonical(store.get(capture["schema_ref"])) != canonical(kernel["schema"]):
        raise ReplayGap("Captured schema is not the origin kernel schema")
    captured = validate_functions(store.get(capture["functions_ref"]), kernel["schema"])
    actual = validate_functions(kernel["functions"], kernel["schema"])
    if [f.model_dump() for f in captured] != [f.model_dump() for f in actual]:
        raise ReplayGap("Captured functions are not the origin kernel catalog")
    selected = next(
        (function for function in captured if function.name == capture["function"]), None
    )
    if selected is None or len(selected.steps) != len(capture["steps"]):
        raise ReplayGap("Capture does not contain the complete selected function execution")

    def digest(value):
        return hashlib.sha256(canonical(value)).hexdigest()

    previous = store.get(capture["initial_graph_ref"])
    dependencies = capture["dependencies"]
    if (
        dependencies.get("graph_sha256") != digest(previous)
        or dependencies.get("schema_sha256") != digest(kernel["schema"])
        or dependencies.get("function_sha256") != digest(selected.model_dump(mode="json"))
    ):
        raise ReplayGap("Capture dependency hashes do not identify its actual execution inputs")
    refs = []
    for expected, step in zip(selected.steps, capture["steps"], strict=True):
        if (
            step.get("id") != expected.id
            or step.get("operator") != expected.operator
            or step.get("status") != "completed"
        ):
            raise ReplayGap("Recorded operator order or completion differs from the function")
        saved_step = store.get(step["step_result_ref"])
        if canonical(saved_step) != canonical(
            {key: value for key, value in step.items() if key != "step_result_ref"}
        ):
            raise ReplayGap("Step capture differs from its independently retained execution record")
        incoming = store.get(step["input_graph_ref"])
        before = (
            store.get(step["before_materialization_graph_ref"])
            if step.get("before_materialization_graph_ref")
            else incoming
        )
        after = store.get(step["graph_after_ref"])
        if canonical(previous) != canonical(before):
            raise ReplayGap("Captured graph state is discontinuous between operator boundaries")
        for field, graph in (
            ("graph_before_sha256", before),
            ("graph_materialized_sha256", incoming),
        ):
            if field in step and step[field] != digest(graph):
                raise ReplayGap("Captured materialization graph hash differs from its snapshot")
        if step["operator"] == "invoke_capability":
            _, receipt_refs = _receipt_at_boundary(store, kernel, step)
            refs.extend(receipt_refs)
        elif canonical(incoming) != canonical(after):
            raise ReplayGap("A pure operator has an unsupported historical graph mutation")
        previous = after
    final = store.get(capture["final_graph_ref"])
    if canonical(previous) != canonical(final) or dependencies.get("graph_after_sha256") != digest(
        final
    ):
        raise ReplayGap("Final captured graph does not match the executed boundary state")
    source_refs = _capture_source_refs(store, capture, kernel)
    if include_source_refs:
        refs.extend(source_refs)
    return capture, list(dict.fromkeys(refs))


def seal_execution_case(
    store,
    kernel_id,
    capture_id,
    *,
    run_id,
    question="",
    split="construction",
    assessment_category="execution_succeeded",
):
    """Seal a successful actual capture, without inventing outer planner bindings."""
    return seal_replay_case(
        store,
        ReplayCase(
            origin_kernel_id=kernel_id,
            run_id=run_id,
            question=question,
            split=split,
            assessment_category=assessment_category,
            calls=[RecordedCall(capture_id=capture_id)],
            comparison_id=store.put(
                "replay_comparison", ComparisonContract().model_dump(mode="json")
            ),
        ),
    )


def seal_replay_case(store, case: ReplayCase | dict) -> str:
    """Verify capture attribution before admitting immutable preservation anchors."""
    case = ReplayCase.model_validate(case) if isinstance(case, dict) else case
    kernel = _kernel(store, case.origin_kernel_id)
    ComparisonContract.model_validate(store.get(case.comparison_id))
    if case.assessment_category != "execution_succeeded" and not case.assessment_refs:
        raise ValueError("A stronger assessment requires its original evidence references")
    for ref in [*case.source_refs, *case.assessment_refs]:
        store.get(ref)
    source_refs = list(case.source_refs)
    values = []
    for call in case.calls:
        capture, sources = _validated_capture(
            store, call.capture_id, kernel, include_source_refs=True
        )
        bound = _arguments(capture, call, values)
        if first_difference(capture["args"], bound, ComparisonContract()):
            raise ValueError("Recorded result binding does not reproduce the original arguments")
        values.append(capture["value"])
        source_refs.extend(sources)
    case = case.model_copy(update={"source_refs": list(dict.fromkeys(source_refs))})
    return store.put("replay_case", case.model_dump(mode="json"))


def _register_kernel_bank(store, kernel_id, case_ids=()):
    """Publish one bank only while its previous and parent pointers remain current."""
    _init(store)
    kernel = _kernel(store, kernel_id)
    parent_bank_id, inherited = None, []
    if kernel.get("parent"):
        parent_bank_id, parent = _bank(store, kernel["parent"])
        inherited = parent.case_ids
    existing = store.rows("SELECT bank_id FROM replay_banks WHERE kernel_id=?", (kernel_id,))
    previous = existing[0]["bank_id"] if existing else None
    prior_ids = _bank(store, kernel_id)[1].case_ids if previous else []
    for identity in case_ids:
        case = ReplayCase.model_validate(store.get(identity))
        if case.origin_kernel_id != kernel_id:
            raise ValueError("Only this kernel's newly sealed cases may be appended")
    bank = ReplayBank(
        kernel_id=kernel_id,
        parent_bank_id=parent_bank_id,
        previous_bank_id=previous,
        case_ids=list(dict.fromkeys([*inherited, *prior_ids, *case_ids])),
    )
    if previous:
        old = ReplayBank.model_validate(store.get(previous))
        if old.case_ids == bank.case_ids and old.parent_bank_id == bank.parent_bank_id:
            return previous
    identity = store.put("replay_bank", bank.model_dump(mode="json"))
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute(
            "SELECT bank_id FROM replay_banks WHERE kernel_id=?", (kernel_id,)
        ).fetchone()
        if (latest[0] if latest else None) != previous:
            raise ReplayGap("Protected bank changed concurrently; retry registration")
        if kernel.get("parent"):
            current_parent = db.execute(
                "SELECT bank_id FROM replay_banks WHERE kernel_id=?", (kernel["parent"],)
            ).fetchone()
            if not current_parent or current_parent[0] != parent_bank_id:
                raise ReplayGap("Ancestor protected bank changed concurrently; retry registration")
        db.execute(
            "INSERT INTO replay_banks VALUES(?,?) ON CONFLICT(kernel_id) DO UPDATE SET bank_id=excluded.bank_id",
            (kernel_id, identity),
        )
    return identity


def register_kernel_bank(store, kernel_id, case_ids=()):
    """Refresh every ancestor iteratively before inheriting its complete current bank."""
    _init(store)
    lineage, seen, cursor = [], set(), kernel_id
    while cursor:
        if cursor in seen or len(seen) >= 1024:
            raise ReplayGap("Protected bank ancestry is cyclic or exceeds its resource limit")
        seen.add(cursor)
        if cursor != kernel_id:
            _bank(store, cursor)
        lineage.append(cursor)
        cursor = _kernel(store, cursor).get("parent")
    for identity in reversed(lineage):
        bank_id = _register_kernel_bank(store, identity, case_ids if identity == kernel_id else ())
    return bank_id


def register_adapter_edge(store, edge: AdapterEdge | dict):
    """Seal one revision-wide package; changing it requires another candidate."""
    _init(store)
    edge = AdapterEdge.model_validate(edge) if isinstance(edge, dict) else edge
    old, new = _kernel(store, edge.parent_id), _kernel(store, edge.child_id)
    checked = validate_adapter(edge.call_adapter, old, new)
    edge = edge.model_copy(update={"call_adapter": checked})
    if new.get("parent") != edge.parent_id:
        raise ValueError("Adapter must follow the actual recorded parent")
    old_names = {f["name"]: f for f in old["functions"]}
    new_names = {f["name"]: f for f in new["functions"]}
    for function, mappings in edge.step_mappings.items():
        mapping = next((m for m in checked.mappings if m.old_function == function), None)
        if mapping is None:
            raise ValueError("Step mapping requires a declared callable mapping")
        before = {s["id"] for s in old_names[function]["steps"]}
        after = {s["id"] for s in new_names[mapping.new_function]["steps"]}
        if not set(mappings).issubset(before) or not set(mappings.values()).issubset(after):
            raise ValueError("Step mapping names an absent operator boundary")
        if len(set(mappings.values())) != len(mappings):
            raise ValueError("Operator boundary mappings must be one-to-one")
        effective = [mappings.get(step, step) for step in before]
        if len(effective) != len(set(effective)):
            raise ValueError("Explicit operator mappings collide with implicit identity mappings")
    identity = store.put("adapter_edge", edge.model_dump(mode="json"))
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute(
            "SELECT edge_id FROM replay_edges WHERE child_id=?", (edge.child_id,)
        ).fetchone()
        if prior and prior[0] != identity:
            raise ValueError("Adapter edge is immutable; create a new candidate for repair")
        db.execute(
            "INSERT OR IGNORE INTO replay_edges VALUES(?,?,?)",
            (edge.child_id, edge.parent_id, identity),
        )
    return identity


def _schema_contract(schema):
    """Ignore only declared schema annotations, never data-property names."""
    contract = parse_schema(schema).model_dump(mode="json")
    contract.pop("name", None)
    contract.pop("description", None)
    for entity in contract["entity_types"].values():
        entity.pop("description", None)
        for declaration in entity["properties"].values():
            declaration.pop("description", None)
    for relation in contract["relations"].values():
        relation.pop("description", None)
    return contract


def prepare_candidate_adapter(store, kernel_id, *, run_id, proposer=None):
    """Construction-only proposal boundary, deliberately separate from replay."""
    _init(store)
    new = _kernel(store, kernel_id)
    parent = new.get("parent")
    if not parent:
        return None
    existing = store.rows("SELECT edge_id FROM replay_edges WHERE child_id=?", (kernel_id,))
    if existing:
        return existing[0]["edge_id"]
    old = _kernel(store, parent)
    identity = validate_adapter(AdapterSpec(old_revision=parent, new_revision=kernel_id), old, new)
    if canonical(_schema_contract(old["schema"])) == canonical(
        _schema_contract(new["schema"])
    ) and len(identity.mappings) == len(old["functions"]):
        edge = AdapterEdge(parent_id=parent, child_id=kernel_id, call_adapter=identity)
    else:
        if proposer is None:
            raise ReplayGap("A nontrivial revision requires a recorded shared adapter package")
        payload = {
            "old": {k: old[k] for k in ("id", "schema", "functions")},
            "new": {k: new[k] for k in ("id", "schema", "functions")},
            "source_contracts": {
                label: [
                    {
                        key: tool[key]
                        for key in (
                            "id",
                            "contract_id",
                            "description",
                            "input_schema",
                            "output_schema",
                            "annotations",
                        )
                        if key in tool
                    }
                    for tool in revision.get("catalog", {}).get("tools", [])
                ]
                for label, revision in (("old", old), ("new", new))
            },
            "response_schema": AdapterEdge.model_json_schema(),
            "constraints": [
                "One shared mapping for this exact parent-child pair.",
                "No task IDs, expected answers, constants, external calls or generated code.",
                "Use existing facts and explicit keys; unsupported semantics must fail.",
            ],
        }
        proposal = proposer(payload)
        proposal_ref = store.put("adapter_proposal", {"inputs": payload, "output": proposal})
        edge = AdapterEdge.model_validate({**proposal, "proposal_ref": proposal_ref})
        if edge.parent_id != parent or edge.child_id != kernel_id:
            raise ValueError("Proposed adapter changed its revision endpoints")
    ref = register_adapter_edge(store, edge)
    store.event(
        run_id,
        "historical_adapter",
        "completed",
        "Shared revision adapter sealed",
        {"kernel_id": kernel_id, "adapter_id": ref},
    )
    return ref


def _path(store, origin, candidate):
    result, seen = [], set()
    cursor = candidate
    while cursor != origin:
        if cursor in seen or len(seen) >= 1024:
            raise ReplayGap("Ancestry is cyclic or exceeds the finite replay resource limit")
        seen.add(cursor)
        kernel = _kernel(store, cursor)
        parent = kernel.get("parent")
        if not parent:
            raise ReplayGap("Original kernel is not an ancestor of this candidate")
        rows = store.rows("SELECT edge_id,parent_id FROM replay_edges WHERE child_id=?", (cursor,))
        if not rows or rows[0]["parent_id"] != parent:
            raise ReplayGap("An ancestor transition has no shared adapter")
        edge = AdapterEdge.model_validate(store.get(rows[0]["edge_id"]))
        if edge.parent_id != parent or edge.child_id != cursor:
            raise ReplayGap("Adapter artifact is not bound to the recorded ancestry")
        validated = validate_adapter(edge.call_adapter, _kernel(store, parent), kernel)
        if canonical(validated.model_dump(mode="json")) != canonical(
            edge.call_adapter.model_dump(mode="json")
        ):
            raise ReplayGap("Stored adapter differs from its validated complete interface mapping")
        result.append((rows[0]["edge_id"], edge))
        cursor = parent
    return list(reversed(result))


def _typed(value):
    if isinstance(value, dict):
        return ["object", [[k, _typed(v)] for k, v in sorted(value.items())]]
    if isinstance(value, list):
        return ["list", [_typed(v) for v in value]]
    return [type(value).__name__, value]


def first_difference(expected, actual, comparison, path="$"):
    """Preserve types, missingness, order and duplicates; never numeric coercion."""
    if comparison.collection == "multiset" and path == "$":
        if not isinstance(expected, list) or not isinstance(actual, list):
            return {"path": path, "reason": "Multiset policy requires list outputs"}
        if Counter(canonical(_typed(v)) for v in expected) == Counter(
            canonical(_typed(v)) for v in actual
        ):
            return None
        return {
            "path": path,
            "reason": "Typed collection multiplicity differs",
            "expected": expected,
            "actual": actual,
        }
    if type(expected) is not type(actual):
        return {
            "path": path,
            "reason": "Value type differs",
            "expected": expected,
            "actual": actual,
        }
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return {
                "path": path,
                "reason": "Object fields differ (absent is not null)",
                "expected": sorted(expected),
                "actual": sorted(actual),
            }
        for key in sorted(expected):
            diff = first_difference(expected[key], actual[key], comparison, f"{path}.{key}")
            if diff:
                return diff
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return {
                "path": path,
                "reason": "Collection length differs",
                "expected": len(expected),
                "actual": len(actual),
            }
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            diff = first_difference(left, right, comparison, f"{path}[{index}]")
            if diff:
                return diff
    elif expected != actual:
        return {"path": path, "reason": "Value differs", "expected": expected, "actual": actual}
    return None


def _read_path(value, path):
    for key in path:
        if isinstance(value, list) and type(key) is int and 0 <= key < len(value):
            value = value[key]
        elif isinstance(value, dict) and isinstance(key, str) and key in value:
            value = value[key]
        else:
            raise ReplayGap("Recorded result binding does not match the replayed value")
    return deepcopy(value)


def _arguments(capture, call, results):
    args = deepcopy(capture["args"])
    for binding in call.bindings:
        if binding.prior_call >= len(results):
            raise ReplayGap("Recorded binding refers to an unavailable prior replay result")
        value = _read_path(results[binding.prior_call], binding.output_path)
        target = args
        for key in binding.argument_path[:-1]:
            if isinstance(target, dict) and isinstance(key, str) and key in target:
                target = target[key]
            elif isinstance(target, list) and type(key) is int and 0 <= key < len(target):
                target = target[key]
            else:
                raise ReplayGap("Argument binding traverses an absent or incompatible value")
        key = binding.argument_path[-1]
        if isinstance(target, dict) and isinstance(key, str) and key in target:
            target[key] = value
        elif isinstance(target, list) and type(key) is int and 0 <= key < len(target):
            target[key] = value
        else:
            raise ReplayGap("Argument binding target is absent")
    return args


def _migrate(store, graph, path, graph_refs):
    for _, edge in path:
        before, after = _kernel(store, edge.parent_id), _kernel(store, edge.child_id)
        migration = migrate_graph(graph, edge.migration, before["schema"], after["schema"])
        store.put(
            "graph_migration", {"parent_id": edge.parent_id, "child_id": edge.child_id, **migration}
        )
        graph = migration["graph"]
        graph_refs.append(store.put("replay_graph", graph))
    return graph


def _execute(store, capture, kernel, args, path, graph_refs):
    """Run a current callable, restoring evidence only at recorded input boundaries."""
    if capture["runtime_dependencies"] != execution_dependencies():
        raise ReplayGap("Pinned original executor dependencies are unavailable")
    function = capture["function"]
    boundary_names = {s["id"]: s["id"] for s in capture["steps"]}
    output_maps = []
    for _, edge in path:
        mapping = next((m for m in edge.call_adapter.mappings if m.old_function == function), None)
        if mapping is None:
            raise ValueError(f"Missing protected callable mapping: {function}")
        args = {mapping.arguments.get(k, k): deepcopy(v) for k, v in args.items()}
        steps = edge.step_mappings.get(function, {})
        boundary_names = {
            original: steps.get(current, current) for original, current in boundary_names.items()
        }
        function = mapping.new_function
        output_maps.append(mapping.output_fields)
    by_current = {boundary_names[s["id"]]: s for s in capture["steps"]}
    graph = _migrate(store, store.get(capture["initial_graph_ref"]), path, graph_refs)
    materializations = {
        boundary_names[step["id"]]: step
        for step in capture["steps"]
        if step.get("before_materialization_graph_ref")
        and canonical(store.get(step["before_materialization_graph_ref"]))
        != canonical(store.get(step["input_graph_ref"]))
    }
    selected = next(item for item in kernel["functions"] if item["name"] == function)
    if not set(materializations).issubset({step["id"] for step in selected["steps"]}):
        raise ReplayGap("Changed function lacks a recorded materialization boundary mapping")
    current = {}

    def before_step(*, step_id, operator, arguments, step_outputs):
        current.update(step_id=step_id, operator=operator)
        if operator == "extract_runtime_slots":
            raise ReplayGap("Model-dependent slot extraction is outside deterministic replay")
        old_step = materializations.get(step_id)
        if old_step is not None:
            before = _migrate(
                store, store.get(old_step["before_materialization_graph_ref"]), path, graph_refs
            )
            if canonical(graph) != canonical(before):
                raise ReplayGap("Current graph diverged before a retained materialization boundary")
            incoming = _migrate(store, store.get(old_step["input_graph_ref"]), path, graph_refs)
            graph.clear()
            graph.update(incoming)

    def retained_acquisition(*, capability, arguments):
        step = by_current.get(current.get("step_id"))
        if step is None or step["operator"] != "invoke_capability":
            raise ReplayGap("No matching retained acquisition boundary")
        if canonical(step["inputs"]) != canonical(
            {"capability": capability, "arguments": arguments}
        ):
            raise ReplayGap("Changed acquisition request has no matching retained receipt")
        original_kernel = _kernel(store, path[0][1].parent_id) if path else kernel
        receipt, _ = _receipt_at_boundary(store, original_kernel, step)
        contracts = [
            tool
            for tool in kernel.get("catalog", {}).get("tools", [])
            if tool.get("id") == capability
        ]
        if len(contracts) != 1 or receipt["contract_id"] != contracts[0].get("contract_id"):
            raise ReplayGap("Current capability contract differs from the retained receipt")
        output, receipt_id = step["output"], step["output"]["receipt_id"]
        expected_input = _migrate(store, store.get(step["input_graph_ref"]), path, graph_refs)
        if canonical(graph) != canonical(expected_input):
            raise ReplayGap("Current graph differs at the retained acquisition boundary")
        incoming = _migrate(store, {"nodes": output["entities"], "edges": []}, path, graph_refs)
        after = _migrate(store, store.get(step["graph_after_ref"]), path, graph_refs)
        graph.clear()
        graph.update(after)
        entities = incoming["nodes"]
        return {
            "entities": entities,
            "entities_by_type": {
                name: [n for n in entities if n["type"] == name]
                for name in kernel["schema"]["entity_types"]
            },
            "receipt_id": receipt_id,
        }

    result = execute_function(
        graph,
        kernel["functions"],
        function,
        args,
        schema=kernel["schema"],
        before_step=before_step,
        capability_invoker=retained_acquisition,
        artifact_store=store,
    )
    _capture_source_refs(store, store.get(result["capture_id"]), kernel)
    value = result["value"]
    for mapping in reversed(output_maps):
        if mapping:
            if not isinstance(value, dict):
                raise ValueError("Output mapping requires an object result")
            value = {mapping.get(k, k): v for k, v in value.items()}
    return {
        "function": function,
        "args": args,
        **result,
        "adapted_value": value,
        "graph_id": store.put("replay_graph", graph),
        "source_mode": "retained_evidence",
    }


def _ontology(store, kernel_id):
    """Run real HermiT, caching only exact schema/runtime-bound successful receipts."""
    kernel = _kernel(store, kernel_id)
    key = hashlib.sha256(canonical([kernel["schema"], replay_dependencies()])).hexdigest()
    for event in store.rows(
        "SELECT artifact_id FROM events WHERE stage='replay_ontology' ORDER BY id DESC"
    ):
        receipt = store.get(event["artifact_id"])
        if receipt.get("key") == key:
            if not receipt["validation"]["valid"]:
                if receipt["validation"].get("status") not in {
                    "inconsistent",
                    "unsatisfiable_classes",
                    "invalid_schema",
                }:
                    continue
                raise ValueError("Candidate ontology failed real HermiT validation")
            return
    directory = store.root / "replay-validation" / uuid.uuid4().hex
    validation = validate_ontology(kernel["schema"], directory)
    store.event(
        kernel.get("run_id", "historical_replay"),
        "replay_ontology",
        "completed" if validation["valid"] else "failed",
        "Historical replay ontology validation",
        {"key": key, "kernel_id": kernel_id, "validation": validation},
    )
    if not validation["valid"]:
        if validation.get("status") not in {
            "inconsistent",
            "unsatisfiable_classes",
            "invalid_schema",
        }:
            raise ReplayGap("Real HermiT validation is unavailable or incomplete")
        raise ValueError("Candidate ontology failed real HermiT validation")


def replay_case(store, case_id, candidate_id):
    """Reproduce originals, execute the full ancestry path, stop on first difference."""
    _init(store)
    case = ReplayCase.model_validate(store.get(case_id))
    report = ReplayReport(
        original_case_id=case_id,
        origin_kernel_id=case.origin_kernel_id,
        candidate_kernel_id=candidate_id,
        status="unable_to_check",
        scope=case.scope,
        assessment_category=case.assessment_category,
        runtime_dependencies=replay_dependencies(),
    ).model_dump(mode="json")
    originals, candidates, original_values, values = [], [], [], []
    phase, index = "baseline", None
    original_function = current_function = None
    try:
        comparison = ComparisonContract.model_validate(store.get(case.comparison_id))
        origin = _kernel(store, case.origin_kernel_id)
        for ref in [*case.source_refs, *case.assessment_refs]:
            store.get(ref)
        for index, call in enumerate(case.calls):
            capture, source_refs = _validated_capture(store, call.capture_id, origin)
            original_function = current_function = capture["function"]
            if not set(source_refs).issubset(case.source_refs):
                raise ReplayGap("Sealed case omits acquisition source receipt references")
            report["original_graph_ids"].extend(
                [capture["initial_graph_ref"], *[s["input_graph_ref"] for s in capture["steps"]]]
            )
            executed = _execute(
                store, capture, origin, _arguments(capture, call, original_values), [], []
            )
            originals.append(executed)
            original_values.append(executed["adapted_value"])
            diff = first_difference(capture["value"], executed["adapted_value"], comparison)
            if not diff:
                original_steps = [
                    {key: step[key] for key in ("id", "operator", "status", "inputs", "output")}
                    for step in capture["steps"]
                ]
                replayed_steps = [
                    {key: step[key] for key in ("id", "operator", "status", "inputs", "output")}
                    for step in executed["steps"]
                ]
                diff = first_difference(
                    original_steps, replayed_steps, ComparisonContract(), "$.steps"
                )
            if diff:
                report["first_difference"] = FirstDifference(
                    phase=phase,
                    call_index=index,
                    repair_target="baseline",
                    original_function=original_function,
                    current_function=current_function,
                    **diff,
                ).model_dump(mode="json")
                raise ReplayGap("Original computation no longer reproduces its sealed observation")
        report["baseline_execution_id"] = store.put("replay_execution", originals)
        phase = "ancestry"
        path = _path(store, case.origin_kernel_id, candidate_id)
        report["adapter_path"] = [ref for ref, _ in path]
        candidate = _kernel(store, candidate_id)
        phase = "schema"
        for identity in dict.fromkeys([edge.child_id for _, edge in path] + [candidate_id]):
            _ontology(store, identity)
        for index, call in enumerate(case.calls):
            capture = store.get(call.capture_id)
            original_function = current_function = capture["function"]
            for _, edge in path:
                mapping = next(
                    (
                        item
                        for item in edge.call_adapter.mappings
                        if item.old_function == current_function
                    ),
                    None,
                )
                current_function = mapping.new_function if mapping else None
            phase = "candidate_execution"
            executed = _execute(
                store,
                capture,
                candidate,
                _arguments(capture, call, values),
                path,
                report["migrated_graph_ids"],
            )
            candidates.append(executed)
            values.append(executed["adapted_value"])
            diff = first_difference(capture["value"], executed["adapted_value"], comparison)
            if diff:
                report["first_difference"] = FirstDifference(
                    phase=phase,
                    call_index=index,
                    repair_target="function",
                    original_function=original_function,
                    current_function=current_function,
                    **diff,
                ).model_dump(mode="json")
                report.update(
                    status="regressed",
                    reason="Current computation changed an original protected observation",
                )
                break
        else:
            report.update(
                status="preserved",
                reason="Original protected computations reproduced through the complete adapter path",
            )
    except KeyboardInterrupt:
        report.update(status="interrupted", reason="Replay interrupted; no preservation claim")
    except Exception as error:
        from oak.migration import MigrationError

        cause, seen = error, set()
        while cause.__cause__ is not None and id(cause) not in seen:
            seen.add(id(cause))
            cause = cause.__cause__
        gap = (
            isinstance(error, (ReplayGap, FileNotFoundError))
            or isinstance(cause, (ReplayGap, FileNotFoundError))
            or phase in {"baseline", "ancestry"}
        )
        target = (
            "verification_gap"
            if gap
            else "migration"
            if isinstance(error, MigrationError) or isinstance(cause, MigrationError)
            else "schema"
            if phase == "schema"
            else "function"
        )
        report.update(
            status="unable_to_check" if gap else "regressed",
            reason=f"{type(error).__name__}: {error}",
        )
        if report["first_difference"] is None:
            report["first_difference"] = FirstDifference(
                phase=phase,
                call_index=index,
                repair_target=target,
                reason=report["reason"],
                original_function=original_function,
                current_function=current_function,
            ).model_dump(mode="json")
        if getattr(error, "steps", None):
            (originals if phase == "baseline" else candidates).append(
                {
                    "error": str(error),
                    "steps": error.steps,
                    "dependencies": getattr(error, "dependencies", {}),
                }
            )
    if originals and report["baseline_execution_id"] is None:
        report["baseline_execution_id"] = store.put("replay_execution", originals)
    if candidates:
        report["candidate_execution_id"] = store.put("replay_execution", candidates)
    for key in ("original_graph_ids", "migrated_graph_ids"):
        report[key] = list(dict.fromkeys(report[key]))
    return ReplayReport.model_validate(report)


def _repair_context(store, kernel_id, reports):
    """Expose failed executable structure, excluding questions, arguments and results."""
    failed = [report for report in reports if report.status != "preserved"]
    if not failed:
        return {}
    candidate = _kernel(store, kernel_id)
    originals, edges = {}, {}
    for report in failed:
        if report.origin_kernel_id and report.first_difference:
            try:
                original = _kernel(store, report.origin_kernel_id)
            except (OSError, ValueError, KeyError):
                continue
            name = report.first_difference.original_function
            record = originals.setdefault(
                report.origin_kernel_id,
                {
                    "kernel_id": report.origin_kernel_id,
                    "schema": original["schema"],
                    "functions": [],
                },
            )
            for function in original["functions"]:
                if function["name"] == name and function not in record["functions"]:
                    record["functions"].append(function)
        for identity in report.adapter_path:
            edge = AdapterEdge.model_validate(store.get(identity))
            edges[identity] = {
                "adapter_id": identity,
                **{
                    name: value
                    for name, value in edge.model_dump(mode="json").items()
                    if name != "proposal_ref"
                },
            }
    return {
        "candidate": {
            "kernel_id": kernel_id,
            "schema": candidate["schema"],
            "functions": candidate["functions"],
        },
        "original_kernels": list(originals.values()),
        "adapter_edges": list(edges.values()),
    }


def replay_bank(store, kernel_id, *, run_id):
    """Mandatory full-bank gate. No proposal, LLM, network, or selective skipping."""
    bank_id = register_kernel_bank(store, kernel_id)
    bank = ReplayBank.model_validate(store.get(bank_id))
    reports, refs = [], []
    for identity in bank.case_ids:
        try:
            report = replay_case(store, identity, kernel_id)
        except (ValueError, KeyError, OSError) as error:
            report = ReplayReport(
                original_case_id=identity,
                origin_kernel_id=None,
                candidate_kernel_id=kernel_id,
                status="unable_to_check",
                scope="unknown",
                assessment_category="unknown",
                runtime_dependencies=replay_dependencies(),
                reason=f"Protected case artifact is unavailable or invalid: {type(error).__name__}: {error}",
                first_difference=FirstDifference(
                    phase="case_integrity",
                    repair_target="verification_gap",
                    reason="Protected case artifact is unavailable or invalid",
                ),
            )
        reports.append(report)
        refs.append(store.put("replay_report", report.model_dump(mode="json")))
        if report.status == "interrupted":
            break
    statuses = {report.status for report in reports}
    status = (
        "interrupted"
        if "interrupted" in statuses
        else "regressed"
        if "regressed" in statuses
        else "preserved"
        if reports and statuses == {"preserved"}
        else "unable_to_check"
    )
    feedback = []
    for report, ref in zip(reports, refs, strict=True):
        if report.first_difference:
            difference = report.first_difference
            feedback.append(
                {
                    "phase": difference.phase,
                    "repair_target": difference.repair_target,
                    "path": difference.path,
                    "reason": difference.reason
                    if difference.reason
                    in {
                        "Value type differs",
                        "Object fields differ (absent is not null)",
                        "Collection length differs",
                        "Value differs",
                        "Typed collection multiplicity differs",
                    }
                    else f"{difference.repair_target} evidence failed; inspect the immutable report",
                    "original_function": difference.original_function,
                    "current_function": difference.current_function,
                    "report_ref": ref,
                    "candidate_kernel_id": kernel_id,
                }
            )
    if not reports:
        feedback.append(
            {
                "phase": "bank",
                "repair_target": "verification_gap",
                "reason": "No sealed successful computations; empty bank cannot pass",
            }
        )
    result = ReplayBankReport(
        kernel_id=kernel_id,
        bank_id=bank_id,
        status=status,
        allowed=status == "preserved",
        case_count=len(bank.case_ids),
        reports=reports,
        report_refs=refs,
        feedback=feedback,
        repair_context=_repair_context(store, kernel_id, reports),
        runtime_dependencies=replay_dependencies(),
    ).model_dump(mode="json")
    ref = store.put("replay_bank_report", result)
    result["report_id"] = ref
    store.event(
        run_id,
        "historical_replay",
        "completed" if result["allowed"] else "failed",
        "Full inherited historical replay bank evaluated",
        {"flow": "verification", **result},
    )
    return result


def check_candidate_replay(store, kernel_id, *, run_id, proposer=None):
    """Construction boundary: prepare shared adapter, then run the fixed verifier."""
    try:
        prepare_candidate_adapter(store, kernel_id, run_id=run_id, proposer=proposer)
        return replay_bank(store, kernel_id, run_id=run_id)
    except Exception as error:
        result = {
            "kernel_id": kernel_id,
            "bank_id": "",
            "status": "unable_to_check",
            "allowed": False,
            "case_count": 0,
            "reports": [],
            "report_refs": [],
            "feedback": [
                {
                    "phase": "preparation",
                    "repair_target": "verification_gap",
                    "reason": f"{type(error).__name__}: {error}",
                }
            ],
            "runtime_dependencies": replay_dependencies(),
            "model_calls": 0,
            "live_mcp_calls": 0,
        }
        ref = store.put(
            "replay_bank_report", ReplayBankReport.model_validate(result).model_dump(mode="json")
        )
        result["report_id"] = ref
        store.event(
            run_id,
            "historical_replay",
            "failed",
            "Historical preservation could not be established",
            {"flow": "verification", **result},
        )
        return result


def accepted_replay_report(store, kernel_id, *, refresh_bank=True):
    """Read an exact, current full-bank pass before adoption into inference."""
    if refresh_bank:
        bank_id = register_kernel_bank(store, kernel_id)
    else:
        if not store.rows(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='replay_banks'"
        ):
            raise ReplayGap("Candidate has no sealed protected bank")
        rows = store.rows("SELECT bank_id FROM replay_banks WHERE kernel_id=?", (kernel_id,))
        if not rows:
            raise ReplayGap("Candidate has no protected bank")
        bank_id = rows[0]["bank_id"]
    bank = ReplayBank.model_validate(store.get(bank_id))
    cursor, seen = bank, set()
    while cursor.parent_bank_id:
        if cursor.kernel_id in seen:
            raise ReplayGap("Protected bank ancestry is cyclic")
        seen.add(cursor.kernel_id)
        parent_id = store.get(cursor.kernel_id).get("parent")
        rows = store.rows("SELECT bank_id FROM replay_banks WHERE kernel_id=?", (parent_id,))
        if not rows or rows[0]["bank_id"] != cursor.parent_bank_id:
            raise ReplayGap("Ancestor protected bank changed; replay is required")
        parent = ReplayBank.model_validate(store.get(cursor.parent_bank_id))
        if not set(parent.case_ids).issubset(cursor.case_ids):
            raise ReplayGap("Protected bank omitted ancestor cases")
        cursor = parent
    for event in store.rows(
        "SELECT artifact_id FROM events WHERE stage='historical_replay' ORDER BY id DESC"
    ):
        data = store.get(event["artifact_id"])
        if data.get("kernel_id") != kernel_id:
            continue
        report = ReplayBankReport.model_validate(store.get(data["report_id"]))
        if (
            report.kernel_id == kernel_id
            and report.bank_id == bank_id
            and report.runtime_dependencies == replay_dependencies()
            and report.allowed
        ):
            if (
                report.status != "preserved"
                or report.case_count == 0
                or len(report.reports) != report.case_count
                or len(report.report_refs) != report.case_count
                or {r.original_case_id for r in report.reports} != set(bank.case_ids)
                or any(r.status != "preserved" for r in report.reports)
            ):
                raise ReplayGap("Incomplete protected bank report cannot authorize adoption")
            for case_report, report_ref in zip(report.reports, report.report_refs, strict=True):
                saved = ReplayReport.model_validate(store.get(report_ref))
                case = ReplayCase.model_validate(store.get(case_report.original_case_id))
                original_kernel = _kernel(store, case.origin_kernel_id)
                for call in case.calls:
                    capture, source_refs = _validated_capture(
                        store, call.capture_id, original_kernel
                    )
                    if capture["runtime_dependencies"] != execution_dependencies() or not set(
                        source_refs
                    ).issubset(case.source_refs):
                        raise ReplayGap("Protected capture dependencies or receipt closure changed")
                expected_path = [ref for ref, _ in _path(store, case.origin_kernel_id, kernel_id)]
                if (
                    saved != case_report
                    or saved.candidate_kernel_id != kernel_id
                    or saved.origin_kernel_id != case.origin_kernel_id
                    or saved.runtime_dependencies != replay_dependencies()
                    or saved.adapter_path != expected_path
                ):
                    raise ReplayGap(
                        "Replay report references or ancestry do not match the current candidate"
                    )
                for artifact_id in [
                    case.comparison_id,
                    *case.source_refs,
                    *case.assessment_refs,
                    *saved.original_graph_ids,
                    *saved.migrated_graph_ids,
                    saved.baseline_execution_id,
                    saved.candidate_execution_id,
                    *[call.capture_id for call in case.calls],
                ]:
                    if not artifact_id:
                        raise ReplayGap("Passing replay lacks actual execution evidence")
                    store.get(artifact_id)
            return {**report.model_dump(mode="json"), "report_id": data["report_id"]}
        raise ReplayGap(
            "Current protected bank lacks a complete passing replay under current dependencies"
        )
    raise ReplayGap("Candidate has no historical preservation acceptance report")


def inference_admission(store, kernel_id):
    """Read-only adoption decision used by UI, job submission and actual inference."""
    kernel = store.get(kernel_id)
    if kernel.get("historical_replay_policy") != "inherited_v1":
        return {
            "allowed": True,
            "reason": "Unchanged legacy kernel uses its original eligibility checks",
        }
    try:
        if not store.rows(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='replay_banks'"
        ):
            raise ReplayGap("Candidate has no protected historical bank")
        accepted_replay_report(store, kernel_id, refresh_bank=False)
        return {"allowed": True, "reason": "Every inherited protected computation passed"}
    except (ValueError, KeyError, OSError) as error:
        return {"allowed": False, "reason": str(error)}
