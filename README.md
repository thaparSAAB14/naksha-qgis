# Naksha 🗺️

*Naksha* (नक्शा) — Hindi for "map". A **free, open-source AI agent plugin for QGIS**:
a dockable chat pane where you state a goal in plain language and Naksha inspects the
project, runs the work, and reports back with real numbers.

**Status: early development (v0.1.0, walking skeleton).** One tool (`project_state`),
one provider family (any OpenAI-compatible endpoint, local [Ollama](https://ollama.com)
by default — free, offline, nothing leaves your machine).

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
