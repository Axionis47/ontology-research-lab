# Model setup

Confirmed role assignment, November 16, 2026: **Qwen is the task executor. Gemini CLI is both the diagnostic judge and the improvement proposer, through separate calls.** [AGENTS.md](AGENTS.md) is the working agreement for new work. The narrow function-improvement cycle now has a [successful automatic AppWorld run](runs/protocol/appworld-gemini-20261116/clean-replay/result.json). Broad ontology construction and extension remain unimplemented.

## Working CLI repair, November 16, 2026

Gemini CLI now passes both authenticated text and structured-response checks through the existing Google Cloud Vertex AI credentials. The installed CLI remains version `0.68.0`, which was the latest stable npm release at verification. No model override was added. The successful probe reported `gemini-3.8-flash` for the main call and `gemini-3.5-flash-lite` for its internal router, with zero tool calls. [Readiness receipt](runs/model-checks/20261116T181431992810Z-gemini.json).

The previous personal-login failure was a service retirement, not a stale binary: Google [ended personal-account Gemini CLI service on June 18, 2026](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/). Testing the already configured Cloud project with Code Assist authentication returned license error `#3501`. The same project already had Vertex AI enabled and matching Application Default Credentials, so the repair uses that supported authentication method through the original Gemini CLI. It uses the Cloud project's API service, not personal-subscription quota. No new project, service, credentials or subscription was created.

Two small changes were necessary:

- Set the existing Gemini user configuration to `vertex-ai`, and save the existing project plus `global` location in `~/.gemini/.env`. The previous settings are backed up privately.
- Correct three statements in the installed CLI's chat request builder so an empty function-declaration list produces no tool object. Vertex rejected the previous empty object. Real proposer attempts also exposed malformed function-call output. Two additional conditionals disable function-call generation and clarify that requested JSON is response text when no tools are available. Normal sessions with tools retain their existing behavior. The deny-all execution policy remains unchanged. [Empty-tools patch](runs/protocol/appworld-reset-20261116/cli-fix/empty-tools.diff), [function-generation patch](runs/protocol/appworld-reset-20261116/cli-fix/no-function-calls.diff), [text-only instruction patch](runs/protocol/appworld-reset-20261116/cli-fix/no-tools-instruction.diff), [original backup receipt](runs/protocol/appworld-reset-20261116/cli-fix/patch-receipt.json), [authentication change receipt](runs/protocol/appworld-reset-20261116/cli-fix/auth-fix.json).

An npm reinstall or update can replace this local CLI patch. The proof manifest records its hash, and `python3 scripts/check_models.py --provider gemini` checks the working route. The historical failures below remain evidence of the earlier configuration.

The final fresh automatic run reported `gemini-3.8-flash` as the main model in both the [diagnostic call](runs/protocol/appworld-gemini-20261116/clean-replay/diagnosis.json) and the [distinct proposer call](runs/protocol/appworld-gemini-20261116/clean-replay/proposer-calls.json). Each also used the CLI's `gemini-3.5-flash-lite` utility router. Both completed with zero executed CLI tools. The runtime staged and evaluated the returned candidate separately.

## Historical checks before the repair

