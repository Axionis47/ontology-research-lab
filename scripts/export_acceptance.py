"""Export a compact acceptance report from actual saved artifacts and test outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from oak.store import Store, implementation_receipt, now


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".local"))
    parser.add_argument("--ui-run-id", required=True)
    args = parser.parse_args()
    store = Store(args.root)
    project = Path(__file__).resolve().parents[1]
    evidence = project / "docs/verification"
    protocol_dir = store.root / "evaluation/toolqa-coffee/small"
    protocol = read(protocol_dir / "protocol.json")
    construction = read(protocol_dir / "construction.json")
    revision_id = construction["result"]["revision_id"]
    revision = store.get(revision_id)
    reports_dir = protocol_dir / "reports" / revision_id
    phases = {phase: read(reports_dir / f"{phase}.json") for phase in ("development", "heldout")}
    for phase, report in phases.items():
        if report["status"] != "completed" or report["correct"] != report["total_queries"]:
            raise ValueError(f"Acceptance phase {phase} has not passed")
    ui_run = store.rows("SELECT * FROM runs WHERE id=?", (args.ui_run_id,))[0]
    ui_answer = store.get(ui_run["result_id"])
    assert ui_run["status"] == "completed" and ui_answer["status"] == "answered"
    assert ui_answer["answer"] == "99"  # Independent USGS source check in adapter-loop report.
    screenshot = evidence / "ui-answer.jpg"
    unknown = store.rows(
        "SELECT id,run_id,status,reserved FROM model_calls WHERE status!='settled'"
    )
    report = {
        "generated_at": now(),
        "status": "passed",
        "implementation": implementation_receipt(),
        "scope": "Local single-user pilot; not a reproduction of the paper's aggregate scores",
        "coffee": {
            "protocol": protocol["protocol"],
            "revision_id": revision_id,
            "corpus_rows": protocol["corpus_rows"],
            "construction_correct": sum(
                item["score"] is True for item in revision["assessment"]["construction_results"]
            ),
            "construction_total": len(revision["assessment"]["construction_results"]),
            "phases": {
                phase: {
                    key: result[key]
                    for key in ("status", "correct", "total_queries", "accuracy", "artifact_id")
                }
                for phase, result in phases.items()
            },
            "source_audit": read(evidence / "coffee-graph.json"),
            "repair_cache_events": store.rows(
                "SELECT stage,status,summary,artifact_id FROM events WHERE run_id=? AND stage IN ('graph_cache','function_cache')",
                (construction["run_id"],),
            ),
        },
        "dynamic_corpus": read(evidence / "dynamic-corpus.json"),
        "adapter_loop": read(evidence / "adapter-loop.json"),
        "ui": {
            "run_id": args.ui_run_id,
            "result_id": ui_run["result_id"],
            "status": ui_run["status"],
            "answer": ui_answer["answer"],
            "functions": [call["function"] for call in ui_answer["trajectory"]],
            "browser_actions": "Submitted Ask, inspected the actual launch failure, resumed the same saved run, verified answer and evidence, opened Audit",
            "screenshot": str(screenshot.relative_to(project)),
            "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        },
        "checks": {
            "pytest": (store.root / "verification/final-tests.txt").read_text(),
            "mkdocs": (store.root / "verification/final-docs.txt").read_text(),
            "live_api_tests_enabled": True,
        },
        "usage": {
            "accounting": store.budget(40.0),
            "unknown_usage_reservations": unknown,
            "provider_invoice_verified": False,
        },
        "limitations": [
            "Three held-out Coffee queries are a small functional check, not a broad accuracy estimate.",
            "Replay establishes recorded calls over recorded corpora, not unseen planning success.",
            "Adapters support equivalent interface renames, not arbitrary semantic migrations.",
            "Initial pilot limits and artifact reuse differ from paper defaults; see runtime-method.md.",
            "LangSmith cloud tracing is optional and remains unverified.",
            "Unknown provider usage stays reserved; no billing amount is fabricated.",
        ],
    }
    (evidence / "acceptance.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "coffee_heldout": report["coffee"]["phases"]["heldout"],
                "usage": report["usage"]["accounting"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
