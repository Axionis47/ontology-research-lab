"""Read-only ontology exploration over immutable, real revision artifacts."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import streamlit as st

from oak.ontology_chart import graph_dot
from oak.ontology_view import entity_catalog, humanize, instance_view, schema_view
from oak.service import Service


@st.cache_data(max_entries=8, show_spinner=False)
def _catalog(revision_id: str, _schema: dict, _graph: dict) -> list[dict]:
    # Revision IDs address immutable content. The underscore arguments avoid
    # rehashing thousands of records on each inspection-only rerun.
    return entity_catalog(_schema, _graph)


@st.cache_data(max_entries=16, show_spinner=False)
def _neighborhood(revision_id: str, focus_id: str, _schema: dict, _graph: dict) -> dict:
    return instance_view(_schema, _graph, focus_id=focus_id, max_nodes=30, max_edges=80)


def _value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return "No value recorded"
    return json.dumps(value, ensure_ascii=False)


def _rules(lines: list[str]) -> None:
    for line in lines:
        st.write(line)


def _properties(rows: list[dict]) -> None:
    st.dataframe(
        [
            {
                "Property": row["label"],
                "Value type": row["datatype_label"],
                "Record rule": ("Required" if row["required"] else "Optional")
                + (" · One value" if row["functional"] else " · List"),
                **(
                    {
                        "Declared on": row["declared_by_label"],
                        "Inherited": "Yes" if row["inherited"] else "No",
                    }
                    if any(item["inherited"] for item in rows)
                    else {}
                ),
            }
            for row in rows
        ],
        hide_index=True,
        alt="Property names, value types, required fields, and declaring classes",
    )


def show_schema(revision: dict, key: str) -> None:
    schema, graph = revision["schema"], revision["graph"]
    view = schema_view(schema, graph)
    st.subheader("How the knowledge is organized")
    st.caption(
        "Concepts define kinds of things. Arrows name how they relate. Select a concept to inspect its rules."
    )
    degree = Counter(edge["source"] for edge in view["edges"])
    names = sorted(
        view["types"], key=lambda name: (-degree[name], -view["types"][name]["direct_count"], name)
    )
    selected = st.selectbox(
        "Inspect a concept",
        names,
        format_func=lambda name: view["types"][name]["label"],
        key=f"{key}_concept",
    )
    if selected is None:
        st.info("No concepts are declared in this revision.")
        return
    st.graphviz_chart(
        graph_dot(view, selected_id=selected),
        width="stretch",
        alt="Schema map. "
        + " ".join(
            f"{humanize(edge['source'])} {edge['label']} {humanize(edge['target'])}."
            for edge in view["edges"]
        ),
    )
    st.caption(
        "Drag to pan; scroll to zoom. Solid arrows are relationships. Dashed arrows mean ‘is a’. Red lines mean classes are disjoint."
    )
    node = view["types"][selected]
    with st.container(border=True):
        st.subheader(node["label"])
        if node["description"]:
            st.write(node["description"])
        st.caption(
            f"{node['direct_count']:,} records stored with this type · {node['compatible_count']:,} including subtypes"
        )
        if node["parents"]:
            st.write("**Is a:** " + ", ".join(humanize(name) for name in node["parents"]))
        st.write(f"**Identity field:** {humanize(node['primary_key'])}")
        st.caption(
            "Identifies a record within its concrete type. This is an application key, not an OWL hasKey axiom."
        )
        st.markdown("**Properties**")
        _properties(node["properties"])
        if any(row["inherited"] for row in node["properties"]):
            st.caption(
                "Inherited and local declarations remain separate, even when their field names match. Both sets of rules apply."
            )
        with st.expander("Property meanings and OWL rules"):
            for row in node["properties"]:
                st.write(f"**{row['declared_by_label']} / {row['label']}**")
                if row["description"]:
                    st.write(row["description"])
                st.write(row["record_rule"])
                st.write(row["ontology_rule"])
        st.markdown("**Class constraints**")
        disjoint = [
            edge
            for edge in view["edges"]
            if edge["kind"] == "disjoint"
            and ({selected, *node["ancestors"]} & {edge["source"], edge["target"]})
        ]
        _rules([line for edge in disjoint for line in edge["details"]])
        _rules([rule["text"] for rule in node["restrictions"]])
        if not disjoint and not node["restrictions"]:
            st.caption(
                "No disjoint classes or additional class restrictions declared. Property rules still apply."
            )
    st.markdown("**Relationships**")
    connected = [
        relation
        for relation in view["relations"]
        if selected in (relation["source"], relation["target"])
    ]
    if not connected:
        st.info(
            "No object relationships declared for this concept. Inheritance, when present, is shown separately in the map."
        )
    for relation in connected:
        count = sum(edge["relation"] == relation["id"] for edge in graph.get("edges", []))
        with st.container(border=True):
            st.write(
                f"**{relation['source_label']} → {relation['label']} → {relation['target_label']}**"
            )
            if relation["description"]:
                st.write(relation["description"])
            _rules(
                relation["details"][1:-1] if relation["description"] else relation["details"][1:]
            )
            st.caption(f"{count:,} explicit links in this revision")
    with st.expander("How to read these rules"):
        _rules(view["semantics"])


def _entity_sources(service: Service, revision: dict, entity: dict) -> None:
    with st.expander(
        "Source evidence for this entity",
        key=f"source_{revision['id']}_{entity['id']}",
        on_change="rerun",
    ) as evidence:
        if not evidence.open:
            return
        documents = {
            document["document_id"]: document
            for document in service.artifact(revision["documents_id"])
        }
        if not entity["sources"]:
            st.info("No source references recorded for this entity.")
        for number, source in enumerate(entity["sources"], 1):
            document = documents.get(source["document_id"])
            locator = source.get("source_ref") or (document or {}).get(
                "locator", "location not recorded"
            )
            st.write(f"**Source {number} · {locator}**")
            if document is None:
                st.warning("The referenced source document is unavailable in this revision.")
            elif document.get("record") is not None:
                st.json(document["record"])
            else:
                st.text(document.get("text", "No source text recorded."))


def show_entities(service: Service, revision: dict, key: str) -> None:
    schema, graph = revision["schema"], revision["graph"]
    catalog = _catalog(revision["id"], schema, graph)
    by_id = {node["id"]: node for node in catalog}
    view = schema_view(schema, graph)
    st.subheader("Explore the actual entities")
    st.caption(
        "Search by a name, date, or property value. Select a record to see its values, neighbors, and evidence."
    )
    names = sorted(
        view["types"],
        key=lambda name: (
            -sum(edge["source"] == name for edge in view["edges"]),
            -view["types"][name]["direct_count"],
            name,
        ),
    )
    selected_type = st.selectbox(
        "Entity type", names, format_func=humanize, key=f"{key}_entity_type"
    )
    if selected_type is None:
        return
    search = st.text_input(
        "Find an entity", placeholder="Search names, dates, or values", key=f"{key}_search"
    )
    needle = search.strip().casefold()
    matching = [
        node
        for node in catalog
        if (
            node["type"] == selected_type
            or selected_type in view["types"].get(node["type"], {}).get("ancestors", [])
        )
        and (
            not needle
            or needle in json.dumps([node["label"], node["values"]], ensure_ascii=False).casefold()
        )
    ]
    st.caption(
        f"{len(matching):,} matching records, including subtypes · {len(catalog):,} total entities · {len(graph.get('edges', [])):,} total relationships"
    )
    if not matching:
        st.info("No saved entities match this selection.")
        return
    # Paginate before sending labels to the browser, including the selector.
    filter_key = f"{key}_{selected_type}_{search}"
    pages = (len(matching) + 49) // 50
    page = (
        st.number_input(
            "Results page", min_value=1, max_value=pages, value=1, key=f"{filter_key}_page"
        )
        if pages > 1
        else 1
    )
    visible = matching[(page - 1) * 50 : page * 50]
    selected = st.selectbox(
        "Inspect an entity",
        [node["id"] for node in visible],
        format_func=lambda identity: by_id[identity]["label"],
        key=f"{filter_key}_{page}_entity",
    )
    entity = by_id[selected]
    neighborhood = _neighborhood(revision["id"], selected, schema, graph)
    if neighborhood["edges"]:
        st.graphviz_chart(
            graph_dot(neighborhood, selected_id=selected),
            width="stretch",
            alt="Saved relationships around "
            + entity["label"]
            + ". "
            + " ".join(edge["details"][0] for edge in neighborhood["edges"]),
        )
        st.caption(
            f"Showing {neighborhood['shown_nodes']} of {len(catalog):,} entities and {neighborhood['shown_edges']} of {len(graph['edges']):,} links, within one step of the selected entity. Directions are preserved."
        )
        if neighborhood["truncated_nodes"] or neighborhood["truncated_edges"]:
            st.warning(
                f"This neighborhood exceeds the display limit. {neighborhood['truncated_nodes']} neighboring entities and {neighborhood['truncated_edges']} eligible links are outside this view. Exact artifacts retain all records."
            )
    else:
        st.info(
            "This entity has no recorded relationships. Its properties and source evidence are shown below."
        )
    with st.container(border=True):
        st.subheader(entity["label"])
        st.caption(entity["type_label"])
        st.table(
            [
                {"Property": humanize(name), "Value": _value(value)}
                for name, value in entity["values"].items()
            ],
            hide_index=True,
            alt="Actual property values for the selected entity",
        )
    neighbors = [
        edge for edge in graph.get("edges", []) if selected in (edge["source"], edge["target"])
    ]
    if neighbors:
        st.markdown("**Follow a relationship**")
        inspected = {selected}
        for index, edge in enumerate(neighbors[:80]):
            other_id = edge["target"] if edge["source"] == selected else edge["source"]
            other = by_id.get(other_id)
            if other is None:
                continue
            direction = "→" if edge["source"] == selected else "←"
            st.write(
                f"{direction} **{humanize(edge['relation'])}** · {other['type_label']}: {other['label']}"
            )
            if other_id in inspected:
                continue
            inspected.add(other_id)
            with st.expander(f"Inspect linked entity {index + 1}: {other['label']}"):
                st.table(
                    [
                        {"Property": humanize(name), "Value": _value(value)}
                        for name, value in other["values"].items()
                    ],
                    hide_index=True,
                    alt="Property values of a linked entity",
                )
                _entity_sources(service, revision, other)
        if len(neighbors) > 80:
            st.caption(
                f"Showing 80 of {len(neighbors)} adjacent links. Download exact artifacts for all links."
            )
    _entity_sources(service, revision, entity)
    with st.expander("Browse matching records"):
        st.dataframe(
            [
                {
                    "Entity": node["label"],
                    "Type": node["type_label"],
                    **{humanize(name): _value(value) for name, value in node["values"].items()},
                }
                for node in visible
            ],
            hide_index=True,
            alt="Matching saved records with meaningful labels and property values",
        )
        st.caption(
            f"Records {(page - 1) * 50 + 1} to {min(page * 50, len(matching))} of {len(matching):,} matches"
        )
    with st.expander("Technical entity identifiers"):
        st.code(selected, language=None)
        st.json({"type": entity["type"], "sources": entity["sources"]})


def _expression(value: Any) -> str:
    if isinstance(value, dict):
        if "$arg" in value:
            return f"Input: {humanize(value['$arg'])}"
        if "$step" in value:
            return f"Result of {humanize(value['$step'])}"
        if "$path" in value:
            return " → ".join(humanize(str(part)) for part in value["$path"])
        return "; ".join(f"{humanize(name)}: {_expression(item)}" for name, item in value.items())
    if isinstance(value, list):
        return ", ".join(_expression(item) for item in value)
    return str(value)


def show_functions(revision: dict, key: str) -> None:
    st.subheader("What the agent can execute")
    st.caption(
        "These are the saved functions, F. The steps below show which entities and fields each function actually reads."
    )
    functions = revision.get("functions", [])
    if not functions:
        st.info("No functions are saved in this revision.")
        return
    position = st.selectbox(
        "Inspect a function",
        range(len(functions)),
        format_func=lambda index: humanize(functions[index]["name"]),
        key=f"{key}_function",
    )
    function = functions[position]
    st.write(function.get("description") or "No description recorded.")
    inputs = function.get("inputs", {})
    if inputs.get("properties"):
        st.table(
            [
                {
                    "Input": humanize(name),
                    "Type": spec.get("type", "See contract"),
                    "Required": "Yes" if name in inputs.get("required", []) else "No",
                }
                for name, spec in inputs["properties"].items()
            ],
            hide_index=True,
            alt="Function inputs and required values",
        )
    else:
        st.caption("No input arguments required.")
    st.markdown("**Execution steps**")
    for index, step in enumerate(function.get("steps", []), 1):
        with st.container(border=True):
            st.write(f"**{index}. {humanize(step['operator'])}**")
            st.caption(humanize(step["id"]))
            for name, value in step.get("args", {}).items():
                st.write(f"**{humanize(name)}:** {_expression(value)}")
    st.write(f"**Returns:** {_expression(function.get('result'))}")
    st.caption(
        "Schema relationships are used only when an execution step explicitly traverses them."
    )
    with st.expander("Exact function and result contract"):
        st.json(function)
