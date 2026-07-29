# Naksha 🗺️

*Naksha* (नक्शा) — Hindi for "map". A **free, open-source AI agent plugin for QGIS**:
a dockable chat pane where you state a goal in plain language and Naksha inspects the
project, runs the work, and reports back with real numbers.

**Status: v0.3.0, experimental.** The agent discovers and runs any Processing algorithm you
have installed — introspected live from the registry, so GRASS, GDAL, PDAL and third-party
plugin algorithms all come for free (715 on the developer's machine; your count depends on
your providers). It **verifies its own outputs** (a 0-feature "success" gets flagged and fixed,
not reported), and runs threaded with native cancel. Three approval modes: *Ask before
writing* (default), *Autonomous*, *Read-only*. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Install

**Have a release ZIP?** In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.

**Working from this repo?** Close QGIS and double-click **`install.bat`**. It copies the
plugin into your QGIS profile and enables it. (It refuses to run while QGIS is open,
because QGIS rewrites its settings on exit and would undo the change.)

Requires QGIS **3.40 LTR** or newer. Start QGIS and look for the teal **N** in the toolbar.
A first-run walkthrough explains the rest.

## Works with no setup at all

Plenty of commands never touch an AI — they run instantly, offline, with no account,
no key and nothing installed:

> *colour roads by highway* · *buffer schools by 500 m* · *zoom to contours* ·
> *how many features in parcels* · *what's in my project* · *save project*

Only open-ended requests ("find flood-exposed schools and map them") need a model.

## Pick an AI — three ways, all free

Everything lives in **⚙ Settings** (also under *Settings → Options → Naksha*). Naksha
detects what's available and shows it in the dock header; you never configure twice.

| | What it costs | Setup |
|---|---|---|
| **The app you already pay for** | Nothing extra | *Connect an AI app*, one click |
| **Local Ollama** | Free, fully offline | Install [Ollama](https://ollama.com), pull a model |
| **An API key** | Provider's rates | Paste it into Settings (stored encrypted) |

### Use the subscription you already have

If you pay for Claude, ChatGPT or similar, its desktop app speaks **MCP** — so it can drive
this QGIS session directly. Your subscription does the thinking; the map updates in front
of you.

1. **⚙ Settings → Connect an AI app to QGIS**
2. Click **Connect** next to Claude Desktop, Claude Code, Cursor, Windsurf or VS Code
3. Restart that app and ask it *"what's in my QGIS project?"*

There is nothing to install: the MCP server is a single standard-library file run by the
Python already inside QGIS — no `uv`, no `pip`, no virtualenv. For Claude Desktop you can
instead press **Build Claude connector (.mcpb)** and double-click the result.

The bridge is localhost-only with a per-session token, off by default, and every call is
logged to the "Naksha" tab. Apps with no MCP client (an X Premium plan, most browser
extensions) can't be connected this way — use an API key instead.

## For developers

**⚙ Settings → Show developer tools** adds *Plugins → Naksha → Developer tools*: the exact
JSON sent and received each turn, per-turn timing/tokens/tool counts, a browser over the
introspected algorithm catalogue, and bridge diagnostics.

Walkthrough screenshots are optional — drop PNGs named `01-dock.png`, `02-instant.png`,
`03-settings.png`, `04-connect.png` into `naksha/help/` and the first-run guide picks them
up; without them it renders as text.

## Security

Naksha **does not run AI-written code**. There is no `exec`, no `eval`, and no
"run this Python" tool — the agent can only call a fixed set of QGIS operations and the
Processing algorithms you already have. No subprocesses, no shell, no pickle, no bundled
binaries, no third-party dependencies, no telemetry. Writes are gated by your approval mode
and logged. Verified with the same tools plugins.qgis.org uses: **0 bandit findings,
0 secrets, ruff clean** (see [docs/RELEASE.md](docs/RELEASE.md) to reproduce).

## Design rules

1. **No pip dependencies** — stdlib + `qgis` + `qgis.PyQt` only. Users can't install
   packages into QGIS's Python, and the plugin repository rejects it.
2. **PyQGIS is main-thread-only** — only network I/O may leave the main thread.

## Test (headless, no AI key needed)

```powershell
& "C:\Program Files\QGIS 3.40.13\bin\python-qgis-ltr.bat" tests\test_smoke.py
```

## License

GPL-2.0-or-later — required for QGIS plugins. See [LICENSE](LICENSE).
