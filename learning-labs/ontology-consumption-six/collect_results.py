"""Collect the latest finished attempted run per project, retaining all attempts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
experiments = sorted(p.name for p in HERE.glob("[0-9][0-9]-*") if p.is_dir())
attempts = {name: [] for name in experiments}
for directory in sorted((HERE / "results").glob("20*")):
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        continue
    manifest = json.loads(manifest_path.read_text())
    for name in experiments:
        path = directory / (name + ".json")
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        if not record["calls"] or any(c["status"] == "IN_FLIGHT" for c in record["calls"]):
            continue
        attempts[name].append({"path": path, "record": record, "manifest": manifest})
if any(not values for values in attempts.values()):
    raise SystemExit("Not every project has a completed attempted run yet")
selected = {name: values[-1] for name, values in attempts.items()}
for field in ("facts_sha256", "ontology_sha256", "runner_sha256", "helper_sha256", "config_sha256", "policy_sha256"):
    if len({row["manifest"][field] for row in selected.values()}) != 1:
        raise SystemExit("Incompatible source/config identities: " + field)
out = HERE / "results" / ("comparison-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
out.mkdir()
manifest = dict(next(iter(selected.values()))["manifest"])
manifest.update(kind="collected_latest_completed_attempts", selection_policy="Latest completed attempted normal-JSON run per experiment; failures are retained, never selected away by score",
                original_receipts={name: str(row["path"].relative_to(HERE)) for name, row in selected.items()},
                task_hashes={name: row["manifest"]["task_hashes"][name] for name, row in selected.items()},
                initial_fact_hashes={name: row["manifest"]["initial_fact_hashes"][name] for name, row in selected.items()})
summary = {"complete": True, "appworld_runs": 0, "experiments": []}
history = []
for name, row in selected.items():
    shutil.copyfile(row["path"], out / (name + ".json"))
    summary["experiments"].append({"experiment": name, "status": row["record"]["status"], "passed": row["record"]["passed"]})
for name, values in attempts.items():
    for value in values:
        r = value["record"]
        history.append({"experiment": name, "original_receipt": str(value["path"].relative_to(HERE)), "status": r["status"],
                        "passed": r["passed"], "reason": r.get("reason"), "cli_calls": len(r["calls"])})
for name, value in (("manifest.json", manifest), ("summary.json", summary), ("attempts.json", history)):
    (out / name).write_text(json.dumps(value, indent=2) + "\n")
subprocess.run([sys.executable, str(HERE / "report.py"), str(out)], check=True)
print("Collected report:", out)
