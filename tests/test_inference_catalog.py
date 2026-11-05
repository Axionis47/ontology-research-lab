"""Real retained Coffee/weather contracts and W3C schema discovery, without models."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError
from langchain_core.tools import StructuredTool
from test_historical_replay import _acceptance
from test_ontology import wine_schema  # noqa: F401
from test_selective_evaluation import retained  # noqa: F401

from oak.functions import execute_function
from oak.inference_catalog import (
    CONTROL_NAMES,
    EXPAND,
    INSPECT,
    SEARCH,
    SEARCH_INDEX_VERSION,
    DiscoveryResult,
    DiscoveryState,
    InferenceCatalog,
    InferenceDecisionBudget,
    _tokens,
)
from oak.materialization import AcquisitionBinding
from oak.schema_context import schema_entries
from oak.store import canonical


@pytest.fixture
def weather_kernel():
    artifacts = Path(__file__).parent / "fixtures/observer/weather/artifacts"
    episode = json.loads(
        (
            artifacts / "697f6356e475e850faee6abc4ca3b70e520f36df9c2fe1d5f235c0dd2a0b51ea.json"
        ).read_text()
    )["data"]
    return json.loads((artifacts / f"{episode['kernel_revision']}.json").read_text())["data"]


@pytest.fixture
def coffee_kernel():
    graph, schema, _ = _acceptance.coffee_inputs()
    functions = _acceptance.catalog("CoffeeRow", "High", "one", include_count=True)
    return {"schema": schema, "functions": functions}, graph


@pytest.fixture
def learned_weather_kernel():
    path = Path(__file__).parent / "fixtures/inference/learned-weather-kernel.json"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "77690c1643152649c7969ef29b9bae7d42a88138a28ad6c944fa8e0f7f9ee5bc"
    )
    return json.loads(raw)["data"]


def browse(catalog, state, tool=SEARCH, **args):
    items, cursor = [], None
    while True:
        state, result = catalog.dispatch(tool, {**args, "cursor": cursor}, state)
        assert result["status"] == "ok", result
        DiscoveryState.model_validate(state)
        DiscoveryResult.model_validate(result)
        assert len(canonical(catalog.prompt(state))) <= catalog.max_context_bytes
        items.extend(result["items"])
        cursor = result["next_cursor"]
        if not cursor:
            assert len(items) == result["total_count"]
            return state, items


def reconstruct(catalog, state, identity, pointer=""):
    """Reassemble actual exact values from explicit fragment/page instructions."""
    cursor, container, fragments = None, None, []
    while True:
        state, result = catalog.dispatch(
            INSPECT, {"id": identity, "pointer": pointer, "cursor": cursor}, state
        )
        assert result["status"] == "ok", result
        assert len(canonical(catalog.prompt(state))) <= catalog.max_context_bytes
        fragment = result["definition"]
        if fragment["complete"]:
            return state, fragment["value"]
        if fragment["type"] == "string":
            fragments.append(fragment["string_fragment"])
        else:
            if container is None:
                container = {} if fragment["type"] == "object" else []
            for item in fragment["children"]:
                if "value" in item:
                    value = item["value"]
                else:
                    assert item["deferred"]
                    state, value = reconstruct(catalog, state, identity, item["pointer"])
                if isinstance(container, dict):
                    container[item["key"]] = value
                else:
                    assert item["key"] == len(container)
                    container.append(value)
        cursor = result["next_cursor"]
        if not cursor:
            return state, "".join(fragments) if fragment["type"] == "string" else container


def test_initial_surface_is_only_controls_and_every_entry_remains_reachable(weather_kernel):
    catalog = InferenceCatalog(weather_kernel, page_size=1, page_bytes=512)
    initial = catalog.initial_state()
    view = catalog.prompt(initial)
    assert {item["name"] for item in view["tools"]} == CONTROL_NAMES
    assert view["definitions"] == []
    assert "DailyForecast" not in canonical(view).decode()
    assert "invoke_capability" not in canonical(view).decode()
    for control in catalog.control_tools():
        assert {"name", "description", "input_schema", "output_schema"} <= control.keys()
        assert control["annotations"]["readOnlyHint"]
    state, miss = catalog.dispatch(SEARCH, {"query": "unmatchedlexicalquery"}, initial)
    assert miss["status"] == "ok" and miss["total_count"] == 0
    state, cards = browse(catalog, state)
    assert [card["id"] for card in cards] == catalog.manifest()["definition_ids"]
    assert len(cards) > 2 * catalog.page_size
    assert initial == catalog.initial_state()
    assert catalog.context_summary(state, catalog.prompt(state)).context_bytes == len(
        canonical(catalog.prompt(state))
    )


def test_search_ranking_and_cursor_are_bound_to_exact_lookup_and_kernel(
    weather_kernel, coffee_kernel
):
    catalog = InferenceCatalog(weather_kernel, page_size=1)
    state, first = catalog.dispatch(SEARCH, {}, catalog.initial_state())
    assert first["next_cursor"]
    for args in (
        {"query": "forecast", "cursor": first["next_cursor"]},
        {"kind": "function", "cursor": first["next_cursor"]},
        {"cursor": "not-a-valid-cursor"},
    ):
        state, invalid = catalog.dispatch(SEARCH, args, state)
        assert invalid["status"] == "error"
        assert "restart" in invalid["error"]
    other = InferenceCatalog(coffee_kernel[0], page_size=1)
    _, rejected = other.dispatch(SEARCH, {"cursor": first["next_cursor"]}, other.initial_state())
    assert rejected["status"] == "error"
    _, found = catalog.dispatch(SEARCH, {"query": "forecast", "kind": "function"}, state)
    assert found["items"] and all(card["kind"] == "function" for card in found["items"])
    with pytest.raises(ValueError, match="different frozen kernel"):
        other.prompt(state)


def test_all_real_large_definitions_and_function_fragments_are_exactly_reconstructible(
    weather_kernel,
):
    catalog = InferenceCatalog(weather_kernel, page_bytes=512, page_size=1, max_context_bytes=7000)
    state = catalog.initial_state()
    definitions = schema_entries(weather_kernel["schema"])
    identity = "/entity_types/DailyForecast"
    state, actual = reconstruct(catalog, state, identity)
    assert actual == definitions[identity]["definition"]
    identity = "/capabilities/weather~1get_forecast"
    state, actual = reconstruct(catalog, state, identity)
    original = next(
        item for item in weather_kernel["catalog"]["tools"] if item["id"] == "weather/get_forecast"
    )
    assert actual == {
        key: value
        for key, value in original.items()
        if key
        in {"id", "contract_id", "description", "input_schema", "output_schema", "annotations"}
    }
    original = weather_kernel["functions"][1]
    identity = "/functions/" + original["name"]
    state, actual = reconstruct(catalog, state, identity)
    assert actual["input_schema"] == original["inputs"]
    assert actual["output_schema"] == original["output_schema"]
    assert "steps" not in actual and "result" not in actual
    state, fragment = catalog.dispatch(INSPECT, {"id": identity, "pointer": "/input_schema"}, state)
    assert fragment["complete"]
    assert catalog.prompt(state)["definitions"][-1]["definition"]["value"] == original["inputs"]
    loaded = [tool for tool in catalog.prompt(state)["tools"] if tool["name"] not in CONTROL_NAMES]
    assert len(loaded) == 1 and not loaded[0]["contract_complete"]
    assert loaded[0]["input_schema_ref"] == {"id": identity, "pointer": "/input_schema"}


def test_w3c_relation_dependencies_are_reachable_without_loading_whole_schema(wine_schema):  # noqa: F811
    catalog = InferenceCatalog({"schema": wine_schema, "functions": []}, page_size=1)
    state, cards = browse(catalog, catalog.initial_state(), EXPAND, id="/relations/hasMaker")
    assert {card["id"] for card in cards} == {
        "/entity_types/Wine",
        "/entity_types/Winery",
        "/entity_types/Wine/properties/iri",
        "/entity_types/Winery/properties/iri",
    }
    state, inspected = catalog.dispatch(INSPECT, {"id": "/relations/hasMaker"}, state)
    assert inspected["definition"]["value"] == wine_schema["relations"]["hasMaker"]
    assert inspected["loaded_tool_name"] is None
    assert not state["loaded_function_ids"]


def test_real_langchain_function_invokes_actual_coffee_and_weather_executors(
    coffee_kernel,
    retained,  # noqa: F811
):
    weather_store, weather, case, _, _ = retained
    kernels = [
        coffee_kernel,
        (
            {"schema": weather.schema, "functions": weather.functions},
            weather_store.get(case.graph_ref),
        ),
    ]
    for kernel, graph in kernels:
        catalog = InferenceCatalog(kernel)
        state, cards = browse(catalog, catalog.initial_state(), kind="function")
        count_card = next(card for card in cards if "count" in card["name"])
        with pytest.raises(ValueError, match="not loaded"):
            catalog.resolve_call(count_card["tool_name"], state)
        state, inspected = catalog.dispatch(INSPECT, {"id": count_card["id"]}, state)
        executions = []

        def execute(name, arguments, kernel=kernel, graph=graph, executions=executions):
            result = execute_function(
                graph, kernel["functions"], name, arguments, schema=kernel["schema"]
            )
            executions.append(result)
            return result["value"]

        tool = catalog.as_langchain_tool(inspected["loaded_tool_name"], state, execute)
        assert isinstance(tool, StructuredTool)
        target = next(
            function for function in kernel["functions"] if function["name"] == count_card["name"]
        )["steps"][0]["args"]["entity_types"][0]
        assert tool.invoke({}) == sum(node["type"] == target for node in graph["nodes"])
        assert executions[0]["steps"]
        with pytest.raises(ValidationError):
            tool.invoke({"unrecognized": 1})
        assert len(executions) == 1
        assert tool.metadata["output_schema"] == {"type": "integer"}


def test_eviction_is_explicit_and_reinspection_restores_callability(coffee_kernel):
    kernel, _ = coffee_kernel
    catalog = InferenceCatalog(kernel, max_loaded_tools=1)
    state, cards = browse(catalog, catalog.initial_state(), kind="function")
    first, second = cards[:2]
    state, _ = catalog.dispatch(INSPECT, {"id": first["id"]}, state)
    assert catalog.resolve_call(first["tool_name"], state) == first["name"]
    state, result = catalog.dispatch(INSPECT, {"id": second["id"]}, state)
    assert first["id"] in result["context"]["evicted_definition_ids"]
    with pytest.raises(ValueError, match="Inspect"):
        catalog.resolve_call(first["tool_name"], state)
    state, _ = catalog.dispatch(INSPECT, {"id": first["id"]}, state)
    assert catalog.resolve_call(first["tool_name"], state) == first["name"]
    with pytest.raises(ValueError, match="Inspect"):
        catalog.resolve_call(first["name"], state)


@pytest.mark.parametrize(
    "tool,args",
    [
        (SEARCH, {"kind": "missing"}),
        (INSPECT, {}),
        (EXPAND, {"id": 4}),
        (INSPECT, {"id": "/unknown"}),
        ("not_a_control", {}),
    ],
)
def test_malformed_control_input_is_an_actionable_receipt(weather_kernel, tool, args):
    catalog = InferenceCatalog(weather_kernel)
    state, result = catalog.dispatch(tool, args, catalog.initial_state())
    assert result["status"] == "error" and result["error"]
    assert not state["loaded_function_ids"]
    DiscoveryResult.model_validate(result)


def test_manifest_pins_frozen_identity_and_is_independent_of_input_mutation(weather_kernel):
    original = deepcopy(weather_kernel)
    catalog = InferenceCatalog(original, kernel_id="retained-weather-artifact")
    manifest = catalog.manifest()
    original["functions"].clear()
    assert catalog.manifest() == manifest
    assert manifest["kernel_id"] == "retained-weather-artifact"
    assert len(manifest["catalog_id"]) == 64
    assert manifest["function_count"] == len(weather_kernel["functions"])


@pytest.mark.parametrize("name", [None, [], {}])
def test_invalid_callable_names_produce_recoverable_loading_guidance(weather_kernel, name):
    catalog = InferenceCatalog(weather_kernel)
    with pytest.raises(ValueError, match="Search and inspect"):
        catalog.resolve_call(name, catalog.initial_state())


def test_decision_accounting_preserves_task_allowance_and_round_trips_checkpoints():
    """Direct counter calls are accounting checks, not simulated agent runs."""
    budget = InferenceDecisionBudget(max_task_steps=4)
    for control in (SEARCH, SEARCH, INSPECT, EXPAND):
        assert budget.record("call", control)
    assert budget.remaining() == {"task_steps": 4, "discovery_steps": 8}
    restored = InferenceDecisionBudget(**budget.to_dict())
    assert restored.to_dict() == budget.to_dict()
    assert restored.record("call", "loaded_function")
    assert restored.record("answer")
    assert restored.task_steps == 2
    assert restored.discovery_steps == 4
    assert budget.task_steps == 0


def test_exhausted_discovery_rejects_and_charges_task_retries_until_finite_stop():
    budget = InferenceDecisionBudget(max_task_steps=3, max_discovery_steps=2)
    assert budget.record("call", SEARCH)
    assert budget.record("call", INSPECT)
    for remaining_task in (2, 1, 0):
        assert budget.can_decide()
        assert not budget.record("call", EXPAND)
        assert budget.remaining() == {"task_steps": remaining_task, "discovery_steps": 0}
    assert budget.exhausted() and not budget.can_decide()
    exhausted = budget.to_dict()
    assert not budget.record("answer")
    assert budget.to_dict() == exhausted
    assert budget.task_steps + budget.discovery_steps == 5


@pytest.mark.parametrize(
    "action,function",
    [
        ("call", None),
        ("call", []),
        ("call", "unknown_function"),
        ("answer", SEARCH),
        ("invalid_action", INSPECT),
    ],
)
def test_only_recognized_discovery_calls_are_exempt_from_task_count(action, function):
    budget = InferenceDecisionBudget(max_task_steps=1)
    assert budget.record(action, function)
    assert budget.exhausted()
    assert budget.discovery_steps == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {"max_task_steps": -1},
        {"max_task_steps": True},
        {"max_task_steps": 1, "max_discovery_steps": -1},
        {"max_task_steps": 1, "task_steps": 2},
        {"max_task_steps": 1, "discovery_steps": 13},
        {"max_task_steps": 1, "discovery_steps": 0.5},
    ],
)
def test_decision_budget_rejects_invalid_limits_and_checkpoint_counters(arguments):
    with pytest.raises(ValueError):
        InferenceDecisionBudget(**arguments)


def test_zero_decision_allowance_never_permits_a_model_decision():
    budget = InferenceDecisionBudget(max_task_steps=0)
    assert budget.exhausted()
    assert not budget.record("call", SEARCH)
    assert budget.task_steps == budget.discovery_steps == 0


def test_dependency_search_recovers_real_learned_temperature_readers(learned_weather_kernel):
    catalog = InferenceCatalog(learned_weather_kernel, page_size=2)
    _, cards = browse(catalog, catalog.initial_state(), query="forecast", kind="function")
    high_readers = {
        "/functions/" + function["name"]
        for function in learned_weather_kernel["functions"]
        if "Daily high temperature" in function["description"]
    }
    assert high_readers
    assert all(
        "forecast" not in function["description"].lower()
        for function in learned_weather_kernel["functions"]
        if "/functions/" + function["name"] in high_readers
    )
    assert high_readers <= {card["id"] for card in cards}
    assert catalog.manifest()["search_index_version"] == SEARCH_INDEX_VERSION
    identity_inputs = {
        "version": 1,
        "search_index_version": SEARCH_INDEX_VERSION,
        "kernel_id": catalog.kernel_id,
        "schema": learned_weather_kernel["schema"],
        "functions": learned_weather_kernel["functions"],
        "capabilities": learned_weather_kernel["catalog"]["tools"],
        "acquisition_bindings": learned_weather_kernel["acquisition_bindings"],
    }
    assert catalog.catalog_id == hashlib.sha256(canonical(identity_inputs)).hexdigest()
    identity_inputs["search_index_version"] = "name-description-lexical-v1"
    assert catalog.catalog_id != hashlib.sha256(canonical(identity_inputs)).hexdigest()


def test_generic_identifier_boundaries_preserve_whole_names_and_component_tokens():
    assert _tokens("DailyForecast XMLParser forecast_date") == {
        "dailyforecast",
        "daily",
        "forecast",
        "xmlparser",
        "xml",
        "parser",
        "date",
    }


def test_real_automatic_binding_exposes_source_constraints_without_rewriting_function(
    learned_weather_kernel,
):
    before = canonical(learned_weather_kernel)
    catalog = InferenceCatalog(learned_weather_kernel)
    function = learned_weather_kernel["functions"][0]
    binding = next(
        AcquisitionBinding.model_validate(item)
        for item in learned_weather_kernel["acquisition_bindings"]
        if item["function_name"] == function["name"]
    )
    state, result = catalog.dispatch(
        INSPECT, {"id": "/functions/" + function["name"]}, catalog.initial_state()
    )
    definition = result["definition"]["value"]
    acquisition = definition["acquisition"]
    assert acquisition["automatic"] is True
    assert "additional argument constraints" in acquisition["guidance"]
    assert definition["input_schema"] == function["inputs"]
    assert definition["input_schema"]["properties"]["source"] == {
        "description": "Weather forecast data source",
        "type": "string",
    }
    binding_id = "/acquisition_bindings/" + binding.binding_id
    capability_id = "/capabilities/" + binding.capability_id.replace("/", "~1")
    assert acquisition["binding_ids"] == [binding_id]
    assert acquisition["capability_ids"] == [capability_id]
    state, dependencies = browse(catalog, state, EXPAND, id="/functions/" + function["name"])
    assert {binding_id, capability_id} <= {item["id"] for item in dependencies}
    state, exact_binding = reconstruct(catalog, state, binding_id)
    assert exact_binding == binding.model_dump(mode="json")
    state, source_inputs = reconstruct(catalog, state, capability_id, "/input_schema")
    assert source_inputs["properties"]["source"]["enum"]
    assert source_inputs["properties"]["temperature_unit"]["enum"]
    assert binding.native_arguments["source"] == {"$arg": "source"}
    assert binding.native_arguments["temperature_unit"] == {"$arg": "temperature_unit"}
    assert canonical(learned_weather_kernel) == before
    _, schema_cards = browse(catalog, state, kind="schema")
    assert all(item["kind"] != "binding" for item in schema_cards)
