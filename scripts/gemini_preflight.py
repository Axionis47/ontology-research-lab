"""Inspect or run one bounded Gemini CLI Vertex preflight in an isolated directory.

The default invocation only inspects effective configuration. ``--run`` makes
one explicitly authorized short model request. It never trusts the Oak checkout
or changes the user's global Gemini settings. MCP, hooks and skills are disabled.
One read-only tool declaration avoids the CLI's empty-tool Vertex request bug;
function calling is disabled and an admin policy denies every tool execution.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local/gemini-isolated"
WORK = Path("/private/tmp/oak-gemini-work")
MODEL = "gemini-3.8-flash"


def prepare() -> tuple[dict[str, str], list[str], Path]:
    """Create only the isolated runtime, and reject a nonempty invocation directory."""
    work = WORK.resolve()
    if work == ROOT or ROOT in work.parents:
        raise RuntimeError("Gemini preflight must never trust the Oak checkout")
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise RuntimeError(f"preflight work directory is not empty: {work}")
    for ancestor in (work, *work.parents):
        if any((ancestor / name).exists() for name in (".gemini", ".agents", "GEMINI.md")):
            raise RuntimeError(f"unexpected inherited configuration near {ancestor}")
    for path in (
        Path("/Library/Application Support/GeminiCli/settings.json"),
        Path("/Library/Application Support/GeminiCli/system-defaults.json"),
    ):
        if path.exists():
            raise RuntimeError(f"system Gemini settings need independent inspection: {path}")
    credential = Path.home() / ".config/gcloud/application_default_credentials.json"
    if not credential.is_file():
        raise FileNotFoundError("existing Google ADC file not found")
    home = RUNTIME / "home"
    config = home / ".gemini"
    config.mkdir(parents=True, exist_ok=True)
    for directory in (home / ".agents", config / "extensions", config / "hooks", config / "skills"):
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(f"unexpected code-bearing runtime directory: {directory}")
    settings: dict[str, Any] = {
        "security": {"auth": {"selectedType": "vertex-ai"}},
        "general": {"enableAutoUpdate": False},
        "hooksConfig": {"enabled": False},
        "skills": {"enabled": False},
        "mcp": {"allowed": []},
        "mcpServers": {},
        "tools": {"core": ["list_directory"]},
        "useWriteTodos": False,
        "context": {"fileName": []},
        "advanced": {"ignoreLocalEnv": True},
        "telemetry": {"enabled": False},
        "model": {"name": MODEL, "maxSessionTurns": 1},
        "modelConfigs": {
            "customOverrides": [
                {
                    "match": {"model": MODEL},
                    "modelConfig": {
                        "generateContentConfig": {
                            "maxOutputTokens": 256,
                            "toolConfig": {"functionCallingConfig": {"mode": "NONE"}},
                            "thinkingConfig": {
                                "thinkingLevel": "low",
                                "includeThoughts": False,
                            },
                        }
                    },
                }
            ]
        },
    }
    (config / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    policy = RUNTIME / "deny-all-tools.toml"
    policy.write_text(
        '[[rule]]\ntoolName = "*"\nargsPattern = ".*"\ndecision = "deny"\npriority = 999\n'
    )
    env = {
        key: os.environ[key]
        for key in (
            "PATH",
            "HOME",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "USER",
            "LOGNAME",
        )
        if key in os.environ
    }
    env.update(
        {
            "GEMINI_CLI_HOME": str(home),
            "GEMINI_CLI_AUTH_OVERRIDE": "vertex-ai",
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "GOOGLE_CLOUD_PROJECT": "plotpointe",
            "GOOGLE_CLOUD_LOCATION": "global",
            "GOOGLE_APPLICATION_CREDENTIALS": str(credential),
            "NO_COLOR": "1",
        }
    )
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required")
    cli = ROOT / "node_modules/@google/gemini-cli/bundle/gemini.js"
    if not cli.is_file():
        raise FileNotFoundError("pinned project Gemini CLI is absent")
    command = [
        node,
        str(cli),
        "--model",
        MODEL,
        "--output-format",
        "json",
        "--approval-mode",
        "default",
        "--admin-policy",
        str(policy),
        "--extensions",
        "none",
        "--prompt",
        "Reply with exactly OAK_VERTEX_OK. Do not use any tools.",
    ]
    return env, command, config / "settings.json"


def inspect_configuration(env: dict[str, str]) -> dict[str, Any]:
    """Call the CLI's actual settings loader without authenticating or generating."""
    bundle = ROOT / "node_modules/@google/gemini-cli/bundle"
    module = next(
        path
        for path in sorted(bundle.glob("chunk-*.js"))
        if "function loadSettings(workspaceDir" in path.read_text()
    )
    program = f"""
const {{loadSettings, USER_SETTINGS_PATH}} = await import({json.dumps(module.as_uri())});
const {{Config, createPolicyEngineConfig}} = await import(
  {json.dumps((bundle / "chunk-RZ3ZVTZB.js").as_uri())});
const loaded = loadSettings({json.dumps(str(WORK))});
const s = loaded.merged;
const policyEngineConfig = await createPolicyEngineConfig(
  {{...s, adminPolicyPaths: [{json.dumps(str(RUNTIME / "deny-all-tools.toml"))}]}},
  'default', {json.dumps(str(bundle / "policies"))}, false);
const c = new Config({{
  sessionId: 'oak-isolated-config-inspection', targetDir: {json.dumps(str(WORK))},
  cwd: {json.dumps(str(WORK))}, model: {json.dumps(MODEL)},
  coreTools: s.tools.core, mcpEnabled: false, extensionsEnabled: false,
  enableHooks: false, skillsSupport: false, useWriteTodos: false,
  useRipgrep: false, policyEngineConfig, telemetry: {{enabled: false}}
}});
const registry = await c.createToolRegistry();
const declarationNames = registry.getFunctionDeclarations().map(x => x.name);
const inspectedDirectory = {json.dumps(str(WORK))};
const policyCheck = await c.getPolicyEngine().check(
  {{name:'list_directory',args:{{dir_path:inspectedDirectory}}}});
console.log(JSON.stringify({{
  userSettingsPath: USER_SETTINGS_PATH,
  authType: s.security.auth.selectedType,
  nativeTools: s.tools.core,
  hooksEnabled: s.hooksConfig.enabled,
  skillsEnabled: s.skills.enabled,
  mcpAllowed: s.mcp.allowed,
  mcpServers: Object.keys(s.mcpServers ?? {{}}),
  contextFiles: s.context.fileName,
  ignoreLocalEnv: s.advanced.ignoreLocalEnv,
  isTrusted: loaded.isTrusted,
  errors: loaded.errors,
  declarationNames,
  toolExecutionDecision: policyCheck.decision,
  generationOverrides: s.modelConfigs.customOverrides
}}));
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", program],
        cwd=WORK,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[:2000])
    actual = json.loads(result.stdout.strip().splitlines()[-1])
    expected = {
        "authType": "vertex-ai",
        "nativeTools": ["list_directory"],
        "hooksEnabled": False,
        "skillsEnabled": False,
        "mcpAllowed": [],
        "mcpServers": [],
        "contextFiles": [],
        "ignoreLocalEnv": True,
        "errors": [],
        "declarationNames": ["list_directory"],
        "toolExecutionDecision": "deny",
    }
    for key, value in expected.items():
        if actual.get(key) != value:
            raise RuntimeError(f"isolated setting mismatch for {key}: {actual.get(key)!r}")
    return actual


def main() -> None:
    """Inspect by default; ``--run`` is one capped, explicitly authorized paid check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run the authorized $0.10 preflight")
    args = parser.parse_args()
    env, command, settings = prepare()
    actual = inspect_configuration(env)
    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "model": MODEL,
        "project": "plotpointe",
        "location": "global",
        "work_directory": str(WORK),
        "settings_path": str(settings),
        "effective_configuration": actual,
        "command": command,
        "approved_budget_usd": 0.10,
        "mode": "run" if args.run else "inspect_only",
        "model_request_made": False,
        "model_request_attempted": False,
    }
    output = ROOT / ".local/verification/gemini-preflight.json"
    if not args.run:
        output = output.with_suffix(".inspection.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.run:
        # Trust is limited to the empty, inspected /private/tmp directory above.
        # This does not modify any persistent trust file or trust the checkout.
        env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
        result = subprocess.run(
            command,
            cwd=WORK,
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )
        raw = output.with_suffix(".stdout.json")
        errors = output.with_suffix(".stderr.txt")
        raw.write_text(result.stdout)
        errors.write_text(result.stderr)
        report.update(returncode=result.returncode, stdout_path=str(raw), stderr_path=str(errors))
        report["model_request_attempted"] = "Error when talking to Gemini API" in result.stderr
        report["model_request_made"] = report["model_request_attempted"]
        try:
            response = json.loads(result.stdout)
            report["response"] = response.get("response")
            report["stats"] = response.get("stats")
            report["error"] = response.get("error")
            report["model_request_made"] = report["model_request_made"] or bool(
                response.get("stats", {}).get("models")
            )
            report["model_request_attempted"] = report["model_request_made"]
            report["native_tool_calls"] = (
                response.get("stats", {}).get("tools", {}).get("totalCalls", 0)
            )
            report["success"] = (
                result.returncode == 0
                and response.get("response", "").strip() == "OAK_VERTEX_OK"
                and report["native_tool_calls"] == 0
            )
        except json.JSONDecodeError:
            report.update(success=False, error="CLI did not emit a JSON result")
            marker = result.stderr.rfind('\n{\n  "session_id"')
            if marker != -1:
                try:
                    report["error"] = json.loads(result.stderr[marker:]).get("error")
                except json.JSONDecodeError:
                    pass
    report["finished_at"] = datetime.now(UTC).isoformat()
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
