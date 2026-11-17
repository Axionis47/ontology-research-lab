#!/usr/bin/env python3
"""Validate the design bundle, not the unimplemented agent runtime."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent


def validate_computational_protocol(definitions: dict, profile: dict, acceptance_ids: set[str]) -> list[str]:
    """Check the declarative design against existing contracts, not runtime enforcement."""
    protocol = json.loads((ROOT / "computational-protocol.json").read_text())
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append("Computational protocol: " + message)

    check(protocol["status"] == "SPECIFICATION_NOT_RUNTIME", "must not claim installed enforcement")
    check(protocol["wire_schema"] == "contracts.schema.json", "wire schema differs from bundle")
    check(protocol["profile"] == "profile.json", "full-system profile differs from bundle")
    for role, name in protocol["record_roles"].items():
        check(name in definitions, f"unknown wire record {name} for {role}")
    check(set(protocol["objects"]) == {
        "domain_structure", "observed_data", "task_contract", "constraint_workspace",
        "control_state", "experience_archive",
    }, "data, task constraints, handling and control ownership must remain separate")

    control = protocol["control"]
    edges = control["allowed_next"]
    state_definition = definitions["LifecycleTransition"]["properties"]
    wire_states = set(state_definition["from_state"]["enum"]) | set(state_definition["to_state"]["enum"])
    check(set(edges) == wire_states, "lifecycle states differ from wire schema")
    check(control["initial_state"] == "CREATED" and control["terminal_state"] == "TERMINAL", "invalid boundary states")
    check(edges.get("TERMINAL") == [], "terminal state allows further execution")
    for source, destinations in edges.items():
        check(len(destinations) == len(set(destinations)), f"duplicate edge from {source}")
        check(set(destinations).issubset(wire_states), f"unknown destination from {source}")
        reached, pending = set(), [source]
        while pending:
            current = pending.pop()
            if current in reached:
                continue
            reached.add(current)
            pending.extend(edges.get(current, []))
        check("TERMINAL" in reached, f"no terminal path from {source}")

    prose_edges = {}
    for line in (ROOT / "02-inference-and-control.md").read_text().splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 5 and cells[1].strip("`") in wire_states:
            prose_edges[cells[1].strip("`")] = re.findall(r"`([A-Z_]+)`", cells[3])
    check({k: set(v) for k, v in edges.items()} == {k: set(v) for k, v in prose_edges.items()},
          "lifecycle edges differ from document 02")

    catalog = set(control["guard_catalog"])
    referenced = set(control["global_guards"])
    check(set(control["entry_guards"]) == wire_states, "entry guard coverage differs from lifecycle")
    for guards in control["entry_guards"].values():
        referenced.update(guards)
    check(catalog == referenced, "unknown or unused transition guard")
    check({"expected_revision_current", "producer_authenticated", "edge_allowed", "durable_transition_commit"}
          .issubset(control["global_guards"]), "missing global control guard")
    check({"allowed_admission_current", "dispatch_intent_committed"}
          .issubset(control["entry_guards"]["EXECUTING"]), "execution can bypass admission/intent")
    proposal_kinds = {
        definitions[variant["$ref"].rsplit("/", 1)[1]]["properties"]["kind"]["const"]
        for variant in definitions["Proposal"]["oneOf"]
    }
    routing = control["proposal_routing"]
    check(set(routing) == proposal_kinds, "proposal variants differ from wire schema")
    expected_targets = {"act": "EXECUTING", "revisit": "READY", "finish": "VERIFYING", "request_input": "WAITING_INPUT"}
    for kind, target in expected_targets.items():
        check(routing.get(kind) == {"accepted_state": target, "rejected_state": "READY"},
              f"invalid routing for {kind}")
    check(control["actor_may_assign_success"] is False, "actor can assign success")
    check(control["package_change_within_episode"] is False, "episode package may mutate")
    check(control["unknown_write_retry"] == "RECONCILE_FIRST", "unknown write can bypass reconciliation")

    constraints = protocol["constraints"]
    check(constraints["truth_values"] == definitions["CheckedFact"]["properties"]["value"]["enum"], "truth values differ")
    for kind in ("protected_policy", "task_obligations", "domain_representation"):
        check(constraints[kind]["solver_may_modify"] is False, f"solver may alter {kind}")
    for key in ("unknown_satisfies_required_predicate", "preferences_may_override_required_predicates", "partial_search_proves_global_infeasibility"):
        check(constraints[key] is False, f"invalid constraint semantics: {key}")

    learning = protocol["learning"]
    check(learning["weights_trainable"] is False and profile["scope"]["weights_trainable"] is False, "weight training enabled")
    check(set(learning["automatically_editable"]) == {"schema", "source_mappings", "function_implementations", "function_io_contracts"},
          "automatic learning surfaces differ from active scope")
    check(set(learning["editable_file_classes"]) == {"schema.json", "mappings.json", "functions/*.py", "function_contracts/*.json"},
          "editable file classes differ from computational package")
    check({"kernel", "policy", "task_obligations", "required_checkers", "operator_membership_and_runtime", "evaluator", "ledger_instrumentation", "budgets", "sandbox", "promotion_rules"}
          .issubset(learning["protected"]), "protected learning boundary is incomplete")
    check(set(learning["selection_inputs"]) == {"FIT", "DEVELOPMENT"} and learning["sealed_check_available_to_proposer"] is False,
          "selection can access sealed evidence")
    check({"relationship_topology", "constraint_combinations"}.issubset(learning["fixture_variation_axes"]),
          "fixtures vary records without testing structural handling")
    check((ROOT / learning["gate_document"]).is_file(), "missing evaluation gate document")
    check(protocol["knowledge_access"]["new_generic_operators"] == [], "locked operator library expanded")
    for key in ("actor_may_write_facts_directly", "actor_may_edit_package", "candidate_may_contain_task_answer_tables"):
        check(protocol["knowledge_access"][key] is False, f"knowledge boundary permits {key}")
    consolidation = protocol["consolidation"]
    check(consolidation["status"] == "SPECIFICATION_NOT_RUNTIME", "consolidation claims installed enforcement")
    check(consolidation["stages"] == ["PIN_CASE", "DISCOVER_EXISTING", "RESOLVE_IDENTITIES",
          "LOCATE_GAP", "VALIDATE_DELTA", "ARCHIVE_DECISION"], "consolidation can bypass discovery or identity resolution")
    check(set(consolidation["discovery_targets"]) == {"entity_instances", "entity_types", "property_definitions",
          "relation_definitions", "source_mappings", "function_interfaces"}, "consolidation discovery is incomplete")
    check(consolidation["entity_identity"] == ["environment_scope", "episode_scope", "source_namespace", "entity_type", "source_key"],
          "consolidation identity can merge unrelated worlds or records")
    for key in ("same_display_name_proves_identity", "cooccurrence_proves_relation", "empty_page_proves_schema_absence",
                "partial_discovery_allows_schema_extension", "actor_may_commit_consolidation", "live_episode_package_may_change"):
        check(consolidation[key] is False, f"unsupported consolidation authority or inference: {key}")
    routes = consolidation["gap_routes"]
    check(set(routes) == {"OBSERVATION_GAP", "MAPPING_GAP", "COMPOSITION_GAP", "SCHEMA_GAP",
                         "NEEDS_EVIDENCE", "CONTROL_FAILURE", "NO_CHANGE"}, "consolidation gap coverage differs")
    expected_routes = {
        "OBSERVATION_GAP": ("observed_data", "trusted_ingestion"),
        "MAPPING_GAP": ("source_mappings", "offline_candidate"),
        "COMPOSITION_GAP": ("function_implementations", "offline_candidate"),
        "SCHEMA_GAP": ("schema", "offline_candidate"),
        "NEEDS_EVIDENCE": (None, None), "NO_CHANGE": (None, None),
        "CONTROL_FAILURE": (None, "separate_engineering_process"),
    }
    for name, (target, writer) in expected_routes.items():
        check(routes.get(name) == {"target": target, "writer": writer, "schema_change": name == "SCHEMA_GAP"},
              f"consolidation changes the wrong surface: {name}")
    check({"scoped_discovery_complete", "independent_semantic_evidence", "mapping_or_composition_fix_insufficient",
           "distinguishing_reproducer"}.issubset(consolidation["schema_gap_requires"]), "schema extension lacks discovery/necessity evidence")
    check({"scope", "package_hash", "graph_revision", "query", "returned_ids", "evidence_refs", "coverage", "continuation"}
          .issubset(consolidation["query_receipts_require"]), "consolidation queries lack bounded evidence receipts")
    check({"original_goal_ref", "trigger_event_ref", "kernel_or_package_version", "pre_handoff_evidence_refs",
           "continuation_event_refs", "terminal_outcome_ref", "evaluation_receipt_or_explicit_unavailable"}
          .issubset(consolidation["case_requires"]), "consolidation case loses handoff/outcome lineage")
    check({"case_refs", "discovery_receipt_refs", "reused_entity_ids", "reused_definition_ids", "gap_class",
           "proposed_delta_or_no_change", "supporting_evidence_refs", "validation_refs", "decision_and_reason"}
          .issubset(consolidation["decision_requires"]), "consolidation decision loses reuse or validation evidence")
    check(set(consolidation["existing_wire_records"]).issubset(definitions), "consolidation invents an undefined wire record")
    check(consolidation["new_generic_operators"] == [], "consolidation expands locked operator membership")
    for label, pointer in protocol["profile_bindings"].items():
        node = profile
        try:
            for part in pointer.lstrip("/").split("/"):
                node = node[part]
            check(isinstance(node, (int, float)) and not isinstance(node, bool) and node > 0,
                  f"invalid numerical limit for {label}")
        except (KeyError, TypeError):
            check(False, f"unresolved profile pointer {pointer}")
    check(set(protocol["acceptance_cases"]).issubset(acceptance_ids), "undefined runtime acceptance case")
    return failures


def main() -> None:
    schema = json.loads((ROOT / "contracts.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    definitions = schema["$defs"]
    failures: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            target = value.get("$ref")
            if target is not None:
                if not isinstance(target, str) or not target.startswith("#/"):
                    failures.append(f"Unexpected nonlocal schema reference: {target}")
                else:
                    node = schema
                    try:
                        for part in target[2:].split("/"):
                            part = part.replace("~1", "/").replace("~0", "~")
                            node = node[int(part)] if isinstance(node, list) else node[part]
                    except (KeyError, IndexError, ValueError, TypeError):
                        failures.append(f"Unresolved schema reference: {target}")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)
    cases = json.loads((ROOT / "contract-cases.json").read_text())["cases"]
    for case in cases:
        if case["schema"] not in definitions:
            failures.append(f"Unknown case schema: {case['name']}")
            continue
        selected = {**schema, "$ref": f"#/$defs/{case['schema']}"}
        errors = list(Draft202012Validator(selected, format_checker=FormatChecker()).iter_errors(case["record"]))
        if (not errors) != case["valid"]:
            failures.append(f"Unexpected validation result: {case['name']}: {[e.message for e in errors[:2]]}")

    catalog = json.loads((ROOT / "event-catalog.json").read_text())
    for event, name in catalog["payload_schemas"].items():
        if name not in definitions:
            failures.append(f"Unknown payload schema for {event}: {name}")
    for name in (catalog["envelope_schema"], catalog["job_envelope_schema"]):
        if name not in definitions:
            failures.append(f"Unknown envelope schema: {name}")
    for event in catalog["job_only_events"] + catalog["shared_job_events"]:
        if event not in catalog["payload_schemas"]:
            failures.append(f"Unknown job event: {event}")

    documents = sorted(ROOT.glob("*.md"))
    for path in documents:
        content = path.read_text()
        if "\u2014" in content:
            failures.append(f"Em dash in {path.name}")
        if content.count("```") % 2:
            failures.append(f"Unbalanced code fences in {path.name}")
        for link in re.findall(r"\]\(([^)]+)\)", content):
            if link.startswith(("https:", "http:", "#")):
                continue
            target = link.split("#", 1)[0]
            if not (path.parent / target).resolve().exists():
                failures.append(f"Broken local link in {path.name}: {link}")
        if re.search(r"\b(?:TODO|TBD|FIXME)\b", content):
            failures.append(f"Unresolved design placeholder in {path.name}")

    profile = json.loads((ROOT / "profile.json").read_text())
    episode, judge, context = profile["episode"], profile["judge"], profile["context"]
    required_segments = max(1, math.ceil((episode["max_steps"] - judge["segment_overlap_steps"]) / (judge["segment_steps"] - judge["segment_overlap_steps"])))
    if required_segments > judge["max_segments_per_episode"]:
        failures.append("Judge window capacity does not cover the episode step cap")
    if judge["max_segments_per_episode"] + judge["max_expansion_requests_per_episode"] + 2 > judge["max_model_calls_per_episode"]:
        failures.append("Judge call cap cannot fit planned windows, expansions and finalization")
    if episode["finalization_tool_reserve"] >= episode["max_tool_attempts"]:
        failures.append("No exploration tool allowance")
    if episode["finalization_time_reserve_seconds"] >= episode["deadline_seconds"]:
        failures.append("No exploration time allowance")
    if context["text_chunk_overlap_tokens"] >= context["text_chunk_tokens"]:
        failures.append("Chunk overlap prevents forward traversal")
    if profile["model_override"] is not None:
        failures.append("Profile unexpectedly overrides the user's CLI model")
    if profile["repair"]["max_candidates_per_cycle"] * profile["repair"]["max_research_cycles"] > profile["evaluation"]["promotion_max_candidates"]:
        failures.append("Candidate search exceeds the preregistered gate slate bound")
    if profile["evaluation"].get("gate_mode") == "NARROW_PILOT_ACCEPTANCE":
        scope = profile.get("scope", {})
        if scope.get("max_task_families") != 1 or scope.get("max_business_apps") != 1:
            failures.append("Narrow pilot must remain one family and one business app")
        if scope.get("additional_surfaces_enabled") or scope.get("weights_trainable"):
            failures.append("Narrow pilot unexpectedly broadens surfaces or enables weight training")
        ev = profile["evaluation"]
        if ev["pilot_train_tasks"] + ev["pilot_dev_tasks"] + ev["sealed_check_tasks"] != scope.get("native_variants_expected"):
            failures.append("Internal instance allocation does not match the selected native family")
        if ev.get("statistical_generalization_claim_enabled") or ev.get("sealed_check_reuses_for_selection") != 0:
            failures.append("Narrow gate permits an unsupported claim or sealed-check reuse")
    elif profile["evaluation"].get("minimum_gate_families_per_surface", 0) < 1:
        failures.append("Broad gate family floor must be positive")
    if profile["evaluation"]["resource_policy"] not in {"STEP_TOOL_WALL", "MEASURED_TOKEN_TOOL"}:
        failures.append("Unknown resource comparison policy")

    operators = [item["properties"]["operator"]["const"] for item in definitions["OperatorCall"]["oneOf"]]
    locked = ["extract_runtime_slots", "lookup_entities", "traverse_relations", "project_properties", "filter_property_categorical", "filter_relation_connected", "filter_numeric", "filter_set_overlap", "aggregate_values"]
    if operators != locked:
        failures.append("Canonical operator membership or ordering changed")
    active_operators = profile.get("scope", {}).get("active_operator_ids", [])
    if not set(active_operators).issubset(locked):
        failures.append("Active operator is outside the locked library")
    if len(active_operators) > profile.get("scope", {}).get("max_active_operators", 9):
        failures.append("Active graph implementation exceeds narrow scope")
    for operator in locked:
        if operator not in (ROOT / "04-domain-and-surfaces.md").read_text():
            failures.append(f"Missing operator contract prose: {operator}")

    acceptance = (ROOT / "09-build-and-acceptance.md").read_text()
    defined = set(re.findall(r"^\| ([A-Z]+-\d{2}) \|", acceptance, re.M))
    referenced: set[str] = set()
    for path in documents:
        referenced.update(re.findall(r"\b(?:KRN|TRC|INF|END|DOM|LONG|JDG|REP|JOB)-\d{2}\b", path.read_text()))
    for name in referenced - defined:
        failures.append(f"Undefined acceptance case: {name}")

    failures.extend(validate_computational_protocol(definitions, profile, defined))

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS: {len(documents)} documents, {len(definitions)} schema definitions, {len(cases)} boundary cases, {len(catalog['payload_schemas'])} event mappings, {len(defined)} runtime acceptance scenarios.")
    print("Checked schema references, formats/examples, local links, defaults, operator membership and coverage IDs. Runtime acceptance scenarios remain unexecuted.")
    print("Checked computational ownership, lifecycle/guard references, constraint semantics, learning surfaces and profile bindings. These are specification checks, not runtime enforcement tests.")


if __name__ == "__main__":
    main()
