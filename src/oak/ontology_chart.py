"""Native Graphviz diagrams with readable labels and explicit edge semantics.

The DOT string goes to Streamlit's bundled Graphviz WASM renderer. All artifact
text is quoted as a literal, never interpreted as HTML or DOT instructions.
"""

from __future__ import annotations

import hashlib
import json
import textwrap
from typing import Any

_FILLS = ("#e0edff", "#d9f4eb", "#f4e5fc", "#fff0cf", "#fce1e8", "#ddf1f7")


def _quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _wrap(value: str) -> str:
    return "\n".join(textwrap.wrap(str(value), width=27))


def graph_dot(view: dict[str, Any], *, selected_id: str | None = None) -> str:
    """Draw exactly the nodes/edges in an already bounded presentation view."""
    nodes, edges = view.get("nodes", []), view.get("edges", [])
    identities = {str(node["id"]) for node in nodes}
    if len(identities) != len(nodes):
        raise ValueError("Chart nodes must have unique identifiers")
    if any(str(edge[end]) not in identities for edge in edges for end in ("source", "target")):
        raise ValueError("Chart edges must refer to nodes in the supplied view")
    lines = [
        "digraph ontology {",
        'graph [rankdir=LR, bgcolor="transparent", pad="0.25", nodesep="0.45", ranksep="0.7"];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=14, fontcolor="#172033", margin="0.18,0.14"];',
        'edge [fontname="Arial", fontsize=12, color="#94a3b8", fontcolor="#94a3b8", penwidth=1.6, arrowsize=0.85];',
    ]
    for node in nodes:
        selected = str(node["id"]) == selected_id
        group = str(node.get("type", node["id"]))
        index = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % len(_FILLS)
        label = _wrap(node["label"])
        if node.get("subtitle"):
            label += "\n" + _wrap(node["subtitle"])
        color = "#2563eb" if selected else "#94a3b8"
        fill = "#dbeafe" if selected else _FILLS[index]
        lines.append(
            f'{_quote(node["id"])} [label={_quote(label)}, fillcolor="{fill}", '
            f'color="{color}", penwidth={3 if selected else 1}];'
        )
    for edge in edges:
        kind = edge.get("kind", "relation")
        style = "dashed" if kind == "inheritance" else "solid"
        color = "#ef4444" if kind == "disjoint" else "#94a3b8"
        arrow = "none" if kind == "disjoint" else "empty" if kind == "inheritance" else "normal"
        lines.append(
            f"{_quote(edge['source'])} -> {_quote(edge['target'])} "
            f'[label={_quote(_wrap(edge["label"]))}, style="{style}", '
            f'color="{color}", fontcolor="{color}", arrowhead="{arrow}"];'
        )
    return "\n".join([*lines, "}"])
