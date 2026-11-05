"""Domain-independent task surfaces, construction samples, and runtime context.

Task inputs contain requests and supplied evidence, never evaluator labels. A
surface can start without a corpus: real tool observations arrive during the
episode. Historical episodes contribute procedural summaries only, and must be
resolved from the artifact store before they can enter a new model context.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from oak.mcp_bridge import ServerConfig

Split = Literal["construction", "development", "heldout"]
ArtifactResolver = Callable[[str], Any]
PROMPT_DIRECTORY = Path(__file__).resolve().parents[2] / "config" / "prompts"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class StrictContract(BaseModel):
    """Reject unrecognized fields, type coercions, and nonfinite numbers."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class QueryInput(StrictContract):
    """Public request fields shared by pool entries and run-local inference."""

    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    requirements: list[str] = Field(default_factory=list)
    supplied_documents: list[dict[str, JsonValue]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_text(self) -> QueryInput:
        """Reject empty requests and invalid JSON evidence before model use."""
        if not self.id.strip() or not self.query.strip():
            raise ValueError("query id and text must contain non-whitespace characters")
        if any(not requirement.strip() for requirement in self.requirements):
            raise ValueError("requirements must contain non-whitespace characters")
        _canonical(self.supplied_documents)
        return self


class QuerySpec(QueryInput):
    """One immutable pool request and split, without reference answers."""

    split: Split


class InferenceQuery(QueryInput):
    """An immutable run-local request, never a member of a construction pool."""

    split: Literal["inference"] = "inference"


class RunLimits(StrictContract):
    """Per-episode execution bounds and a ceiling on new model spending."""

    max_steps: int = Field(default=8, ge=1, le=100)
    max_tool_calls: int = Field(default=6, ge=1, le=100)
    max_new_spend_usd: float = Field(default=5.0, gt=0)


class TaskSurface(StrictContract):
    """User-owned task scope and inputs, independent of any generated kernel.

    Server configuration is defined by the MCP bridge, not replicated here.
    Evaluators and reference labels remain outside this model. Query partitions
    are fixed at onboarding; only the construction partition is sampled.
    """

    format_version: Literal[1] = 1
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    base_prompt: str = Field(min_length=1)
    servers: list[ServerConfig] = Field(min_length=1)
    queries: list[QuerySpec] = Field(min_length=1)
    limits: RunLimits = Field(default_factory=RunLimits)
    seed: int = Field(default=42, ge=0)
    sampling_fraction: float = Field(default=0.2, gt=0, le=1)

    @model_validator(mode="after")
    def validate_surface(self) -> TaskSurface:
        """Keep identifiers unambiguous and exact requests out of two splits."""
        if any(not value.strip() for value in (self.name, self.description, self.base_prompt)):
            raise ValueError("surface name, description, and base_prompt must be nonempty")
        query_ids = [query.id for query in self.queries]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("query IDs must be unique across all partitions")
        server_names = [server.name for server in self.servers]
        if len(server_names) != len(set(server_names)):
            raise ValueError("MCP server names must be unique")
        partitions: dict[str, str] = {}
        for query in self.queries:
            fingerprint = _digest(
                {
                    "query": " ".join(query.query.split()).casefold(),
                    "requirements": query.requirements,
                    "supplied_documents": query.supplied_documents,
                }
            )
            if fingerprint in partitions and partitions[fingerprint] != query.split:
                raise ValueError("identical task inputs cannot occur in different partitions")
            partitions[fingerprint] = query.split
        return self


class SamplingReceipt(StrictContract):
    """Reproduce a fresh seeded draw from the immutable construction pool."""

    format_version: Literal[1] = 1
    strategy: Literal["seeded_random_without_replacement_per_round", "seeded_unseen_first"] = (
        "seeded_random_without_replacement_per_round"
    )
    seed: int
    round_index: int
    round_seed: str
    sampling_fraction: float
    pool_sha256: str
    pool_size: int
    sample_size: int
    selected_query_ids: list[str]
    previously_executed_query_ids: list[str] = Field(default_factory=list)


def sample_construction(
    surface: TaskSurface, round_index: int, *, seen_query_ids: list[str] | None = None
) -> SamplingReceipt:
    """Draw ceil(fraction * pool size), at least one, with no held-out access.

    ``round_index`` is zero-based. Draws are without replacement within a round;
    examples may recur between rounds, as fresh sampling is not a disjoint
    partition. Reordering the surface's query list does not change the draw.
    """
    surface = TaskSurface.model_validate(surface.model_dump(mode="json"))
    if type(round_index) is not int or round_index < 0:
        raise ValueError("round_index must be a nonnegative integer")
    pool = sorted(
        (query for query in surface.queries if query.split == "construction"),
        key=lambda query: query.id,
    )
    if not pool:
        raise ValueError("construction requires at least one construction query")
    pool_hash = _digest([query.model_dump(mode="json") for query in pool])
    round_seed = _digest(
        {"seed": surface.seed, "round_index": round_index, "pool_sha256": pool_hash}
    )
    size = max(1, math.ceil(surface.sampling_fraction * len(pool)))
    randomizer = random.Random(int(round_seed, 16))
    seen = set(seen_query_ids or [])
    if seen_query_ids is None:
        selected = randomizer.sample(pool, size)
    else:
        if not seen.issubset({query.id for query in pool}):
            raise ValueError("sampling history contains a non-construction query")
        unseen = [query for query in pool if query.id not in seen]
        repeated = [query for query in pool if query.id in seen]
        selected = randomizer.sample(unseen, min(size, len(unseen)))
        selected += randomizer.sample(repeated, size - len(selected))
    return SamplingReceipt(
        seed=surface.seed,
        round_index=round_index,
        round_seed=round_seed,
        sampling_fraction=surface.sampling_fraction,
        pool_sha256=pool_hash,
        pool_size=len(pool),
        sample_size=size,
        selected_query_ids=[query.id for query in selected],
        strategy="seeded_unseen_first"
        if seen_query_ids is not None
        else "seeded_random_without_replacement_per_round",
        previously_executed_query_ids=sorted(seen),
    )


def load_task_prompt(kind: Literal["runtime", "construction"]) -> str:
    """Read the versioned general prompt used by the corresponding stage."""
    if kind not in {"runtime", "construction"}:
        raise ValueError("prompt kind must be runtime or construction")
    return (PROMPT_DIRECTORY / f"task-{kind}.md").read_text(encoding="utf-8")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", text.casefold()))


def _resolve_query(surface: TaskSurface, query: QuerySpec | str) -> QuerySpec:
    query_id = query if isinstance(query, str) else query.id
    matches = [candidate for candidate in surface.queries if candidate.id == query_id]
    if not matches:
        raise ValueError(f"query {query_id!r} is absent from this task surface")
    selected = matches[0]
    if isinstance(query, QuerySpec) and query != selected:
        raise ValueError("query differs from its registered task-surface definition")
    return selected


def _history_card(
    identity: str,
    surface: TaskSurface,
    resolve: ArtifactResolver,
) -> dict[str, Any]:
    """Resolve evidence and expose only a procedural summary, never old values."""
    episode = resolve(identity)
    required = {"format_version", "query_id", "split", "query", "status", "observations"}
    if not isinstance(episode, dict) or not required.issubset(episode):
        raise ValueError("history must resolve to an episode manifest")
    if type(episode["format_version"]) is not int or episode["format_version"] != 1:
        raise ValueError("unsupported history episode format")
    query = _resolve_query(surface, episode["query_id"])
    if query.split != "construction" or episode["split"] != "construction":
        raise ValueError("only construction episodes may enter procedural history")
    if episode["query"] != query.query:
        raise ValueError("history query does not match its registered construction input")
    if not isinstance(episode["status"], str) or not isinstance(episode["observations"], list):
        raise ValueError("history status and observations have invalid types")
    route: list[str] = []
    receipt_ids: list[str] = []
    contracts: list[dict[str, Any]] = []
    function_route: list[dict[str, Any]] = []
    for observation in episode["observations"]:
        if not isinstance(observation, dict):
            raise ValueError("history observations must be objects")
        function = observation.get("function")
        if function is not None:
            if not isinstance(function, str) or not isinstance(observation.get("status"), str):
                raise ValueError("history function observations require a name and status")
            function_route.append({"function": function, "status": observation["status"]})
        execution_id = observation.get("execution_id")
        if execution_id is not None:
            if not isinstance(execution_id, str) or not isinstance(resolve(execution_id), dict):
                raise ValueError("history function execution must resolve to an artifact")
        references = observation.get("receipt_ids")
        if references is None:
            references = [observation["receipt_id"]] if observation.get("receipt_id") else []
        if not isinstance(references, list) or any(not isinstance(ref, str) for ref in references):
            raise ValueError("history receipt_ids must be a list of artifact identifiers")
        last_receipt = observation.get("receipt_id")
        if last_receipt is not None and (not references or references[-1] != last_receipt):
            raise ValueError("history's singular receipt must identify its last acquired result")
        if not references and observation.get("capability_id") is not None:
            raise ValueError("history claims a capability result without a call receipt")
        for receipt_id in references:
            receipt = resolve(receipt_id)
            capability = receipt.get("capability_id") if isinstance(receipt, dict) else None
            if not isinstance(capability, str):
                raise ValueError("history observation is not supported by its capability receipt")
            if receipt_id == last_receipt and observation.get("capability_id") != capability:
                raise ValueError("history observation disagrees with its last capability receipt")
            route.append(capability)
            receipt_ids.append(receipt_id)
            contracts.append(
                {"capability_id": capability, "contract_id": receipt.get("contract_id")}
            )
    return {
        "episode_id": identity,
        "query_id": query.id,
        "split": "construction",
        "query": query.query,
        "status": episode["status"],
        "capability_route": route,
        "function_route": function_route,
        "receipt_ids": receipt_ids,
        "capability_contracts": contracts,
        "use": "procedural_evidence_only; prior answers and observation values omitted",
    }


def build_runtime_context(
    surface: TaskSurface,
    query: QuerySpec | InferenceQuery | str,
    capability_catalog: list[dict[str, Any]],
    *,
    history: Sequence[str] = (),
    resolve_history: ArtifactResolver | None = None,
    history_limit: int = 3,
) -> dict[str, Any]:
    """Build an answer-free initial context and an inspectable history selection.

    ``history`` contains episode artifact IDs. ``resolve_history`` should be
    ``Store.get``, which verifies content identities. Every supplied history
    episode and referenced call receipt is checked, even if it ranks poorly.
    This first slice ranks by lexical token overlap. Semantic ranking and
    semantic compatibility are not implemented or claimed.
    """
    surface = TaskSurface.model_validate(surface.model_dump(mode="json"))
    selected = (
        InferenceQuery.model_validate(query.model_dump(mode="json"))
        if isinstance(query, InferenceQuery)
        else _resolve_query(surface, query)
    )
    if type(history_limit) is not int or not 0 <= history_limit <= 10:
        raise ValueError("history_limit must be an integer between zero and ten")
    if isinstance(history, (str, bytes)) or any(not isinstance(item, str) for item in history):
        raise ValueError("history must contain episode artifact ID strings")
    if len(history) != len(set(history)):
        raise ValueError("history must contain unique episode artifact IDs")
    if len(history) > 50:
        raise ValueError("first-slice history selection supports at most 50 episode manifests")
    if history and resolve_history is None:
        raise ValueError("history requires an artifact resolver; unverified history is refused")
    catalog = json.loads(_canonical(capability_catalog))
    if not isinstance(catalog, list) or any(not isinstance(item, dict) for item in catalog):
        raise ValueError("capability_catalog must be a list of tool contract objects")
    capability_contracts: dict[str, str] = {}
    for capability in catalog:
        identity, contract = capability.get("id"), capability.get("contract_id")
        if not isinstance(identity, str) or not isinstance(contract, str):
            raise ValueError("catalog entries require id and contract_id strings")
        if identity in capability_contracts:
            raise ValueError("capability IDs must be unique")
        capability_contracts[identity] = contract
    terms = _tokens(selected.query + " " + " ".join(selected.requirements))
    cards = []
    excluded = []
    for identity in history:
        card = _history_card(identity, surface, resolve_history)  # type: ignore[arg-type]
        if any(
            not item["contract_id"]
            or capability_contracts.get(item["capability_id"]) != item["contract_id"]
            for item in card["capability_contracts"]
        ):
            excluded.append(
                {"episode_id": identity, "reason": "capability_contract_absent_or_changed"}
            )
            continue
        card["lexical_overlap"] = len(
            terms & _tokens(card["query"] + " " + " ".join(card["capability_route"]))
        )
        cards.append(card)
    ranked = sorted(cards, key=lambda card: (-card["lexical_overlap"], card["episode_id"]))
    chosen = [card for card in ranked if card["lexical_overlap"] > 0][:history_limit]
    prompt = load_task_prompt("runtime")
    return {
        "format_version": 1,
        "task": {"name": surface.name, "description": surface.description},
        "base_prompt": surface.base_prompt,
        "runtime_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "query_id": selected.id,
        "query": selected.query,
        "requirements": selected.requirements,
        "supplied_facts": selected.supplied_documents,
        "capability_catalog": catalog,
        "procedural_history": chosen,
        "observations": [],
        "observation_state": (
            "Initial context contains no tool observations. Subsequent current-episode "
            "observations are supplied separately by the executor."
        ),
        "limits": surface.limits.model_dump(mode="json"),
        "history_selection": {
            "strategy": "deterministic_lexical_token_overlap",
            "semantic_ranking": "not_implemented",
            "semantic_compatibility": "not_established_by_retrieval",
            "interface_compatibility": "matching_capability_and_contract_ids_only",
            "eligible_split": "construction",
            "candidate_episode_ids": sorted(history),
            "selected_episode_ids": [card["episode_id"] for card in chosen],
            "limit": history_limit,
            "excluded": excluded,
            "rankings": [
                {"episode_id": card["episode_id"], "lexical_overlap": card["lexical_overlap"]}
                for card in ranked
            ],
        },
    }
