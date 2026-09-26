# Brag Plan: Naksha — the full tour (60s, voiced)

## What is this app?
Naksha (नक्शा, Hindi for "map") is a free, open-source AI agent that lives in a QGIS dock. You say what you need, and it runs real Processing algorithms, checks its own output, and builds print maps. It works with local Ollama, an API key, or the AI app you already pay for.

## The angle
An Apple-style product film: true dark, liquid glass, big type and a laptop demo, covering every surface of the plugin in one minute. Complex work gets the most screen time. The 0-feature catch is the emotional beat ("0 features ≠ done").

## Tone
- Preset: polished (cinematic energy in the transitions)
- Creative direction: Apple keynote product film with glass, a hero device and word-slam type
- Voice: Kokoro `af_sky` at 1.05x, via `hyperframes tts` (`--voice` requested)

## Format: landscape — 1920x1080 · Duration: 60.0s

## Visual identity
The tokens from `naksha/plugin.py` (accent `#35B8A5`, tile `#10695C`, user `#7FB3E8`, warn `#D08F58`, text `#E6EDEB`) on a near-black `#0C1211` tinted toward the brand. Fonts: Montserrat (display/UI), IBM Plex Mono (machine facts), Tiro Devanagari Hindi (नक्शा only). Glass panels use real backdrop blur over drifting, audio-reactive teal and blue glows and a contour-line field.

## Persistent elements
- The contour field and glows, across the whole film
- A cartographic scale bar at bottom-left acting as a progress bar, with the playhead at film time and the chapter label beside it

## Voiceover script
| # | Start | Line |
|---|---|---|
| 1 | 1.0 | This is Naksha. Hindi, for map. |
| 2 | 5.0 | An AI agent that lives inside QGIS. Just say what you need. |
| 3 | 10.2 | Simple jobs run instantly. Offline. No key, no model, no waiting. |
| 4 | 15.3 | Bigger jobs get a plan. Naksha picks the right tools, runs them, and checks every result. |
| 5 | 20.8 | An empty output isn't success. It's a bug, and Naksha fixes it. |
| 6 | 25.5 | Then it builds the print map. Legend, scale bar, north arrow. |
| 7 | 29.6 | Every Processing algorithm you have, discovered live. |
| 8 | 33.2 | You decide how much it can do. Ask before writing. Autonomous. Or read-only. |
| 9 | 38.5 | Bring your own brain. Local Ollama, free and offline. An API key. Or the subscription you already pay for, connected in one click. |
| 10 | 46.6 | Developers see every request, every token, every millisecond. |
| 11 | 50.7 | No exec. No eval. Just GIS. |
| 12 | 54.3 | Naksha. Free, and open source, for QGIS. |

## Storyboard
1. **Meet (0–4.6):** a glass pane on near-black shows नक्शा → "Naksha" → "Hindi · noun · map". At 3.6s it shatters into 15 seeded 3D fragments (glass-shatter SFX).
2. **Laptop (4.4–10):** a laptop rises with "Lives inside QGIS." above it. The screen shows the QGIS map and the Naksha dock with its greeting, then the camera pushes into the screen.
3. **Instant (10–15):** three instant commands are typed and sent: `colour roads by highway` (roads recolour by category), `zoom to schools` (map zooms), `how many features in schools` ("14 features match"). Glass caption: "Instant. offline · no key · no model".
4. **Verified (15–25.3):** `find flood-exposed schools and map them` → a 4-step plan → search_algorithms → extractbylocation → `WARNING: 0 features` → the caption "0 features ≠ done." → reprojectlayer, with the flood zone snapping onto the river (beat-locked at 24.02s) → "4 of 14 schools are in the flood zone."
5. **Print (25.3–29.4):** the camera pulls back and the print sheet flies out of the screen: title, map, then legend, scale bar and north arrow on the voiceover's cues → `flood_schools.pdf`.
6. **Algorithms (29.4–33):** 715 counts up (disclosed as the developer's count), provider chips (native, gdal, grass, pdal, + your plugins), and a scrolling algorithm list.
7. **Modes (33–38.3):** three glass cards. Ask before writing (the real approval dialog, clicked Yes), Autonomous (a tool chain ticks through), Read-only (the real read-only error).
8. **Any AI (38.3–46.4):** Local Ollama (the real source-picker menu), An API key (provider, key, model; stored encrypted), The app you already pay for (bridge toggle, Claude Desktop / Claude Code / Cursor / Windsurf / VS Code). Connect is clicked and the real "Connected to Claude Desktop…" message appears.
9. **Dev tools (46.4–50.5):** the developer tools window. Raw traffic → Timing (tokens, then time highlighted) → Catalogue.
10. **Safe (50.5–53.3):** word slams "No exec." / "No eval." / "Just GIS.", plus "0 bandit findings · 0 secrets · ruff clean · no subprocesses · no telemetry" (from the README).
11. **Lockup (53.3–60):** N tile, Naksha + नक्शा (beat-locked at 54.02s), tagline, URL, "works with…" line.

Privacy note: map data, layer names, token and time figures in the dev-tools mock, and the dialog arguments are illustrative. No real project, key, host or person appears.

## Audio
`happy-beats-business-moves-vol-1` (120 BPM) as a narration bed at 0.16 through its volume automation, about 11 dB under the voice, fading out over the last 1.6s. SFX are motion-matched: glass shatter, keys, clicks, a drop on the plan, a knock on the warning, a thud on the snap, a bong on "4 of 14", a slide for the sheet, chips on the count, plate hits on the slams, and a low bell on the wordmark. The glows react to the music's bass.
