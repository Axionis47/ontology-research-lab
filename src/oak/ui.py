"""Local Streamlit workspace for evidence, answers, and ontology revisions.

Every displayed answer and artifact is read from the real service. Expensive work
starts only from explicit submit buttons; page refreshes only inspect stored state.
Run from the project root with ``uv run streamlit run src/oak/ui.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from difflib import unified_diff
from pathlib import Path
from typing import Any

import streamlit as st

from oak.corpus import MAX_BYTES, fetch_usgs, load_local_corpus
from oak.ontology_ui import show_entities, show_functions, show_schema
from oak.ontology_view import humanize
from oak.service import Service

DATA_ROOT = Path(os.environ.get("OAK_DATA_ROOT", ".local"))
ACTIVE_STATUSES = {"queued", "running", "pending", "starting", "in_progress"}
JOB_NAMES = {
    "construct": "Build knowledge",
    "ask": "Answer a question",
    "revise": "Propose a revision",
    "regress": "Check previous tasks",
}


def _date_label(value: str | None) -> str:
    if not value:
        return "Time not recorded"
    try:
        return datetime.fromisoformat(value).astimezone(UTC).strftime("%b %d, %Y at %H:%M UTC")
    except ValueError:
        return value


def _text(value: Any) -> str:
    """Render structured evidence without turning missing values into claims."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


def _json_download(value: Any, name: str, key: str) -> None:
    st.download_button(
        "Download saved JSON",
        data=json.dumps(value, ensure_ascii=False, indent=2, default=str),
        file_name=f"{name}.json",
        mime="application/json",
        key=key,
        on_click="ignore",
    )


def _table(rows: list[dict[str, Any]], key: str, page_size: int = 100) -> None:
    if not rows:
        st.caption("No records in this artifact.")
        return
    pages = (len(rows) + page_size - 1) // page_size
    page = st.number_input("Page", min_value=1, max_value=pages, step=1, key=f"{key}_page")
    start = (page - 1) * page_size
    st.dataframe(rows[start : start + page_size], hide_index=True, width="stretch")
    st.caption(
        f"Showing {start + 1} to {min(start + page_size, len(rows))} of {len(rows)} records."
    )


def _remember_snapshot(snapshot: dict[str, Any], prefix: str) -> None:
    """Retain successful and failed acquisition receipts, including original response bytes."""
    identifier = snapshot.get("snapshot_id") or hashlib.sha256(_text(snapshot).encode()).hexdigest()
    folder = DATA_ROOT / "acquisitions"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{identifier}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    st.session_state[f"{prefix}_snapshot"] = snapshot
    st.session_state[f"{prefix}_snapshot_receipt"] = str(path)


def _snapshot_summary(snapshot: dict[str, Any], key: str) -> None:
    if snapshot.get("kind") == "corpus_bundle":
        parts = snapshot.get("parts", [])
        st.caption(f"{len(parts)} saved evidence sources")
        for index, part in enumerate(parts):
            st.write(f"**Source {index + 1}: {part.get('source_id', 'unnamed')}**")
            _snapshot_summary(part, f"{key}_{index}")
        _json_download(snapshot, "evidence-bundle", f"{key}_bundle_download")
        return
    status = snapshot.get("status", "unknown")
    coverage = snapshot.get("coverage", {})
    if status == "ready":
        st.success("Evidence captured.")
    else:
        st.error(_text(snapshot.get("error") or f"Evidence is {status}."))
    st.caption(
        f"Observed: {snapshot.get('fetched_at', 'not recorded')} · "
        f"Records: {coverage.get('records_returned', 'not recorded')} · "
        f"Complete for request: {coverage.get('complete_for_request', False)}"
    )
    with st.expander("Source and coverage"):
        st.json({name: value for name, value in snapshot.items() if name != "raw_payload_base64"})
        _json_download(snapshot, "evidence-snapshot", f"{key}_download")


