"""Local, versioned application boundary for execution and evidence observation.

Requests enqueue durable subprocess work. Read routes and SSE only project saved
evidence. The application owns a periodic worker reconciliation loop independent
of browser connections, so navigation never starts or restarts execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from oak import api_contracts as contracts

PROJECT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger(__name__)
Cursor = Annotated[str, Query(pattern=r"^[0-9]+$")]


def _error(code: str, message: str, status: int, *, retryable=False, evidence_refs=None):
    return JSONResponse(
        status_code=status,
        content=contracts.ErrorResponse(
            code=code, message=message, retryable=retryable, evidence_refs=evidence_refs or []
        ).model_dump(mode="json"),
    )


def create_app(root: Path = Path(".local"), frontend_dir: Path | None = None) -> FastAPI:
    """Create the local application without opening storage or launching workers.

    Storage migration and ownership reconciliation occur only during server
    startup. This permits generating OpenAPI without touching a workspace.
    """
    root = Path(root).resolve()
    frontend_dir = (frontend_dir or PROJECT / "frontend/dist").resolve()
    session = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from oak.web_jobs import WebJobs

        jobs = await asyncio.to_thread(WebJobs, root)
        app.state.jobs = jobs

        async def reconcile():
            while True:
                try:
                    await asyncio.to_thread(jobs.reconcile)
                except Exception:
                    # Diagnostics remain local. Never put tracebacks in API replies.
                    LOG.exception("Worker ownership reconciliation failed")
                await asyncio.sleep(2)

        monitor = asyncio.create_task(reconcile())
        try:
            yield
        finally:
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor

    app = FastAPI(
        title="OaK observation API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        try:
            address = urlsplit("http://" + request.headers.get("host", ""))
            valid_host = (
                address.hostname in {"localhost", "127.0.0.1", "::1"} and not address.username
            )
            _ = address.port
        except ValueError:
            valid_host = False
        if not valid_host:
            return _error("invalid_host", "This application accepts loopback hosts only.", 403)
        origin = request.headers.get("origin")
        allowed = {
            str(request.base_url).rstrip("/"),
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        }
        if origin and origin not in allowed:
            return _error(
                "invalid_origin", "This origin is not part of the local application.", 403
            )
        if request.headers.get("sec-fetch-site") == "cross-site":
            return _error("invalid_origin", "Cross-site requests are not supported.", 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            supplied = request.headers.get("x-oak-session", "")
            if not secrets.compare_digest(supplied, session):
                return _error(
                    "session_required", "Refresh the local application before submitting.", 403
                )
            if not request.headers.get("content-type", "").startswith("application/json"):
                return _error("invalid_input", "Mutations require application/json.", 415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid_input(request, error):
        return _error("invalid_input", "The request does not match the supported contract.", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return _error(
            "not_found" if error.status_code == 404 else "invalid_input",
            "The requested resource is unavailable.",
            error.status_code,
        )

    @app.exception_handler(Exception)
    @app.exception_handler(LookupError)
    @app.exception_handler(FileNotFoundError)
    @app.exception_handler(ValueError)
    async def application_error(request, error):
        code = getattr(error, "code", None)
        if code:
            status = {
                "active_run_conflict": 409,
                "idempotency_conflict": 409,
                "tool_contract_changed": 409,
                "budget_exhausted": 409,
                "artifact_missing": 404,
                "not_found": 404,
            }.get(code, 422)
            return _error(
                code,
                str(error),
                status,
                retryable=getattr(error, "retryable", False),
                evidence_refs=getattr(error, "evidence_refs", []),
            )
        if isinstance(error, (FileNotFoundError, LookupError)):
            return _error(
                "artifact_missing",
                "The requested evidence was not recorded or is unavailable.",
                404,
            )
        if isinstance(error, ValueError):
            return _error(
                "invalid_input", "The request cannot be used with this saved evidence.", 422
            )
        LOG.exception("Application request failed", exc_info=error)
        return _error(
            "internal_error", "The operation failed. Inspect the saved run evidence.", 500
        )

    def observer():
        from oak.observer import Observer

        return Observer(root)

    def key(value: str | None) -> str:
        if not value or not 1 <= len(value) <= 200 or any(ord(c) < 33 for c in value):
            raise ValueError("A printable idempotency key is required")
        return value

    def public(model, value: dict, *, sanitize=False) -> dict:
        """Adapt service metadata without leaking private storage fields."""
        if sanitize:
            from oak.observer import sanitize_public

            value, _ = sanitize_public(value)
        return {name: value[name] for name in model.model_fields if name in value}

    error_responses = {
        code: {"model": contracts.ErrorResponse} for code in (403, 404, 409, 422, 500)
    }
    api = "/api/v1"

    @app.get(
        api + "/workspace", response_model=contracts.WorkspaceResponse, responses=error_responses
    )
    def workspace():
        from oak.model import runtime_config

        config = runtime_config()
        data = observer().workspace()
        data.update(
            session_token=session,
            model=config["model"],
            readiness={
                "api": True,
                "frontend": (frontend_dir / "index.html").is_file(),
                "execution": "not_checked",
            },
            settings={
                "max_steps": {"min": 1, "max": min(100, config["max_agent_steps"])},
                "max_tool_calls": {"min": 1, "max": 100},
                "sampling_fraction": {"min": 0.01, "max": 1.0},
                "max_new_spend_usd": {"min": 0.01, "max": config["total_budget_usd"]},
                "construction_rounds_per_submission": 1,
            },
            supported_actions=["discover", "create_task", "construct", "infer"],
        )
        return data

    @app.post(
        api + "/connector-discoveries",
        status_code=202,
        response_model=contracts.AcceptedRun,
        responses=error_responses,
    )
    def discover(
        body: contracts.DiscoveryRequest,
        request: Request,
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        return public(
            contracts.AcceptedRun,
            request.app.state.jobs.discover(
                body.connection.model_dump(mode="json"), key(idempotency_key)
            ),
        )

    @app.get(
        api + "/connector-discoveries/{identity}",
        response_model=contracts.DiscoveryResponse,
        responses=error_responses,
    )
    def discovery(identity: str, request: Request):
        return public(
            contracts.DiscoveryResponse, request.app.state.jobs.discovery(identity), sanitize=True
        )

    @app.post(
        api + "/connectors",
        status_code=201,
        response_model=contracts.ConnectorResponse,
        responses=error_responses,
    )
    def save_connector(body: contracts.ConnectorRequest, request: Request):
        return public(
            contracts.ConnectorResponse,
            request.app.state.jobs.save_connector(body.discovery_id, body.allowed_tools),
            sanitize=True,
        )

    @app.get(api + "/connectors", response_model=contracts.ConnectorListResponse)
    def connectors(request: Request):
        return {
            "items": [
                public(contracts.ConnectorResponse, item, sanitize=True)
                for item in request.app.state.jobs.connectors()
            ]
        }

    @app.post(
        api + "/tasks",
        status_code=201,
        response_model=contracts.TaskCreatedResponse,
        responses=error_responses,
    )
    def create_task(body: contracts.TaskCreateRequest, request: Request):
        config = body.model_dump(mode="json", exclude={"connector_ids"})
        return public(
            contracts.TaskCreatedResponse,
            request.app.state.jobs.create_task(config, body.connector_ids),
        )

    @app.get(api + "/tasks", response_model=contracts.TaskListResponse)
    def tasks():
        return observer().tasks()

    @app.get(
        api + "/tasks/{identity}", response_model=contracts.TaskResponse, responses=error_responses
    )
    def task(identity: str):
        return observer().task(identity)

    @app.get(
        api + "/tasks/{identity}/history",
        response_model=contracts.HistoryResponse,
        responses=error_responses,
    )
    def history(identity: str):
        return observer().history(identity)

    @app.post(
        api + "/tasks/{identity}/runs",
        status_code=202,
        response_model=contracts.AcceptedRun,
        responses=error_responses,
    )
    def submit(
        identity: str,
        body: contracts.RunCreateRequest,
        request: Request,
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        return public(
            contracts.AcceptedRun,
            request.app.state.jobs.submit(
                identity,
                body.operation,
                key(idempotency_key),
                **body.model_dump(exclude={"operation"}, exclude_unset=True),
            ),
        )

    @app.get(
        api + "/runs/{identity}", response_model=contracts.RunResponse, responses=error_responses
    )
    def run(identity: str):
        return observer().run(identity)

    @app.get(
        api + "/runs/{identity}/events",
        response_model=contracts.EventsResponse,
        responses=error_responses,
    )
    def events(
        identity: str,
        after: Cursor = "0",
        through: Cursor | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ):
        return observer().events(identity, after=after, through=through, limit=limit)

    @app.get(api + "/runs/{identity}/stream", responses=error_responses)
    async def stream(
        identity: str,
        request: Request,
        after: Cursor = "0",
        last_event_id: Annotated[str | None, Header()] = None,
    ):
        cursor = last_event_id or after
        if not cursor.isdecimal():
            raise ValueError("Invalid cursor")
        view = observer()
        await asyncio.to_thread(view.run, identity)

        async def records():
            nonlocal cursor
            heartbeat = 0
            while not await request.is_disconnected():
                page = await asyncio.to_thread(view.events, identity, after=cursor, limit=100)
                for event in page["items"]:
                    cursor = event["cursor"]
                    yield f"id: {cursor}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if page["has_more"]:
                    continue
                current = await asyncio.to_thread(view.run, identity)
                if current["status"] in {"completed", "failed", "interrupted"}:
                    # One final read covers a terminal commit racing the page read.
                    tail = await asyncio.to_thread(view.events, identity, after=cursor, limit=100)
                    if tail["items"]:
                        continue
                    return
                heartbeat += 1
                if heartbeat % 15 == 0:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            records(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
        )

    @app.get(
        api + "/kernels/{identity}",
        response_model=contracts.KernelResponse,
        responses=error_responses,
    )
    def kernel(identity: str):
        return observer().kernel(identity)

    @app.get(
        api + "/kernels/{identity}/diff",
        response_model=contracts.KernelDiffResponse,
        responses=error_responses,
    )
    def diff(identity: str, against: str):
        return observer().kernel_diff(identity, against)

    @app.get(
        api + "/graphs/{identity}",
        response_model=contracts.GraphResponse,
        responses=error_responses,
    )
    def graph(
        identity: str, focus: str | None = None, limit: Annotated[int, Query(ge=1, le=80)] = 80
    ):
        return observer().graph(identity, focus=focus, limit=limit)

    @app.get(
        api + "/artifacts/{identity}",
        response_model=contracts.ArtifactResponse,
        responses=error_responses,
    )
    def artifact(identity: str):
        return observer().artifact(identity)

    if (frontend_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            return _error("not_found", "This API route does not exist.", 404)
        index = frontend_dir / "index.html"
        if not index.is_file():
            return _error(
                "frontend_not_built",
                "Build the frontend with npm --prefix frontend run build.",
                503,
            )
        return FileResponse(index)

    return app
