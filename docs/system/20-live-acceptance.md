# Live model acceptance protocol

## Gemini loop verified November 16, 2026

**The narrow AppWorld improvement loop now works, including a fresh automatic run with no manual resume.** Qwen executed the failed starting task; Gemini diagnosed its evidence; a separate Gemini call authored a bounded function correction; the runtime validated and activated it; subsequent tasks passed through the accepted program. [Fresh automatic result](../../runs/protocol/appworld-gemini-20261116/clean-replay/result.json).

The supported tasks ask to follow Spotify artists matching both a genre and a minimum follower count. Task setup binds those requirements, observes a fresh AppWorld world through its official MCP APIs, and records the scoped graph and package version. The ontology surface includes `Account`, `Artist`, genre and follower-count properties, the `follows` relation, and the follow-action contract. Each starting graph contains one account and 36 observed artists. Facts are rebuilt from each world's observations; the accepted computation persists. [Task bindings and representation evidence](../../runs/protocol/appworld-gemini-20261116/representation.json).

### What changed and why it helped

The original program selected artists by genre but omitted the requested numeric condition. Deterministic preflight rejected that plan because it would also follow artists below the threshold. Qwen recovery then stalled on invalid discovery arguments. Gemini distinguished these as separate function and actor failures.

The separate proposer added the existing numeric-filter operator after categorical filtering in the `direct` function. It references the task's numeric predicates, so different genres and thresholds use the same computation. It contains no artist IDs or hardcoded task answers, changes no ontology definition, and leaves the other function unchanged. The runtime interpreted and tested this candidate; Gemini did not execute or activate it. [Diagnosis](../../runs/protocol/appworld-gemini-20261116/clean-replay/diagnosis.json), [original proposer response](../../runs/protocol/appworld-gemini-20261116/clean-replay/proposer-calls.json), [accepted comparison](../../runs/protocol/appworld-gemini-20261116/clean-replay/acceptance.json).

### Native results

The first experiment collected all three baselines before learning. Each after-result below is a new execution in a fresh world, using the newly accepted Gemini-authored program.

| AppWorld task | Requirement | Before improvement | After improvement |
| --- | --- | --- | --- |
| `07b42fd_1` | Classical, at least 22 followers | Failed | Passed, 5/5 official checks |
| `07b42fd_2` | EDM, at least 23 followers | Failed | Passed, 5/5 official checks |
| `07b42fd_3` | Reggae, at least 21 followers | Failed | Passed, 5/5 official checks |

The baselines made ten actual Qwen calls and ended with `NO_PROGRESS`. The accepted candidate passed fresh native execution gates for all three retained cases with fallback disabled. Subsequent episodes passed 3/3, with zero Qwen calls, because the reusable program handled them directly. The next learning check returned `IDLE`. [Measured result](../../runs/protocol/appworld-gemini-20261116/protocol-result.json), [episode audits](../../runs/protocol/appworld-gemini-20261116/episodes.json), [final validation receipt](../../runs/protocol/appworld-gemini-20261116/validation-retry.json).

After the CLI corrections, a second experiment started with a fresh archive and the original seed, importing no prior program. Its ordinary `run_request(..., learn=True)` path completed automatically:

1. Task `_1` failed, with three real Qwen calls.
2. A validated Gemini diagnosis triggered one separate Gemini proposer call.
3. The candidate passed the retained native case and 16 structural challenges, then activated. Only `_1` had been observed in this archive at that point.
4. Subsequent tasks `_2`, `_3`, and `_1` each passed all five official checks, with zero Qwen calls and no further patch needed.

This clean experiment required no manual resume or validation retry. Both Gemini calls reported `gemini-3.8-flash` as the main model and `gemini-3.5-flash-lite` as the CLI utility router. Qwen remained the configured `qwen3:8b-q4_K_M` actor. [Frozen schedule](../../runs/protocol/appworld-gemini-20261116/clean-replay/manifest.json), [episodes](../../runs/protocol/appworld-gemini-20261116/clean-replay/episodes.json), [result](../../runs/protocol/appworld-gemini-20261116/clean-replay/result.json).

### Losses retained and corrections made

