# Combined ontology consumption with revocation recovery

**Executed: [actual recovery trace, exact contexts, and token totals](RESULTS.md).** Gemini selected Vera/Tao, received the revocation rejection, recomputed against revision 8, and returned `panel=null`. Five calls reported 101,424 total tokens including routing and thinking.

This extends the same synthetic approval task without changing its initial facts or business rules. Gemini remains the user-requested experimental participant using its configured CLI model and login.

Available mechanisms: catalog, dependency-based definition retrieval through inspection, record queries, directed graph traversal, typed valid-panel computation, candidate constraint checks, and runtime validation. Full ontology injection is intentionally not added to on-demand retrieval because it would eliminate the definition-discovery step.

The model chooses among the interfaces. To finish, it must have inspected eligibility and obtained a valid-panel computation at the current graph revision. This is enforced in code, with corrective feedback for premature finishes.

The first correct proposal triggers exactly one fixture change before execution: `del-Vera.active=false`, revision 7 becomes 8. Gemini receives the rejection, changed record ID, and instruction to refresh evidence and recompute. It receives no evaluator answer. Old observations remain in the history with their old revision. The model can query the changed delegation, diagnose panels, recompute all valid panels, and return a new answer. No new authority is created to manufacture success.

The hand-authored original oracle and deterministic checks establish that no valid pair remains. Correct recovery is a current `panel=null` finish after new computation, with no execution. This is task blockage with correct recovery, not a completed approval.

Bound: 12 CLI invocations, configured 180-second timeout each, no automatic retries or model substitutions. Each continuation resends base context plus history. Capture all exact submitted prompts, original CLI envelopes, role/model usage, interface responses, gate outcomes, and file hashes.

```sh
python3 -m unittest discover -s learning-labs/ontology-consumption-complex/combined-recovery -p test_recovery.py
python3 learning-labs/ontology-consumption-complex/combined-recovery/run.py --live
python3 learning-labs/ontology-consumption-complex/combined-recovery/report.py <evidence-directory>
```

Two dedicated regression tests cover stale and falsely updated proposals, disappearance of valid panels, unchanged original data, and the current-computation requirement. The original 14 engine tests cover domain constraints.

This is a local synthetic application protocol, not a native MCP server or AppWorld run. No external actions execute. The runtime still needs transactional enforcement for actual concurrent writes in a real deployment.
