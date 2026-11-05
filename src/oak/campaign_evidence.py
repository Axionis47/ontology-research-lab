"""Reuse a campaign's genuine starter evidence without repeating its agent loop.

Snapshots are explicitly frozen comparison inputs. They are never presented as
fresh MCP dispatches or as successful execution of a different candidate.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from oak.store import Store, canonical


def starter_key(surface_id: str, query: dict, catalog_id: str | None) -> str:
    """Key immutable query and capability inputs within one construction campaign."""
    return hashlib.sha256(canonical([surface_id, query, catalog_id])).hexdigest()


def retained_starter(
    store: Store,
    episode_id: str,
    *,
    surface_id: str,
    query_id: str,
    catalog_id: str | None,
    document_reader: Callable[[dict], list[dict]],
) -> dict:
    """Read verified construction receipts, rejecting foreign/evaluation episodes.

    A completed acquisition remains useful even when the starter did not finish
    its question. Its recorded answer is deliberately excluded from this view.
    """
    episode = store.get(episode_id)
    if (
        episode.get("surface_id") != surface_id
        or episode.get("query_id") != query_id
        or episode.get("split") != "construction"
        or episode.get("mode") != "bootstrap"
        or episode.get("catalog_id") != catalog_id
    ):
        raise ValueError("Starter evidence does not match the frozen construction inputs")
    receipt_ids = list(
        dict.fromkeys(
            identity
            for observation in episode.get("observations", [])
            for identity in observation.get("receipt_ids", [])
        )
    )
    documents, retained = [], []
    for identity in receipt_ids:
        receipt = store.get(identity)
        if receipt.get("status") != "completed" or not receipt.get("tool_call_attempted"):
            continue
        documents.extend(document_reader({**receipt, "evidence_id": identity}))
        retained.append(identity)
    return {
        "episode_id": episode_id,
        "query_id": query_id,
        "receipt_ids": retained,
        "documents": documents,
        "source_snapshot": "recorded_campaign_evidence",
        "fresh_agent_evidence": False,
    }
