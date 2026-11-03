"""Prepare and inspect the pinned Gemini CLI without user or workspace code."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
POLICY = '[[rule]]\ntoolName = "*"\nargsPattern = ".*"\ndecision = "deny"\npriority = 999\n'
LAUNCH_PROMPT = "Read the JSON request on stdin. Return only the requested JSON value."


def runtime_settings(config: dict) -> dict:
    """Disable execution and retain one declaration for Vertex's tool schema."""
    return {
        "security": {"auth": {"selectedType": "vertex-ai"}},
        "general": {"enableAutoUpdate": False, "retryFetchErrors": False, "maxAttempts": 1},
        "hooksConfig": {"enabled": False},
        "skills": {"enabled": False},
        "mcp": {"allowed": []},
        "mcpServers": {},
        "tools": {"core": ["list_directory"]},
        "useWriteTodos": False,
        "context": {"fileName": []},
        "advanced": {"ignoreLocalEnv": True},
        "telemetry": {"enabled": False},
        "model": {"name": config["model"], "maxSessionTurns": 1},
        "modelConfigs": {
            "customOverrides": [
                {
                    "match": {"model": config["model"]},
                    "modelConfig": {
                        "generateContentConfig": {
                            "maxOutputTokens": config["max_output_tokens"],
                            "temperature": 0,
                            "toolConfig": {"functionCallingConfig": {"mode": "NONE"}},
                            "thinkingConfig": {"thinkingLevel": "low", "includeThoughts": False},
                        }
                    },
                }
            ]
        },
    }


