"""Inspect saved, genuine OaK revisions through the actual Streamlit controls.

These checks clone the real pilot catalog and reuse immutable artifacts. They
do not generate data, substitute a backend, or submit model/reasoner jobs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from oak.service import Service

ROOT = Path(__file__).resolve().parents[1]
USGS_TASK = "92a95ecf291d41d9887cdaa1be74fe67"
COFFEE_TASK = "6cd20839ae78451caa3fb68d77a060b7"


@pytest.fixture
def saved_workspace(tmp_path: Path) -> Service:
    if not (ROOT / ".local/catalog.sqlite").exists():
        pytest.skip("Run the genuine acceptance pilots before saved-ontology UI checks")
    with sqlite3.connect(f"file:{ROOT / '.local/catalog.sqlite'}?mode=ro", uri=True) as original:
        with sqlite3.connect(tmp_path / "catalog.sqlite") as snapshot:
            original.backup(snapshot)
    (tmp_path / "artifacts").symlink_to(ROOT / ".local/artifacts", target_is_directory=True)
    return Service(tmp_path)


def _audit_app(service: Service, task_id: str) -> AppTest:
    if task_id not in {task["id"] for task in service.tasks()}:
        pytest.skip("The genuine task pilot is not installed")
    task = service.task(task_id)
    if not task.get("active_revision"):
        pytest.skip("The genuine task pilot has no completed revision")
    return AppTest.from_string(
        "from oak.ui import _audit\n"
        "from oak.service import Service\n"
        f"service = Service({str(service.root)!r})\n"
        f"_audit(service, service.task({task_id!r}))\n",
        default_timeout=30,
    ).run()


def _section(app: AppTest, section: str) -> None:
    app.get("button_group")[0].set_value(section).run()
    assert not app.exception


def test_saved_earthquakes_have_readable_schema_and_real_entity_evidence(
    saved_workspace: Service,
) -> None:
    service = saved_workspace
    before_budget = service.budget()
    before_runs = service.runs(USGS_TASK)
    app = _audit_app(service, USGS_TASK)
    assert not app.exception
    revision = service.revision(USGS_TASK)
    graph = revision["graph"]
    versions = next(item for item in app.selectbox if item.label == "Revision")
    assert all(option.startswith("Version ") for option in versions.options)
    assert all(revision["id"] not in option for option in versions.options)
    assert versions.value == revision["id"]
    assert {item.label: item.value for item in app.metric} == {
        "Concepts": str(len(revision["schema"]["entity_types"])),
        "Entities": f"{len(graph['nodes']):,}",
        "Relationships": f"{len(graph['edges']):,}",
    }
    concept = next(item for item in app.selectbox if item.label == "Inspect a concept")
    assert concept.value == "EarthquakeEvent"
    assert "Earthquake Event" in concept.options
    assert any("At most one distinct target" in item.value for item in app.markdown)
    assert any("not an OWL hasKey" in item.value for item in app.caption)
    assert not any(revision["id"] in item.value for item in app.caption)
    property_table = next(table.value for table in app.dataframe if "Property" in table.value)
    assert "Place" in set(property_table["Property"])
    assert "Value type" in property_table
    assert "Record rule" in property_table

    _section(app, "Entities")
    selector = next(item for item in app.selectbox if item.label == "Inspect an entity")
    assert all(len(label) != 64 for label in selector.options)
    selected = next(node for node in graph["nodes"] if node["id"] == selector.value)
    assert selected["properties"]["place"] in selector.options
    assert any("Showing 4 of 60 entities and 3 of 45 links" in item.value for item in app.caption)
    value_table = app.table[0].value
    actual_values = dict(zip(value_table["Property"], value_table["Value"], strict=True))
    assert actual_values["Place"] == selected["properties"]["place"]
    assert float(actual_values["Magnitude"]) == selected["properties"]["magnitude"]
    assert float(actual_values["Depth km"]) == selected["properties"]["depth_km"]

    # Expander state is a supported Streamlit session-state control. AppTest
    # does not expose an expand() method, so open the actual keyed container.
    app.session_state[f"source_{revision['id']}_{selected['id']}"] = True
    app.run()
    assert not app.exception
    documents = {doc["document_id"]: doc for doc in service.artifact(revision["documents_id"])}
    expected_sources = [
        documents[source["document_id"]]["record"] for source in selected["sources"]
    ]
    visible_json = [json.loads(item.value) for item in app.json]
    assert all(source in visible_json for source in expected_sources)
    assert service.budget() == before_budget
    assert service.runs(USGS_TASK) == before_runs


def test_saved_coffee_exposes_inheritance_and_searchable_records(
    saved_workspace: Service,
) -> None:
    service = saved_workspace
    before_budget = service.budget()
    before_runs = service.runs(COFFEE_TASK)
    app = _audit_app(service, COFFEE_TASK)
    assert not app.exception
    revision = service.revision(COFFEE_TASK)
    assert any("Commodity Price Record" in item.value for item in app.markdown)
    property_table = next(table.value for table in app.dataframe if "Declared on" in table.value)
    assert len(property_table) == 14
    assert set(property_table["Declared on"]) == {"Coffee Market Day", "Commodity Price Record"}
    assert set(property_table["Inherited"]) == {"Yes", "No"}
    assert any("remain separate" in item.value for item in app.caption)
    assert any("No object relationships declared" in item.value for item in app.info)
    concept = next(item for item in app.selectbox if item.label == "Inspect a concept")
    concept.select("CommodityPriceRecord").run()
    assert not app.exception
    assert any(
        "0 records stored with this type · 5,746 including subtypes" in item.value
        for item in app.caption
    )

    _section(app, "Entities")
    assert any("no recorded relationships" in item.value for item in app.info)
    next(item for item in app.text_input if item.label == "Find an entity").set_value(
        "2000-01-03"
    ).run()
    assert not app.exception
    entity = next(item for item in app.selectbox if item.label == "Inspect an entity")
    assert entity.options == ["2000-01-03"]
    selected = next(node for node in revision["graph"]["nodes"] if node["id"] == entity.value)
    table = app.table[0].value
    values = dict(zip(table["Property"], table["Value"], strict=True))
    assert values["Date"] == selected["properties"]["Date"]
    assert float(values["High"]) == selected["properties"]["High"]
    assert any("1 matching records" in item.value for item in app.caption)
    assert service.budget() == before_budget
    assert service.runs(COFFEE_TASK) == before_runs


def test_saved_function_inspection_shows_actual_operations_without_execution(
    saved_workspace: Service,
) -> None:
    service = saved_workspace
    before_budget = service.budget()
    before_runs = service.runs(USGS_TASK)
    app = _audit_app(service, USGS_TASK)
    assert not app.exception
    revision = service.revision(USGS_TASK)
    _section(app, "Functions")
    functions = revision["functions"]
    depth_index = next(
        index for index, function in enumerate(functions) if function["name"] == "maximum_depth_km"
    )
    next(item for item in app.selectbox if item.label == "Inspect a function").select(
        depth_index
    ).run()
    assert not app.exception
    rendered = "\n".join(item.value for item in app.markdown)
    assert "Lookup entities" in rendered
    assert "Aggregate values" in rendered
    assert "depth_km" in rendered
    assert "EarthquakeEvent" in rendered
    assert any(
        "only when an execution step explicitly traverses" in item.value for item in app.caption
    )
    _section(app, "Checks")
    assert any("Held-out accuracy is not measured" in item.value for item in app.caption)
    app.run()
    assert not app.exception
    assert service.budget() == before_budget
    assert service.runs(USGS_TASK) == before_runs
