"""Campaign reuse on an actual recorded starter, without paid dispatch."""

from pathlib import Path

import pytest

from oak.bootstrap import receipt_documents
from oak.campaign_evidence import retained_starter, starter_key
from oak.store import Store


def test_retained_starter_reuses_sources_without_claiming_a_new_execution():
    root = Path(__file__).parents[1] / ".local"
    artifact = "4f5f485408ab689516fae4995abaec6e23c5fc953955e9f5cdb4db2c4995343d"
    if not (root / "artifacts" / f"{artifact}.json").exists():
        pytest.skip("Genuine two-flow construction starter is unavailable")
    store = Store(root)
    result = store.get(artifact)
    episode_id = result["episode_id"]
    episode = store.get(episode_id)
    before = store.budget()
    kwargs = {
        "surface_id": episode["surface_id"],
        "query_id": episode["query_id"],
        "catalog_id": episode["catalog_id"],
        "document_reader": receipt_documents,
    }
    view = retained_starter(store, episode_id, **kwargs)
    assert view["documents"] and view["receipt_ids"]
    assert view["fresh_agent_evidence"] is False
    assert "answer" not in view and "trajectory" not in view
    assert retained_starter(store, episode_id, **kwargs) == view
    assert store.budget() == before
    with pytest.raises(ValueError, match="frozen construction"):
        retained_starter(store, episode_id, **{**kwargs, "query_id": "wrong-query"})
    query = {"id": episode["query_id"], "query": episode["query"]}
    key = starter_key(episode["surface_id"], query, episode["catalog_id"])
    assert key == starter_key(episode["surface_id"], query, episode["catalog_id"])
    assert key != starter_key(episode["surface_id"], query, "changed-catalog")