def _source_picker(prefix: str) -> dict[str, Any] | None:
    """Acquire a source only after an explicit upload-capture or API-fetch action."""
    source_type = st.radio(
        "Evidence source", ["Upload a file", "USGS earthquake catalog"], key=f"{prefix}_source_type"
    )
    if source_type == "Upload a file":
        upload = st.file_uploader(
            "Evidence file",
            type=["txt", "md", "csv", "json", "jsonl"],
            max_upload_size=5,
            key=f"{prefix}_upload",
            help="Supply facts or documents. Reference answers belong in evaluation.",
        )
        if st.button("Capture uploaded evidence", disabled=upload is None, key=f"{prefix}_capture"):
            st.session_state.pop(f"{prefix}_snapshot", None)
            try:
                data = upload.getvalue()
                if len(data) > MAX_BYTES:
                    raise ValueError(f"File exceeds the {MAX_BYTES:,}-byte evidence limit.")
                suffix = Path(upload.name).suffix.lower()
                directory = DATA_ROOT / "uploads"
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"{hashlib.sha256(data).hexdigest()}{suffix}"
                path.write_bytes(data)
                snapshot = load_local_corpus(path, source_id=f"upload:{Path(upload.name).name}")
                _remember_snapshot(snapshot, prefix)
            except (OSError, ValueError) as error:
                st.error(str(error))
    else:
        st.caption("Fetch the actual public catalog. Dates and times below use UTC.")
        with st.form(f"{prefix}_usgs_form"):
            today = datetime.now(UTC).date()
            left, right = st.columns(2)
            start = left.date_input("From", value=today - timedelta(days=1), key=f"{prefix}_start")
            end = right.date_input("Through", value=today, key=f"{prefix}_end")
            magnitude = st.number_input(
                "Minimum magnitude", value=4.5, step=0.1, key=f"{prefix}_magnitude"
            )
            limit = st.number_input(
                "Maximum records", min_value=1, max_value=1000, value=100, key=f"{prefix}_limit"
            )
            fetch = st.form_submit_button("Fetch catalog evidence")
        if fetch:
            st.session_state.pop(f"{prefix}_snapshot", None)
            try:
                with st.spinner("Fetching the catalog and saving its response…"):
                    snapshot = fetch_usgs(str(start), str(end), float(magnitude), int(limit))
                _remember_snapshot(snapshot, prefix)
            except (OSError, ValueError) as error:
                st.error(str(error))
    snapshot = st.session_state.get(f"{prefix}_snapshot")
    expected_connector = (
        "supplied-file-v1" if source_type == "Upload a file" else "usgs-earthquakes-v1"
    )
    if snapshot is not None and snapshot.get("connector_id") != expected_connector:
        st.info("Capture the selected source before using it.")
        return None
    if source_type == "Upload a file" and upload is not None and snapshot is not None:
        if hashlib.sha256(upload.getvalue()).hexdigest() != snapshot.get("raw_sha256"):
            st.info("The uploaded file changed. Capture it to create a new evidence snapshot.")
            return None
    if snapshot is not None:
        _snapshot_summary(snapshot, prefix)
        st.caption(f"Saved receipt: {st.session_state.get(f'{prefix}_snapshot_receipt')}")
    return snapshot


def _create_task(service: Service) -> None:
    with st.expander("Create a task", expanded=not service.tasks()):
        st.write("Describe what the agent should answer, then supply its evidence.")
        snapshot = _source_picker("create")
        with st.form("create_task"):
            title = st.text_input("Task name")
            scope = st.text_area("What should this agent be able to do?")
            queries_text = st.text_area(
                "Example questions, one per line",
                help="Questions guide construction. Keep final evaluation questions separate.",
            )
            submitted = st.form_submit_button("Save task", type="primary")
        if submitted:
            queries = [line.strip() for line in queries_text.splitlines() if line.strip()]
            if not title.strip() or not scope.strip() or not queries:
                st.error("Add a name, a task scope, and at least one example question.")
            elif snapshot is None or snapshot.get("status") != "ready":
                st.error("Capture complete evidence before saving the task.")
            else:
                try:
                    task_id = service.create_task(title.strip(), scope.strip(), snapshot, queries)
                    st.session_state["selected_task"] = task_id
                    st.rerun()
                except Exception as error:
                    st.error(str(error))


def _launch(service: Service, task_id: str, kind: str, **arguments: Any) -> None:
    try:
        run_id = service.start_job(task_id, kind, **arguments)
        st.session_state[f"selected_run_{task_id}"] = run_id
        st.rerun()
    except Exception as error:
        st.error(str(error))


