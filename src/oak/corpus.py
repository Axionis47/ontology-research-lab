"""Acquire and preserve the evidence supplied to an OaK query.

The paper consumes an accompanying corpus C_q. Fetching that corpus from a
live service is an application boundary implemented here, before frozen-kernel
reasoning. A saved response is evidence for its recorded fetch time, not a claim
that a later request will return the same facts.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

USGS_ENDPOINT = "https://earthquake.usgs.gov/fdsnws/event/1/query"
MAX_BYTES = 5_000_000
USGS_FORMAT_NOTE = (
    "USGS GeoJSON: geometry.coordinates are [longitude degrees, latitude degrees, "
    "depth kilometres]. properties.time and properties.updated are Unix milliseconds. "
    "Null values mean the source did not supply a value."
)


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _snapshot(connector: str, source_id: str, request: dict[str, Any]) -> dict[str, Any]:
    return {
        "format_version": 1,
        "kind": "corpus_snapshot",
        "connector_id": connector,
        "source_id": source_id,
        "request": request,
        "fetched_at": _utc(),
        "completed_at": None,
        "snapshot_id": None,
        "status": "pending",
        "http_status": None,
        "response_headers": {},
        "media_type": None,
        "raw_payload_base64": "",
        "raw_sha256": None,
        "raw_bytes": 0,
        "raw_payload_complete": False,
        "coverage": {"complete_for_request": False},
        "freshness": {"observed_at": None, "upstream_may_revise": True},
        "error": None,
    }


def _finish(snapshot: dict[str, Any], body: bytes) -> dict[str, Any]:
    snapshot["raw_payload_base64"] = base64.b64encode(body).decode("ascii")
    snapshot["raw_sha256"] = _digest(body)
    snapshot["raw_bytes"] = len(body)
    snapshot["completed_at"] = _utc()
    snapshot["freshness"]["observed_at"] = snapshot["fetched_at"]
    snapshot["snapshot_id"] = _digest(
        _json({key: value for key, value in snapshot.items() if key != "snapshot_id"}).encode(
            "utf-8"
        )
    )
    return snapshot


def _fail(snapshot: dict[str, Any], code: str, message: str, *, retryable: bool = False) -> None:
    snapshot["status"] = "failed"
    snapshot["error"] = {"code": code, "message": message, "retryable": retryable}


def fetch_usgs(
    starttime: str,
    endtime: str,
    minmagnitude: float = 4.5,
    max_records: int = 100,
    *,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Fetch a bounded, explicit USGS earthquake catalog interval.

    Args:
        starttime: Inclusive ISO date/time; absent timezone means UTC.
        endtime: Inclusive ISO date/time; must be later than starttime.
        minmagnitude: Minimum source magnitude filter, not an inferred value.
        max_records: Maximum usable records, between 1 and 1000. One extra
            record is requested to detect incomplete coverage.
        timeout_seconds: Positive per-operation HTTP timeout, at most 60 seconds.

    Returns:
        A JSON-serializable snapshot with exact response bytes, request metadata,
        content digest, coverage, and explicit failure/incomplete state. Network
        failures are returned as evidence. Invalid local arguments raise ValueError.

    The connector has one fixed public endpoint. It accepts no arbitrary URL,
    authentication secret, side-effecting operation, or model-provided HTTP header.
    """
    start, end = _timestamp(starttime), _timestamp(endtime)
    if datetime.fromisoformat(start.replace("Z", "+00:00")) >= datetime.fromisoformat(
        end.replace("Z", "+00:00")
    ):
        raise ValueError("endtime must be later than starttime")
    if not math.isfinite(minmagnitude):
        raise ValueError("minmagnitude must be finite")
    if isinstance(max_records, bool) or not isinstance(max_records, int):
        raise ValueError("max_records must be an integer")
    if not 1 <= max_records <= 1000:
        raise ValueError("max_records must be between 1 and 1000")
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
        raise ValueError("timeout_seconds must be positive and at most 60")
    parameters = {
        "format": "geojson",
        "starttime": start,
        "endtime": end,
        "minmagnitude": minmagnitude,
        "orderby": "time-asc",
        "limit": max_records + 1,
        "eventtype": "earthquake",
    }
    url = str(httpx.URL(USGS_ENDPOINT, params=parameters))
    snapshot = _snapshot(
        "usgs-earthquakes-v1",
        "usgs:earthquake-catalog",
        {
            "method": "GET",
            "url": url,
            "parameters": parameters,
        },
    )
    snapshot["coverage"].update(
        {
            "starttime_inclusive": start,
            "endtime_inclusive": end,
            "minmagnitude": minmagnitude,
            "record_limit": max_records,
            "scope": "USGS catalog records matching the declared filters at fetch time",
        }
    )
    chunks: list[bytes] = []
    size = 0
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            with client.stream("GET", url, headers={"Accept": "application/geo+json"}) as response:
                snapshot["http_status"] = response.status_code
                snapshot["media_type"] = response.headers.get("content-type", "")
                snapshot["response_headers"] = {
                    key: response.headers[key]
                    for key in ["date", "etag", "last-modified", "content-type"]
                    if key in response.headers
                }
                for chunk in response.iter_bytes():
                    remaining = MAX_BYTES - size
                    chunks.append(chunk[:remaining])
                    size += min(len(chunk), remaining)
                    if len(chunk) > remaining:
                        _fail(
                            snapshot, "response_too_large", f"Response exceeded {MAX_BYTES} bytes"
                        )
                        return _finish(snapshot, b"".join(chunks))
                snapshot["raw_payload_complete"] = True
                if response.status_code == 204:
                    snapshot["status"] = "ready"
                    snapshot["coverage"].update(complete_for_request=True, records_returned=0)
                    return _finish(snapshot, b"")
                if response.status_code != 200:
                    _fail(
                        snapshot,
                        "http_error",
                        f"USGS returned HTTP {response.status_code}",
                        retryable=response.status_code == 429 or response.status_code >= 500,
                    )
                    return _finish(snapshot, b"".join(chunks))
        body = b"".join(chunks)
        data = json.loads(body)
        if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
            raise ValueError("Expected a USGS GeoJSON FeatureCollection")
        count = len(data["features"])
        reported_count = data.get("metadata", {}).get("count")
        if reported_count is not None and reported_count != count:
            raise ValueError("USGS metadata count differs from the returned feature count")
        snapshot["coverage"].update(
            records_returned=count, complete_for_request=count <= max_records
        )
        snapshot["freshness"]["source_generated_unix_ms"] = data.get("metadata", {}).get(
            "generated"
        )
        if count > max_records:
            snapshot["status"] = "incomplete"
            snapshot["error"] = {
                "code": "record_limit_exceeded",
                "message": "Narrow the interval or raise the record limit before reasoning.",
                "retryable": False,
            }
        else:
            snapshot["status"] = "ready"
    except httpx.HTTPError as error:
        _fail(snapshot, "network_error", f"{type(error).__name__}: {error}", retryable=True)
    except (ValueError, TypeError, AttributeError) as error:
        _fail(snapshot, "invalid_payload", f"{type(error).__name__}: {error}")
    return _finish(snapshot, b"".join(chunks))


