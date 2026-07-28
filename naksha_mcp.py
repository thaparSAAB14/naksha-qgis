# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2"]
# ///
"""MCP stdio proxy for Naksha — drive live QGIS from the AI subscription you already pay for.

Any MCP client app (the desktop/CLI agents bundled with Claude, ChatGPT, Gemini
subscriptions, agentic IDEs, ...) can use this. Example registration:

    claude mcp add naksha -- uv run C:\\path\\to\\naksha_mcp.py

Requires QGIS to be running with the Naksha plugin's "AI Bridge" toggled on
(Plugins → Naksha → AI Bridge). This file lives OUTSIDE the plugin package —
pip deps are fine here, never inside naksha/.
"""

import asyncio
import json
import urllib.request
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

DISCOVERY = Path.home() / ".naksha" / "bridge.json"


def _request(path, data=None):
    try:
        info = json.loads(DISCOVERY.read_text())
    except OSError:
        raise RuntimeError(
            "QGIS is not running with Naksha's AI Bridge enabled "
            "(in QGIS: Plugins → Naksha → AI Bridge)"
        ) from None
    req = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers={"X-Naksha-Token": info["token"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


app = Server("naksha")


@app.list_tools()
async def list_tools():
    return [
        Tool(name=s["name"], description=s["description"], inputSchema=s["parameters"])
        for s in _request("/tools")
    ]


@app.call_tool()
async def call_tool(name, arguments):
    result = _request("/call", {"name": name, "args": arguments or {}})
    return [TextContent(type="text", text=result["result"])]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