def _run_detail(service: Service, run: dict[str, Any], key: str) -> None:
    st.write(f"**{JOB_NAMES.get(run['kind'], run['kind'])}** · {run.get('status', 'unknown')}")
    st.caption(f"Started {_date_label(run.get('created_at'))}")
    with st.expander("Technical run identifiers"):
        st.json({"run_id": run["id"], "result_id": run.get("result_id")})
    if run.get("error"):
        st.error(_text(run["error"]))
    if run.get("status") in {"failed", "interrupted"}:
        st.caption(
            "Resume keeps this request and its saved checkpoints. Unknown usage stays reserved."
        )
        if st.button("Resume saved run", key=f"{key}_resume"):
            try:
                service.resume_job(run["id"])
                st.rerun()
            except Exception as error:
                st.error(str(error))
    result = service.artifact(run["result_id"]) if run.get("result_id") else None
    if isinstance(result, dict) and "answer" in result:
        st.subheader("Answer")
        st.write(result["answer"])
        st.caption(f"Answer status: {result.get('status', 'not recorded')}")
        if result.get("query"):
            st.caption(f"Question: {result['query']}")
        if result.get("citations"):
            observations = {
                observation["id"]: observation
                for observation in result.get("observations", result.get("trajectory", []))
            }
            with st.expander("Supporting evidence"):
                for index, citation in enumerate(result["citations"]):
                    observation = observations.get(citation)
                    if observation is None:
                        st.warning(f"Saved citation {citation} has no matching observation.")
                        continue
                    execution = observation
                    if observation.get("artifact_id"):
                        try:
                            saved_execution = service.artifact(observation["artifact_id"])
                            if isinstance(saved_execution, dict):
                                execution = saved_execution
                        except (OSError, ValueError) as error:
                            st.error(f"Could not load the saved execution evidence: {error}")
                    st.write(f"**Function:** {observation.get('function', 'not recorded')}")
                    st.caption(f"{citation} · {observation.get('status', 'not recorded')}")
                    left, right = st.columns(2)
                    with left:
                        st.write("Arguments")
                        st.json(observation.get("args", {}))
                    with right:
                        st.write("Observed value")
                        st.write(observation.get("value"))
                    dependencies = execution.get("dependencies", {})
                    sources = dependencies.get("sources") or [
                        {"document_id": identifier}
                        for identifier in dependencies.get("source_ids", [])
                    ]
                    if sources:
                        st.write("Recorded source documents")
                        if dependencies.get("coverage") == "entire_graph_conservative":
                            st.caption(
                                "This function records the complete graph as its dependency "
                                "coverage. These sources may exceed what the answer needed."
                            )
                        st.dataframe(sources[:100], hide_index=True, width="stretch")
                        st.caption(
                            f"Showing {min(100, len(sources))} of {len(sources)} recorded sources. "
                            "The saved execution download includes every source."
                        )
                    else:
                        st.caption("No source document identifiers were recorded for this call.")
                    _json_download(
                        execution, "execution-evidence", f"{key}_citation_{index}_download"
                    )
        with st.expander("Complete saved result"):
            st.json(result)
            _json_download(result, "run-result", f"{key}_result_download")
    elif result is not None:
        with st.expander("Complete saved result"):
            st.json(result)
            _json_download(result, "run-result", f"{key}_result_download")
    events = service.events(run["id"])
    if events:
        with st.expander(
            "Run timeline and saved steps", expanded=run.get("status") in ACTIVE_STATUSES
        ):
            st.dataframe(
                [
                    {
                        field: _text(event.get(field, ""))
                        for field in ("time", "stage", "status", "summary")
                    }
                    for event in events
                ],
                hide_index=True,
                width="stretch",
            )
            artifact_events = [event for event in events if event.get("artifact_id")]
            if artifact_events:
                selected = st.selectbox(
                    "Step",
                    range(len(artifact_events)),
                    format_func=lambda index: (
                        f"{artifact_events[index].get('stage')} · "
                        f"{artifact_events[index].get('status')} · {index + 1}"
                    ),
                    key=f"{key}_event",
                )
                artifact = service.artifact(artifact_events[selected]["artifact_id"])
                st.json(artifact)
                _json_download(artifact, "saved-step", f"{key}_step_download")
    elif run.get("status") in ACTIVE_STATUSES:
        st.info("Waiting for the first recorded step.")


