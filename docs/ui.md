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
- **Audit** selects a readable version number and provides Schema, Entities, Functions, and Checks views. The schema map shows concepts, directed relationships, inheritance, and disjointness. Concept inspectors explain properties, datatypes, required fields, identity, inherited declarations, and OWL restrictions. Entity search uses actual names, dates, and values, with readable property tables, linked-record inspectors, and original source evidence. Functions show their actual execution steps. Technical identifiers, serialized OWL, and exact downloadable JSON remain in expandable details.
- **Revise** records the new scope and the user's suggestion, optionally with additional or refreshed evidence and new validation questions. New sources are added; a refreshed copy of the same API request replaces its earlier snapshot. It creates a candidate instead of editing the active revision. The service's promotion check determines whether the interface enables promotion and displays its reason and previous-task regression evidence.
- **History** shows real run states, their step timeline, intermediate artifacts, and full saved results. Active runs are inspected every two seconds. Polling does not launch or resume jobs.

The sidebar displays the actual budget ledger's limit, estimated spend, reservations, remaining estimate, and call count. Those values are estimates, not provider billing records.

The active run is visible above the tabs. While it is running, submit controls for that task are disabled to avoid accidental repeated work. Historical revision selection affects inspection only; questions bind to the task's active revision. A structurally valid revision can still have unmeasured task accuracy, which is displayed separately. Construction scores identify questions used to build the revision; they are not held-out scores. Later benchmark results have their own saved reports.

Rendering checks use the real service with an empty store, retained paper evidence, and a corpus bundle. Saved-runtime AppTests reuse actual USGS and Coffee pilot artifacts to check answer placement, citations, readable versions, ontology semantics, entity values, source evidence, inherited declarations, function steps, and unchanged spending/run history. Pilot-specific checks skip if the genuine artifacts are absent. Presentation helpers also use the genuine W3C Wine fixture. These checks establish artifact visibility; model task outcomes and revision compatibility have separate run evidence.

History and failed-answer views provide **Resume saved run** for failed or interrupted jobs. Resume preserves the request and checkpoint IDs. The live interface never waits on a job-submission file lock. Audit shows schema/function diffs and added, removed, or changed graph-record counts against the parent.

## Ontology exploration

The map uses the Graphviz renderer bundled with pinned Streamlit, without a new graph service or frontend dependency. Pan/zoom and fullscreen are available. Select concepts and entities with the native keyboard-accessible selectors; clicking graph nodes does not change the inspector. Relation arrows preserve source-to-target direction; dashed arrows mean subclass membership and red lines mean disjoint classes. Native text inspectors provide the same declarations without relying on the graphic.

Entity search happens before pagination. Each page contains at most 50 options and records. A selected entity map shows one step of actual incoming/outgoing relationships, bounded at 30 nodes and 80 links, with visible scope and omission counts. Disconnected entities display their properties and an explicit no-relationships message. No edges or example records are invented. Duplicate semantic labels are disambiguated while exact identities remain available in technical details.

Counts distinguish directly stored types from compatible superclass membership. The real USGS revision has 15 earthquakes, 60 total entities, and 45 relationships. Coffee has 5,746 daily records and zero instance relationships; its schema still has an inheritance arrow. Same-named properties on Coffee Market Day and Commodity Price Record retain their separate declaring classes.

Required fields, functional properties, primary keys, and OWL restrictions have different meanings. The inspector explains these rather than presenting them as interchangeable booleans. Functional means at most one value, and primary keys are application identities rather than OWL hasKey axioms. HermiT consistency and task accuracy are displayed separately.

Visual verification and screenshots are recorded in [the ontology UI receipt](verification/ontology-ui.md).
