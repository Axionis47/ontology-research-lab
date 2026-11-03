"""Real MCP discovery and explicit, version-bound calls through the official SDK.

Server configurations are reviewed application inputs, never model-generated
commands. The allowlist declares the read-only surface approved for this pilot;
MCP annotations alone do not authorize a capability. Resolved environment values
are passed only to the subprocess and are never included in configuration receipts.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from copy import deepcopy
from typing import Any, Literal
from urllib.parse import urlsplit

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, ConfigDict, Field, model_validator

from oak.store import Store, canonical, now

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SENSITIVE_NAME = re.compile(r"secret|token|password|credential|api.?key|authorization", re.I)


class ServerConfig(BaseModel):
    """One reviewed server and its explicitly permitted read-only tools.

    ``env_refs`` maps subprocess variable names to names in the host environment.
    It contains references, not values. HTTP authentication and model-selected
    subprocesses are outside this initial bridge's contract.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    transport: Literal["stdio", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env_refs: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @model_validator(mode="after")
    def check_connection(self) -> ServerConfig:
        """Reject ambiguous transports, duplicate tools, and literal credentials."""
        if self.transport == "stdio":
            if not self.command or not self.command.strip() or self.url is not None:
                raise ValueError("stdio requires a command and no URL")
        else:
            if not self.url or self.command is not None or self.args or self.env_refs:
                raise ValueError("streamable_http requires a URL and no command, args, or env_refs")
            address = urlsplit(self.url)
            if address.scheme not in {"http", "https"} or not address.hostname:
                raise ValueError("MCP URL must be an absolute HTTP or HTTPS address")
            if address.username or address.password or address.query or address.fragment:
                raise ValueError(
                    "MCP URL must not contain credentials, query parameters, or a fragment"
                )
        if any("\x00" in value for value in [self.command or "", *self.args]):
            raise ValueError("Commands and arguments must not contain NUL bytes")
        if len(set(self.allowed_tools)) != len(self.allowed_tools) or any(
            not tool or tool.strip() != tool or "/" in tool for tool in self.allowed_tools
        ):
            raise ValueError("allowed_tools must contain unique nonempty unqualified tool names")
        if any(
            not _ENV_NAME.fullmatch(key) or not _ENV_NAME.fullmatch(value)
            for key, value in self.env_refs.items()
        ):
            raise ValueError("env_refs must map environment variable names to variable names")
        if any(
            _SENSITIVE_NAME.search(arg.split("=", 1)[0])
            for arg in self.args
            if arg.startswith("--")
        ):
            raise ValueError("Pass credentials through env_refs, not command arguments")
        return self


class MCPBridgeError(ValueError):
    """A failed discovery with a persisted partial result and failure receipt."""

    def __init__(self, message: str, evidence_id: str):
        super().__init__(message)
        self.evidence_id = evidence_id


class _RecordingSession(ClientSession):
    """Retain a genuine result before the SDK validates its declared output."""

    received_tool_result: types.CallToolResult | None = None

    async def validate_tool_result(self, name: str, result: types.CallToolResult) -> None:
        self.received_tool_result = result
        await super().validate_tool_result(name, result)


