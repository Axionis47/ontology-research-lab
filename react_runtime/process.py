"""Execute a fixed command without a shell and capture stdout directly to disk."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .store import timestamp


def execute(command: list[str], stdin: bytes, output_path: Path, *, timeout: float,
            max_output_bytes: int, cwd: Path, stderr_path: Path, env: dict | None = None) -> dict:
    started = time.monotonic()
    started_at = timestamp()
    reason = "COMPLETE"
    returncode = None
    stderr_code = None
    # Both streams go directly to private files. Diagnostics are never actor-visible.
    with tempfile.TemporaryFile() as input_file, stderr_path.open("wb+") as stderr_file:
        input_file.write(stdin)
        input_file.seek(0)
        with output_path.open("wb") as output_file:
            try:
                process = subprocess.Popen(command, stdin=input_file, stdout=output_file,
                                           stderr=stderr_file, cwd=cwd, env=env,
                                           start_new_session=True, shell=False)
            except OSError as error:
                return {"status": "START_ERROR", "returncode": None,
                        "error_type": type(error).__name__, "error_message": str(error),
                        "started_at": started_at, "finished_at": timestamp(), "duration_ms": 0}
            try:
                while process.poll() is None:
                    if time.monotonic() - started >= timeout:
                        reason = "TIMEOUT"
                    elif output_path.stat().st_size > max_output_bytes or os.fstat(stderr_file.fileno()).st_size > max_output_bytes:
                        reason = "OUTPUT_LIMIT"
                    if reason != "COMPLETE":
                        break
                    time.sleep(0.02)
            except KeyboardInterrupt:
                reason = "CANCELLED"
            finally:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                returncode = process.wait()
                output_file.flush()
                os.fsync(output_file.fileno())
                stderr_file.flush()
                os.fsync(stderr_file.fileno())
        stderr_file.seek(0)
        diagnostic = stderr_file.read(max_output_bytes)
        stderr_bytes = os.fstat(stderr_file.fileno()).st_size
        for code in (b"UNSUPPORTED_CLIENT", b"connection refused", b"operation not permitted"):
            if code in diagnostic:
                stderr_code = code.decode()
        if reason == "COMPLETE" and (output_path.stat().st_size > max_output_bytes or stderr_bytes > max_output_bytes):
            reason = "OUTPUT_LIMIT"
    if reason == "COMPLETE" and returncode:
        reason = "EXIT_ERROR"
    return {"status": reason, "returncode": returncode,
            "pid": process.pid, "started_at": started_at, "finished_at": timestamp(),
            "timeout_seconds": timeout, "capture_limit_bytes": max_output_bytes,
            "stdout_bytes": output_path.stat().st_size,
            "stderr_code": stderr_code, "stderr_bytes": stderr_bytes,
            "duration_ms": round((time.monotonic() - started) * 1000)}
