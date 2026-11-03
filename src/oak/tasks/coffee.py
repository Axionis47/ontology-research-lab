"""Load genuine ToolQA Coffee evidence and score answers with its official metric.

The adapter supplies data, query partitions, and benchmark scoring. It does not
provide an ontology, reasoning functions, a solver, or a canned agent response.
Reference answers are exposed only through the separate evaluator-facing loader.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import string
import struct
import tempfile
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal
from urllib.request import Request, urlopen

PROJECT = Path(__file__).resolve().parents[3]
SOURCE_LOCK = PROJECT / "data/sources/coffee-source.lock.json"
DEFAULT_CACHE = PROJECT / ".local/benchmarks/toolqa-coffee"


def source_lock() -> dict[str, Any]:
    """Return the committed repository, member, and evaluator provenance pins."""
    return json.loads(SOURCE_LOCK.read_text())


def _verify(data: bytes, record: dict[str, Any]) -> None:
    if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"Pinned source integrity failed for {record.get('filename', 'artifact')}")


def _get(url: str, maximum_bytes: int, *, byte_range: tuple[int, int, int] | None = None) -> bytes:
    headers = {"User-Agent": "OaK-Coffee-Adapter/1"}
    if byte_range:
        start, end, total = byte_range
        headers["Range"] = f"bytes={start}-{end}"
    with urlopen(Request(url, headers=headers), timeout=45) as response:
        if byte_range and (
            response.status != 206
            or response.headers.get("Content-Range") != f"bytes {start}-{end}/{total}"
        ):
            raise ValueError("Corpus server did not honor the pinned byte range; download aborted")
        data = response.read(maximum_bytes + 1)
    if len(data) > maximum_bytes:
        raise ValueError("Source response exceeded its pinned byte limit")
    return data


def _coffee_member(record: dict[str, Any]) -> bytes:
    """Fetch only the pinned ZIP directory/header/member, never the complete archive."""
    total = record["archive_bytes"]

    def ranged(start: int, length: int) -> bytes:
        result = _get(record["archive_url"], length, byte_range=(start, start + length - 1, total))
        if len(result) != length:
            raise ValueError("Corpus byte range was truncated")
        return result

    directory = ranged(record["directory_offset"], total - record["directory_offset"])
    if hashlib.sha256(directory).hexdigest() != record["directory_and_end_sha256"]:
        raise ValueError("Official archive directory changed from the pinned snapshot")
    header = ranged(record["header_offset"], record["data_offset"] - record["header_offset"])
    signature, _, flags, method = struct.unpack_from("<4s3H", header)
    name_length, extra_length = struct.unpack_from("<HH", header, 26)
    if (
        signature != b"PK\x03\x04"
        or flags & 1
        or method != record["compression"]
        or 30 + name_length + extra_length != len(header)
        or header[30 : 30 + name_length].decode() != record["member"]
    ):
        raise ValueError("ZIP member header differs from the pinned Coffee entry")
    compressed = ranged(record["data_offset"], record["compressed_bytes"])
    if hashlib.sha256(compressed).hexdigest() != record["compressed_sha256"]:
        raise ValueError("Compressed Coffee member failed its pinned checksum")
    decompressor = zlib.decompressobj(-15)
    data = decompressor.decompress(compressed, record["bytes"] + 1)
    if not decompressor.eof or decompressor.unused_data or zlib.crc32(data) != record["crc32"]:
        raise ValueError("Coffee member failed ZIP decompression/CRC validation")
    _verify(data, record)
    return data


def ensure_coffee_data(cache_dir: Path = DEFAULT_CACHE) -> dict[str, str]:
    """Download missing authentic sources and verify existing files before reuse.

    Returns local paths keyed by corpus, questions, scorer, and repository_license.
    A changed or corrupt existing file fails explicitly instead of being reused.
    The original labels remain in the evaluator source file, never in model inputs.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock = source_lock()
    paths = {}
    for kind in ("corpus", "questions", "scorer", "repository_license"):
        record = lock[kind]
        path = cache_dir / record["filename"]
        if path.exists():
            _verify(path.read_bytes(), record)
        else:
            data = (
                _coffee_member(record) if kind == "corpus" else _get(record["url"], record["bytes"])
            )
            _verify(data, record)
            with tempfile.NamedTemporaryFile(dir=cache_dir, delete=False) as temporary:
                temporary.write(data)
                temporary_path = Path(temporary.name)
            temporary_path.replace(path)
        paths[kind] = str(path)
    return paths


def _questions(cache_dir: Path) -> list[dict[str, str]]:
    lock = source_lock()
    path = Path(cache_dir) / lock["questions"]["filename"]
    data = path.read_bytes()
    _verify(data, lock["questions"])
    questions = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    if len(questions) != lock["questions"]["records"]:
        raise ValueError("Unexpected Coffee question count")
    if len({question["qid"] for question in questions}) != len(questions):
        raise ValueError("Duplicate Coffee question identifiers")
    return questions


