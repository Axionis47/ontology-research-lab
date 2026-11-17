# First AppWorld surface: selective updates through MCP

Decision date: November 13, 2026. This implementation follows the user's request for at least three distinct single-request tasks before kernel construction, with MCP discovery and a future same-state ReAct fallback. It supersedes earlier adapter deferrals and pilot budget counts for this baseline only. Existing full-kernel specifications are not claimed implemented.

## Surface and selection

The capability is to resolve records through properties or relationships, select the requested targets, perform one kind of update, and verify the result. Use one business application and its supervisor/documentation support. Preserve complete native instructions, initial state and evaluator checks. Task IDs, names, values and answers remain instance data.

`config/appworld_surface.json` defines the surface. The trusted selector inventories only the official `train` split, groups by native scenario ID, requires at least three variants and one business application, and orders eligible scenarios by native difficulty, the union of required API identities, then scenario ID. Task variants are ordered by ID. API counts include helper APIs, and explicit required-API lists take precedence over older descriptive metadata counts. Native difficulty labels are coarse author-assigned labels, not measured difficulty for this model.

Semantic eligibility is recorded in `config/appworld_surface_reviews.json` with exact task-spec hashes. This is a reviewed dataset annotation, not a keyword guess or a function of whether the actor passes. Changed or unreviewed single-app scenarios stop selection for review. Required-API metadata stays private to selection; the actor gets the entire public MCP catalog for the selected application and supervisor, not an oracle subset of required tools. Older datasets lacking an API list are inspected with Python AST parsing of their validation solution, never executed or supplied to the actor.

On the pinned data 0.2.0, selection yields scenario `07b42fd`, Spotify, and variants `07b42fd_1`, `07b42fd_2`, `07b42fd_3`. Its abstract operation is property-filtered membership updates. The selection manifest records the ranking, rejected scenarios, source hashes, original task instructions and evaluation/input fingerprints before any model run.

## Setup and execution

Use a separate Python environment because the native AppWorld dependency set is larger than C0's. The official MCP-capable source is pinned to commit `42b5bcf3cd334fee33f0c37c02070a9f5807add5`. Compatible dependency versions are pinned where upstream uses private interfaces.

```sh
uv --cache-dir .venv/uv-cache venv .venv/appworld --python 3.12
uv --cache-dir .venv/uv-cache pip install --python .venv/appworld/bin/python -r requirements-appworld.txt
.venv/appworld/bin/python scripts/setup_appworld.py
.venv/appworld/bin/python scripts/run_appworld.py select --output runs/appworld/selection.json
.venv/appworld/bin/python scripts/run_appworld.py run --selection runs/appworld/selection.json
```

The setup helper verifies the official LFS objects against their SHA-256 pointers before unpacking them. It downloads native data only if absent; incompatible existing data produces an explicit error. `.appworld/`, `.venv/` and `runs/` remain local. Do not publish decrypted benchmark data or native trace contents. For inventory inspection, use `inventory --output runs/appworld/inventory.json`.

The runner retains the configured Ollama CLI/model. It records the installed model ID prefix, applied CLI options, unavailable generation settings, dependency versions and budgets. It does not download a different model or train weights. `config/appworld_loop.toml` fixes a 40-decision/40-tool-attempt baseline, including discovery and schema inspection, a 900-second episode deadline, and the existing 16,000-character context cap. These are experimental limits, not official benchmark defaults.

## Episode protocol and evidence

Each task starts one isolated native API server on localhost and one official AppWorld MCP stdio connection. The actor has only three bridge operations: `discover_tools`, `inspect_tool`, and `call_tool`, plus C0's saved-output readers. Discovery returns bounded names/descriptions; inspection returns one real MCP schema; calls validate against that schema and the application's scope. The full catalog is saved outside context. Arbitrary Python, server initialization, evaluator access and state-reset methods are not actor tools.

The original instruction is pinned in every model input. Public supervisor identity, task time and application identify the task world. Native evaluator results, required APIs, reference solutions and difficulty metadata never enter the acting context. There is no follow-up user conversation. Rejected arguments are observable and consume the ordinary action budget; transport failures on possibly mutating calls stop the episode without automatic retry.

