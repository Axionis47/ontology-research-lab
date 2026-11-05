# Verified MCP task-surface slice

Verified on 2026-11-03 against the genuine `@dangahagan/weather-mcp@1.35.7` server and Gemini CLI. The [evidence manifest](mcp-slice.json) records actual run, kernel, graph, receipt, evaluation, source, and cost identities. This is a small authored real-service pilot, not an official benchmark or a statistical generalization result.

The engine starts with MCP contracts, a starter prompt, public task requests, and empty observations. It retrieves construction history without old answer values, samples construction requests, collects actual episodes, generates S/F, runs real HermiT, and probes functions through live calls. Frozen inference acquires fresh data through F and extracts G under the same S. Each acquisition exposes its own typed entity groups, avoiding unrelated accumulated graph records during the demonstrated computations. Native arguments remain validated by the MCP bridge even when F accepts a general argument object.

| Evidence | Observed result |
| --- | --- |
| Starter episode | Acquired Berlin forecast and independently scored correctly |
| Round 0 | Schema passed HermiT; function argument and JSON repair failures prevented kernel creation |
| Round 1 | City-only candidate passed logical and function probes, then failed the exact-coordinate development task |
| Fresh round 2 | Constructed a child from requests 02 and 07; HermiT and two live function probes passed |
| Frozen child, development-01 regression | Prague highs 8, 9, 9 degrees Celsius, returned count 0 correctly |
| Same child, development-02 | Vienna highs 8, 9, 10 degrees Celsius, returned maximum 10 correctly |
| Same child, untouched heldout-01 | Helsinki highs 8, 8, 4 degrees Celsius, returned count 2 correctly; local dates were November 4 through 6 |

The original development failure is substantive. Its city-only function received the coordinate string `50.0755, 14.4378` as a city name. The server returned the swapped point, latitude 14.4378 and longitude 50.0755. The agent claimed completion with answer 3. The independent evaluator rejected that location mismatch. Logical validity and executable functions therefore did not establish task success.

The final frozen candidate is `f9d723509bcd5f6e64c0f76a8adf809950d702e7eaaf221e5539716e91339c90`, with parent `eb54778d20ecbb4041d0d7c7e4d753a24b315cbc35526f29505be8cc4ab1c227`. Neither manifest was rewritten after evaluation or automatically promoted. The held-out request was executed once after the development checks, with no subsequent tuning against its result. Two other held-out requests remain untouched.

The final suite passed 84 tests. Six opt-in live tests were skipped by the default command, consisting of two USGS checks and four MCP checks. All four MCP scenarios passed separately against the real server: acquisition, predispatch rejection, changed configuration, and removed capability discovery. Ruff, the strict documentation build, and diff checks passed. Sandbox DNS failures were retained as failures; successful network-enabled retries are separate receipts.

Estimated model usage for this campaign was $0.29333025 across 45 calls, with $0.5867775 retained as unknown reservation. These are estimates and reservations, not a provider invoice. Both the additional $5 campaign bound and the global $40 bound were respected.

The graph audit matched task-critical temperatures, units, date meanings, location relations, and coverage to the actual receipts. It also found limits that remain material:

- Dates mix ISO values and source display labels. Canonical date and stable identity guarantees are not established.
- Generated `low_temperature` remains required despite these tasks needing only highs. Missing-low behavior is untested.
- F does not enforce all task obligations, including arbitrary completeness, granularity, and unit requirements. The independent evaluator verifies these for this narrow pilot.
- An unused wind-speed description says average while the native daily display uses a maximum. Temperature success does not validate every ontology field.
- Fresh sampling and bounded candidate repairs are implemented. The demonstrated refinement included engineering changes to generic prompts and result handling; it is not a fully autonomous task-score optimization loop.
- History ranking is lexical. Semantic retrieval, mutating workflows, robust MCP resume, semantic server migrations, repeated-acquisition identity behavior, and a second materially different MCP task surface remain unverified or deferred.

Use the [MCP surface guide](../mcp-surface.md) to reproduce onboarding and execution. Full local artifacts are hash-verified through `oak artifact ID`; this public report excludes credential-bearing provider diagnostics.
