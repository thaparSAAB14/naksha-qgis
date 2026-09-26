# Brag Plan: Naksha

## What is this app?
Naksha (नक्शा, Hindi for "map") is a free, open-source AI agent that lives in a QGIS dock: you state a GIS goal in plain language, it runs the real Processing algorithms, then checks its own output and reports real numbers instead of a bare "done".

## The angle
Most AI tools say "Done!" whether or not anything happened. Naksha's whole personality is the opposite: its system prompt literally says *"Report real numbers (feature counts, CRS codes), never a bare 'done'"*, and its tools flag `WARNING: 0 features — verify inputs (CRS mismatch? wrong filter?)`. The video shows that honesty in action: plain language goes in, and verified numbers come out. The centrepiece is a run that goes wrong: the first pass returns 0 features, Naksha catches the CRS mismatch, reprojects, and comes back with "4 of 14 schools".

Register switching carries the concept: human language is set in a sans-serif, and machine facts (tool ids, feature counts, EPSG codes) are set in mono.

## Hook (first 2-3 seconds)
A convincing QGIS workspace (map canvas + the real Naksha dock) is already on screen. The headline *"Ask for any GIS job in plain language."* (the dock's own input placeholder, verbatim) slams in top-left, and the dock input types `buffer schools by 500 m` with soft key ticks. The viewer understands the product before second 3.

## Key moments (the middle)
- **Instant, no AI.** The Send press triggers `native:buffer`, and 500 m rings bloom around 14 school pins in a wave. The dock answers in mono: `native:buffer finished: … 14 features, CRS EPSG:32643`. Headline: *"Some things need no AI at all."* (verbatim walkthrough title).
- **It checks its own output.** An open-ended request, `find flood-exposed schools and map them` (verbatim from the README), goes to the model. The `flood_zones` layer draws in far off-map and misaligned (EPSG:4326). The first extract returns **0 features** and the dock shows a warm-coloured WARNING row instead of a success. Naksha runs `native:reprojectlayer`, the flood zone visibly snaps onto the river, and 4 school pins turn warm.
- **Real numbers.** Final answer bubble: *"4 of 14 schools are in the flood zone."* plus a mono footnote that says what was fixed and why.

## Outro / punchline
The workspace pulls away onto a quiet contour-line field. The teal **N** tile (the plugin's real icon) lands, then the wordmark **Naksha** with **नक्शा** beside it, the line *"Free, open-source AI agent for QGIS."*, and a mono URL line `github.com/thaparSAAB14/naksha-qgis`.

## User flow worth showing
1. **Entry:** the dock is open with its greeting ("Namaste! Tell me what you need and I'll do the GIS work — I check my own results, and nothing is written without your OK.").
2. **Key action:** type a plain-language job and press Send. First an instant offline command (`buffer schools by 500 m`), then an open-ended one (`find flood-exposed schools and map them`).
3. **Result:** the map updates in front of you and the dock reports verified numbers: 14 buffers, then the 0-feature catch, the CRS fix, and "4 of 14 schools".

## Tone
- Preset: polished
- Creative direction: a cartographer's field notebook, calm and exact, where every claim carries a number
- Interpretation: restrained motion and long, readable holds. One continuous workspace instead of hard scene cuts, with the headline band changing like chapter titles. The dry wit comes from the product's own honesty (the 0-feature catch), not from jokes. No hype language.

## Format: landscape — 1920x1080
## Duration: 20.5 seconds

## Visual identity (from the project)
Source: the colour tokens in `naksha/plugin.py` (`NakshaDock.c`, dark theme), `scripts/preview_ui.py`, and `naksha/icon.png`.
- Background: `#1B2523` (dock `field` token, the darkest surface)
- Panel surface: `#2B3634` (preview page), `#233230` (Naksha bubble)
- Accent: `#35B8A5` (dark-theme accent); icon tile `#10695C`
- User accent: `#7FB3E8`; user bubble `#1D2A38`
- Warning: `#D08F58`
- Text: `#E6EDEB`; dim `#8A9997`; muted `#9AA5A3`; border `#3A4A47`
- Display font: Montserrat 900/400. The project ships no web fonts (Qt system UI); Montserrat is a bundled, geometric, map-legend-like choice.
- Mono font: IBM Plex Mono, for tool ids, feature counts and EPSG codes
- Devanagari: Tiro Devanagari Hindi, for the single word नक्शा in the outro, embedded locally
- Strongest visual element: the dock itself. It has rounded bubbles with a 3px teal (Naksha) or blue (you) left edge, uppercase letter-spaced sender labels, an italic "· running …" status chip, and the status pill "● Ollama (local, free) · qwen2.5:7b".

Privacy note: all map data is fictional. Layer names (`schools`, `flood_zones`, `roads`), counts (14, 4) and the CRS pair (EPSG:4326 → EPSG:32643) are illustrative stand-ins. No real project, person, key or host appears. The only URL is the project's public GitHub homepage from `metadata.txt`.

## Share copy (draft)
Naksha is a free, open-source AI agent for QGIS: ask for any GIS job in plain language, and it runs the real Processing tools, checks its own output, and reports numbers, never a bare "done".

## Audio direction
- Role: warm bed with sparse professional accents
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (steady and clean, suits a polished tone)
- Music treatment: starts at 0 at around 0.32 volume, sits under the UI sounds, and fades out over the final ~1.2s after the URL line lands
- Music cue guidance: bundled preset read (`assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json`), tempo 109.96 BPM. Strong cues to target: **13.11s** (the "4 of 14" payoff) and **17.47s** (wordmark lands). Beat-grid windows: 4.39–5.34s for the buffer-ring wave (non-text, so it may hit every beat); 2.73s Send press; 3.82s, 8.19s and 15.84s for the chapter/headline changes.
- Audio-reactive treatment: subtle. Music bass/RMS lets a teal glow behind the map panel breathe, and in the outro it lifts the N tile's glow. No waveform or equalizer visuals.
- SFX posture: sparse, motion-matched, professional restraint
- Audio-coupled moments: typed command (thinned key ticks), Send press (click), buffer-ring wave (soft drop on the first ring only), 0-feature warning (dry soft knock), flood zone snapping into place (soft thud), "4 of 14" payoff (warm bong), wordmark landing (low bell, quiet)
- Restraint rule: no stacked hits, no bright or glassy sounds, nothing louder than the music at the outro, and no key tick on every character

## Storyboard

### Scene 1 — Plain language — 3.82s (0.00–3.82)
The workspace is on screen from frame 0. On the left is a map canvas: dark land, a sinuous river, hairline roads, faint teal contour lines, 14 white school pins, a small QGIS-style layer list (`schools · 14`, `roads`), and a mono status bar `EPSG:32643`. On the right is the Naksha dock: header with the N tile, "Naksha", the status pill and ⚙; the greeting bubble; and the input showing the placeholder "Ask for any GIS job in plain language…". The headline "Ask for any GIS job in plain language." slams in at ~0.3s and holds. From ~1.1s the input types `buffer schools by 500 m`. At 2.73s (beat) Send is pressed and the message becomes a right-indented "YOU" bubble.
Sequential/interaction: yes. Character-by-character typing, then a simulated Send press.
Audio intent: invite the viewer in; quiet and precise.
Audio-coupled idea: soft key ticks on roughly every other character; one click on Send.
Music: vol-12 bed from 0.
Transition mood: clean (headline swaps in place) → Scene 2

### Scene 2 — No AI needed — 4.37s (3.82–8.19)
The headline swaps to "Some things need no AI at all." with a small mono sub-label `instant · offline · no key` (hold ≥2.5s). An italic chip `· running native:buffer…` appears in the dock. Across the map, 500 m buffer rings bloom around the 14 schools in a left-to-right wave (4.39–5.34s). At 6.00s (beat) Naksha's answer lands in mono: `native:buffer finished:` / `OUTPUT: layer 'buffer_output' added — 14 features, CRS EPSG:32643`. The layer list gains `buffer_output · 14`. The answer holds ≥2s.
Sequential/interaction: yes. 14 rings arrive one after another (non-text, so beat-grid spacing is fine) and the layer-list row appears.
Audio intent: effortless, instant.
Audio-coupled idea: one soft drop as the ring wave starts; nothing on each ring.
Transition mood: clean → Scene 3

### Scene 3 — It checks its own output — 7.65s (8.19–15.84)
The headline swaps to "Then it checks its own output." The dock transcript scrolls up (the earlier exchange slides away). A YOU bubble lands: "find flood-exposed schools and map them". The `flood_zones` layer draws in misaligned, as a small dashed polygon far from the river tagged `flood_zones · EPSG:4326`. Chip `· running native:extractbylocation…`. At ~10.37s a warm-coloured row appears: `WARNING: 0 features — verify inputs (CRS mismatch?)`. This is the product refusing to call an empty result a success, so it holds ≥1.2s. Chip `· running native:reprojectlayer…`, and at ~11.46s the flood-zone polygon glides and snaps onto the river, its tag becoming `EPSG:32643`. At **13.11s (strong cue)** the 4 schools inside the zone turn warm with a single ring pulse, the layer list gains `extract_output · 4`, and Naksha's answer lands: **"4 of 14 schools are in the flood zone."** with a mono footnote `first pass: 0 features — CRS mismatch, reprojected and re-ran`. The answer holds ~2.7s.
Sequential/interaction: yes. A tool-status sequence (chip → warning → chip → answer) and a visible map correction.
Audio intent: a small moment of tension (the 0), then quiet satisfaction.
Audio-coupled idea: dry knock on the warning; soft thud as the polygon snaps; warm bong on "4 of 14".
Transition mood: soft, pull-back → Outro

### Scene 4 — Outro — 4.66s (15.84–20.50)
The workspace scales down slightly and fades, leaving a quiet contour-line field on `#1B2523`. The teal N tile scales in (16.38s). At **17.47s (strong cue)** the wordmark "Naksha" lands with "नक्शा" beside it. At 18.02s: "Free, open-source AI agent for QGIS." At 18.56s, a mono line: `github.com/thaparSAAB14/naksha-qgis · GPL-2.0 · QGIS 3.40+`. Everything holds to the end. The last frame is the full lockup, never black.
Sequential/interaction: lockup pieces arrive in order (tile → wordmark → line → URL).
Audio intent: a confident, quiet landing.
Audio-coupled idea: one low bell at the wordmark lock; music fades under the final second.
Music: bed fades out 19.3–20.5s.

**Music mood for this video:** upbeat but restrained (polished)
**Audio summary:** a clean, steady bed with a handful of motion-matched UI sounds (keys, click, drop, knock, thud, bong), resolving to one low bell on the wordmark and a gentle fade.
