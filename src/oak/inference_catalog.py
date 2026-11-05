"""Bounded, read-only discovery of a frozen inference kernel.

Search is a navigation aid, never a capability filter. Empty searches enumerate
all entries; exact definitions, dependencies, and oversized fragments can always
be inspected by version-bound continuation. Execution still belongs to the
existing executor and its full-schema admission and validation boundaries.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from oak.functions import FunctionSpec
from oak.materialization import AcquisitionBinding
from oak.store import canonical

SEARCH = "oak_search_catalog"
INSPECT = "oak_inspect_definition"
EXPAND = "oak_expand_context"
CONTROL_NAMES = frozenset({SEARCH, INSPECT, EXPAND})
SEARCH_INDEX_VERSION = "dependency-lexical-v2"


@dataclass
class InferenceDecisionBudget:
    """Bound discovery separately while retaining the task decision allowance.

    This counter controls decisions, not provider spending. Callers must retain
    their existing spending limits and persist ``to_dict()`` with each decision.
    Only calls to the fixed discovery tools use the discovery allowance. Once
    that allowance is spent, further discovery requests are rejected and charge
    a task decision so an uncooperative planner cannot retry indefinitely.

    ``record`` accounts for the decision already obtained from the model. A
    final accepted task decision still executes after spending the final slot.
    ``can_decide`` determines whether another model decision may be requested.
    """

    max_task_steps: int
    max_discovery_steps: int = 12
    task_steps: int = 0
    discovery_steps: int = 0

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.task_steps > self.max_task_steps:
            raise ValueError("Recorded task decisions exceed their allowance")
        if self.discovery_steps > self.max_discovery_steps:
            raise ValueError("Recorded discovery decisions exceed their allowance")

    def to_dict(self) -> dict[str, int]:
        """Return constructor-shaped checkpoint state with limits and counters."""
        return {
            "max_task_steps": self.max_task_steps,
            "max_discovery_steps": self.max_discovery_steps,
            "task_steps": self.task_steps,
            "discovery_steps": self.discovery_steps,
        }

    def remaining(self) -> dict[str, int]:
        """Return remaining task and discovery decisions, separately."""
        return {
            "task_steps": self.max_task_steps - self.task_steps,
            "discovery_steps": self.max_discovery_steps - self.discovery_steps,
        }

    def exhausted(self) -> bool:
        """Stop when task decisions are spent, even if discovery remains."""
        return self.task_steps >= self.max_task_steps

    def can_decide(self) -> bool:
        """Whether the caller may request another decision from the model."""
        return not self.exhausted()

    def record(self, action: str, function: str | None = None) -> bool:
        """Account for a decision and say whether its action may run."""
        if self.exhausted():
            return False
        discovery = action == "call" and isinstance(function, str) and function in CONTROL_NAMES
        if discovery and self.discovery_steps < self.max_discovery_steps:
            self.discovery_steps += 1
            return True
        self.task_steps += 1
        return not discovery


class DiscoveryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DiscoveryContextSummary(DiscoveryContract):
    catalog_id: str
    kernel_id: str
    context_bytes: int = 0
    max_context_bytes: int = 36000
    loaded_function_ids: list[str] = Field(default_factory=list)
    view_definition_ids: list[str] = Field(default_factory=list)
    evicted_definition_ids: list[str] = Field(default_factory=list)


class DiscoveryResult(DiscoveryContract):
    """One actual read-only lookup, distinct from domain execution evidence."""

    version: Literal[1] = 1
    catalog_id: str
    kernel_id: str
    tool: str
    status: Literal["ok", "error"] = "ok"
    query: str = ""
    kind: str = "all"
    definition_id: str | None = None
    pointer: str = ""
    items: list[dict[str, JsonValue]] = Field(default_factory=list)
    total_count: int = 0
    offset: int = 0
    next_cursor: str | None = None
    has_more: bool = False
    complete: bool = True
    definition: JsonValue = None
    dependencies: list[str] = Field(default_factory=list)
    dependency_count: int = 0
    loaded_tool_name: str | None = None
    error: str | None = None
    context: DiscoveryContextSummary | None = None


class DiscoveryState(DiscoveryContract):
    """Small checkpoint state; canonical definitions stay in the frozen kernel."""

    version: Literal[1] = 1
    catalog_id: str
    loaded_function_ids: list[str] = Field(default_factory=list)
    views: list[dict[str, JsonValue]] = Field(default_factory=list)
    evicted_definition_ids: list[str] = Field(default_factory=list)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _tokens(value: str) -> set[str]:
    # Retain whole identifiers while also matching their snake_case, camelCase,
    # and acronym boundaries. This is lexical normalization, without synonyms
    # or domain-specific question patterns.
    split = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", value)
    split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", split)
    return set(re.findall(r"[^\W_]+", (value + " " + split).casefold(), flags=re.UNICODE))


def _excerpt(value: str, size: int = 260) -> tuple[str, bool]:
    return (value[:size], len(value) > size)


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    return "number"


class InferenceCatalog:
    """Version-bound schema/function discovery with bounded model-facing views.

    The complete kernel is retained internally and never copied into prompt
    state. Function definitions use familiar name, description, input_schema,
    and output_schema contracts. Large contracts are explicitly fragmentary
    in prompts and remain exact in ``as_langchain_tool`` and the real executor.
    """

    def __init__(
        self,
        kernel: dict,
        *,
        kernel_id: str | None = None,
        max_context_bytes: int = 36000,
        page_bytes: int = 8000,
        page_size: int = 8,
        max_loaded_tools: int = 4,
    ):
        if not 4096 <= max_context_bytes <= 96000:
            raise ValueError("Discovery context byte bound must be between 4096 and 96000")
        if not 512 <= page_bytes <= min(16000, max_context_bytes // 2):
            raise ValueError("Discovery page bound must fit within half the context bound")
        if not 1 <= page_size <= 32 or not 1 <= max_loaded_tools <= 8:
            raise ValueError("Discovery page/tool counts exceed their bounded range")
        from oak.schema_context import schema_entries

        self._kernel = deepcopy(kernel)
        self.kernel_id = kernel_id or kernel.get("id") or _digest(kernel)
        self.catalog_id = _digest(
            {
                "version": 1,
                "search_index_version": SEARCH_INDEX_VERSION,
                "kernel_id": self.kernel_id,
                "schema": kernel["schema"],
                "functions": kernel["functions"],
                "capabilities": kernel.get("catalog", {}).get("tools", []),
                "acquisition_bindings": kernel.get("acquisition_bindings", []),
            }
        )
        self.max_context_bytes = max_context_bytes
        self.page_bytes, self.page_size = page_bytes, page_size
        self.max_loaded_tools = max_loaded_tools
        self._entries = deepcopy(schema_entries(kernel["schema"]))
        self._functions, self._aliases = {}, {}
        for raw in kernel["functions"]:
            function = FunctionSpec.model_validate(raw).model_dump(mode="json")
            name = function["name"]
            identity = "/functions/" + _escape(name)
            alias = "oak_fn_" + name[:32] + "_" + _digest(name)[:12]
            if identity in self._entries or alias in self._aliases:
                raise ValueError("Frozen function names or discovery aliases collide")
            self._aliases[alias] = name
            self._functions[name] = identity
            definition = {
                "name": alias,
                "description": function["description"],
                "input_schema": function["inputs"],
                "output_schema": function["output_schema"],
            }
            # A conservative navigation dependency inventory, not a minimal
            # execution dependency claim. Runtime validation uses full S.
            literals = set()

            def visit(value, literals=literals):
                if isinstance(value, str):
                    literals.add(value)
                elif isinstance(value, dict):
                    literals.update(value)
                    for nested in value.values():
                        visit(nested)
                elif isinstance(value, list):
                    for nested in value:
                        visit(nested)

            visit(function["steps"])
            dependencies = sorted(
                key
                for key, entry in self._entries.items()
                if entry.get("name") in literals
                or entry.get("title") in literals
                or (
                    entry.get("kind") == "property" and entry["name"].rsplit(".", 1)[-1] in literals
                )
            )
            self._entries[identity] = {
                "kind": "function",
                "name": name,
                "description": function["description"],
                "definition": definition,
                "dependencies": dependencies,
                "tool_name": alias,
            }
        for capability in kernel.get("catalog", {}).get("tools", []):
            identity = "/capabilities/" + _escape(capability["id"])
            if identity in self._entries:
                raise ValueError("Frozen capability identifiers are not unique")
            self._entries[identity] = {
                "kind": "capability",
                "name": capability["id"],
                "description": capability.get("description", ""),
                "definition": {
                    key: deepcopy(capability[key])
                    for key in (
                        "id",
                        "contract_id",
                        "description",
                        "input_schema",
                        "output_schema",
                        "annotations",
                    )
                    if key in capability
                },
                "dependencies": [],
            }
        for raw_binding in kernel.get("acquisition_bindings", []):
            binding = AcquisitionBinding.model_validate(raw_binding)
            function_id = self._functions.get(binding.function_name)
            capability_id = "/capabilities/" + _escape(binding.capability_id)
            if function_id is None or capability_id not in self._entries:
                raise ValueError(
                    "Acquisition navigation requires a known frozen function and capability"
                )
            binding_id = "/acquisition_bindings/" + binding.binding_id
            self._entries[binding_id] = {
                "kind": "binding",
                "name": binding.function_name + " acquisition binding",
                "description": "Frozen automatic acquisition mapping from function arguments to source arguments.",
                "definition": binding.model_dump(mode="json"),
                "dependencies": [capability_id],
            }
            function = self._entries[function_id]
            function["dependencies"] = sorted(
                set([*function["dependencies"], binding_id, capability_id])
            )
            acquisition = function["definition"].setdefault(
                "acquisition",
                {
                    "automatic": True,
                    "binding_ids": [],
                    "capability_ids": [],
                    "guidance": "The runtime acquires source evidence automatically when this function executes. Do not search for or call an acquisition helper. Source contracts impose additional argument constraints such as enum values. Inspect these binding definitions for argument mappings and their capability definitions for exact source input constraints before supplying those arguments.",
                },
            )
            acquisition["binding_ids"] = sorted(set([*acquisition["binding_ids"], binding_id]))
            acquisition["capability_ids"] = sorted(
                set([*acquisition["capability_ids"], capability_id])
            )
        for identity, entry in self._entries.items():
            entry.setdefault("kind", "schema")
            entry.setdefault("name", identity)
            entry.setdefault("description", "")
            entry.setdefault("dependencies", [])
            missing = set(entry["dependencies"]) - self._entries.keys()
            if missing:
                raise ValueError(f"Schema navigation has missing declarations: {sorted(missing)}")
        self._search = {
            identity: _tokens(" ".join((identity, str(entry["name"]), str(entry["description"]))))
            for identity, entry in self._entries.items()
        }
        own_tokens = self._search
        self._search = {
            identity: tokens.union(
                *(own_tokens[dependency] for dependency in self._entries[identity]["dependencies"])
            )
            for identity, tokens in own_tokens.items()
        }

    def control_tools(self) -> list[dict]:
        """Three read-only tools; descriptions include recovery and expansion."""
        common = {
            "cursor": {
                "type": ["string", "null"],
                "description": "Exact next_cursor from this same lookup; null starts a lookup.",
            }
        }
        schemas = {
            SEARCH: {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "maxLength": 2000,
                        "default": "",
                        "description": "Terms to match in names, descriptions, and declared dependency metadata. Empty query browses every entry.",
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["all", "function", "schema", "capability", "binding"],
                        "default": "all",
                    },
                    **common,
                },
                "additionalProperties": False,
            },
            INSPECT: {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Exact definition id returned by search or dependency expansion.",
                    },
                    "pointer": {
                        "type": "string",
                        "default": "",
                        "description": "JSON Pointer inside this definition. Empty reads its root; deferred children return exact pointers.",
                    },
                    **common,
                },
                "required": ["id"],
                "additionalProperties": False,
            },
            EXPAND: {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Definition whose transitive schema, acquisition binding, and source capability dependencies should be browsed.",
                    },
                    **common,
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        }
        descriptions = {
            SEARCH: "Find frozen functions, schema declarations, automatic acquisition bindings or source capability contracts. Search returns summaries, never executes work. Retry other terms or use an empty query and next_cursor to browse everything. Inspect a function before calling its tool_name.",
            INSPECT: "Read exact frozen definition content and load a callable interface. Large content returns a bounded page with explicit deferred JSON pointers and next_cursor. Follow those pointers to inspect more. Reading schema, bindings or capabilities never executes a domain function.",
            EXPAND: "Discover all transitive dependencies of a function or declaration, including automatic acquisition bindings and exact source contracts. Follow next_cursor until exhausted, then inspect any relevant dependency. A navigation dependency list is not a certificate that a smaller schema is independently valid.",
        }
        return [
            {
                "name": name,
                "description": descriptions[name],
                "input_schema": schemas[name],
                "output_schema": DiscoveryResult.model_json_schema(),
                "annotations": {"readOnlyHint": True, "idempotentHint": True},
            }
            for name in (SEARCH, INSPECT, EXPAND)
        ]

    def initial_state(self) -> dict:
        return DiscoveryState(catalog_id=self.catalog_id).model_dump(mode="json")

    def manifest(self) -> dict:
        """Offline source and configuration receipt, never a model prompt."""
        return {
            "version": 1,
            "search_index_version": SEARCH_INDEX_VERSION,
            "catalog_id": self.catalog_id,
            "kernel_id": self.kernel_id,
            "schema_sha256": _digest(self._kernel["schema"]),
            "functions_sha256": _digest(self._kernel["functions"]),
            "capabilities_sha256": _digest(self._kernel.get("catalog", {}).get("tools", [])),
            "acquisition_bindings_sha256": _digest(self._kernel.get("acquisition_bindings", [])),
            "definition_ids": sorted(self._entries),
            "function_ids": sorted(self._functions.values()),
            "definition_count": len(self._entries),
            "function_count": len(self._functions),
            "max_context_bytes": self.max_context_bytes,
            "page_bytes": self.page_bytes,
            "page_size": self.page_size,
            "max_loaded_tools": self.max_loaded_tools,
            "controls": self.control_tools(),
        }

    def _state(self, state: dict) -> dict:
        result = DiscoveryState.model_validate(state).model_dump(mode="json")
        if result["catalog_id"] != self.catalog_id:
            raise ValueError(
                "Discovery state belongs to a different frozen kernel; start a new state"
            )
        if any(
            identity not in self._functions.values() for identity in result["loaded_function_ids"]
        ):
            raise ValueError("Discovery state references an unknown frozen function")
        return result

    def _card(self, identity: str) -> dict:
        entry = self._entries[identity]
        description, abbreviated = _excerpt(str(entry["description"]))
        return {
            "id": identity,
            "kind": entry["kind"],
            "name": entry["name"],
            "description": description,
            "description_is_excerpt": abbreviated,
            "definition_bytes": len(canonical(entry["definition"])),
            "dependency_count": len(entry["dependencies"]),
            **({"tool_name": entry["tool_name"]} if entry.get("tool_name") else {}),
        }

    def _tool_view(self, identity: str) -> dict:
        """Present a full small contract or explicit large-contract navigation.

        A fragmentary prompt view is not a native provider tool declaration.
        ``as_langchain_tool`` always uses the complete original JSON schemas.
        """
        definition = deepcopy(self._entries[identity]["definition"])
        if len(canonical(definition)) <= self.page_bytes:
            return {**definition, "definition_id": identity, "contract_complete": True}
        description, abbreviated = _excerpt(definition["description"], 500)
        return {
            "name": definition["name"],
            "description": description,
            "description_is_excerpt": abbreviated,
            "definition_id": identity,
            "contract_complete": False,
            "input_schema_ref": {"id": identity, "pointer": "/input_schema"},
            "output_schema_ref": {"id": identity, "pointer": "/output_schema"},
            **(
                {"acquisition_ref": {"id": identity, "pointer": "/acquisition"}}
                if "acquisition" in definition
                else {}
            ),
            "guidance": "Inspect the exact contract fragments needed to supply arguments. The executor validates the full unchanged contract.",
        }

    def _prompt(self, state: dict) -> dict:
        # Control output schemas use a local generic result contract reference
        # rather than repeating the same several-kilobyte schema three times.
        controls = self.control_tools()
        for tool in controls:
            tool["output_schema"] = {
                "type": "object",
                "description": "Versioned discovery receipt with status, exact fragments, continuation and context accounting.",
            }
        return {
            "version": 1,
            "catalog_id": self.catalog_id,
            "kernel_id": self.kernel_id,
            "catalog_counts": {
                "functions": len(self._functions),
                "definitions": len(self._entries),
            },
            "instructions": "Use search, inspect and expansion to discover this frozen kernel. Only inspected callable tool names can execute. Empty searches and pagination recover misses. Schema/capability entries are read-only definitions. Definitions may be evicted to bound context and can be inspected again. The complete kernel, full validation and historical replay gate remain executor-owned.",
            "tools": [
                *controls,
                *[self._tool_view(identity) for identity in state["loaded_function_ids"]],
            ],
            "definitions": deepcopy(state["views"]),
            "evicted_definition_ids": state["evicted_definition_ids"],
            "max_context_bytes": self.max_context_bytes,
        }

    def prompt(self, state: dict) -> dict:
        """Return bounded actual prompt content, never full function programs."""
        checked = self._state(state)
        result = self._prompt(checked)
        if len(canonical(result)) > self.max_context_bytes:
            raise ValueError(
                "Discovery state exceeds its context budget; use a state returned by dispatch"
            )
        return result

    def _summary(self, state: dict) -> DiscoveryContextSummary:
        return DiscoveryContextSummary(
            catalog_id=self.catalog_id,
            kernel_id=self.kernel_id,
            context_bytes=len(canonical(self._prompt(state))),
            max_context_bytes=self.max_context_bytes,
            loaded_function_ids=state["loaded_function_ids"],
            view_definition_ids=list(
                dict.fromkeys(
                    view["definition_id"] for view in state["views"] if view.get("definition_id")
                )
            ),
            evicted_definition_ids=state["evicted_definition_ids"],
        )

    def context_summary(self, state: dict, view: dict | None = None) -> DiscoveryContextSummary:
        """Return typed byte accounting for the exact reproducible prompt view."""
        checked = self._state(state)
        expected = self.prompt(checked)
        if view is not None and canonical(view) != canonical(expected):
            raise ValueError("Context accounting must refer to this state's exact prompt view")
        return self._summary(checked)

    def _cursor(self, operation: str, key: dict, offset: int) -> str:
        body = {
            "version": 1,
            "catalog_id": self.catalog_id,
            "operation": operation,
            "key": key,
            "offset": offset,
        }
        raw = canonical({"body": body, "sha256": _digest(body)})
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def _offset(self, cursor: str | None, operation: str, key: dict) -> int:
        if cursor is None:
            return 0
        if len(cursor) > 16000:
            raise ValueError("Invalid discovery cursor size; start the lookup again")
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            body = data["body"]
            expected = {
                "version": 1,
                "catalog_id": self.catalog_id,
                "operation": operation,
                "key": key,
                "offset": body["offset"],
            }
            if (
                body != expected
                or data["sha256"] != _digest(body)
                or type(body["offset"]) is not int
                or body["offset"] < 0
            ):
                raise ValueError
            return body["offset"]
        except (ValueError, KeyError, TypeError, UnicodeError) as error:
            raise ValueError(
                "Cursor does not match this frozen catalog and lookup; restart the lookup"
            ) from error

    def _ranked(self, query: str, kind: str) -> list[str]:
        terms = _tokens(query)
        selected = [
            identity
            for identity, entry in self._entries.items()
            if kind == "all"
            or entry["kind"] == kind
            or (kind == "schema" and entry["kind"] not in {"function", "capability", "binding"})
        ]
        if not terms:
            return sorted(selected)
        return sorted(
            (identity for identity in selected if terms & self._search[identity]),
            key=lambda identity: (-len(terms & self._search[identity]), identity),
        )

    def _page_cards(self, identities: list[str], offset: int) -> tuple[list[dict], int]:
        if offset > len(identities):
            raise ValueError("Cursor offset exceeds this lookup")
        cards = []
        while offset < len(identities) and len(cards) < self.page_size:
            card = self._card(identities[offset])
            if cards and len(canonical([*cards, card])) > self.page_bytes:
                break
            if len(canonical(card)) > self.page_bytes:
                raise ValueError(
                    "A definition identifier exceeds the page bound; inspect its exact id"
                )
            cards.append(card)
            offset += 1
        return cards, offset

    def _read_pointer(self, value: Any, pointer: str) -> Any:
        if pointer == "":
            return value
        if not pointer.startswith("/"):
            raise ValueError("Definition pointer must be empty or begin with /")
        for raw in pointer[1:].split("/"):
            if re.search(r"~(?![01])", raw):
                raise ValueError("Invalid JSON Pointer escape")
            key = raw.replace("~1", "/").replace("~0", "~")
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif (
                isinstance(value, list)
                and key.isdigit()
                and str(int(key)) == key
                and int(key) < len(value)
            ):
                value = value[int(key)]
            else:
                raise ValueError("Definition pointer is absent; inspect its parent or search again")
        return value

    def _fragment(self, value: Any, pointer: str, offset: int) -> tuple[dict, int, int]:
        size = len(canonical(value))
        if size <= self.page_bytes:
            if offset:
                raise ValueError("This exact fragment has no further page")
            return {"pointer": pointer, "value": deepcopy(value), "complete": True}, 0, 0
        if isinstance(value, str):
            if offset >= len(value):
                raise ValueError("String fragment offset is outside the definition")
            end = min(len(value), offset + self.page_bytes // 6)
            fragment = {
                "pointer": pointer,
                "type": "string",
                "string_fragment": value[offset:end],
                "character_offset": offset,
                "total_characters": len(value),
                "complete": False,
            }
            return fragment, end, len(value)
        if not isinstance(value, dict | list):
            raise ValueError("Scalar definition exceeds the explicit fragment byte bound")
        children = sorted(value) if isinstance(value, dict) else list(range(len(value)))
        if offset >= len(children):
            raise ValueError("Definition page offset is outside its children")
        items = []
        while offset < len(children) and len(items) < self.page_size:
            key = children[offset]
            nested = value[key]
            child_pointer = pointer + "/" + _escape(str(key))
            item = {"key": key, "pointer": child_pointer, "type": _json_type(nested)}
            if len(canonical(nested)) <= self.page_bytes // 3:
                item["value"] = deepcopy(nested)
            else:
                item.update(deferred=True, bytes=len(canonical(nested)))
            if items and len(canonical([*items, item])) > self.page_bytes:
                break
            if len(canonical(item)) > self.page_bytes:
                raise ValueError("A definition key exceeds the explicit fragment byte bound")
            items.append(item)
            offset += 1
        return (
            {
                "pointer": pointer,
                "type": _json_type(value),
                "children": items,
                "complete": False,
                "guidance": "Values are exact. Inspect deferred child pointers; follow next_cursor for remaining siblings.",
            },
            offset,
            len(children),
        )

    def _expand_ids(self, identity: str) -> list[str]:
        seen, pending = set(), list(self._entries[identity]["dependencies"])
        while pending:
            current = pending.pop()
            if current == identity or current in seen:
                continue
            seen.add(current)
            pending.extend(self._entries[current]["dependencies"])
        return sorted(seen)

    def dispatch(self, tool_name: str, args: dict, state: dict) -> tuple[dict, dict]:
        """Execute only catalog reads and return a small immutable-state update."""
        state = self._state(state)
        base = {"catalog_id": self.catalog_id, "kernel_id": self.kernel_id, "tool": tool_name}
        result = DiscoveryResult(**base)
        try:
            tools = {tool["name"]: tool for tool in self.control_tools()}
            if tool_name not in tools:
                raise ValueError("Unknown discovery tool; use the three advertised control names")
            Draft202012Validator(tools[tool_name]["input_schema"]).validate(args)
            if tool_name == SEARCH:
                query, kind = args.get("query", ""), args.get("kind", "all")
                key = {"query": query, "kind": kind}
                offset = self._offset(args.get("cursor"), tool_name, key)
                identities = self._ranked(query, kind)
                cards, after = self._page_cards(identities, offset)
                result = result.model_copy(
                    update={
                        "query": query,
                        "kind": kind,
                        "items": cards,
                        "total_count": len(identities),
                        "offset": offset,
                        "has_more": after < len(identities),
                        "complete": after == len(identities),
                        "next_cursor": self._cursor(tool_name, key, after)
                        if after < len(identities)
                        else None,
                    }
                )
            else:
                identity = args["id"]
                if identity not in self._entries:
                    raise ValueError("Unknown definition id; search or browse this frozen catalog")
                entry = self._entries[identity]
                key = {
                    "id": identity,
                    **({"pointer": args.get("pointer", "")} if tool_name == INSPECT else {}),
                }
                offset = self._offset(args.get("cursor"), tool_name, key)
                if tool_name == EXPAND:
                    identities = self._expand_ids(identity)
                    cards, after = self._page_cards(identities, offset)
                    result = result.model_copy(
                        update={
                            "definition_id": identity,
                            "kind": entry["kind"],
                            "items": cards,
                            "total_count": len(identities),
                            "offset": offset,
                            "has_more": after < len(identities),
                            "complete": after == len(identities),
                            "next_cursor": self._cursor(tool_name, key, after)
                            if after < len(identities)
                            else None,
                        }
                    )
                else:
                    pointer = args.get("pointer", "")
                    value = self._read_pointer(entry["definition"], pointer)
                    fragment, after, total = self._fragment(value, pointer, offset)
                    result = result.model_copy(
                        update={
                            "definition_id": identity,
                            "kind": entry["kind"],
                            "pointer": pointer,
                            "definition": fragment,
                            "complete": fragment["complete"],
                            "total_count": total,
                            "offset": offset,
                            "has_more": after < total,
                            "next_cursor": self._cursor(tool_name, key, after)
                            if after < total
                            else None,
                            "dependencies": entry["dependencies"][: self.page_size],
                            "dependency_count": len(entry["dependencies"]),
                            "loaded_tool_name": entry.get("tool_name"),
                        }
                    )
                    if entry["kind"] == "function":
                        state["loaded_function_ids"] = [
                            item for item in state["loaded_function_ids"] if item != identity
                        ] + [identity]
        except (ValueError, KeyError, TypeError, ValidationError) as error:
            result = DiscoveryResult(
                **base, status="error", error=str(error)[:1500], complete=False
            )
        # Never keep an unbounded transcript of searches or definitions in the
        # model context. Caller persists full receipts separately for inspection.
        view = result.model_dump(mode="json", exclude_none=True, exclude={"context"})
        if (
            result.loaded_tool_name
            and not result.pointer
            and self._entries[result.definition_id]["kind"] == "function"
            and result.complete
        ):
            view.pop("definition", None)
            view["contract_location"] = "tools"
        state["views"] = [*state["views"], view]
        evicted = []
        while len(state["loaded_function_ids"]) > self.max_loaded_tools:
            evicted.append(state["loaded_function_ids"].pop(0))
        while len(state["views"]) > 3:
            old = state["views"].pop(0)
            if old.get("definition_id"):
                evicted.append(old["definition_id"])
        state["evicted_definition_ids"] = list(dict.fromkeys(evicted))
        while len(canonical(self._prompt(state))) > self.max_context_bytes:
            if state["views"]:
                old = state["views"].pop(0)
                if old.get("definition_id"):
                    evicted.append(old["definition_id"])
            elif state["loaded_function_ids"]:
                evicted.append(state["loaded_function_ids"].pop(0))
            else:
                raise ValueError("Configured context bound cannot hold the fixed discovery tools")
            state["evicted_definition_ids"] = list(dict.fromkeys(evicted))[-32:]
        state = DiscoveryState.model_validate(state).model_dump(mode="json")
        result = result.model_copy(update={"context": self._summary(state)})
        return state, result.model_dump(mode="json")

    def resolve_call(self, tool_name: str, state: dict) -> str:
        """Resolve an inspected agent tool to its unchanged executor function name."""
        state = self._state(state)
        if not isinstance(tool_name, str):
            raise ValueError(
                "Callable tool name must be a string. Search and inspect a function, then use its tool_name."
            )
        original = self._aliases.get(tool_name)
        if original is None:
            hint = self._functions.get(tool_name)
            raise ValueError(
                "Unknown callable tool name. Search and inspect a function, then use its tool_name."
                + (f" Inspect {hint}." if hint else "")
            )
        if self._functions[original] not in state["loaded_function_ids"]:
            raise ValueError(
                f"Callable contract is not loaded or was evicted. Inspect {self._functions[original]} and retry."
            )
        return original

    def as_langchain_tool(
        self, tool_name: str, state: dict, executor: Callable[[str, dict], Any]
    ) -> StructuredTool:
        """Expose an actual inspected function through LangChain's tool interface.

        ``executor`` owns execution, persistence and authorization and returns
        the callable's public value. This wrapper supplies exact input/output
        JSON validation; it never substitutes historical outputs or acquires
        independent access to models, services, or a different kernel.
        """
        original = self.resolve_call(tool_name, state)
        definition = self._entries[self._functions[original]]["definition"]

        def invoke(**arguments):
            Draft202012Validator(
                definition["input_schema"], format_checker=FormatChecker()
            ).validate(arguments)
            output = executor(original, arguments)
            Draft202012Validator(
                definition["output_schema"], format_checker=FormatChecker()
            ).validate(output)
            return output

        return StructuredTool.from_function(
            func=invoke,
            name=tool_name,
            description=definition["description"],
            args_schema=deepcopy(definition["input_schema"]),
            infer_schema=False,
            metadata={
                "catalog_id": self.catalog_id,
                "kernel_id": self.kernel_id,
                "definition_id": self._functions[original],
                "output_schema": deepcopy(definition["output_schema"]),
            },
        )
