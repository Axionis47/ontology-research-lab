"""Private local transport between fixed ReAct commands and an MCP session owner."""

import json
import socket

MAX_MESSAGE = 4 * 1024 * 1024


def receive(connection) -> dict:
    stream = connection.makefile("rb")
    try:
        payload = stream.readline(MAX_MESSAGE + 1)
    finally:
        stream.close()
    if not payload.endswith(b"\n") or len(payload) > MAX_MESSAGE:
        raise ValueError("Incomplete or oversized session message")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Session messages must be objects")
    return value


def request(address: str, method: str, arguments: dict | None = None, timeout: float = 90) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(address)
        connection.sendall((json.dumps({"method": method, "arguments": arguments or {}}, allow_nan=False) + "\n").encode())
        result = receive(connection)
    if "session_error" in result:
        raise RuntimeError(result["session_error"])
    return result