MCP changes live API-server state. The owner explicitly saves native state after a call and before evaluation. Raw MCP result envelopes and a separate call transcript are retained, including semantic errors. Completion is the agent's claim; the official database-state evaluator runs only after the ReAct episode terminates, including on budget exhaustion or model failure.

The immutable C0 terminal trace remains separate from `evaluation.json`, which links back to the episode's final event-chain hash. The batch result distinguishes `execution_status`, `evaluation_status`, `benchmark_success`, trace integrity and native-input integrity. Evaluator errors remain unavailable results, never a task pass. Original native task/evaluator/input hashes are checked before and after each episode. Native outputs and session artifacts are hashed in the episode result. A completed batch can contain three failed tasks and still supply valid construction evidence.

`construction_ready` means all selected episodes have complete audited evidence, available official evaluations and unchanged inputs. It does not certify sufficient evidence for any particular schema, relationship or learned function.

## Kernel handoff and next boundary

The first batch runs without a learned kernel. `ReactLoop` additionally accepts a trusted, versioned `kernel_policy` for subsequent integration. It can propose actions through the same admission/dispatch path or return `KernelHandoff(reason, pending_work, evidence_ids)`. Supported handoff reasons are capability gap, evidence gap and no progress. An exception or invalid proposal remains a runtime error.

An explicit handoff records the kernel version, unresolved work and evidence references, then continues in ReAct with the same tools, world, history, original goal and remaining budget. The handoff consumes a decision; it cannot grant additional steps, erase effects or restart the world. The resulting task outcome stays attached to that episode. The hook accepts trusted actions, handoffs and finish proposals routed through the independent verifier. The later [repair-loop component](18-running-repair-loop.md) supplies a closed declarative package interpreter and development registry for its local adapter; it is not an unrestricted generated-code loader or a native AppWorld repair qualification.

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests cover deterministic selection, missing/stale semantic reviews, minimum variant count, native-input integrity, non-execution of reference solutions, bounded/scoped MCP discovery, call-schema rejection, three distinct fresh episodes, evaluator privacy and same-episode handoff without resets. A state-changing handoff test checks that ReAct observes the kernel's update without replaying it. Native integration checks use isolated real AppWorld servers. Baseline scores and trace locations are retained under `runs/appworld/`; synthetic tests are never counted as native results.

## Recorded first baseline

The local November 13, 2026 batch is preserved at `runs/appworld/baseline-v1/summary.json`, with bounded failure counts and source checks in `review.json`. All three episodes used identical captured implementation sources, and native input and recorded artifact hashes remained unchanged.

| Task | Terminal execution status | Decisions | Native success | Complete trace |
| --- | --- | --- | --- | --- |
| `07b42fd_1` | `MODEL_ERROR` (90-second model timeout) | 14 | No | No, interrupted model capture |
| `07b42fd_2` | `MODEL_ERROR` (90-second model timeout) | 17 | No | No, interrupted model capture |
| `07b42fd_3` | `BUDGET_EXHAUSTED` | 40 | No | Yes |

The result is **0/3 native tasks passed**, with all three officially evaluated. The actor repeatedly used discovered native names as top-level actions instead of invoking the bridge; later proposals also violated the response schema. No native API call reached dispatch in these baseline episodes. These observations identify tool routing and proposal format as repair targets; they do not establish an entity/relationship reasoning limit. Earlier complete steps remain inspectable, but interrupted outputs keep the batch's `construction_ready` flag false.

After all three baseline source snapshots were captured, a separate regression test exposed and fixed an error-classification bug: exceptions after native dispatch now stop as uncertain outcomes rather than returning retryable rejections. This fix is not claimed as a measured agent improvement. All 31 tests pass. The separate native probe at `runs/appworld-smoke/write-probe/result.json` verifies a real MCP update, readback, saved state, application scoping and official evaluation with unchanged original inputs. Its manually driven calls are not counted as agent task success.
