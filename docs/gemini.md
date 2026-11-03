# Gemini CLI runtime

`oak.model.GeminiCLI` uses the pinned Gemini CLI 0.66.0 with the user's existing Google application-default credentials. The verified model is `gemini-3.8-flash` in `global`, with low thinking. Model selection, pricing, limits and the $40 budget are read from `config/runtime.json`. The original `config/gemini-system.md` is preserved and snapshotted for every call.

## Isolation and authentication

Every call receives a fresh Gemini home below the store's `gemini-runtimes/<call_id>/home` and a newly created empty `/private/tmp/oak-gemini-work-*` working directory. `GEMINI_CLI_HOME` selects that home; `GEMINI_CLI_AUTH_OVERRIDE=vertex-ai` selects Vertex rather than personal Code Assist. `GOOGLE_APPLICATION_CREDENTIALS` points to the existing ADC file. Credential contents are never copied or included in artifacts. The parent environment is reduced to ordinary process variables and the explicitly configured Vertex/runtime variables.

The CLI reads a generated `.gemini/settings.json`, with hooks, skills, MCP, extensions, local context files and local environment discovery disabled. Existing system settings/policies or inherited workspace configuration fail inspection rather than silently overriding these controls. The process-scoped workspace-trust variable applies only to the empty temporary directory. The Oak checkout and the user's global Gemini settings are not changed. The temporary directory is removed if it remains empty; unexpected contents are preserved.

The stock CLI generates an invalid Vertex request when its tool registry is empty. The verified workaround retains only the `list_directory` declaration. Model function calling is set to `NONE`, and an admin policy with `argsPattern = ".*"`, decision `deny`, and priority `999` denies execution for every argument. Before authentication, the adapter uses the actual CLI settings loader, registry and policy engine to verify these settings and the deny decision. A response is rejected if native tool-call statistics are nonzero or absent. The generated policy in `oak.gemini_runtime.POLICY` is authoritative for this adapter.

Gemini 3.8 Flash supports low, medium and high thinking. Minimal thinking returns a validation error. See the [official model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash).

## Receipts and resume

Each attempted call records the exact canonical prompt, runtime settings, system text, output schema, CLI identity, policy, isolation inspection, raw stdout/stderr and reported usage. Model text must parse as JSON and satisfy the supplied JSON Schema before its receipt is marked successful. Failures are persisted before they are raised. LangSmith's `traceable` boundary remains available when tracing is configured; local artifacts remain available without remote tracing.

Malformed response JSON or an output-schema mismatch after a successful provider response raises `ModelOutputError`, a `ValueError` carrying `evidence_id`, `details` and the actual `response`. Construction can use that evidence for bounded repair. Authentication, transport, timeout and native-tool-policy failures remain runtime errors. Non-finite JSON numbers are rejected.

An exact request key includes the run ID, stage, prompt, runtime configuration, generated settings, system text, output schema, project, CLI/dependency identity, launch prompt and policy. Only a completed, validated receipt with that same key can be reused. Cache hits identify the original call and artifact and explicitly record that no new provider call occurred. A per-key filesystem lock prevents concurrent resumes from issuing the same request twice. This is reuse of a prior completed model stage, not a substitute for executing graph functions or validation.

Before a new request, the store transactionally reserves a conservative input/output allowance under its shared $40 limit. Actual reported prompt tokens and output plus thinking tokens settle the estimate using pinned rates. Unknown models, missing usage and timeouts retain the reservation. Preparation failures before an attempted generation settle at zero; errors after an attempted invocation retain unknown usage. Estimates are not provider invoices. The budget is shared by calls in one root store; separate stores do not share a global ledger.

`register_preflight_receipt` imports the completed external preflight by its actual CLI session ID, so repeated registration does not charge it twice. Earlier HTTP 400 failures have raw error evidence but no generation-usage report; they are not presented as successful inference or as confirmed billing amounts.

## Actual verification on 2026-11-03

The isolated preflight returned `OAK_VERTEX_OK`: one provider request, 5,435 input tokens, six output tokens, zero thinking tokens and zero native tool calls. The estimated cost was $0.00409875. Its raw response and report are retained in `.local/verification/gemini-preflight.*`.

The integrated adapter then read the actual runtime configuration and returned its model and location fields as schema-validated JSON. That request reported 564 input tokens, 16 output tokens, zero thinking tokens and zero native tool calls, estimated at $0.000483. Immediate repetition of the identical run/stage request returned the original validated result without another model-call entry or budget change. Evidence is in `.local/verification/gemini-adapter-check.json`, run `d263d58171cd4bca9a5886071f8ba7aa`. The two completed calls totaled $0.00458175 at that checkpoint. Later application calls have their own receipts.

These checks verify authentication, isolation, JSON validation, usage accounting and receipt reuse. They do not establish ontology construction accuracy or benchmark performance.
