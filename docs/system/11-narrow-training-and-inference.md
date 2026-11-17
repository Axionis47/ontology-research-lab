# Active protocol: one narrow task family, inference first

**Latest first-delivery correction:** the user subsequently excluded the benchmark adapter from the first component and required automatic compaction and separate output recording. Build [C0](13-react-component.md) before the native-task stages below. This document still governs the later narrow training experiment; it does not require an adapter or graph work in C0.

Decision date: November 13, 2026. This is the active scope following the user's correction. It supersedes earlier requirements to start across multiple task families, implement every graph operator, pass a second surface, or run the broad promotion study. Existing contracts and control invariants remain applicable. The full operator library is a compatibility specification, not the first implementation checklist.

**The unit we build.** One complete native AppWorld scenario, one business application, one clear goal shape, a small fixed API set, one ReAct actor and the configured CLI. Initial bounds: twelve actor decisions, twenty-four tool attempts including four reserved for final verification, thirty-two model attempts, and ten minutes including a one-minute finalization reserve. These are experimental limits, recorded alongside native benchmark settings. A twelve-step budget is not permission to claim success at step twelve.

Choose a workflow shaped like resolve a target, inspect its current state, perform one permitted kind of update, and verify it. This is the selection criterion, not an invented AppWorld task ID or a change to a native objective. Keep the entire selected task and its official evaluator. Bootstrap/authentication/supervisor tools are identified separately from the business API set and remain scoped/metered.

**Exact family selection.** Load the pinned official train task IDs in the trusted selection process; group by `task_id_to_generator_id`; inspect train metadata for required API identities and public instructions for goal shape. Require exactly one business application, at most five business API identities, no asynchronous completion requirement, and a deterministic native final-state evaluator. Rank eligible families by number of required API identities, declared train difficulty, then generator ID. Select the first; do not rank by whether our actor happens to pass. Store all selection inputs, rejected eligibility reasons, family ID, native variant IDs, API union and selection algorithm version before rollouts. The actor never sees privileged selection metadata or solutions. If no family qualifies, return `NO_MATCHING_NARROW_FAMILY`; do not silently enlarge the surface or truncate a task.

The actual data inventory has not been loaded in this planning step, so no task ID is fabricated. AppWorld's inspected package tests expect three variants per scenario, and its task loader exposes the generator grouping. Verify that against the installed pinned dataset at bootstrap. [Pinned split tests](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/tests/package/test_load_task_ids.py), [task grouping](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/task.py#L301).

**What training means now.** Model weights stay fixed. The learning target is a small versioned computational package: one action/observation interface, its mapping, and one helper if needed. The helper improves how relationships, task constraints and missing evidence are handled across differing instances. Observed data and the current task's obligations are separate inputs. The kernel, permissions, evaluator and tool semantics stay fixed. A changed mapping/function/interface, or independently justified schema change, is a recorded learning output only after execution tests support it. Schema is stable by default; new records do not require schema training. Prompt/context prose is not an automatic learning target. See the [computational protocol](12-computational-learning-protocol.md). Ordinary inference, storing logs and adding a new task to history do not update weights.

**Curriculum and completion gates.**

| Stage | Work | Done when |
| --- | --- | --- |
| N0: fixed inference contract | Existing CLI emits one validated action; scripted fixtures exercise allowed/denied calls and truthful finish handling | Model readiness passes; denied calls have zero effects; schema errors have bounded observations |
| N1: one native task | Use fit instance with raw tools, actual reset, receipts and official terminal evaluator | Complete trace and honest outcome for each run; diagnose a failure if the actor cannot yet solve it |
| N2: one-family repair | Use fit and development instances; one supported failure mechanism and one patch per cycle | Deterministic reproducer, preserved passing cases and paired native results recorded |
| N3: optional abstraction/graph comparison | Add one typed helper only if N1/N2 expose repeated selection/composition errors; test graph implementation separately | Keep the simplest implementation supported by measured results; a graph is not mandatory |
| N4: frozen inference check | Freeze the selected package, compare on the sealed third variant | Report within-scenario behavior and limits; no broad-transfer claim |

Stay on the family if fit/dev failures remain. Increase instance diversity within the family before adding new goal shapes. Later expansion changes only one dimension per experiment: more candidate records, then ambiguity/missingness, then one relation, then one recoverable fault, then longer sequences. Synthetic variations are separately labeled conformance/stress fixtures and use independently specified checks; they do not become official benchmark examples by assertion. Another business application or benchmark is deferred until explicitly reopened.

