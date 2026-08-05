"""Plugin shell: toolbar action, menus, and the dockable chat pane."""

import html
import json

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPalette
from qgis.PyQt.QtWidgets import (
    QAction,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import ICON, bridge, connect, panels, provider, settings, tools
from .task import AgentTask, MainThreadBridge


def log(text, level=Qgis.Info):
    QgsMessageLog.logMessage(text, "Naksha", level)


class NakshaPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.bridge = None
        self.options = None
        self._menu_actions = []

    # --- lifecycle -------------------------------------------------------
    def initGui(self):
        self.action = QAction(QIcon(ICON), "Naksha", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self._toggle)
        self.iface.addToolBarIcon(self.action)
        self._add_menu(self.action)

        self._add_menu(self._make_action("Settings…", self.open_settings))
        self._add_menu(self._make_action("Getting started", self.show_welcome))
        self._add_menu(self._make_action("Developer tools", self.open_devtools))

        self.options = settings.NakshaOptionsFactory(self)
        self.iface.registerOptionsWidgetFactory(self.options)

        if QgsSettings().value("naksha/bridge_enabled", False, type=bool):
            self.set_bridge(True)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        for act in self._menu_actions:
            self.iface.removePluginMenu("&Naksha", act)
        self._menu_actions = []
        if self.options is not None:
            self.iface.unregisterOptionsWidgetFactory(self.options)
            self.options = None
        # remember=False: shutting QGIS down must not rewrite the user's preference.
        # It used to, so the bridge came back off after every restart and every
        # plugin reload, which read as "the bridge keeps dying on its own".
        self.set_bridge(False, remember=False)
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock = None
        self.action = None

    def _make_action(self, text, slot):
        act = QAction(text, self.iface.mainWindow())
        act.triggered.connect(slot)
        return act

    def _add_menu(self, act):
        self.iface.addPluginToMenu("&Naksha", act)
        self._menu_actions.append(act)

    # --- surfaces --------------------------------------------------------
    def _toggle(self, checked):
        if self.dock is None:
            self.dock = NakshaDock(self)
            self.dock.visibilityChanged.connect(self.action.setChecked)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.setVisible(checked)

    def open_settings(self):
        dialog = settings.NakshaSettingsDialog(self.iface.mainWindow(), self)
        if dialog.exec_() and self.dock is not None:
            self.dock.refresh_status()

    def show_welcome(self):
        QgsSettings().setValue("naksha/seen_welcome", "")
        self.action.setChecked(True)
        self._toggle(True)
        self.dock.show_welcome()

    def open_devtools(self):
        panels.DevTools(lambda: self.bridge, self.iface.mainWindow()).show()

    # --- the localhost bridge -------------------------------------------
    def set_bridge(self, on, remember=True):
        if remember:
            QgsSettings().setValue("naksha/bridge_enabled", bool(on))
        if on and self.bridge is None:
            try:
                self.bridge = bridge.BridgeServer()
            except RuntimeError as e:
                log(str(e), Qgis.Critical)
                return False
            log(f"AI bridge listening on 127.0.0.1:{self.bridge.port()}")
        elif not on and self.bridge is not None:
            self.bridge.stop()
            self.bridge = None
            log("AI bridge stopped")
        return True


class NakshaDock(QDockWidget):
    MODES = settings.MODES

    def __init__(self, plugin):
        super().__init__("Naksha")
        self.setObjectName("NakshaDock")
        self.plugin = plugin
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
            "warn": "#D08F58" if dark else "#8F4E24",
        }

        self.status = QToolButton()
        self.status.setPopupMode(QToolButton.InstantPopup)
        self.status.setToolTip("Which AI is answering. Click to change.")
        self.status.setAutoRaise(True)
        gear = QToolButton()
        gear.setText("⚙")
        gear.setAutoRaise(True)
        gear.setToolTip("Naksha settings")
        gear.clicked.connect(self.plugin.open_settings)

        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QIcon(ICON).pixmap(18, 18))
        head.addWidget(icon)
        head.addWidget(QLabel("<b>Naksha</b>"))
        head.addStretch()
        head.addWidget(self.status)
        head.addWidget(gear)

        self.transcript = QTextBrowser()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask for any GIS job in plain language…")
        self.input.returnPressed.connect(self.send)
        self.btn = QPushButton("Send")
        self.btn.clicked.connect(self.send)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.btn)
        self.chat = QWidget()
        chat_col = QVBoxLayout(self.chat)
        chat_col.setContentsMargins(0, 0, 0, 0)
        chat_col.addWidget(self.transcript)
        chat_col.addLayout(row)

        self.body = QWidget()
        col = QVBoxLayout(self.body)
        col.addLayout(head)
        col.addWidget(self.chat)
        self.body.setStyleSheet(
            f"""
            QLineEdit {{ border: 1px solid {self.c['border']}; border-radius: 9px; padding: 7px 10px; }}
            QLineEdit:focus {{ border-color: {self.c['accent']}; }}
            QPushButton {{ background: {self.c['accent']}; color: white; border: none;
                           border-radius: 9px; padding: 7px 18px; font-weight: 600; }}
            QPushButton:hover {{ background: {self.c['user']}; }}
            QTextBrowser {{ border: 1px solid {self.c['border']}; border-radius: 9px; padding: 4px; }}
            QToolButton {{ border-radius: 7px; padding: 3px 8px; }}
            """
        )
        self.setWidget(self.body)
        self.welcome = None
        self.refresh_status()

        if str(QgsSettings().value("naksha/seen_welcome", "")).lower() != "true":
            self.show_welcome()
        else:
            self._greet()

    # --- header ----------------------------------------------------------
    def refresh_status(self):
        source_id, label, ready, detail = provider.resolve(self.plugin.bridge)
        dot = self.c["accent"] if ready else self.c["warn"]
        model = provider.active_model()
        self.status.setText(f"● {label}" + (f" · {model}" if ready and model else ""))
        self.status.setStyleSheet(f"color: {dot};")
        self.status.setToolTip(f"{label} — {detail}\nClick to change.")
        menu = QMenu(self.status)
        for sid, slabel, sready, sdetail in provider.detect(self.plugin.bridge):
            act = menu.addAction(f"{'✓' if sready else '·'}  {slabel} — {sdetail}")
            act.setEnabled(sready and sid != "bridge")
            act.triggered.connect(lambda _=False, s=sid: self._pick(s))
        menu.addSeparator()
        menu.addAction("Settings…").triggered.connect(self.plugin.open_settings)
        self.status.setMenu(menu)

    def _pick(self, source_id):
        QgsSettings().setValue("naksha/provider", source_id)
        provider.invalidate()
        self.refresh_status()

    # --- welcome ---------------------------------------------------------
    def show_welcome(self):
        if self.welcome is None:
            self.welcome = panels.Welcome(self._welcome_done, self.plugin.open_settings, self)
            self.body.layout().addWidget(self.welcome)
        self.chat.hide()
        self.welcome.show()

    def _welcome_done(self):
        self.welcome.hide()
        self.chat.show()
        self.refresh_status()
        if not self.history:
            self._greet()

    def _greet(self):
        ready = provider.resolve(self.plugin.bridge)[2]
        extra = ("" if ready else
                 "<br><br>No AI is configured yet — but commands like "
                 "<i>“colour roads by highway”</i> or <i>“what's in my project”</i> already "
                 "work, instantly and offline. Click ⚙ to add an AI for everything else.")
        self._bubble("Naksha", self.c["accent"],
                     "Namaste! Tell me what you need and I'll do the GIS work — I check my "
                     "own results, and nothing is written without your OK.", extra_html=extra)

    # --- rendering -------------------------------------------------------
    def _bubble(self, sender, color, text, extra_html=""):
        body = html.escape(text).replace("\n", "<br>")
        self.transcript.append(
            f'<table width="100%" cellpadding="7" style="margin-bottom:6px;">'
            f'<tr><td bgcolor="{self.c["bubble"]}">'
            f'<span style="color:{color}; font-weight:600;">{sender}</span><br>{body}{extra_html}'
            f"</td></tr></table>"
        )
        self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())

    def _chip(self, text):
        self.transcript.append(
            f'<p style="color:{self.c["muted"]}; font-style:italic; margin:2px 10px;">· {html.escape(text)}</p>'
        )

    # --- the turn --------------------------------------------------------
    def send(self):
        if self.task is not None:
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

        mode = str(provider.setting("mode", self.MODES[0]) or self.MODES[0])
        self.task = AgentTask(self.history, self._make_gate(mode), self.marshal)
        self.task.tool_started.connect(self._on_tool)
        self.task.turn_finished.connect(self._finished)
        self.input.setEnabled(False)
        self.btn.setText("Stop")
        QgsApplication.taskManager().addTask(self.task)

    def _on_tool(self, name):
        self._chip(f"running {name}…")
        log(f"tool: {name}")

    def _finished(self, reply):
        self.task = None
        self.btn.setText("Send")
        self.input.setEnabled(True)
        self.input.setFocus()
        self._bubble("Naksha", self.c["accent"], reply)
        log(f"naksha: {reply}")
        self.refresh_status()

    # --- approval gate (called from the worker thread) -------------------
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
