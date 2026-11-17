"""A bounded actor-facing view of a discovered MCP catalog."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from jsonschema import Draft202012Validator
from react_runtime.policy import rank_tools


class Catalog:
    def __init__(self, tools: list[dict], application: str):
        self.allowed_apps = {application, "supervisor", "api_docs"}
        self.tools = {}
        for original in tools:
            tool = deepcopy(original)
            name = tool["name"]
            if name.split("__", 1)[0] not in self.allowed_apps:
                continue
            if name in self.tools:
                raise ValueError(f"Duplicate MCP tool: {name}")
            schema = tool.get("inputSchema", tool.get("input_schema"))
            if not isinstance(schema, dict):
                raise ValueError(f"Missing MCP input schema: {name}")
            Draft202012Validator.check_schema(schema)
            tool["inputSchema"] = schema
            self.tools[name] = tool
        if not self.tools:
            raise ValueError("No tools discovered for the selected task surface")
        self.revision = hashlib.sha256(json.dumps(self.tools, sort_keys=True).encode()).hexdigest()
        self.cache = {}

    def discover(self, query: str = "", offset: int = 0, limit: int = 5, strategy: str = "legacy") -> dict:
        if offset < 0 or not 1 <= limit <= 10:
            raise ValueError("Discovery requires offset >= 0 and 1 <= limit <= 10")
        key = (self.revision, query, json.dumps(strategy, sort_keys=True))
        if key not in self.cache:
            if strategy == "legacy":
                words = query.casefold().split()
                matches = [t for _, t in sorted(self.tools.items()) if all(
                    w in (t["name"] + " " + t.get("description", "")).casefold() for w in words)]
            else: matches = rank_tools(self.tools.values(), query, strategy)
            self.cache[key] = matches
        matches = self.cache[key]
        page = matches[offset:offset + limit]
        return {"catalog_revision": self.revision, "total_matches": len(matches),
                "tools": [{"name": t["name"], "description": t.get("description", "")[:220]} for t in page],
                "next_offset": offset + len(page) if offset + len(page) < len(matches) else None}

    def describe(self, name: str) -> dict:
        if name not in self.tools:
            raise KeyError("Tool is outside the discovered task surface")
        return {"catalog_revision": self.revision, "tool": self.tools[name]}

    def validate_call(self, name: str, arguments: dict) -> dict:
        tool = self.describe(name)["tool"]
        # Native schemas are authoritative. Reject undeclared API parameters
        # rather than allowing SDK-internal override kwargs through the bridge.
        schema = deepcopy(tool["inputSchema"])
        schema["additionalProperties"] = False
        Draft202012Validator(schema).validate(arguments)
        return tool
