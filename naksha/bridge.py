"""Localhost bridge: lets the user's existing AI subscription apps drive QGIS.

A tiny HTTP endpoint on 127.0.0.1 (random port, per-session token) exposing
Naksha's tools. naksha_mcp.py proxies it as an MCP server, so any MCP client —
the ones bundled with Claude, ChatGPT, Gemini subscriptions and agentic IDEs —
can inspect and operate the live project. Runs entirely on the Qt event loop:
no threads, every tool body stays on the main thread by construction.
"""

import json
import os
import secrets
import time
from pathlib import Path

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtNetwork import QHostAddress, QTcpServer

from . import __version__, tools

DISCOVERY = Path.home() / ".naksha" / "bridge.json"
PROTOCOL = "2024-11-05"


class BridgeServer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.token = secrets.token_hex(16)
        self.last_seen = 0.0  # epoch of the last authenticated call
        self.client = ""  # name the MCP client gave us at initialize
        self.server = QTcpServer(self)
        if not self.server.listen(QHostAddress.LocalHost, 0):
            raise RuntimeError(f"bridge could not listen: {self.server.errorString()}")
        self.server.newConnection.connect(self._accept)
        DISCOVERY.parent.mkdir(exist_ok=True)
        # pid is here so a client can tell WHICH QGIS it reached. Two instances
        # running at once silently diverge otherwise: the tool list comes from one
        # and the calls land on the other.
        DISCOVERY.write_text(json.dumps(
            {"port": self.port(), "token": self.token, "pid": os.getpid()}))

    def port(self):
        return self.server.serverPort()

    def _owns_discovery(self):
        """True when the discovery file still points at this server. A second QGIS
        instance may have replaced it, and its bridge is still listening."""
        try:
            return json.loads(DISCOVERY.read_text()).get("token") == self.token
        except (OSError, ValueError):
            return False  # unreadable or not ours either way: leave it alone

    def stop(self):
        self.server.close()
        if self._owns_discovery():
            DISCOVERY.unlink(missing_ok=True)

    def _accept(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))

    def _read(self, sock):
        buf = (sock.property("buf") or b"") + bytes(sock.readAll())
        sock.setProperty("buf", buf)
        if b"\r\n\r\n" not in buf:
            return
        head, _, body = buf.partition(b"\r\n\r\n")
        lines = head.decode("latin1").split("\r\n")
        headers = {}
        for line in lines[1:]:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
        if len(body) < int(headers.get("content-length", 0)):
            return  # wait for the rest of the body
        status, payload = self._route(lines[0], headers, body)
        data = json.dumps(payload).encode()
        sock.write(
            b"HTTP/1.1 " + status + b"\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(data)).encode() + b"\r\n"
            b"Connection: close\r\n\r\n" + data
        )
        sock.disconnectFromHost()

    def _route(self, request_line, headers, body):
        if headers.get("x-naksha-token") != self.token:
            return b"403 Forbidden", {"error": "bad or missing X-Naksha-Token"}
        self.last_seen = time.time()
        method, path = request_line.split(" ", 2)[:2]
        if method == "GET" and path == "/tools":
            return b"200 OK", [
                {"name": n, "description": t["description"], "parameters": t["parameters"]}
                for n, t in tools.TOOLS.items()
            ]
        if method == "POST" and path == "/call":
            try:
                req = json.loads(body)
            except ValueError:
                return b"400 Bad Request", {"error": "invalid JSON body"}
            return b"200 OK", {"result": tools.run_tool(req.get("name", ""), req.get("args") or {})}
        if method == "POST" and path == "/mcp":
            try:
                req = json.loads(body)
            except ValueError:
                return b"400 Bad Request", _rpc_error(None, -32700, "parse error")
            return b"200 OK", self.mcp(req)
        return b"404 Not Found", {"error": "unknown endpoint"}

    # --- MCP protocol lives here, once. naksha_mcp.py just forwards to it, and
    # --- clients that speak MCP over HTTP can POST here directly.
    def mcp(self, req):
        """Handle one JSON-RPC message. Returns the response, or None for a notification."""
        rpc_id = req.get("id")
        method = req.get("method", "")
        if rpc_id is None:  # notification: acknowledge nothing
            return None
        if method == "initialize":
            self.client = (req.get("params") or {}).get("clientInfo", {}).get("name", "") or ""
            return _rpc_ok(rpc_id, {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "naksha", "version": __version__},
            })
        if method == "ping":
            return _rpc_ok(rpc_id, {})
        if method == "tools/list":
            return _rpc_ok(rpc_id, {"tools": [
                {"name": n, "description": t["description"], "inputSchema": t["parameters"]}
                for n, t in tools.TOOLS.items()
            ]})
        if method == "tools/call":
            params = req.get("params") or {}
            text = tools.run_tool(params.get("name", ""), params.get("arguments") or {})
            # tool failures come back as content, not an RPC error, so the model can react
            return _rpc_ok(rpc_id, {
                "content": [{"type": "text", "text": text}],
                "isError": text.startswith("error:"),
            })
        return _rpc_error(rpc_id, -32601, f"unknown method '{method}'")


def _rpc_ok(rpc_id, result):
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _rpc_error(rpc_id, code, message):
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