def pilot_splits(
    cache_dir: Path = DEFAULT_CACHE, *, pilot: Literal["small", "expanded"] = "small"
) -> dict[str, Any]:
    """Select disjoint real queries by template, without consulting reference answers.

    Small uses three templates and three queries per split. Expanded covers all
    eight templates and eight queries per split. This is an OaK project protocol,
    not a claim to recover the paper authors' unpublished partition.
    """
    if pilot not in {"small", "expanded"}:
        raise ValueError("pilot must be 'small' or 'expanded'")
    lock = source_lock()
    groups: dict[str, list[str]] = defaultdict(list)
    questions = _questions(cache_dir)
    for question in questions:
        template = re.sub(r"\d{4}-\d{2}-\d{2}", "{date}", question["question"])
        groups[template].append(question["qid"])
    chosen = lock["pilot"]["small_templates"] if pilot == "small" else sorted(groups)
    splits: dict[str, Any] = {"construction": [], "development": [], "heldout": []}
    for template in chosen:
        if len(groups[template]) < 3:
            raise ValueError(f"Too few real queries for template {template}")
        ordered = sorted(
            groups[template],
            key=lambda qid: hashlib.sha256(f"{lock['pilot']['version']}:{qid}".encode()).digest(),
        )
        for index, role in enumerate(splits):
            splits[role].append(ordered[index])
    selected = {qid for ids in splits.values() for qid in ids}
    splits["unused"] = sorted(q["qid"] for q in questions if q["qid"] not in selected)
    splits["protocol"] = lock["pilot"]["version"]
    splits["pilot"] = pilot
    splits["templates"] = chosen
    return splits


def load_coffee(
    cache_dir: Path = DEFAULT_CACHE, *, pilot: Literal["small", "expanded"] = "small"
) -> dict[str, Any]:
    """Load all genuine corpus rows and label-free task inputs after explicit setup.

    Each document preserves original column values and CSV line provenance.
    All 100 questions remain accessible; the split manifest chooses the pilot.
    This function performs no network request and never returns answer labels.
    """
    lock = source_lock()
    corpus = lock["corpus"]
    data = (Path(cache_dir) / corpus["filename"]).read_bytes()
    _verify(data, corpus)
    reader = csv.DictReader(io.StringIO(data.decode()))
    if reader.fieldnames != corpus["columns"]:
        raise ValueError("Coffee CSV columns differ from the pinned contract")
    documents = []
    for row_number, row in enumerate(reader, start=2):
        documents.append(
            {
                "id": f"toolqa-coffee:row:{row_number}",
                "content": json.dumps(row, ensure_ascii=False, sort_keys=True),
                "source_ref": f"{corpus['member']}#row={row_number}",
                "metadata": {
                    "row_number": row_number,
                    "date": row["Date"],
                    "source_sha256": corpus["sha256"],
                    "source_url": corpus["archive_page"],
                },
            }
        )
    if len(documents) != corpus["records"]:
        raise ValueError("Coffee CSV row count differs from the pinned contract")
    return {
        "task_id": "toolqa-coffee-easy",
        "task_description": (
            "Answer questions about daily coffee prices and volumes using the supplied official "
            "corpus. Return the requested value or label as text."
        ),
        "corpus": {
            "id": f"toolqa-coffee:{corpus['sha256']}",
            "columns": corpus["columns"],
            "documents": documents,
            "row_count": len(documents),
            "sha256": corpus["sha256"],
        },
        "task_inputs": [{"id": q["qid"], "query": q["question"]} for q in _questions(cache_dir)],
        "splits": pilot_splits(cache_dir, pilot=pilot),
        "provenance": {
            "repository": lock["repository"],
            "commit": lock["commit"],
            "questions_sha256": lock["questions"]["sha256"],
            "evaluator_sha256": lock["scorer"]["sha256"],
        },
    }


def load_reference_answers(cache_dir: Path = DEFAULT_CACHE) -> dict[str, str]:
    """Load labels for evaluator use only; never include this mapping in model context."""
    return {question["qid"]: question["answer"] for question in _questions(cache_dir)}


def normalize_answer(answer: Any) -> str:
    """Apply ToolQA's official normalization, including its punctuation behavior.

    Semantics ported from ToolQA benchmark/ReAct/code/agents.py at the locked
    commit (Apache-2.0). This intentionally removes signs and decimal punctuation;
    it must not be mistaken for exact numeric equivalence.
    """
    lowered = str(answer).lower()
    unpunctuated = "".join(
        character for character in lowered if character not in string.punctuation
    )
    without_articles = re.sub(r"\b(a|an|the|usd)\b", " ", unpunctuated)
    return " ".join(without_articles.split())


def score_answer(prediction: Any, reference: Any) -> bool:
    """Return official ToolQA normalized exact match without an LLM judge."""
    return normalize_answer(prediction) == normalize_answer(reference)
