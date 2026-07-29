"""Two extra surfaces: the first-run walkthrough, and the developer panel."""

import json
import os

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import ICON, __version__, agent, connect

HELP_DIR = os.path.join(os.path.dirname(__file__), "help")


def _shot(name):
    """<img> for a bundled screenshot, or nothing if it hasn't been captured yet."""
    path = os.path.join(HELP_DIR, name)
    if not os.path.exists(path):
        return ""
    return f'<p><img src="file:///{path.replace(os.sep, "/")}" width="420"></p>'


STEPS = [
    ("Naksha lives in this panel",
     "Ask for GIS work in plain language. Naksha reads your project, picks the right "
     "Processing algorithms out of the hundreds you already have installed, runs them, "
     "then <b>checks its own output</b> — an empty result gets flagged, not reported as "
     "success.", "01-dock.png"),
    ("Some things need no AI at all",
     "Try <i>“colour roads by highway”</i> or <i>“buffer schools by 500 m”</i>. Commands "
     "like these run <b>instantly and offline</b>, with nothing installed and no API key. "
     "Only open-ended requests go to a model.", "02-instant.png"),
    ("Point it at an AI, or don't",
     "Open <b>Settings</b> to paste an API key, or install Ollama to run a model locally "
     "and free. Naksha detects whatever is available and shows it in the header — you "
     "never have to configure anything twice.", "03-settings.png"),
    ("Already pay for Claude or ChatGPT?",
     "Under <b>Connect an AI app</b>, one click registers this QGIS session with the "
     "desktop app you already use. Your subscription does the thinking; the map updates "
     "in front of you. Nothing extra to install.", "04-connect.png"),
]


class Welcome(QWidget):
    """Shown in the dock on first run instead of the chat."""

    def __init__(self, on_done, on_settings, parent=None):
        super().__init__(parent)
        self._on_done = on_done
        self._on_settings = on_settings
        self.index = 0

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.back = QPushButton("Back")
        self.back.clicked.connect(lambda: self.go(-1))
        self.next = QPushButton("Next")
        self.next.clicked.connect(lambda: self.go(1))
        settings = QPushButton("Open settings")
        settings.clicked.connect(self._on_settings)
        skip = QPushButton("Skip")
        skip.clicked.connect(self.finish)

        row = QHBoxLayout()
        row.addWidget(skip)
        row.addWidget(settings)
        row.addStretch()
        row.addWidget(self.back)
        row.addWidget(self.next)
        col = QVBoxLayout(self)
        col.addWidget(self.view)
        col.addLayout(row)
        self.render()

    def render(self):
        title, body, shot = STEPS[self.index]
        self.view.setHtml(
            f"<h3 style='margin-bottom:4px'>{title}</h3>"
            f"<p style='color:#777;font-size:11px;margin-top:0'>"
            f"Step {self.index + 1} of {len(STEPS)}</p>"
            f"<p>{body}</p>{_shot(shot)}"
        )
        self.back.setEnabled(self.index > 0)
        self.next.setText("Start using Naksha" if self.index == len(STEPS) - 1 else "Next")

    def go(self, delta):
        if self.index + delta >= len(STEPS):
            return self.finish()
        self.index = max(0, self.index + delta)
        self.render()

    def finish(self):
        QgsSettings().setValue("naksha/seen_welcome", "true")
        self._on_done()


class DevTools(QDialog):
    """Everything a developer wants and a normal user should never see."""

    def __init__(self, bridge_getter, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Naksha developer tools — v{__version__}")
        self.setWindowIcon(QIcon(ICON))
        self.resize(760, 560)
        self._bridge_getter = bridge_getter

        self.tabs = QTabWidget()
        self.raw = QTextBrowser()
        self.timing = QTextBrowser()
        self.diagnostics = QTextBrowser()
        self.catalogue = QTreeWidget()
        self.catalogue.setHeaderLabels(["Algorithm", "Parameters"])
        self.tabs.addTab(self.raw, "Raw traffic")
        self.tabs.addTab(self.timing, "Timing")
        self.tabs.addTab(self.catalogue, "Catalogue")
        self.tabs.addTab(self.diagnostics, "Diagnostics")

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(refresh)
        col = QVBoxLayout(self)
        col.addWidget(self.tabs)
        col.addLayout(row)
        self.reload()

    def reload(self):
        turns = list(agent.HISTORY)
        self.raw.setHtml(
            "<p>Nothing yet — send a message first.</p>" if not turns else
            "".join(
                f"<h4>{i + 1}. {t.get('asked', '')[:80]}</h4>"
                f"<pre style='white-space:pre-wrap'>{json.dumps(t.get('raw') or t.get('answer'), indent=2)[:4000]}</pre>"
                for i, t in enumerate(reversed(turns))
            )
        )
        rows = "".join(
            f"<tr><td>{t.get('path')}</td><td>{t.get('seconds', '?')}s</td>"
            f"<td>{len(t.get('calls') or [])}</td><td>{', '.join(t.get('calls') or []) or '—'}</td>"
            f"<td>{(t.get('usage') or {}).get('total_tokens', '—')}</td></tr>"
            for t in reversed(turns)
        )
        self.timing.setHtml(
            "<table cellpadding=6><tr><th>Path</th><th>Time</th><th>Calls</th>"
            f"<th>Tools</th><th>Tokens</th></tr>{rows}</table>"
            if turns else "<p>Nothing yet.</p>"
        )

        self.catalogue.clear()
        try:
            from qgis.core import QgsApplication

            from .introspect import _params

            for alg in sorted(QgsApplication.processingRegistry().algorithms(), key=lambda a: a.id()):
                node = QTreeWidgetItem([alg.id(), alg.displayName()])
                for p in _params(alg):
                    node.addChild(QTreeWidgetItem([f"  {p.name()}", p.type()]))
                self.catalogue.addTopLevelItem(node)
        except Exception as e:  # a broken provider must not take the panel down
            self.catalogue.addTopLevelItem(QTreeWidgetItem([f"unavailable: {e}", ""]))

        bridge = self._bridge_getter()
        lines = [f"<b>Version</b> {__version__}",
                 f"<b>Server command</b><br><code>{connect.python_exe()}</code>",
                 f"<b>Server script</b><br><code>{connect.SERVER}</code>"]
        if bridge is None:
            lines.append("<b>AI Bridge</b> off")
        else:
            lines.append(f"<b>AI Bridge</b> listening on 127.0.0.1:{bridge.port()}<br>"
                         f"MCP endpoint <code>http://127.0.0.1:{bridge.port()}/mcp</code><br>"
                         f"last client: {bridge.client or '—'}")
        lines.append("<b>Connected apps</b> " + (", ".join(
            label for _, label, _, on in connect.status() if on) or "none"))
        self.diagnostics.setHtml("<p>" + "</p><p>".join(lines) + "</p>")
