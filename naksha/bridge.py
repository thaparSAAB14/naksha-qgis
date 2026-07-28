"""Localhost bridge: lets the user's existing AI subscription apps drive QGIS.

A tiny HTTP endpoint on 127.0.0.1 (random port, per-session token) exposing
Naksha's tools. naksha_mcp.py proxies it as an MCP server, so any MCP client —
the ones bundled with Claude, ChatGPT, Gemini subscriptions and agentic IDEs —
can inspect and operate the live project. Runs entirely on the Qt event loop:
no threads, every tool body stays on the main thread by construction.
"""

import json
import secrets
from pathlib import Path

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtNetwork import QHostAddress, QTcpServer

from . import tools

DISCOVERY = Path.home() / ".naksha" / "bridge.json"


class BridgeServer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.token = secrets.token_hex(16)
        self.server = QTcpServer(self)
        if not self.server.listen(QHostAddress.LocalHost, 0):
            raise RuntimeError(f"bridge could not listen: {self.server.errorString()}")
        self.server.newConnection.connect(self._accept)
        DISCOVERY.parent.mkdir(exist_ok=True)
        DISCOVERY.write_text(json.dumps({"port": self.port(), "token": self.token}))

    def port(self):
        return self.server.serverPort()

    def stop(self):
        self.server.close()
        try:
            DISCOVERY.unlink()
        except OSError:
            pass

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
        return b"404 Not Found", {"error": "unknown endpoint"}
