# Hyperframes Composition Brief: Naksha

## Objective
Create a short launch-style brag video for Naksha, the free, open-source AI agent plugin for QGIS.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 20.5 seconds

## Source Material
- Project root: `naksha-qgis/`
- Primary files read: `README.md`, `naksha/metadata.txt`, `naksha/plugin.py` (dock UI + colour tokens), `naksha/panels.py` (walkthrough copy), `naksha/quick.py` (instant commands), `naksha/agent.py` (system prompt), `naksha/introspect.py` (run_algorithm output + 0-feature warning), `naksha/provider.py` (status labels), `scripts/preview_ui.py` (canonical transcript), `naksha/icon.png`
- Product name: Naksha (नक्शा, Hindi for "map")
- Tagline / strongest claim: "Report real numbers (feature counts, CRS codes), never a bare 'done'." / "an empty result gets flagged, not reported as success"
- Key UI or visual moment to recreate: the Naksha dock (header + status pill, transcript bubbles, italic running chip, input + Send) beside a QGIS map canvas that updates as tools run
- Copy that must appear verbatim:
  - Ask for any GIS job in plain language (input placeholder, used as the hook headline)
  - Some things need no AI at all (walkthrough step title)
  - buffer schools by 500 m (walkthrough / README example)
  - find flood-exposed schools and map them (README example)
  - Namaste! Tell me what you need and I'll do the GIS work — I check my own results, and nothing is written without your OK. (dock greeting)
  - WARNING: 0 features — verify inputs (CRS mismatch? …) (tool output format)
  - native:buffer finished: … layer 'buffer_output' added — 14 features, CRS EPSG:32643 (tool output format)
  - Free, open-source AI agent for QGIS

## Creative Direction
- Tone preset: polished
- Creative direction: a cartographer's field notebook, calm and exact, where every claim carries a number
- Interpretation: restrained, confident motion with long readable holds. One continuous workspace (map + dock) with chapter-style headline swaps instead of hard cuts, then a quiet lockup.
- Angle: most AI says "Done!" regardless. Naksha shows its numbers, and when a run returns 0 features it flags the problem, fixes the CRS mismatch, and reports "4 of 14 schools". Human language is set in sans; machine facts are set in mono.
- Hook: a real-looking QGIS workspace, the headline "Ask for any GIS job in plain language.", and the dock typing `buffer schools by 500 m`
- Outro / punchline: N tile → "Naksha" + "नक्शा" → "Free, open-source AI agent for QGIS." → URL line
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign (keep the dock faithful to plugin.py)

## Visual Identity
- Background: `#1B2523`
- Surfaces: `#2B3634`, `#233230`; user bubble `#1D2A38`; border `#3A4A47`
- Text: `#E6EDEB` (dim `#8A9997`, muted `#9AA5A3`)
- Accent: `#35B8A5`; icon tile `#10695C`; user `#7FB3E8`; warning `#D08F58`
- Display font: Montserrat (bundled) 900 headlines / 400 secondary
- Mono font: IBM Plex Mono (bundled) for tool ids, counts, EPSG codes
- Devanagari: Tiro Devanagari Hindi, embedded via local `@font-face`, used only for नक्शा
- Visual references from the project: dock bubbles with a 3px left edge (teal = Naksha, blue = you), uppercase letter-spaced sender label, italic "· running …" chip, rounded 10px fields, the status pill "● Ollama (local, free) · qwen2.5:7b", the teal "N" icon

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Plain language — 3.82s — hook headline; the input types `buffer schools by 500 m`; Send
2. No AI needed — 4.37s — "Some things need no AI at all."; buffer rings bloom around 14 schools; mono result with 14 features / EPSG:32643
3. It checks its own output — 7.65s — flood request; misaligned flood_zones; 0-feature WARNING row; reproject snaps the polygon onto the river; "4 of 14 schools are in the flood zone."
4. Outro — 4.66s — N tile, Naksha + नक्शा, tagline, URL line

## Audio
- Audio role: warm bed with sparse professional accents
- Audio arc: steady bed from frame 0 → small UI sounds on the real actions → warm bong on the payoff → low bell at the wordmark → fade
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: volume ~0.32, fade out over the last ~1.2s
- Music cue guidance: bundled preset `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json` (109.96 BPM). Lock 13.11s (payoff) and 17.47s (wordmark). Beat grid: 2.73 (Send), 3.82 / 8.19 / 15.84 (chapter swaps), 4.39–5.34 (ring wave), 6.00 (buffer result).
- Audio-reactive treatment: subtle. Bass/RMS drives the teal glow behind the map panel and the outro N-tile glow. No waveform visuals.
- Audio-coupled moments:
  - Scene 1 typing — thinned keypress ticks
  - Scene 1 Send — click
  - Scene 2 ring wave — one soft drop at the wave start
  - Scene 3 0-feature warning — dry soft knock
  - Scene 3 flood zone snap — soft thud
  - Scene 3 "4 of 14" — warm bong
  - Outro wordmark — low bell, quiet
- SFX selection guidance: low-HF-risk picks from `sfx-analysis.md` (impactSoft_medium_*, bong_001, click_003, keyboard keypresses at low volume)
- SFX analysis guidance: `skills/brag/assets/sfx/sfx-analysis.md`
- Exact SFX choice: chosen after the animation exists
- Audio files: copied into `brag-output/composition/assets/`

## Hyperframes Instructions
Built with the Hyperframes domain skills (`hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, `hyperframes-cli`), bypassing the generic promo workflow.

Requirements:
- Show real UI and copy from the source project (the dock is recreated from plugin.py).
- Keep all text readable in the final render; `hyperframes check` must pass with 0 errors, including contrast.
- Keep the video at 20.5s.
- Include music and SFX as planned.
- 1–3 strong-cue locks (13.11s, 17.47s); non-text ring wave on the beat grid.
- Subtle audio-reactive glow from pre-extracted audio data.
- All assets are local (GSAP, fonts, audio).