def _dump(model: BaseModel) -> dict[str, Any]:
    """Preserve MCP wire aliases and supplied fields from the actual SDK result."""
    return model.model_dump(mode="json", by_alias=True, exclude_unset=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _validator(schema: dict[str, Any]):
    """Check declared schemas without allowing validation to fetch remote documents."""

    def check_references(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"$ref", "$dynamicRef", "$recursiveRef"} and (
                    not isinstance(item, str) or not item.startswith("#")
                ):
                    raise ValueError("MCP schemas may reference only their own document")
                check_references(item)
        elif isinstance(value, list):
            for item in value:
                check_references(item)

    check_references(schema)
    cls = validator_for(schema, default=None) if "$schema" in schema else validator_for(schema)
    if cls is None:
        raise ValueError("Unsupported JSON Schema dialect in MCP contract")
    cls.check_schema(schema)
    return cls(schema, format_checker=FormatChecker())


class MCPBridge:
    """Discover real servers and execute only explicitly pinned, allowed tools.

    Each operation opens and closes its own SDK session. The first successful
    discovery pins the catalog unless ``expected_catalog`` already supplies one.
    Invocations rediscover the target server in the same session before dispatch,
    detecting changes in its configuration, environment fingerprint, initialization
    metadata, or tool contract. Contract identity is not a proof of semantic identity.
    """

    def __init__(
        self,
        configs: list[ServerConfig | dict],
        store: Store,
        run_id: str,
        expected_catalog: dict | None = None,
    ) -> None:
        self.configs = [
            config if isinstance(config, ServerConfig) else ServerConfig.model_validate(config)
            for config in configs
        ]
        if not self.configs or len({config.name for config in self.configs}) != len(self.configs):
            raise ValueError("Provide at least one server, with unique server names")
        self.store, self.run_id = store, run_id
        self.expected_catalog = deepcopy(expected_catalog)

    def _environment(self, config: ServerConfig) -> dict[str, str]:
        missing = [source for source in config.env_refs.values() if source not in os.environ]
        if missing:
            raise ValueError("Missing environment references: " + ", ".join(sorted(set(missing))))
        return {target: os.environ[source] for target, source in config.env_refs.items()}

    def _redact(self, text: str) -> str:
        for config in self.configs:
            for target, source in config.env_refs.items():
                value = os.environ.get(source)
                if value and (_SENSITIVE_NAME.search(target) or _SENSITIVE_NAME.search(source)):
                    text = text.replace(value, "[redacted environment value]")
        return text

    def _error(self, code: str, error: BaseException) -> dict[str, str]:
        if isinstance(error, BaseExceptionGroup):
            message = "; ".join(self._error(code, child)["message"] for child in error.exceptions)
        else:
            message = f"{type(error).__name__}: {error}"
        return {"code": code, "message": self._redact(message)}

    @asynccontextmanager
    async def _session(
        self, config: ServerConfig, diagnostics: dict
    ) -> AsyncIterator[_RecordingSession]:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
            try:
                async with asyncio.timeout(config.timeout_seconds), AsyncExitStack() as stack:
                    if config.transport == "stdio":
                        streams = await stack.enter_async_context(
                            stdio_client(
                                StdioServerParameters(
                                    command=config.command,
                                    args=config.args,
                                    env=self._environment(config),
                                ),
                                errlog=stderr,
                            )
                        )
                    else:
                        streams = await stack.enter_async_context(
                            streamable_http_client(config.url)
                        )
                    session = await stack.enter_async_context(
                        _RecordingSession(
                            streams[0],
                            streams[1],
                            read_timeout_seconds=config.timeout_seconds,
                            client_info=types.Implementation(name="oak-mcp-bridge", version="1"),
                        )
                    )
                    yield session
            finally:
                stderr.seek(0)
                diagnostics["server_stderr"] = self._redact(stderr.read())

    async def _server_catalog(
        self, config: ServerConfig, session: ClientSession, diagnostics: dict
    ) -> tuple[dict, list[dict]]:
        diagnostics["config"] = config.model_dump(mode="json")
        diagnostics["environment_fingerprint"] = _digest(self._environment(config))
        initialized = _dump(await session.initialize())
        diagnostics["initialize"] = initialized
        pages, discovered, cursors = [], {}, set()
        diagnostics["tool_pages"] = pages
        cursor = None
        for _ in range(100):
            page = await session.list_tools(
                params=types.PaginatedRequestParams(cursor=cursor) if cursor is not None else None
            )
            pages.append(_dump(page))
            for tool in page.tools:
                if tool.name in discovered:
                    raise ValueError(f"Server listed duplicate tool {tool.name}")
                discovered[tool.name] = tool
            cursor = page.next_cursor
            if cursor is None:
                break
            if cursor in cursors:
                raise ValueError("MCP tool discovery repeated a pagination cursor")
            cursors.add(cursor)
        else:
            raise ValueError("MCP catalog exceeds the 100-page discovery limit")
        missing = sorted(set(config.allowed_tools) - discovered.keys())
        if missing:
            raise ValueError("Configured tools are absent from server: " + ", ".join(missing))
        identity = {
            "config": config.model_dump(mode="json"),
            "environment_fingerprint": diagnostics["environment_fingerprint"],
            "initialize": initialized,
        }
        server = {"name": config.name, **identity, "tool_pages": pages}
        tools = []
        for name in config.allowed_tools:
            raw = _dump(discovered[name])
            _validator(raw["inputSchema"])
            if raw.get("outputSchema") is not None:
                _validator(raw["outputSchema"])
            annotations = raw.get("annotations") or {}
            if (
                annotations.get("readOnlyHint") is False
                or annotations.get("destructiveHint") is True
            ):
                raise ValueError(
                    f"Tool {name} contradicts this bridge's reviewed read-only surface"
                )
            tool = {
                "id": f"{config.name}/{name}",
                "server": config.name,
                "name": name,
                "description": raw.get("description", ""),
                "input_schema": raw["inputSchema"],
                "output_schema": raw.get("outputSchema"),
                "annotations": annotations,
                "contract_id": _digest({"server": identity, "tool": raw}),
            }
            tools.append(tool)
        return server, tools

    def discover(self) -> dict:
        """Persist the real catalog, or raise MCPBridgeError with failure evidence."""
        result = {"format_version": 1, "started_at": now(), "servers": [], "tools": []}
        try:
            asyncio.run(self._discover(result))
            result["status"] = "completed"
        except Exception as error:
            result.update(status="failed", error=self._error("discovery_failed", error))
        result["finished_at"] = now()
        evidence_id = self.store.event(
            self.run_id, "mcp_discovery", result["status"], "Real MCP catalog discovery", result
        )
        if result["status"] != "completed":
            raise MCPBridgeError(result["error"]["message"], evidence_id)
        result["catalog_id"] = evidence_id
        if self.expected_catalog is None:
            self.expected_catalog = deepcopy(result)
        return result

    async def _discover(self, result: dict) -> None:
        for config in self.configs:
            diagnostics: dict = {"name": config.name, "config": config.model_dump(mode="json")}
            result["servers"].append(diagnostics)
            async with self._session(config, diagnostics) as session:
                server, tools = await self._server_catalog(config, session, diagnostics)
                diagnostics.update(server)
                result["tools"].extend(tools)

    def invoke(self, capability_id: str, args: dict[str, Any]) -> dict:
        """Execute one actual allowed call, returning an attributable success or failure.

        A call is never repeated automatically. ``tool_call_attempted`` records
        whether dispatch was reached; a transport failure after that point does
        not claim that the provider performed no work. The output is the SDK's
        serialized MCP result, including genuine tool-error results when returned.
        """
        started = time.monotonic()
        receipt = {
            "format_version": 1,
            "capability_id": capability_id,
            "contract_id": None,
            "args": deepcopy(args),
            "started_at": now(),
            "tool_call_attempted": False,
            "output": None,
        }
        try:
            if not isinstance(capability_id, str) or capability_id.count("/") != 1:
                raise ValueError("Use a fully qualified server/tool capability ID")
            server_name, tool_name = capability_id.split("/")
            config = next((item for item in self.configs if item.name == server_name), None)
            if config is None or tool_name not in config.allowed_tools:
                raise ValueError("Capability is outside the configured tool allowlist")
            if not isinstance(args, dict):
                raise ValueError("MCP call arguments must be a JSON object")
            if self.expected_catalog is None:
                self.discover()
            expected = next(
                (tool for tool in self.expected_catalog["tools"] if tool["id"] == capability_id),
                None,
            )
            if expected is None:
                raise ValueError("Capability is absent from the pinned catalog")
            receipt.update(
                contract_id=expected["contract_id"],
                catalog_id=self.expected_catalog.get("catalog_id"),
            )
            _validator(expected["input_schema"]).validate(args)
            asyncio.run(self._invoke(config, expected, args, receipt))
        except Exception as error:
            receipt.update(status="failed", error=self._error("invocation_failed", error))
            if isinstance(error, MCPBridgeError):
                receipt["discovery_evidence_id"] = error.evidence_id
        receipt["finished_at"] = now()
        receipt["duration_seconds"] = round(time.monotonic() - started, 6)
        receipt["evidence_id"] = self.store.event(
            self.run_id, "mcp_call", receipt["status"], f"MCP call {capability_id}", receipt
        )
        return receipt

    async def _invoke(
        self, config: ServerConfig, expected: dict, args: dict, receipt: dict
    ) -> None:
        diagnostics: dict = {}
        receipt["connection"] = diagnostics
        async with self._session(config, diagnostics) as session:
            server, tools = await self._server_catalog(config, session, diagnostics)
            receipt["live_catalog_evidence_id"] = self.store.event(
                self.run_id,
                "mcp_contract_check",
                "completed",
                "Live MCP contract before invocation",
                {"server": server, "tools": tools},
            )
            live = next(tool for tool in tools if tool["id"] == expected["id"])
            receipt["observed_contract_id"] = live["contract_id"]
            if live["contract_id"] != expected["contract_id"]:
                raise ValueError(
                    "MCP contract changed since discovery; explicitly onboard a new catalog"
                )
            receipt["dispatch_evidence_id"] = self.store.event(
                self.run_id,
                "mcp_dispatch",
                "started",
                "Validated MCP call ready for dispatch",
                receipt,
            )
            receipt["tool_call_attempted"] = True
            try:
                result = await session.call_tool(expected["name"], args, allow_input_required=True)
            except Exception:
                if session.received_tool_result is not None:
                    receipt["output"] = _dump(session.received_tool_result)
                raise
            receipt["output"] = _dump(result)
            if not isinstance(result, types.CallToolResult):
                raise ValueError(
                    "Server requested additional client interaction; no handler is authorized"
                )
            if result.is_error:
                receipt.update(
                    status="failed",
                    error={"code": "tool_error", "message": "MCP server returned isError"},
                )
                return
            if expected["output_schema"] is not None:
                _validator(expected["output_schema"]).validate(result.structured_content)
                receipt["output_validation"] = "passed"
            else:
                receipt["output_validation"] = "not_declared"
            receipt["status"] = "completed"
