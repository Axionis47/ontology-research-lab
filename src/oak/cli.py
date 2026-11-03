"""Commands for the local application and explicit background jobs."""

from pathlib import Path

import typer

from oak.service import Service

app = typer.Typer(no_args_is_help=True)


@app.command()
def worker(run_id: str, root: Path = Path(".local")):
    """Execute or resume an already saved job."""
    Service(root).run_worker(run_id)


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


if __name__ == "__main__":
    app()