- The initial Gemini personal-login route returned `UNSUPPORTED_CLIENT`. The installed CLI now uses already configured Vertex AI credentials. This is the Cloud API billing route. Small CLI request-builder corrections handle sessions with no tools. No alternative model provider was substituted. The [setup record](../../MODEL_SETUP.md#working-cli-repair-november-16-2026) contains the patches and backup receipts; reinstalling the CLI can overwrite those local patches.
- The first experiment retains seven proposer transport failures with `INVALID_STREAM`. Their failures did not become diagnoses or accepted proposals. The successful clean experiment followed the final CLI correction. [All initial proposer calls](../../runs/protocol/appworld-gemini-20261116/gemini-proposer-calls.json).
- One initial candidate validation had two native successes and one `UNKNOWN` due to AppWorld session startup failure. Activation was withheld. A later duplicate proposal was rejected. An explicit validation-only retry of the already stored candidate passed all three fresh worlds before activation; proposal spending was not reset. [Retry record](../../runs/protocol/appworld-gemini-20261116/validation-retry.json).
- Qwen's invalid discovery arguments remain unresolved. The improvement is to the reusable function, not Qwen's weights or general task-solving quality. Gemini's actor finding remains in the record.

The runtime correction connected the existing evidence store, separate Gemini roles, and existing deterministic comparison/release gates. It validates diagnosis citations, restricts proposal to the diagnosed function case, and records unavailable stages without provider substitution. It does not add a general ontology-learning system. Protected runtime source hashes stayed unchanged during each live experiment. Archive integrity checks passed. Separately, **135 unit tests passed** and specification validation passed; those are component checks, not additional native tasks. [Unit log](../../runs/protocol/appworld-gemini-20261116/unit-tests.log), [specification log](../../runs/protocol/appworld-gemini-20261116/spec-validation.log).

### Limits of this evidence

All three tasks are previously exposed training variants of one Spotify family. The new archive tests automatic learning and reuse on later tasks in that sequence; it does not establish held-out benchmark performance. The candidate matches an older search-produced composition, but the current experiments began from the original seed and retain fresh Gemini responses authoring that composition, with no prior candidate imported. Broad semantic definition retrieval, task-conditioned ontology extension, other applications, and arbitrary API learning remain unimplemented.

The sections below preserve historical results and requirements. Their earlier unavailable-model status does not describe the working run above.

## AppWorld results reviewed November 16, 2026

**Historical review before the CLI repair: the live AppWorld improvement loop had not passed. The previously retained program still passed its three native tasks.** Qwen was the task actor and Gemini CLI the diagnostic judge. The [actual AppWorld results](../../runs/learning/appworld-gemini-review-20261115/appworld-results.json) preserve both outcomes separately.

These were real executions through AppWorld's official MCP server and official evaluator, using fresh simulated worlds. The tasks were `07b42fd_1`, `07b42fd_2`, and `07b42fd_3`: follow classical artists with at least 22 followers, EDM artists with at least 23, and reggae artists with at least 21. They are previously exposed training variants of one supported Spotify task family. No local ticket fixtures contribute to the following results.

| AppWorld phase | Official task successes | Observed result |
| --- | --- | --- |
| Live Qwen, raw execution | 0/3 | Repeated invalid discovery arguments, then `NO_PROGRESS` |
| Seed program with live Qwen recovery | 0/3 | Same failure during recovery |
| Previously retained native program | 3/3 | All five official checks passed per task; zero model calls |
| Gemini diagnostic judgment | Unavailable | CLI returned `UNSUPPORTED_CLIENT`; no verdict |

The six baseline episodes made 18 actual Qwen calls, with valid provider receipts. Each repeatedly supplied an empty object for `discover_tools.strategy`, which violated its schema. Runtime validation rejected those calls. See the [baseline audits](../../runs/learning/appworld-gemini-review-20261115/baseline-native-audits.json) and [original execution record](../../runs/learning/appworld-gemini-review-20261115/native/inference-result.json).

The retained program came from the first accepted repair in the earlier native AppWorld run. It was originally produced by bounded program search, so its successful replay is evidence of retention, not a newly demonstrated LLM improvement. The third retention session initially timed out during initialization; a separate fresh-world retry passed. Both the timeout and retry are recorded in the results. [Original native promotion](../../runs/learning/appworld-gemini-review-20261115/retained-program-origin.json), [retry receipt](../../runs/learning/appworld-gemini-review-20261115/retention-retry-result.json).

A real failed AppWorld episode was submitted to the installed Gemini CLI with an event index and bounded original evidence. Google rejected the request before inference. The [judge input](../../runs/learning/appworld-gemini-review-20261115/gemini-judge-input.json) and [unavailable result](../../runs/learning/appworld-gemini-review-20261115/gemini-judge-result.json) are retained. No other model is counted as its replacement.

The assistant incorrectly added a separate Qwen schema-repair proposer experiment. That experiment produced one native pass out of six, but it did not follow the intended role assignment and is withdrawn. Its provider projection and associated test were reverted. Runtime source hashes match the original native baseline, and the evidence remains available for audit. See the [role correction](../../runs/learning/appworld-gemini-review-20261115/role-correction.json). No new improvement is accepted from that experiment.

## Earlier synthetic review: November 15, 2026

**The existing repair mechanism demonstrated improvement and retention. The requested loop with Gemini as diagnostic judge is still unverified and blocked.** The current runtime judge is deterministic; automatic Gemini diagnosis feeding the proposer is not implemented. A direct Gemini CLI check and an actual diagnosis request against a recorded failure both returned `UNSUPPORTED_CLIENT` before a model response. Restoring CLI access and connecting its validated findings to the proposer are both still required.

This review preserved the existing implementation and model configuration. Its control used the scripted reference actor, bounded program search, and deterministic checks. These results must not be described as Gemini judgments or LLM-authored improvements. All writes were to fresh synthetic local worlds. The evidence directory is [gemini-judge-review-20261115](../../runs/learning/gemini-judge-review-20261115/manifest.json). Timestamps in artifacts use November 16 UTC, which was November 15 in America/New_York.

### Wins observed

| Measurement | Result | Evidence |
| --- | --- | --- |
| Existing automated tests | 131 passed in 155.139 seconds | [Test log](../../runs/learning/gemini-judge-review-20261115/unit-tests.log) |
| Sequential control after small per-request adjustments | 8/10 initially, then 10/10 on the exposed development rerun | [Adjusted execution record](../../runs/learning/gemini-judge-review-20261115/adjusted-control/inference-result.json) |
| Structural repairs retained | Three accepted, 71 candidates rejected | [Repair lineage and gates](../../runs/learning/gemini-judge-review-20261115/accepted-repairs.json) |
| Separate frozen generated checks | Seed: 42/96 passed. Final package: 96/96 passed | [Paired results](../../runs/learning/gemini-judge-review-20261115/unseen-check-results.json) |
| Final fresh-world execution | 10/10 requests passed with fallback disabled and zero actor calls | [Replay receipts](../../runs/learning/gemini-judge-review-20261115/final-replays.json) |
| Larger work | Numeric, relationship, and combined selection passed on 256-ticket worlds | [Requests and initial states](../../runs/learning/gemini-judge-review-20261115/control-requests.json) |
| Evidence integrity | Archive audit passed; protected runtime and model configuration hashes unchanged | [Control summary](../../runs/learning/gemini-judge-review-20261115/control-summary.json) |

The three accepted edits were small changes to stored operator compositions:

1. Add the bound numeric filter to direct selection. A 24-ticket age requirement exposed the gap; the learned package then handled 96 and 256 tickets.
2. Join selected tickets to the matching customers. A 48-ticket customer-region requirement exposed the gap; the learned package then handled 128 and 256 tickets.
3. Apply the numeric filter after the relationship join. The combined age-and-region requirement exposed this separate gap; the learned package then handled 256 tickets and preserved the original simple task.

Each accepted edit passed 16 fresh structural challenges and actual fresh-world executions of every retained case, with fallback disabled. The successive retained suites contained 2, 4, and 8 distinct cases. Candidate packages use bound slots, not hardcoded ticket IDs, regions, or age thresholds. The final package is `b6fb51dfbe300eed1351c8535df8ee3c3529e5e107024def7961d529e72de4e0`.

### Losses and small adjustments

The initial sequence completed 8/10 requests. Both failures remain failures in the original record, even though learning subsequently repaired their selectors.

| Request | First execution | What happened afterward |
| --- | --- | --- |
| Open tickets, 12 | Passed | Passed again after all three repairs |
| New age condition, 24 | Passed through scripted recovery | Numeric composition repaired |
| Different age condition, 96 | Passed without fallback | Reused the numeric repair |
| New customer-region condition, 48 | `NO_PROGRESS` | Relationship composition repaired; final replay passed |
| Different customer region, 128 | Passed without fallback | Reused the relationship repair |
| Age condition, 256 | Passed without fallback | Preserved earlier behavior |
| Customer-region condition, 256 | Passed without fallback | Preserved earlier behavior |
| Combined age and region, 48 | `NO_PROGRESS` | Combined composition repaired; final replay passed |
| Different combined condition, 256 | Passed without fallback | Reused the combined repair |
| Original task again, 12 | Passed without fallback | Earlier simple behavior preserved |

The two failed reference-actor runs repeatedly called `inspect_state`. Their roughly 19,000-character contexts were compacted to roughly 5,000 characters, removing the recent observation from the fixture actor's expected input. Original outputs remained stored. See [trace observations](../../runs/learning/gemini-judge-review-20261115/trace-observations.json).

Counterfactual replays pinned each request's original, still-defective package and changed only per-run context settings. Increasing `max_context_chars` from 16,000 to 32,768 restored recovery for the relationship case. The combined case still failed with `MODEL_ERROR` because its 12,002-byte observation was cut at the 12,000-character inline limit. Raising `inline_output_chars` to 20,000 restored recovery there too. The [three replay results](../../runs/learning/gemini-judge-review-20261115/context-replay-results.json) retain the intermediate failure. These are fixture-specific adjustments, not validated settings for the configured 8,192-token Qwen model. Global defaults were not changed.

A subsequent full sequence applied these two limits only to the two previously failed requests. It completed 10/10 requests, retained three repairs, and produced exactly the same final package as the initial sequence. Both archive audits passed. This was a development rerun on exposed cases. Its [manifest](../../runs/learning/gemini-judge-review-20261115/adjusted-manifest.json) records the changes before execution; the [overall verdict](../../runs/learning/gemini-judge-review-20261115/review-result.json) keeps this control success separate from the blocked Gemini loop.

Gemini remained unavailable through the installed CLI and its existing login. The [direct CLI receipt](../../runs/learning/gemini-judge-review-20261115/direct-cli-check.json) records exit code 55 and Google's rejection message. The separate [judge input](../../runs/learning/gemini-judge-review-20261115/gemini-judge-input.json) supplied a real failed episode's 36-event index, three complete original artifacts, explicit omitted evidence, and the existing `JudgeAssessment` contract. The [judge result](../../runs/learning/gemini-judge-review-20261115/gemini-judge-result.json) is `JUDGE_UNAVAILABLE`, with no model response. No other provider replaced Gemini. A matching failure is reported in the [Gemini CLI repository](https://github.com/google-gemini/gemini-cli/issues/28846).

The earlier six Qwen proposal experiments also remain negative results: zero accepted improvements. Their [summary](../../runs/learning/llm-new-work-20261115-v6/demonstration-summary.json) is historical evidence, not a fresh test of Gemini judging.

### Scope and reproducibility

The 96 checks were frozen before this control began and withheld from its repair inputs. They vary schema names, comparisons, relationship directions, empty results, and update types. They are small synthetic examples from the existing structural generator, not an independent benchmark or production reliability estimate. Larger-world execution is the separate 256-ticket result. The original seven workload definitions were reused from earlier exposed experiments; the two combined-condition requests and final preservation request extend that sequence. There are 10 executions and 9 distinct retained cases.

The control spent 74 candidate proposals and the default 20 learning cycles. Further learning needs a deliberate cycle-budget increase; this run does not establish unlimited improvement as work grows. No model weights, new operators, application code, or authentication settings were changed.

To repeat the control with a new archive path:

```sh
python3 scripts/inference.py run \
  --archive runs/learning/gemini-review-repeat \
  --requests runs/learning/gemini-judge-review-20261115/control-requests.json \
  --allow-kernel-repair
```

An exit code of 1 is expected for the original sequence because two initial requests failed. Its persisted learning and final-package replays must be inspected separately. The frozen check inputs and all final replay receipts are saved alongside the manifest. To check the installed Gemini CLI again, use `python3 scripts/check_models.py --provider gemini`; passing readiness would still not establish integrated Gemini judging.

To repeat the successful adjusted control, use the same command with a fresh archive path and `--requests runs/learning/gemini-judge-review-20261115/adjusted-control-requests.json`. That sequence exited 0 in this review.

## Earlier live-model protocol

This protocol verifies the connected loop using the configured `qwen3:8b-q4_K_M` model. It does not offer a scripted actor option. The official AppWorld evaluator, typed completion checker and promotion requirements remain protected.

The completed frozen attempt failed the full live-recovery criteria. See the [measured results](../../runs/learning/live-acceptance-v2/RESULTS.md) and [machine-readable verdict](../../runs/learning/live-acceptance-v2/proof-report.json). Its two automatic program repairs and regression gates passed within the declared scope; live-model recovery did not.

Run from the project root, using the installed native environment:

```sh
.venv/appworld/bin/python scripts/prove_inference.py --archive runs/learning/live-acceptance-v2
```

The runner records its manifest, source identities, installed model identity, task selection and generated stress inputs before starting. It resumes completed request IDs without repeating their application writes. An interrupted execution still requires reconciliation; a missing result cannot count as a pass.

## Scheduled evidence

1. Three raw model-driven ReAct episodes, one for each preselected native training variant.
2. Three episodes using the initial program, requiring a recorded kernel gap and successful live-model recovery in the same world.
3. Automatic program repair, followed by fresh executions of every retained case with fallback disabled before activation.
4. Three fresh-environment repeats of each native variant through the accepted program, requiring zero fallback model calls.
5. A local relationship case requiring live-model recovery and a second automatic repair. The old native cases remain in its mandatory regression suite.
6. A different relationship instance and an old native task executed after the second repair.
7. One hundred preregistered generated cases varying schema names, values, record identities, numeric comparisons and relationship topology. These are separate structural checks, not native benchmark instances.
8. A negative control that bypasses the learned numeric filter. Fresh execution gates must reject it and leave the active package unchanged.

`proof-report.json` lists every acceptance condition and exits nonzero unless all pass. `proof-progress.json` retains per-request outcomes during the run. Each row links the original trace and judge receipt. Accepted repairs retain paired comparisons, challenge checks and native execution-gate receipts.

## Runtime defects found through live testing

The initial scripted integration tests did not reveal several model-facing problems. Their failed live probes are retained under `runs/learning/live-proof-probe*`.

* Authentication was left to the model, which guessed access tokens. The session broker now injects the already-authorized token only for its selected application. It removes that field from actor-facing schemas, retains the native schema for validation, and rejects conflicting tokens or attempts to bind business arguments.
* The old Ollama CLI invocation did not apply the configured 8,192-token context. The server reported 4,096 tokens. A fixed-command HTTP transport now applies the unchanged configured model, context, output limit, temperature and thinking setting. Each call captures the actual request, response, usage and server context size in the private diagnostic receipt.
* Free-form JSON let the model invent batch arguments for a single-record endpoint. The transport now presents registered actions and recently inspected APIs as native function tools, with their observed input schemas and actual tool-result roles. A proposed native call is mapped into the serial broker once. Schemas guide the model; the runtime and native broker independently enforce admission. Additional calls proposed in the same response are recorded but not dispatched.
* Reading a large record dump encouraged guessed fields and IDs. The observation tool now provides schema inspection and bounded caller-specified queries using the existing operators. Its schema is derived from observed entity types and property types. Unknown types/properties are rejected, not silently interpreted as an empty target set. No query automatically supplies the task's predicates or target IDs.
* A model could complete the requested state and then continue making changes. The independent completion verifier now runs after each successful ReAct write. A satisfied goal stops execution immediately; an unmet goal returns bounded feedback. This does not treat a tool's success response as task success.
* The first preregistered attempt exposed a case-sensitive genre query, inconsistent with the native search API's uncased semantics, and conflicting legacy wrapper instructions. That attempt remains under `runs/learning/live-acceptance`, with two completed native passes, one native failure and an interrupted recovery. The second attempt uses the same acceptance criteria after correcting those adapter issues. It is a development rerun, not an independent held-out evaluation.

These are versioned runtime fixes. The subsequent accepted program changes remain automatically proposed and regression-gated. The acceptance run freezes the runtime before measuring them.

## What a pass establishes

A pass establishes the scheduled execution, recovery, repair and regression behavior with the configured model and unchanged native checks. Wire receipts establish that model calls occurred, used the configured settings, and retained the original goal. It does not turn the three previously exposed native training variants into sealed held-out tasks. Repeated worlds test repeatability on those variants; generated cases test structural variation separately. The native goal binder currently accepts one declared artist-following grammar. The operator vocabulary and completion rules are implemented beforehand. Automatic learning edits the typed operator composition, not model weights, arbitrary Python, new API semantics or the native grammar. The relationship transfer uses local fixtures. These limits must accompany any reported pass.

The raw actor can choose an irrelevant inspected API or guess arguments. Native schema admission checks argument structure, not the wisdom of an action. Readback and official evaluation decide task success. The current no-progress guard detects consecutive identical action/outcome pairs; alternating unproductive actions can reach the hard step or time budget. This is not a proven general cycle detector or a guarantee of reliable live-model recovery.

The seed's missing-filter preflight normally hands off before the first mutation. A successful live recovery establishes continuity within that native session and budget, but is not by itself a live demonstration of recovery after a partially completed mutation sequence. Partial-progress handoff has separate automated fixture coverage. Repair is bounded search over the existing operator vocabulary, scored with trusted completion checks; it does not require a successful model trajectory and does not learn new verifier semantics. Native action routing remains implemented in the adapter. A successful repaired executor does not establish learned API semantics or a general-purpose learned dispatcher.
