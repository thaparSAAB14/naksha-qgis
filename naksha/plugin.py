"""Plugin shell: toolbar action + dockable chat pane."""

import html
import os

from qgis.core import Qgis, QgsMessageLog, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QDockWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import agent, bridge


def log(text, level=Qgis.Info):
    QgsMessageLog.logMessage(text, "Naksha", level)


class NakshaPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.bridge_action = None
        self.bridge = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icon, "Naksha", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self._toggle)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Naksha", self.action)

        self.bridge_action = QAction("AI Bridge (use your AI subscription apps)", self.iface.mainWindow())
        self.bridge_action.setCheckable(True)
        self.bridge_action.triggered.connect(self._toggle_bridge)
        self.iface.addPluginToMenu("&Naksha", self.bridge_action)
        if QgsSettings().value("naksha/bridge_enabled", False, type=bool):
            self.bridge_action.setChecked(True)
            self._toggle_bridge(True)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&Naksha", self.action)
        self.iface.removePluginMenu("&Naksha", self.bridge_action)
        if self.bridge is not None:
            self.bridge.stop()
            self.bridge = None
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock = None
        self.action = None

    def _toggle_bridge(self, on):
        QgsSettings().setValue("naksha/bridge_enabled", bool(on))
        if on and self.bridge is None:
            try:
                self.bridge = bridge.BridgeServer()
            except RuntimeError as e:
                log(str(e), Qgis.Critical)
                self.bridge_action.setChecked(False)
                return
            log(f"AI bridge listening on 127.0.0.1:{self.bridge.port()}")
            self.iface.messageBar().pushInfo(
                "Naksha", "AI bridge on — subscription apps can connect via naksha_mcp.py"
            )
        elif not on and self.bridge is not None:
            self.bridge.stop()
            self.bridge = None
            log("AI bridge stopped")

    def _toggle(self, checked):
        if self.dock is None:
            self.dock = NakshaDock()
            self.dock.visibilityChanged.connect(self.action.setChecked)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.setVisible(checked)


class NakshaDock(QDockWidget):
    def __init__(self):
        super().__init__("Naksha")
        self.setObjectName("NakshaDock")
        self.history = []

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask about your project…")
        self.input.returnPressed.connect(self.send)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(send_btn)
        col = QVBoxLayout()
        col.addWidget(self.transcript)
        col.addLayout(row)
        body = QWidget()
        body.setLayout(col)
        self.setWidget(body)

    def _append(self, html_text):
        self.transcript.append(html_text)

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._append(f"<b>You:</b> {html.escape(text)}")
        self.history.append({"role": "user", "content": text})
        log(f"user: {text}")
        # ponytail: synchronous turn on the main thread (QgsBlockingNetworkRequest
        # keeps the UI painting); move to QgsTask with cancel when the full agent lands (M3)
        self.setEnabled(False)
        try:
            reply = agent.run_turn(self.history, self._on_event)
        except Exception as e:
            reply = f"Error: {e}"
            log(str(e), Qgis.Warning)
        finally:
            self.setEnabled(True)
        self._append(f"<b>Naksha:</b> {html.escape(reply)}")
        log(f"naksha: {reply}")
        self.input.setFocus()

    def _on_event(self, kind, text):
        if kind == "tool":
            self._append(f"<i>· running {html.escape(text)}…</i>")
            log(f"tool: {text}")
