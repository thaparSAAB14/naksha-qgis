"""MCP stdio server for Naksha — drive live QGIS from any AI app that speaks MCP.

Pure standard library on purpose: no `mcp` package, no `uv`, no pip, no venv. Run it
with the Python that ships inside QGIS and it just works:

    "C:\\Program Files\\QGIS 3.40.13\\bin\\python-qgis-ltr.bat" naksha_mcp.py

All protocol handling lives in the plugin (naksha/bridge.py). This file only moves
JSON-RPC frames between the client's stdin/stdout and the plugin's localhost endpoint,
so there is exactly one implementation of MCP to keep correct.

Requires QGIS running with the AI Bridge on (Plugins -> Naksha -> AI Bridge).
"""

import http.client
import json
import sys
from pathlib import Path

DISCOVERY = Path.home() / ".naksha" / "bridge.json"
BRIDGE_DOWN = (
    "QGIS is not reachable. Start QGIS and turn on the AI Bridge "
    "(Settings -> Naksha -> allow connected apps), then retry."
)


class BridgeHTTPError(RuntimeError):
    """The bridge answered, but not with 200."""


def forward(message):
    """POST one JSON-RPC message to the running plugin and return its reply.

    http.client rather than urllib.request on purpose: it can only ever speak HTTP to
    the host given, so there is no scheme handling to get wrong (bandit B310).
    """
    info = json.loads(DISCOVERY.read_text())  # re-read every time: the port changes per session
    conn = http.client.HTTPConnection("127.0.0.1", int(info["port"]), timeout=600)
    try:
        conn.request(
            "POST", "/mcp",
            body=json.dumps(message).encode(),
            headers={"X-Naksha-Token": str(info["token"]), "Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = response.read()
        if response.status != 200:
            raise BridgeHTTPError(
                f"bridge answered HTTP {response.status}. If this is 404, the running "
                f"QGIS has an older Naksha loaded - restart QGIS."
            )
        return json.loads(payload)
    finally:
        conn.close()


def _parse(line):
    """The decoded frame, or None when the client sent something unreadable."""
    try:
        return json.loads(line)
    except ValueError:
        return None


def main():
    out = sys.stdout
    for line in sys.stdin:  # MCP stdio framing is newline-delimited JSON
        message = _parse(line.strip())
        if message is None:
            continue  # unreadable frame carries no id, so there is nothing to answer
        try:
            reply = forward(message)
        except Exception as e:  # noqa: BLE001 - a dead pipe must still answer the client
            if message.get("id") is None:
                continue  # a notification we cannot deliver needs no reply
            if isinstance(e, BridgeHTTPError):
                detail = str(e)          # the bridge is up but rejected us
            elif isinstance(e, OSError):
                detail = BRIDGE_DOWN     # covers missing file, refused connection, timeout
            else:
                detail = f"{type(e).__name__}: {e}"
            reply = {"jsonrpc": "2.0", "id": message["id"],
                     "error": {"code": -32603, "message": detail}}
        if reply is None:
            continue  # notification: the protocol expects silence
        out.write(json.dumps(reply) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