@st.fragment(run_every="2s")
def _live_run(service: Service, task_id: str, run_id: str) -> None:
    """Poll real saved state; this fragment never submits or resumes work."""
    run = next((item for item in service.runs(task_id) if item["id"] == run_id), None)
    if run is None:
        st.error("The selected run could not be found.")
        return
    budget = service.budget()
    st.caption(
        f"Current estimated spend USD {budget['estimated_usd']:.2f} · "
        f"Reserved USD {budget['reserved_usd']:.2f} · Calls {budget['calls']}"
    )
    _run_detail(service, run, f"live_{run_id}")
    if run.get("status") not in ACTIVE_STATUSES:
        st.rerun()


def _validation(revision: dict[str, Any]) -> None:
    st.subheader("Validation evidence")
    validation = revision.get("validation", {})
    if validation.get("consistent") is True and not validation.get("unsatisfiable_classes"):
        st.success("HermiT reports a consistent ontology with no named unsatisfiable classes.")
    elif validation.get("consistent") is False:
        st.error("HermiT reports an inconsistent ontology.")
    elif validation.get("unsatisfiable_classes"):
        st.error("Some named classes are unsatisfiable. See the saved check for details.")
    else:
        st.info("No completed logical consistency result recorded.")
    st.caption(
        "Logical consistency checks the ontology rules. Task results and source coverage are separate evidence."
    )
    assessment = revision.get("assessment", {})
    st.write(assessment.get("summary") or "No assessment summary recorded.")
    st.caption(f"Recorded assessment: {assessment.get('status', 'not recorded')}")
    if assessment.get("task_accuracy") in (None, "unmeasured"):
        st.warning(
            "Task accuracy is unmeasured. A passing logical check alone does not establish it."
        )
    elif assessment.get("task_accuracy") in {
        "measured_on_construction",
        "partially_measured_on_construction",
    }:
        measured = [
            result.get("score")
            for result in assessment.get("construction_results", [])
            if result.get("score") is not None
        ]
        st.caption(
            f"Construction questions: {sum(measured)} of {len(measured)} scored correct. "
            "These questions helped build this revision."
        )
    if assessment.get("heldout_accuracy") in (None, "unmeasured"):
        st.caption(
            "Held-out accuracy is not measured in this revision assessment. "
            "Any later evaluation has its own saved report."
        )
    with st.expander("Logical checks, task checks, and coverage"):
        st.json({"validation": revision.get("validation"), "assessment": assessment})


