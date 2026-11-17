#!/usr/bin/env python3
"""Run independent educational projects and retain exact outputs, never model claims."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent


def main():
    output = ROOT / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    projects = sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit())
    for project in projects:
        script = project / "run.py"
        hashes = {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in project.rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and "results" not in p.parts}
        try:
            result = subprocess.run([sys.executable, str(script)], cwd=ROOT.parent,
                                    capture_output=True, text=True, timeout=60)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
            stderr, code = "RUNNER_TIMEOUT", 124
        try:
            parsed = json.loads(stdout)
            valid_json = isinstance(parsed, dict)
        except (ValueError, TypeError):
            valid_json = False
            parsed = {}
        checks = parsed.get("checks", {}) if valid_json else {}
        checks_passed = bool(checks) and all(value is True for value in checks.values())
        row = {"project": project.name, "exit_code": code,
               "json_result": valid_json, "passed": code == 0 and valid_json and checks_passed,
               "check_count": len(checks), "status": parsed.get("status", "EXECUTED"),
               "source_sha256": hashes, "stdout": stdout, "stderr": stderr}
        (output / (project.name + ".json")).write_text(json.dumps(row, indent=2) + "\n")
        rows.append({k: row[k] for k in ("project", "exit_code", "json_result", "passed", "check_count", "status")})
        print(f"{'PASS' if row['passed'] else 'FAIL'} {project.name} ({row['status']})")
    summary = {"kind": "synthetic_educational_checks", "models_run": False,
               "appworld_run": False, "expected_projects": 10,
               "all_passed": len(rows) == 10 and all(r["passed"] for r in rows),
               "projects": rows, "python": sys.version}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Evidence: {output}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
