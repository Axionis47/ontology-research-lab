# Local task workspace

Run the Streamlit interface from the project root:

```bash
uv run streamlit run src/oak/ui.py
```

The default workspace is `.local`. Set `OAK_DATA_ROOT` to use another real workspace, including an isolated integration-test workspace.

The interface reads real task, revision, and run records from the service. It never populates an empty workspace with sample answers or substitute model outputs.

## Evidence and task setup

Create a task by describing its scope, supplying example questions, and capturing a source. Supported uploaded files are UTF-8 TXT, Markdown, CSV, JSON, and JSONL, up to five million bytes. Only the explicitly uploaded bytes are written under `.local/uploads`; the interface does not browse unrelated local paths.

The USGS connector fetches the actual earthquake catalog for the selected UTC interval, minimum magnitude, and record limit. Fetching requires its own button. Successful and failed acquisition snapshots are saved under `.local/acquisitions`, including request metadata, coverage, timestamps, and original response bytes. Incomplete or failed evidence cannot be submitted as a ready task corpus.

Saving a task does not make a model call. **Build knowledge** explicitly submits construction. Page refreshes inspect stored state and never automatically restart construction or answer a question.

## Ask, audit, revise, and history

- **Ask** submits a question against the active revision. The saved answer appears before its collapsed run history. Citations resolve to the actual function, arguments, observed value, and source document identifiers, including when the answer contains a compact execution reference. At most 100 source rows are rendered; their total count and full saved execution download remain available. Conservative dependency coverage is labeled so it is not mistaken for a minimal proof of the answer. A missing result remains missing; failed runs display their recorded error.
- **Audit** selects a revision and exposes its schema, entities, relationships, function definitions, validation report, assessment, and exact downloadable JSON. Graph tables are paginated without removing records from the stored artifact. OWL is shown when the service includes its serialized ontology.
- **Revise** records the new scope and the user's suggestion, optionally with additional or refreshed evidence and new validation questions. New sources are added; a refreshed copy of the same API request replaces its earlier snapshot. It creates a candidate instead of editing the active revision. The service's promotion check determines whether the interface enables promotion and displays its reason and previous-task regression evidence.
- **History** shows real run states, their step timeline, intermediate artifacts, and full saved results. Active runs are inspected every two seconds. Polling does not launch or resume jobs.

The sidebar displays the actual budget ledger's limit, estimated spend, reservations, remaining estimate, and call count. Those values are estimates, not provider billing records.

The active run is visible above the tabs. While it is running, submit controls for that task are disabled to avoid accidental repeated work. Historical revision selection affects inspection only; questions bind to the task's active revision. A structurally valid revision can still have unmeasured task accuracy, which is displayed separately. Construction scores identify questions used to build the revision; they are not held-out scores. Later benchmark results have their own saved reports.

Three integration checks render the real service with an empty store, retained paper evidence, and a corpus bundle, without making model calls. An additional saved-runtime AppTest uses an actual completed USGS pilot answer to verify answer-first placement, resolved citations, and no extra model calls. It requires the genuine pilot to have run first. A separate AppTest inspection of the actual model-built USGS revision displayed one entity type, seven evidence entities, and four functions without exceptions. Its receipt is `.local/verification/ui-real-revision.json`. These rendering checks establish artifact visibility; model task outcomes and revision compatibility have separate run evidence.

History and failed-answer views provide **Resume saved run** for failed or interrupted jobs. Resume preserves the request and checkpoint IDs. The live interface never waits on a job-submission file lock. Audit shows schema/function diffs and added, removed, or changed graph-record counts against the parent.