def _audit(service: Service, task: dict[str, Any]) -> None:
    revisions = service.revisions(task["id"])
    if not revisions:
        st.info("Build knowledge to inspect the first schema, graph, and function catalog.")
        return
    ids = [revision["id"] for revision in revisions]
    versions = {
        row["id"]: index + 1
        for index, row in enumerate(
            sorted(revisions, key=lambda row: (row.get("created_at", ""), row["id"]))
        )
    }
    revision_dates = {row["id"]: _date_label(row.get("created_at")) for row in revisions}
    selected = st.selectbox(
        "Revision",
        ids,
        index=ids.index(task["active_revision"]) if task.get("active_revision") in ids else 0,
        format_func=lambda identifier: (
            f"Version {versions[identifier]}{' · Active' if identifier == task.get('active_revision') else ''} · {revision_dates[identifier]}"
        ),
        key=f"revision_{task['id']}",
    )
    revision = service.revision(task["id"], selected)
    if revision.get("parent"):
        st.caption(
            f"Based on version {versions.get(revision['parent'], 'unknown')}. Questions use the active version."
        )
    else:
        st.caption("Initial version. Questions use the active version.")
    if revision.get("parent"):
        parent = service.revision(task["id"], revision["parent"])
        with st.expander("Changes from parent"):
            st.write(revision.get("suggestion") or "No suggestion text recorded for this revision.")
            st.caption(f"Previous scope: {parent['scope']}")
            st.caption(f"Current scope: {revision['scope']}")
            st.write(
                "Evidence changed"
                if parent["corpus_id"] != revision["corpus_id"]
                else "Same evidence snapshot"
            )
            before = {node["id"]: node for node in parent["graph"]["nodes"]}
            after = {node["id"]: node for node in revision["graph"]["nodes"]}
            st.caption(
                f"Graph records: {len(after.keys() - before.keys())} added, "
                f"{len(before.keys() - after.keys())} removed, "
                f"{sum(before[key] != after[key] for key in before.keys() & after.keys())} changed."
            )
            for field in ("schema", "functions"):
                difference = "\n".join(
                    unified_diff(
                        json.dumps(parent[field], indent=2, sort_keys=True).splitlines(),
                        json.dumps(revision[field], indent=2, sort_keys=True).splitlines(),
                        fromfile=f"parent/{field}",
                        tofile=f"candidate/{field}",
                        lineterm="",
                    )
                )
                if difference:
                    st.code(difference, language="diff")
                else:
                    st.caption(f"{field.capitalize()}: unchanged")
    schema = revision.get("schema", {})
    graph = revision.get("graph", {})
    columns = st.columns(3)
    columns[0].metric("Concepts", len(schema.get("entity_types", {})))
    columns[1].metric("Entities", f"{len(graph.get('nodes', [])):,}")
    columns[2].metric("Relationships", f"{len(graph.get('edges', [])):,}")
    counts = {}
    for node in graph.get("nodes", []):
        label = humanize(node["type"])
        counts[label] = counts.get(label, 0) + 1
    st.caption(" · ".join(f"{label}: {count:,}" for label, count in sorted(counts.items())))
    section = st.segmented_control(
        "Explore this version",
        ["Schema", "Entities", "Functions", "Checks"],
        default="Schema",
        required=True,
        key=f"audit_section_{selected}",
    )
    if section == "Schema":
        show_schema(revision, selected)
    elif section == "Entities":
        show_entities(service, revision, selected)
    elif section == "Functions":
        show_functions(revision, selected)
    else:
        _validation(revision)
    with st.expander("Technical details and downloads", on_change="rerun") as details:
        if details.open:
            st.json({"revision_id": selected, "parent_id": revision.get("parent")})
            if revision.get("owl"):
                with st.expander("OWL ontology"):
                    st.code(revision["owl"], language="xml")
            _json_download(revision, "kernel-revision", f"revision_download_{selected}")
            with st.expander("Exact revision artifacts"):
                st.json(revision)
    if selected != task.get("active_revision"):
        promotion = service.promotion_check(task["id"], selected)
        acceptable = bool(promotion.get("allowed"))
        with st.expander("Promotion and previous-task checks"):
            st.json(promotion)
        if st.button("Use this revision", disabled=not acceptable, key=f"promote_{selected}"):
            try:
                service.promote(task["id"], selected)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        if not acceptable:
            st.caption(promotion.get("reason") or "This candidate is not ready to become active.")