def cli_identity() -> dict:
    """Identify the installed, verified CLI and its dependency lock."""
    package = PROJECT / "node_modules/@google/gemini-cli"
    version = json.loads((package / "package.json").read_text())["version"]
    if version != "0.66.0":
        raise RuntimeError("Gemini CLI isolation must be reverified before changing version 0.66.0")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for Gemini CLI")
    node_version = subprocess.run(
        [node, "--version"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()
    return {
        "version": version,
        "node": node,
        "node_version": node_version,
        "entry_sha256": hashlib.sha256((package / "bundle/gemini.js").read_bytes()).hexdigest(),
        "package_lock_sha256": hashlib.sha256(
            (PROJECT / "package-lock.json").read_bytes()
        ).hexdigest(),
    }


def configured_project() -> str:
    """Read the configured GCP project without changing cloud configuration."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        project = result.stdout.strip()
    if not project or project == "(unset)":
        raise RuntimeError("No GCP project configured for Gemini CLI")
    return project


@dataclass
class Invocation:
    """A fresh CLI session with inspectable configuration and no executable tools."""

    command: list[str]
    env: dict[str, str]
    cwd: Path
    directory: Path
    settings: dict
    inspection: dict

    def close(self) -> None:
        """Remove the empty work directory, preserving anything unexpected."""
        try:
            self.cwd.rmdir()
        except OSError:
            pass


def prepare_invocation(
    store_root: Path,
    call_id: str,
    config: dict,
    project: str,
    system_prompt: str,
) -> Invocation:
    """Build an isolated home and inspect the actual CLI registry before auth.

    Only the new empty temporary directory is trusted during invocation. This
    never trusts the checkout, reads its hooks, or changes global user settings.
    The existing ADC file is referenced by path and is never copied or logged.
    """
    for path in (
        Path("/Library/Application Support/GeminiCli/settings.json"),
        Path("/Library/Application Support/GeminiCli/system-defaults.json"),
    ):
        if path.exists():
            raise RuntimeError(f"System Gemini settings require independent inspection: {path}")
    system_policies = Path("/Library/Application Support/GeminiCli/policies")
    if system_policies.exists() and any(system_policies.glob("*.toml")):
        raise RuntimeError("System Gemini policies require independent inspection")
    credentials = Path.home() / ".config/gcloud/application_default_credentials.json"
    if not credentials.is_file():
        raise FileNotFoundError("Existing Google application-default credentials were not found")
    cwd = Path(tempfile.mkdtemp(prefix="oak-gemini-work-", dir="/private/tmp")).resolve()
    try:
        for ancestor in (cwd, *cwd.parents):
            if any((ancestor / name).exists() for name in (".gemini", ".agents", "GEMINI.md")):
                raise RuntimeError(f"Unexpected inherited Gemini configuration near {ancestor}")
        directory = store_root / "gemini-runtimes" / call_id
        home = directory / "home"
        settings_dir = home / ".gemini"
        settings_dir.mkdir(parents=True, exist_ok=False)
        settings = runtime_settings(config)
        (settings_dir / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
        policy = directory / "deny-tools.toml"
        policy.write_text(POLICY)
        system_path = directory / "system.md"
        system_path.write_text(system_prompt)
        env = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "USER", "LOGNAME")
            if key in os.environ
        }
        env.update(
            {
                "GEMINI_CLI_HOME": str(home),
                "GEMINI_CLI_AUTH_OVERRIDE": "vertex-ai",
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                "GOOGLE_CLOUD_PROJECT": project,
                "GOOGLE_CLOUD_LOCATION": config["location"],
                "GOOGLE_APPLICATION_CREDENTIALS": str(credentials),
                "GEMINI_SYSTEM_MD": str(system_path),
                "NO_COLOR": "1",
            }
        )
        bundle = PROJECT / "node_modules/@google/gemini-cli/bundle"
        settings_module = next(
            path
            for path in sorted(bundle.glob("chunk-*.js"))
            if "function loadSettings(workspaceDir" in path.read_text()
        )
        core = bundle / "chunk-RZ3ZVTZB.js"
        program = f"""
const {{loadSettings}} = await import({json.dumps(settings_module.as_uri())});
const {{Config, createPolicyEngineConfig}} = await import({json.dumps(core.as_uri())});
const cwd = {json.dumps(str(cwd))};
const loaded = loadSettings(cwd), s = loaded.merged;
const policyEngineConfig = await createPolicyEngineConfig(
  {{...s, adminPolicyPaths:[{json.dumps(str(policy))}]}},
  'default', {json.dumps(str(bundle / "policies"))}, false);
const c = new Config({{
  sessionId:'oak-runtime-inspection', targetDir:cwd, cwd, model:s.model.name,
  coreTools:s.tools.core, mcpEnabled:false, extensionsEnabled:false, enableHooks:false,
  skillsSupport:false, useWriteTodos:false, useRipgrep:false, policyEngineConfig,
  telemetry:{{enabled:false}}
}});
const registry = await c.createToolRegistry();
const check = await c.getPolicyEngine().check({{name:'list_directory',args:{{dir_path:cwd}}}});
console.log(JSON.stringify({{
  authType:s.security.auth.selectedType, nativeTools:s.tools.core,
  hooksEnabled:s.hooksConfig.enabled, skillsEnabled:s.skills.enabled,
  mcpAllowed:s.mcp.allowed, mcpServers:Object.keys(s.mcpServers ?? {{}}),
  contextFiles:s.context.fileName, ignoreLocalEnv:s.advanced.ignoreLocalEnv,
  errors:loaded.errors, declarationNames:registry.getFunctionDeclarations().map(x=>x.name),
  toolExecutionDecision:check.decision, modelOverrides:s.modelConfigs.customOverrides,
  isTrustedDuringInspection:loaded.isTrusted
}}));
"""
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required")
        inspected = subprocess.run(
            [node, "--input-type=module", "-e", program],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        inspection = json.loads(inspected.stdout.strip().splitlines()[-1])
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
            "modelOverrides": settings["modelConfigs"]["customOverrides"],
        }
        for key, value in expected.items():
            if inspection.get(key) != value:
                raise RuntimeError(f"Gemini isolation inspection failed for {key}")
        inspection["workspace_trust"] = "session_only_empty_temporary_directory"
        if any(cwd.iterdir()):
            raise RuntimeError("Gemini work directory stopped being empty during inspection")
        env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
        command = [
            node,
            str(bundle / "gemini.js"),
            "--model",
            config["model"],
            "--output-format",
            "json",
            "--approval-mode",
            "default",
            "--admin-policy",
            str(policy),
            "--extensions",
            "none",
            "--prompt",
            LAUNCH_PROMPT,
        ]
        return Invocation(command, env, cwd, directory, settings, inspection)
    except BaseException:
        try:
            cwd.rmdir()
        except OSError:
            pass
        raise
