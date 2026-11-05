"""Deferred corpus views over an unchanged genuine retained Coffee kernel.

No model response or source load is substituted. The retained graph path uses
actual artifact bytes and executes its original frozen functions directly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oak.corpus_materialization import CorpusMaterializer
from oak.functions import execute_function
from oak.materialization import derive_demand
from oak.model import GeminiCLI
from oak.service import corpus_documents
from oak.store import Store

PROJECT = Path(__file__).parents[1]
ARTIFACTS = PROJECT / ".local/artifacts"
COFFEE_KERNEL = "0c7e58d98071595d62bb8f8276de18b96fbb6c76e520c3344e305ef46d95a431"


def artifact(identity):
    path = ARTIFACTS / f"{identity}.json"
    if not path.is_file():
        pytest.skip("Retained genuine Coffee kernel is unavailable in this checkout")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == identity
    return json.loads(raw)["data"]


def test_retained_corpus_view_is_deferred_cached_and_executes_the_original_function(tmp_path):
    kernel = artifact(COFFEE_KERNEL)
    store = Store(tmp_path / "store")
    run_id = store.create_run("retained-coffee", "ask", {"kernel_id": COFFEE_KERNEL})
    model = GeminiCLI(store, run_id)
    materialize = CorpusMaterializer(
        store,
        model,
        schema=kernel["schema"],
        kernel_id=COFFEE_KERNEL,
        corpus_id=kernel["corpus_id"],
        retained_graph=kernel["graph"],
        load_documents=lambda: corpus_documents(artifact(kernel["corpus_id"])),
    )
    assert materialize.documents is None and materialize.cache == {}
    assert not store.rows("SELECT * FROM model_calls")
    function = kernel["functions"][1]
    args = {"date": kernel["graph"]["nodes"][0]["properties"]["Date"]}
    demand = derive_demand(kernel["schema"], function, args)
    small = materialize(demand)
    assert len(small["nodes"]) == 1 and len(kernel["graph"]["nodes"]) == 5746
    full_result = execute_function(
        kernel["graph"], kernel["functions"], function["name"], args, schema=kernel["schema"]
    )
    small_result = execute_function(
        small, kernel["functions"], function["name"], args, schema=kernel["schema"]
    )
    assert small_result["value"] == full_result["value"]
    event_count = len(store.rows("SELECT * FROM events WHERE run_id=?", (run_id,)))
    assert materialize(demand) == small
    assert len(store.rows("SELECT * FROM events WHERE run_id=?", (run_id,))) == event_count
    assert materialize.documents is None
    assert not store.rows("SELECT * FROM model_calls")
    assert kernel == artifact(COFFEE_KERNEL)