def main() -> None:
    """Render task setup, answers, artifact audit, revisions, and actual run history."""
    st.set_page_config(page_title="OaK", page_icon="🌳", layout="wide")
    service = Service(root=DATA_ROOT)
    st.title("OaK")
    st.caption("Ask from evidence. Inspect the knowledge. Revise it with visible checks.")
    with st.sidebar:
        st.header("Workspace")
        budget = service.budget()
        st.metric("Estimated spend", f"${budget['estimated_usd']:.2f}")
        st.caption(
            f"Limit USD {budget['limit_usd']:.2f} · Reserved USD {budget['reserved_usd']:.2f} · "
            f"Remaining USD {budget['remaining_usd']:.2f} · Calls {budget['calls']}"
        )
        st.caption("Cost estimates, not a provider invoice.")
    _create_task(service)
    tasks = service.tasks()
    if not tasks:
        st.info("Create a task with real evidence to begin.")
        return
    titles = {task["id"]: task["title"] for task in tasks}
    selected_id = st.sidebar.selectbox(
        "Task", list(titles), format_func=titles.get, key="selected_task"
    )
    task = service.task(selected_id)
    runs = sorted(
        service.runs(selected_id), key=lambda run: run.get("created_at", ""), reverse=True
    )
    active_runs = [run for run in runs if run.get("status") in ACTIVE_STATUSES]
    busy = bool(active_runs)
    st.subheader(task["title"])
    with st.expander("Task scope, evidence, and example questions"):
        st.write(task["scope"])
        st.caption(f"Task status: {task.get('status', 'not recorded')}")
        if task.get("corpus_id"):
            _snapshot_summary(service.artifact(task["corpus_id"]), f"task_{selected_id}")
        st.write(task.get("example_queries", []))
    if not task.get("active_revision"):
        if st.button(
            "Build knowledge", type="primary", disabled=busy, key=f"construct_{selected_id}"
        ):
            _launch(service, selected_id, "construct")
    if active_runs:
        st.subheader("Current run")
        _live_run(service, selected_id, active_runs[0]["id"])
    ask_tab, audit_tab, revise_tab, history_tab = st.tabs(["Ask", "Audit", "Revise", "History"])
    with ask_tab:
        if not task.get("active_revision"):
            st.info("Build and validate a knowledge revision before asking questions.")
        with st.form(f"ask_{selected_id}"):
            query = st.text_area("Your question")
            submitted = st.form_submit_button(
                "Ask", disabled=busy or not task.get("active_revision")
            )
        if submitted and query.strip():
            _launch(service, selected_id, "ask", query=query.strip())
        elif submitted:
            st.error("Enter a question first.")
    with audit_tab:
        _audit(service, task)
    with revise_tab:
        st.write("Expand the task scope or suggest a change. The active revision stays available.")
        include_evidence = st.checkbox(
            "Add or refresh evidence",
            key=f"new_source_{selected_id}",
            help=(
                "New sources are added. A refreshed copy of the same API request replaces "
                "its earlier snapshot."
            ),
        )
        snapshot = _source_picker(f"revise_{selected_id}") if include_evidence else None
        with st.form(f"revise_{selected_id}"):
            scope = st.text_area("Updated task scope", value=task["scope"])
            suggestion = st.text_area("Describe the change and why it is needed")
            new_questions = st.text_area(
                "New validation questions, one per line (optional)",
                help="These examples guide revision. Keep final held-out questions separate.",
            )
            submitted = st.form_submit_button(
                "Create and check candidate", disabled=busy or not task.get("active_revision")
            )
        if submitted:
            if not scope.strip() or not suggestion.strip():
                st.error("Provide the intended scope and a description of the change.")
            elif include_evidence and (snapshot is None or snapshot.get("status") != "ready"):
                st.error("Capture complete new evidence before creating the candidate.")
            else:
                _launch(
                    service,
                    selected_id,
                    "revise",
                    query=suggestion.strip(),
                    scope=scope.strip(),
                    snapshot=snapshot,
                    queries=[line.strip() for line in new_questions.splitlines() if line.strip()]
                    or None,
                )
        if st.button(
            "Check previous tasks",
            disabled=busy or not task.get("active_revision"),
            key=f"regress_{selected_id}",
        ):
            _launch(service, selected_id, "regress")
    with history_tab:
        if not runs:
            st.info("No runs have been submitted for this task.")
        else:
            st.dataframe(
                [
                    {
                        "Activity": JOB_NAMES.get(run["kind"], run["kind"]),
                        "Status": humanize(run.get("status", "unknown")),
                        "Started": _date_label(run.get("created_at")),
                    }
                    for run in runs
                ],
                hide_index=True,
                alt="Run activities, statuses, and start times",
            )
            run_ids = [run["id"] for run in runs]
            run_labels = {
                run[
                    "id"
                ]: f"{JOB_NAMES.get(run['kind'], run['kind'])} · {run['status']} · {_date_label(run.get('created_at'))}"
                for run in runs
            }
            selected_run = st.selectbox(
                "Run", run_ids, format_func=run_labels.get, key=f"selected_run_{selected_id}"
            )
            run = next(item for item in runs if item["id"] == selected_run)
            if run.get("status") in ACTIVE_STATUSES:
                st.info("This run is in progress. Follow its current steps above.")
            else:
                _run_detail(service, run, f"history_{selected_run}")
    latest_ask = next((run for run in runs if run["kind"] == "ask"), None)
    if latest_ask is not None:
        with ask_tab:
            st.divider()
            if latest_ask.get("status") in ACTIVE_STATUSES:
                st.info("The answer is being prepared. Follow the current run above.")
            else:
                _run_detail(service, latest_ask, f"answer_{latest_ask['id']}")


if __name__ == "__main__":
    main()
