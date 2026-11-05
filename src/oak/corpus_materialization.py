"""Deferred corpus extraction through the same evidence-demand contract as MCP.

Constructing this object does not read source documents or call a model. A
selected frozen function supplies the demand that triggers materialization.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from oak.materialization import (
    MATERIALIZATION_VERSION,
    EvidenceDemand,
    materialization_cache_key,
    slice_graph,
)
from oak.model import GeminiCLI
from oak.pipeline import build_graph
from oak.store import Store


class CorpusMaterializer:
    """Run-local source materialization with optional genuine frozen-graph reuse."""

    def __init__(
        self,
        store: Store,
        model: GeminiCLI,
        *,
        schema: dict,
        kernel_id: str,
        corpus_id: str,
        load_documents: Callable[[], list[dict]],
        retained_graph: dict | None = None,
    ):
        self.store = store
        self.model = model
        self.schema = deepcopy(schema)
        self.kernel_id = kernel_id
        self.corpus_id = corpus_id
        self.load_documents = load_documents
        self.retained_graph = deepcopy(retained_graph)
        self.cache: dict[str, str] = {}
        self.documents: list[dict] | None = None

    def __call__(self, demand: EvidenceDemand) -> dict:
        """Materialize only after a frozen function has provided a typed demand."""
        key = materialization_cache_key(
            self.corpus_id, self.kernel_id, MATERIALIZATION_VERSION, demand
        )
        if key in self.cache:
            return self.store.get(self.cache[key])
        self.store.event(
            self.model.run_id,
            "materialization_plan",
            "running",
            "Materialize the selected corpus computation",
            {
                "flow": "instantiation",
                "kernel_id": self.kernel_id,
                "corpus_id": self.corpus_id,
                "demand_id": demand.demand_id,
                "demand": demand.model_dump(mode="json"),
                "retained_graph_available": self.retained_graph is not None,
            },
        )
        if self.retained_graph is not None:
            incoming = slice_graph(self.schema, self.retained_graph, demand)
            origin = "retained_source_graph"
        else:
            if self.documents is None:
                self.documents = self.load_documents()
            incoming = build_graph(
                self.store,
                self.model,
                self.schema,
                self.documents,
                f"inference_extract.{len(self.cache)}",
                demand=demand,
            )
            origin = "fresh_demand_extraction"
        graph_id = self.store.put("corpus_materialization", incoming)
        self.cache[key] = graph_id
        self.store.event(
            self.model.run_id,
            "materialization",
            "completed",
            "Actual corpus evidence materialized",
            {
                "flow": "instantiation",
                "graph_id": graph_id,
                "demand_id": demand.demand_id,
                "origin": origin,
                "node_count": len(incoming["nodes"]),
                "edge_count": len(incoming["edges"]),
            },
        )
        return incoming