**Split and repetition.** Deterministically order the three native variants by a stored hash seed. Assign one to `fit`, one to `development`, one to `sealed_check`. All retain original split `train`; these internal roles are not AppWorld's official dev/test. Fit traces and development feedback are available for diagnosis. The sealed instruction/state/result is not exposed to the improver. Run three fresh-environment repeats per scheduled visible instance/variant with the same configured model/settings and recorded seeds where supported. Repeats assess stochastic consistency on the same instance, not independent task generalization.

At most one candidate per cycle and three visible repair cycles. Diagnose fit failures first; add targeted synthetic boundary cases for missing values, ambiguity, denied operations or recovery. Preserve the native task unchanged. Use development for selection, openly acknowledging adaptive reuse. Freeze exactly one candidate before comparing it with its parent on the sealed instance, three repeats each. Do not choose a new candidate after seeing that check and call the same instance sealed again. Retire an exposed check into development; fresh sealed evidence requires a genuinely new same-family instance from a versioned generator or another valid source, explicitly labeled if it is not native data. If unavailable, stop making fresh-holdout claims and keep improvement status limited.

**The repair loop.** Run a frozen package → retain full execution/evaluation → isolate one failure → produce a cited finding → specify a distinguishing test → make one bounded patch → run the reproducer and preserving fixtures → rerun paired visible native cases → retain or reject. A judge may propose a mapping, function/interface or independently justified schema change. It cannot edit policy, lower a requirement, alter the evaluator, approve its own patch or see the sealed check. Infrastructure/model-readiness failures return operational findings, not a request to train around broken access.

The narrow judge reads the entire short event index plus original suspect input/output and source excerpts. Long-trace segmentation is available as a later extension, not needed for a twelve-step pilot. Bound diagnosis to one segment, two evidence expansions and six model calls. Model judgments remain advisory until a deterministic reproducer supports the mechanism; the larger judge qualification study is deferred. For this pilot every repair needs that reproducer and its independent expected result.

**Where graph operators enter.** They compute over admitted observed records inside a domain helper. They do not authorize actions, advance the execution lifecycle, verify external writes or undo effects. The actor chooses a typed function; its implementation may call operators; every external effect still passes the kernel.

```text
Task + observation
  → CLI proposes find_target(...) or an admitted raw tool
  → kernel checks scope, state, contract and budget
  → helper uses ordinary rows OR admitted graph operators
  → candidate IDs + evidence + completeness
  → actor proposes the selected update
  → kernel admits the actual tool call
  → independent state verification
```

For a flat selection problem, ordinary records can suffice. A potential helper can use `lookup_entities`, `filter_property_categorical` and `project_properties`; activate only those actually needed. Add `traverse_relations` only when the task introduces a real relationship question. Add `aggregate_values` only when the goal requires a count/total. The remaining locked operators stay unimplemented/inactive until justified. `extract_runtime_slots` adds a model invocation; do not add it when the actor's existing typed arguments already provide validated slots. Graphs contain only authorized observed facts with provenance; no hidden benchmark state is loaded for convenience.

**Ablation that attributes the gain correctly.**

| Variant | Interface and computation | Question it answers |
| --- | --- | --- |
| A | Raw tools and bounded observations behind the kernel | Can the simple actor solve this family? |
| B | One typed helper, ordinary validated rows; same available evidence | Does the abstraction reduce actual actor/mapping errors? |
| C | Same helper schema and semantic output as B, implemented with the needed graph operators | Does graph structure improve provenance, update handling, reuse or computation cost? |

A gain from A to B is evidence for a typed abstraction, not proof that a graph helped. If B and C produce identical model-visible observations, we should not attribute different actor intelligence to the representation alone. Compare implementation correctness, fresh-state behavior, traceability, operator work and latency. Keep B unless C demonstrates a concrete advantage worth its cost. Hold data visibility, kernel, actor, budgets, reset and evaluator fixed. Any extra reads/extraction calls in a variant are logged and counted.

**Narrow success.** No unauthorized effects, no bypass, no false verified-success claim, complete required traces, and valid actions still executable. A retained candidate must fix the deterministic target, preserve all existing conformance cases, have no per-instance observed native pass-count regression over the three repeats, and improve an outcome that motivated the patch. Local baseline promotion uses document 08's stricter gate: candidate three-of-three passes on fit, development and the frozen sealed check, control fixtures intact, and the preregistered resource check satisfied. Label this `NARROW_PILOT_ACCEPTANCE`, not statistically established transfer. If baseline is already perfect and no reproducible defect exists, skip repair; success can be a working inference loop with no demonstrated learning gain.

The family-level bootstrap and ten-family gate from the earlier broad plan are inapplicable here. Report exact pass counts per instance, individual failures, attempts, denied proposals, effect uncertainty, model usage/capture limitations and cost. The full multi-surface qualification and later weight training remain future work, not prerequisites for this incremental phase.
