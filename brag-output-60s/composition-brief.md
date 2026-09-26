# Hyperframes Composition Brief: Naksha — the full tour

- Composition: `brag-output-60s/composition/index.html` (single file, one root timeline)
- Render: `brag-output-60s/brag.mp4` · 1920x1080 · 60.0s · 30fps
- Storyboard, voiceover script and audio: see `brag-plan.md`
- Source files: `README.md`, `naksha/plugin.py`, `settings.py`, `connect.py`, `panels.py`, `provider.py`, `agent.py`, `quick.py`, `introspect.py`, `layout.py`, `tools.py`
- Verbatim product copy: the input placeholder, greeting, tool outputs (`styled '…'`, `zoomed to '…'`, `… features match on '…'`, `WARNING: 0 features — verify inputs (CRS mismatch? wrong filter?)`, `exported layout '…' to …`), approval dialog title, read-only error, source-picker menu format, "Connect an AI app to QGIS", the bridge toggle label, "Connected to Claude Desktop. Restart Claude Desktop to pick it up.", developer tools title and tab names, "Build Claude connector (.mcpb)…"
- Voice: `npx hyperframes tts --voice af_sky --speed 1.05`, one WAV per line in `assets/vo/`
- Music: vol-1 preset cues (120 BPM); locks at 16.02 (request sent), 24.02 (flood zone lands), 54.02 (wordmark)
- Techniques: seeded (mulberry32, seed 42) clip-path glass shatter; CSS 3D laptop with a camera push into the screen; backdrop-blur glass; per-character typing; count-up via per-frame text sets; per-frame audio-reactive glow from `extract-audio-data.py`
- Gate: `npx hyperframes check` passes (132/132 WCAG AA)
