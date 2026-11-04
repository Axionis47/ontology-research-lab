"""Commands for the local application and explicit background jobs."""

import json
from pathlib import Path

import typer

from oak.service import Service

app = typer.Typer(no_args_is_help=True)


@app.command()
def worker(run_id: str = typer.Option(..., "--run-id"), root: Path = Path(".local")):
    """Execute or resume an already saved job."""
    Service(root).run_worker(run_id)


@app.command()
def web_worker(run_id: str = typer.Option(..., "--run-id"), root: Path = Path(".local")):
    """Execute one previously accepted discovery, construction, or inference job."""
    from oak.web_jobs import WebJobs

    WebJobs(root).run_worker(run_id)


@app.command()
def serve():
    """Open the small local ontology auditor."""
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(Path(__file__).with_name("ui.py")),
            "--server.address",
            "127.0.0.1",
            "--server.port",
            "8501",
            "--browser.gatherUsageStats",
            "false",
        ],
        check=True,
    )


@app.command()
def resume(run_id: str, root: Path = Path(".local")):
    """Resume a failed job from its saved workflow checkpoint."""
    Service(root).resume_job(run_id)


@app.command()
def mcp_onboard(configuration: Path, root: Path = Path(".local")):
    """Discover a real configured MCP surface without a preloaded answer corpus."""
    from oak.bootstrap import SurfaceEngine

    result = SurfaceEngine(root).onboard(json.loads(configuration.read_text()))
    typer.echo(json.dumps(result, indent=2))


@app.command()
def mcp_run(
    surface_id: str, query_id: str, kernel_id: str | None = None, root: Path = Path(".local")
):
    """Run a starter episode, or supply a frozen kernel for fresh live inference."""
    from oak.bootstrap import SurfaceEngine

    result = SurfaceEngine(root).run_episode(surface_id, query_id, kernel_id=kernel_id)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def mcp_construct(
    surface_id: str, round_index: int = 0, parent_id: str | None = None, root: Path = Path(".local")
):
    """Sample construction requests and construct a candidate S/F from real episodes."""
    from oak.bootstrap import SurfaceEngine

    result = SurfaceEngine(root).construct(surface_id, round_index=round_index, parent_id=parent_id)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def artifact(identity: str, root: Path = Path(".local")):
    """Inspect a hash-verified capability, context, episode, kernel, or receipt."""
    from oak.store import Store

    typer.echo(json.dumps(Store(root).get(identity), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
