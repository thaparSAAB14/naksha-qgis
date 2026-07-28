"""Plugin shell: toolbar action + dockable chat pane (threaded, approval-gated)."""

import html
import json
import os

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPalette
from qgis.PyQt.QtWidgets import (
    QAction,
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import bridge, tools
from .task import AgentTask, MainThreadBridge

ICON = os.path.join(os.path.dirname(__file__), "icon.png")


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
        self.action = QAction(QIcon(ICON), "Naksha", self.iface.mainWindow())
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

    def _toggle(self, checked):
        if self.dock is None:
            self.dock = NakshaDock()
            self.dock.visibilityChanged.connect(self.action.setChecked)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.setVisible(checked)

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


class NakshaDock(QDockWidget):
    MODES = ("Ask before writing", "Autonomous", "Read-only")

    def __init__(self):
        super().__init__("Naksha")
        self.setObjectName("NakshaDock")
        self.history = []
        self.task = None
        self.marshal = MainThreadBridge(self)  # created on the main thread

        dark = self.palette().color(QPalette.Base).lightness() < 128
        self.c = {
            "accent": "#35B8A5" if dark else "#0F6A5C",
            "user": "#7FB3E8" if dark else "#33608C",
            "muted": "#9AA5A3" if dark else "#7A8886",
            "bubble": "#233230" if dark else "#EDF5F3",
            "border": "#3A4A47" if dark else "#CFDEDB",
        }

        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QIcon(ICON).pixmap(20, 20))
        title = QLabel("<b>Naksha</b>")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(self.MODES)
        self.mode_combo.setToolTip("Read-only tools always run; this governs anything that writes")
        self.mode_combo.setCurrentText(QgsSettings().value("naksha/mode", self.MODES[0]))
        self.mode_combo.currentTextChanged.connect(lambda m: QgsSettings().setValue("naksha/mode", m))
        head.addWidget(icon)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.mode_combo)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask for any GIS job in plain language…")
        self.input.returnPressed.connect(self.send)
        self.btn = QPushButton("Send")
        self.btn.clicked.connect(self.send)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.btn)
        col = QVBoxLayout()
        col.addLayout(head)
        col.addWidget(self.transcript)
        col.addLayout(row)
        body = QWidget()
        body.setLayout(col)
        body.setStyleSheet(
            f"""
            QLineEdit {{ border: 1px solid {self.c['border']}; border-radius: 9px; padding: 7px 10px; }}
            QLineEdit:focus {{ border-color: {self.c['accent']}; }}
            QPushButton {{ background: {self.c['accent']}; color: white; border: none;
                           border-radius: 9px; padding: 7px 18px; font-weight: 600; }}
            QPushButton:hover {{ background: {self.c['user']}; }}
            QComboBox {{ border: 1px solid {self.c['border']}; border-radius: 7px; padding: 3px 8px; }}
            QTextBrowser {{ border: 1px solid {self.c['border']}; border-radius: 9px; padding: 4px; }}
            """
        )
        self.setWidget(body)
        self._bubble(
            "Naksha",
            self.c["accent"],
            "Namaste! Tell me what you need — I can inspect the project and run any of the "
            "~1000 Processing algorithms, and I check my own outputs. Nothing is written "
            "without your OK unless you switch to Autonomous.",
        )

    # ---- rendering -------------------------------------------------------
    def _bubble(self, sender, color, text, italic=False):
        style = "font-style:italic;" if italic else ""
        body = html.escape(text).replace("\n", "<br>")
        self.transcript.append(
            f'<table width="100%" cellpadding="7" style="margin-bottom:6px;">'
            f'<tr><td bgcolor="{self.c["bubble"]}" style="{style}">'
            f'<span style="color:{color}; font-weight:600;">{sender}</span><br>{body}'
            f"</td></tr></table>"
        )
        self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())

    def _chip(self, text):
        self.transcript.append(
            f'<p style="color:{self.c["muted"]}; font-style:italic; margin:2px 10px;">· {html.escape(text)}</p>'
        )

    # ---- the turn --------------------------------------------------------
    def send(self):
        if self.task is not None:  # running -> the button is "Stop"
            self.task.cancel()
            self._chip("stopping…")
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._bubble("You", self.c["user"], text)
        self.history.append({"role": "user", "content": text})
        log(f"user: {text}")

        self.task = AgentTask(self.history, self._make_gate(self.mode_combo.currentText()), self.marshal)
        self.task.tool_started.connect(lambda name: (self._chip(f"running {name}…"), log(f"tool: {name}")))
        self.task.turn_finished.connect(self._finished)
        self.input.setEnabled(False)
        self.btn.setText("Stop")
        QgsApplication.taskManager().addTask(self.task)

    def _finished(self, reply):
        self.task = None
        self.btn.setText("Send")
        self.input.setEnabled(True)
        self.input.setFocus()
        self._bubble("Naksha", self.c["accent"], reply)
        log(f"naksha: {reply}")

    # ---- approval gate (called from the worker thread) -------------------
    def _make_gate(self, mode):
        if mode == "Autonomous":
            return None

        def gate(name, args):
            if name in tools.READ_ONLY:
                return None
            if mode == "Read-only":
                return "error: read-only mode is on — the user must switch modes to allow writes"
            approved = self.marshal.call(lambda: self._confirm(name, args))
            return None if approved else "error: the user declined this action"

        return gate

    def _confirm(self, name, args):
        pretty = json.dumps(args, indent=2, default=str)
        if len(pretty) > 600:
            pretty = pretty[:600] + "…"
        answer = QMessageBox.question(
            self, "Naksha wants to run a tool", f"{name}\n\n{pretty}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        return answer == QMessageBox.Yes
