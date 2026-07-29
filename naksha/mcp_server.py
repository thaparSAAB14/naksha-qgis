"""MCP stdio server for Naksha — drive live QGIS from any AI app that speaks MCP.

Pure standard library on purpose: no `mcp` package, no `uv`, no pip, no venv. Run it
with the Python that ships inside QGIS and it just works:

    "C:\\Program Files\\QGIS 3.40.13\\bin\\python-qgis-ltr.bat" naksha_mcp.py

All protocol handling lives in the plugin (naksha/bridge.py). This file only moves
JSON-RPC frames between the client's stdin/stdout and the plugin's localhost endpoint,
so there is exactly one implementation of MCP to keep correct.

Requires QGIS running with the AI Bridge on (Plugins -> Naksha -> AI Bridge).
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DISCOVERY = Path.home() / ".naksha" / "bridge.json"
BRIDGE_DOWN = (
    "QGIS is not reachable. Start QGIS and turn on the AI Bridge "
    "(Plugins -> Naksha -> AI Bridge), then retry."
)


def forward(message):
    """POST one JSON-RPC message to the running plugin and return its reply."""
    info = json.loads(DISCOVERY.read_text())  # re-read every time: the port changes per session
    req = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}/mcp",
        data=json.dumps(message).encode(),
        headers={"X-Naksha-Token": info["token"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def main():
    out = sys.stdout
    for line in sys.stdin:  # MCP stdio framing is newline-delimited JSON
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue  # nothing sane to reply to
        try:
            reply = forward(message)
        except Exception as e:  # noqa: BLE001 - a dead pipe must still answer the client
            if message.get("id") is None:
                continue  # a notification we cannot deliver needs no reply
            # HTTPError subclasses URLError, so it has to be tested first or a stale
            # plugin (404 on /mcp) would be misreported as "QGIS is not running".
            if isinstance(e, urllib.error.HTTPError):
                detail = (f"bridge answered HTTP {e.code}. If this is 404, the running "
                          f"QGIS has an older Naksha loaded - restart QGIS.")
            elif isinstance(e, (FileNotFoundError, urllib.error.URLError)):
                detail = BRIDGE_DOWN
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
