# Naksha 🗺️

*Naksha* (नक्शा) — Hindi for "map". A **free, open-source AI agent plugin for QGIS**:
a dockable chat pane where you state a goal in plain language and Naksha inspects the
project, runs the work, and reports back with real numbers.

**Status: v0.2.0, experimental.** The agent discovers and runs any Processing algorithm you
have installed — introspected live from the registry, so GRASS, GDAL, PDAL and third-party
plugin algorithms all come for free (715 on the developer's machine; your count depends on
your providers). It **verifies its own outputs** (a 0-feature "success" gets flagged and fixed,
not reported), and runs threaded with native cancel. Three approval modes: *Ask before
writing* (default), *Autonomous*, *Read-only*. Providers: any OpenAI-compatible endpoint
(local [Ollama](https://ollama.com) by default — free, offline), or bring your existing
AI subscription via the MCP bridge below. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Install (development)

Requires QGIS **3.40 LTR** or newer. Link the plugin into your profile
(no elevation needed — junctions are plain-user; adjust paths if your profile differs):

```powershell
New-Item -ItemType Junction -Path "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\naksha" -Target "C:\Users\ps103\Downloads\Naksha\naksha"
```

Then in QGIS: **Plugins → Manage and Install Plugins → Installed → check "Naksha"**
(enable *experimental* plugins in Settings). A toolbar "N" button opens the chat dock.

## Configure

Defaults target local Ollama (`http://localhost:11434/v1`, model `qwen2.5:7b`):

```
ollama pull qwen2.5:7b
```

To change provider/model, in the QGIS Python console:

```python
from qgis.core import QgsSettings, QgsApplication
QgsSettings().setValue("naksha/base_url", "https://api.groq.com/openai/v1")
QgsSettings().setValue("naksha/model", "llama-3.3-70b-versatile")
QgsApplication.authManager().storeAuthSetting("naksha/api_key", "sk-…", True)  # encrypted
```

A settings dialog is planned; the API key lives in QGIS's encrypted auth store, never a
plain file.

## Use the AI subscription you already pay for

No API key needed: if you already pay for an AI assistant (Claude, ChatGPT, Gemini —
or use an agentic IDE), its desktop/CLI app is an **MCP client**, and Naksha ships an MCP
bridge that lets it drive your live QGIS session. Your subscription does the thinking;
QGIS updates in front of you.

1. In QGIS: **Plugins → Naksha → AI Bridge** (one click, remembered).
2. Register the proxy with your AI app (needs [uv](https://docs.astral.sh/uv/); examples):

   ```bash
   claude mcp add naksha -- uv run C:\path\to\Naksha\naksha_mcp.py
   ```

   Claude Desktop / other MCP apps — add to their MCP config:

   ```json
   {"mcpServers": {"naksha": {"command": "uv", "args": ["run", "C:\\path\\to\\Naksha\\naksha_mcp.py"]}}}
   ```

3. Ask your assistant: *"what's in my QGIS project?"* — it discovers every Naksha tool
   (search/describe/run any of the ~1000 Processing algorithms included).

The bridge is localhost-only with a per-session token, off by default, and every call is
logged to the "Naksha" log tab. Note: assistants without an MCP client app (e.g. an
X Premium plan) can't be bridged — use their API with the built-in provider instead.

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