Earlier role correction and native review, November 16, 2026: **Qwen executes AppWorld tasks; Gemini CLI judges their traces.** The extra Qwen schema-repair proposer experiment was withdrawn and its code change reverted. The [earlier native results](docs/system/20-live-acceptance.md#appworld-results-reviewed-november-16-2026) distinguish that failed live loop from successful replay of an older retained program.

Earlier check: November 15, 2026, America/New_York. Gemini is the intended **diagnostic judge** for the requested improvement loop. The installed CLI (`0.68.0`), existing `oauth-personal` login, and inherited model selection were preserved. Both a direct text probe and an actual recorded-failure diagnosis request were rejected with `UNSUPPORTED_CLIENT` before any model response. See the [direct receipt](runs/learning/gemini-judge-review-20261115/direct-cli-check.json), [judge receipt](runs/learning/gemini-judge-review-20261115/gemini-judge-result.json), and [earlier synthetic review](docs/system/20-live-acceptance.md#earlier-synthetic-review-november-15-2026).

At that review, `judge_episode` was deterministic and the proposer transport did not implement Gemini diagnostic judging. CLI availability and automatic judge-to-proposer integration were outstanding requirements. No provider substitution, login reset, model change, or global context change was made during that earlier review. The working repair above supersedes this historical status.

## Earlier setup record

Status recorded on November 12, 2026, America/New_York.

| Role | Provider and model | Verified status |
| --- | --- | --- |
| Local task execution | Ollama, `qwen3:8b-q4_K_M` | Passed text, structured JSON, and native tool-call round trip |
| Code repair | Installed `gemini` CLI, using its own model selection and saved login | Default inference rejected by Google with `UNSUPPORTED_CLIENT` |

These are small model readiness checks. They do not measure AppWorld performance or prove authorization enforcement. The benchmark runtime, control kernel, and repair loop have not been implemented in this setup step.

## Local model

The model is installed and served at `http://127.0.0.1:11434`. The running Ollama server reports version `0.40.5`. The installed CLI reports `0.9.5`; the checks use the native HTTP API.

Configuration in `config/models.toml` sets an 8,192-token context, a 512-token output limit, temperature zero, and thinking disabled. This setup was checked on an Apple Silicon machine with 16 GB RAM.

The checks verified:

1. Exact `MODEL_OK` response.
2. A schema-constrained JSON object for a synthetic order.
3. A native `inspect_order(order_id=123)` call, consumption of a synthetic tool result, and the correct final status.

The three checks completed in approximately 12 seconds with the model already loaded. This is a setup observation, not a performance benchmark.

## Original Gemini repair-path setup

The project invokes the installed `gemini` executable directly. It does not pass `--model`, pin a replacement model, or select another provider. Authentication and model selection belong to the existing CLI configuration. The checker records the model usage returned by the CLI when inference succeeds.

The installed version is `0.68.0`. Its user settings specify `oauth-personal` authentication with no explicit model override. A live call with no model argument was rejected by Google with `UNSUPPORTED_CLIENT` for the saved login. Cloud inference and the code-repair test remain unverified.

The probe calls the CLI using this shape, with the policy path resolved to an absolute path by the script:

```sh
gemini --extensions none \
  --allowed-mcp-server-names model-check-no-servers \
  --policy config/gemini-no-tools.toml \
  --skip-trust --output-format json \
  --prompt 'Do not use tools. Reply with exactly MODEL_OK and nothing else.'
```

The policy denies tools for these small probes. The repair check requires a JSON object containing a corrected Python function. The function is validated against the expected Python AST without executing generated code. These probe restrictions are not the future project's control kernel.

Earlier setup installed Antigravity CLI `1.5.7` and added `~/.local/bin` to `.zshrc`, `.zprofile`, `.bash_profile`, and `.config/fish/config.fish`. Its sign-in attempt was stopped. The project no longer selects Antigravity. Checks of other installed CLIs found expired Claude OAuth and a broken Codex launcher. Codex `0.117.0` was reinstalled at the same version and its missing executable restored from the matching npm package, but the OS terminated it with signal 9. Neither is selected by this project, and their model settings were not changed.

## Repeat the checks

Requires Python 3.11 or newer. Verified locally with Python 3.12.8. No Python packages are required.

Run from this project directory:

```sh
python3 scripts/check_models.py --provider ollama
python3 scripts/check_models.py --provider gemini
python3 scripts/check_models.py --provider all
```

The script exits nonzero if any selected provider fails. Reports go to `runs/model-checks/`, including `latest-<provider>.json`. Reports contain synthetic responses, model and usage receipts, timings, and sanitized failure reasons. They do not save arbitrary authentication stderr.

The local success evidence is in `runs/model-checks/20261113T024917714855Z-all.json`. The current Gemini CLI result is in `runs/model-checks/latest-gemini.json`. The earlier combined report predates the correction to use the CLI's own model selection. Filenames use UTC, which is the next calendar day for this session.