def load_local_corpus(path: str | Path, source_id: str | None = None) -> dict[str, Any]:
    """Capture an explicitly supplied UTF-8 text, JSON, JSONL, or CSV file.

    The file is evidence, not instructions to execute. Its exact bytes are retained.
    Record types remain as supplied, including CSV string values and JSON nulls.
    """
    source = Path(path)
    suffix = source.suffix.lower()
    formats = {".json": "json", ".jsonl": "jsonl", ".csv": "csv", ".txt": "text", ".md": "text"}
    if suffix not in formats:
        raise ValueError("Supported corpus files: .json, .jsonl, .csv, .txt, .md")
    snapshot = _snapshot(
        "supplied-file-v1",
        source_id or f"file:{source.name}",
        {
            "filename": source.name,
            "format": formats[suffix],
        },
    )
    snapshot["media_type"] = {
        "json": "application/json",
        "jsonl": "application/x-ndjson",
        "csv": "text/csv",
        "text": "text/plain",
    }[formats[suffix]]
    snapshot["freshness"] = {"observed_at": None, "upstream_may_revise": True}
    body = b""
    try:
        with source.open("rb") as stream:
            body = stream.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            _fail(snapshot, "file_too_large", f"Corpus file exceeds {MAX_BYTES} bytes")
            return _finish(snapshot, body[:MAX_BYTES])
        body.decode("utf-8-sig")
        snapshot["raw_payload_complete"] = True
        snapshot["coverage"] = {
            "complete_for_request": True,
            "scope": "The supplied file only; completeness for the task is not established",
        }
        snapshot["status"] = "ready"
        snapshot = _finish(snapshot, body)
        snapshot["coverage"]["records_returned"] = len(normalize_snapshot(snapshot))
    except (OSError, ValueError, UnicodeError) as error:
        _fail(snapshot, "invalid_file", f"{type(error).__name__}: {error}")
    return _finish(snapshot, body)


