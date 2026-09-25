r"""Render the chat transcript offscreen and save a PNG, so the UI can be looked
at without launching QGIS.

Run:  & "C:\Program Files\QGIS 3.40.13\bin\python-qgis-ltr.bat" scripts\preview_ui.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

app = QApplication(sys.argv)

from naksha.plugin import Transcript  # noqa: E402

THEMES = {
    "light": {
        "accent": "#0F6A5C", "user": "#33608C", "muted": "#7A8886",
        "bubble": "#EDF5F3", "border": "#CFDEDB", "warn": "#8F4E24",
        "text": "#1B2A28", "dim": "#6B7A78", "bubble_mine": "#EAF1F8", "field": "#FFFFFF",
    },
    "dark": {
        "accent": "#35B8A5", "user": "#7FB3E8", "muted": "#9AA5A3",
        "bubble": "#233230", "border": "#3A4A47", "warn": "#D08F58",
        "text": "#E6EDEB", "dim": "#8A9997", "bubble_mine": "#1D2A38", "field": "#1B2523",
    },
}

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist")
os.makedirs(out_dir, exist_ok=True)

for name, colors in THEMES.items():
    page = QWidget()
    page.setStyleSheet(f"background: {'#2B3634' if name == 'dark' else '#F7FAF9'};")
    page.resize(420, 520)
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 0, 0, 0)

    t = Transcript(colors)
    lay.addWidget(t)

    t.bubble("Naksha", "Namaste! Tell me what you need and I'll do the GIS work — "
                       "I check my own results, and nothing is written without your OK.")
    t.bubble("You", "colour the roads by highway type", mine=True)
    t.chip("running style_layer…")
    t.bubble("Naksha", "Styled 'Vancouver Roads' by highway: 9 categories over 2,883 "
                       "features, CRS EPSG:3005.")
    t.bubble("You", "now buffer the schools by 500 m", mine=True)
    t.working("sent to Connected app · Claude Code — waiting for it to answer…")

    page.show()
    app.processEvents()
    path = os.path.abspath(os.path.join(out_dir, f"ui_transcript_{name}.png"))
    page.grab().save(path)
    print("wrote", path)
    page.close()

print("preview: ok")
