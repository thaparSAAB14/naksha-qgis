"""One-click connection of desktop AI apps to this QGIS session.

Writes our MCP server entry into another application's config file. That is a real
side effect on someone else's file, so every write is: user-initiated, backed up to
`.bak`, merged (never clobbering other servers), and written atomically. Disconnect
removes only our own key.
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path

KEY = "naksha"
SERVER = Path(__file__).with_name("mcp_server.py")


def _config_paths():
    """Per-client config location for this OS. Missing parents mean 'not installed'."""
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        claude_desktop = appdata / "Claude" / "claude_desktop_config.json"
        vscode = appdata / "Code" / "User" / "mcp.json"
        vscode_insiders = appdata / "Code - Insiders" / "User" / "mcp.json"
    elif system == "Darwin":
        support = home / "Library" / "Application Support"
        claude_desktop = support / "Claude" / "claude_desktop_config.json"
        vscode = support / "Code" / "User" / "mcp.json"
        vscode_insiders = support / "Code - Insiders" / "User" / "mcp.json"
    else:
        claude_desktop = home / ".config" / "Claude" / "claude_desktop_config.json"
        vscode = home / ".config" / "Code" / "User" / "mcp.json"
        vscode_insiders = home / ".config" / "Code - Insiders" / "User" / "mcp.json"
    return {
        # id: (label, path, key holding the server map)
        "claude-desktop": ("Claude Desktop", claude_desktop, "mcpServers"),
        "claude-code": ("Claude Code", home / ".claude.json", "mcpServers"),
        "cursor": ("Cursor", home / ".cursor" / "mcp.json", "mcpServers"),
        "windsurf": ("Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json", "mcpServers"),
        "vscode": ("VS Code", vscode, "servers"),
        "vscode-insiders": ("VS Code Insiders", vscode_insiders, "servers"),
    }


CLIENTS = _config_paths()


def python_exe():
    """The interpreter that ships inside QGIS - guaranteed present, and mcp_server.py
    is stdlib-only so it needs nothing else. .resolve() expands Windows 8.3 short
    paths, which would otherwise look broken in the user's config file."""
    exe = Path(sys.prefix) / ("python.exe" if platform.system() == "Windows" else "bin/python3")
    try:
        return str(exe.resolve())
    except OSError:
        return str(exe)


def entry():
    """The MCP server definition we install into a client's config."""
    return {"command": python_exe(), "args": [str(SERVER.resolve())]}


def snippet():
    """Copy-pasteable JSON for clients we do not automate."""
    return json.dumps({"mcpServers": {KEY: entry()}}, indent=2)


def _read(path):
    """Parsed config, or {} if absent. Raises ValueError on malformed JSON so callers
    refuse to overwrite a file they did not understand."""
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"{path.name} is not valid JSON ({e}); left untouched") from None
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not a JSON object; left untouched")
    return data


def _write(path, data):
    """Back up, then replace atomically so a crash mid-write cannot truncate the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def status():
    """[(id, label, installed, connected)] for every known client.

    Reads the filesystem on every call, so it is also the rescan: an app installed
    after QGIS started shows up the next time this is asked.
    """
    out = []
    for cid, (label, path, key) in CLIENTS.items():
        installed = path.exists() or path.parent.exists()
        connected = False
        if path.exists():
            try:
                connected = KEY in (_read(path).get(key) or {})
            except ValueError:
                connected = False
        out.append((cid, label, installed, connected))
    return out


def rescan():
    """Re-derive the client table, then report status.

    CLIENTS is built at import time from $APPDATA/$HOME, and the UI built its rows
    from whatever existed then — so a coding agent installed mid-session stayed
    invisible until QGIS restarted. Re-deriving here costs nothing and makes the
    refresh button honest about both halves: where we look, and what is there now.
    """
    global CLIENTS
    CLIENTS = _config_paths()
    return status()


def connect(client_id):
    label, path, key = CLIENTS[client_id]
    data = _read(path)
    servers = data.get(key)
    if not isinstance(servers, dict):
        servers = {}
    servers[KEY] = entry()
    data[key] = servers
    _write(path, data)
    return f"Connected to {label}. Restart {label} to pick it up."


def disconnect(client_id):
    label, path, key = CLIENTS[client_id]
    data = _read(path)
    servers = data.get(key)
    if not isinstance(servers, dict) or KEY not in servers:
        return f"{label} was not connected."
    del servers[KEY]  # only ours - every other server stays exactly as it was
    _write(path, data)
    return f"Disconnected from {label}."


def build_connector(dest_dir):
    """Write a double-click installable Claude connector (.mcpb) and return its path.

    Built here rather than shipped prebuilt because the manifest has to name a real
    interpreter on *this* machine - and QGIS's own Python is the one we can count on.
    Bundle layout and manifest fields follow the MCPB spec (manifest_version 0.3).
    """
    import zipfile

    from . import __version__

    manifest = {
        "manifest_version": "0.3",
        "name": "naksha",
        "display_name": "Naksha for QGIS",
        "version": __version__,
        "description": "Inspect and operate your live QGIS project - layers, geoprocessing, "
                       "styling and map layouts - from Claude.",
        "author": {"name": "Naksha contributors"},
        "server": {
            "type": "python",
            "entry_point": "server/mcp_server.py",
            "mcp_config": {
                "command": python_exe(),
                "args": ["${__dirname}/server/mcp_server.py"],
                "env": {},
            },
        },
    }
    dest = Path(dest_dir) / "naksha-connector.mcpb"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.write(SERVER, "server/mcp_server.py")
        icon = Path(__file__).with_name("icon.png")
        if icon.exists():
            z.write(icon, "icon.png")
    return dest