def normalize_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize complete evidence into provenance-linked documents without building an ontology.

    JSON arrays and JSONL produce one document per record; a JSON object is one
    record. CSV produces one document per row with original column names. Text
    produces one document. USGS emits the unmodified features with field-unit
    documentation from its published format. Failed or incomplete input is rejected.
    """
    if snapshot["status"] != "ready" or not snapshot["coverage"]["complete_for_request"]:
        raise ValueError("Only ready snapshots with complete request coverage can be normalized")
    body = base64.b64decode(snapshot["raw_payload_base64"], validate=True)
    if _digest(body) != snapshot["raw_sha256"]:
        raise ValueError("Corpus payload digest mismatch")
    if not snapshot["raw_payload_complete"]:
        raise ValueError("The saved response payload is incomplete")
    text = body.decode("utf-8-sig")
    note = ""
    if snapshot["connector_id"] == "usgs-earthquakes-v1":
        if snapshot["http_status"] == 204:
            return []
        values = json.loads(text)["features"]
        identifiers = [value["id"] for value in values]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("USGS response contains duplicate event identifiers")
        records = [
            (f"/features/{index}", f"usgs:{value['id']}", value)
            for index, value in enumerate(values)
        ]
        note = USGS_FORMAT_NOTE + "\n"
    else:
        format_name = snapshot["request"]["format"]
        if format_name == "json":
            value = json.loads(text)
            values = value if isinstance(value, list) else [value]
            locators = (
                [f"/{index}" for index in range(len(values))] if isinstance(value, list) else [""]
            )
        elif format_name == "jsonl":
            entries = [
                (index, line) for index, line in enumerate(text.splitlines(), 1) if line.strip()
            ]
            values = [json.loads(line) for _, line in entries]
            locators = [f"line:{index}" for index, _ in entries]
        elif format_name == "csv":
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("CSV requires unique column names")
            values = list(reader)
            if any(None in row or None in row.values() for row in values):
                raise ValueError("CSV row width differs from the header")
            locators = [f"row:{index}" for index in range(1, len(values) + 1)]
        else:
            values, locators = [text], ["text"]
        records = [
            (locator, snapshot["source_id"], value)
            for locator, value in zip(locators, values, strict=True)
        ]
    documents = []
    for locator, source_id, value in records:
        rendered = note + (value if isinstance(value, str) else _json(value))
        documents.append(
            {
                "document_id": _digest(f"{snapshot['raw_sha256']}:{locator}".encode()),
                "source_id": source_id,
                "snapshot_id": snapshot["snapshot_id"],
                "locator": locator,
                "text": rendered,
                "record": value,
                "content_sha256": _digest(rendered.encode("utf-8")),
            }
        )
    return documents
