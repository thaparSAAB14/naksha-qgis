"""Settings: one widget, two homes.

The same NakshaSettings widget is hosted in QGIS's own Options dialog (where QGIS
users look for plugin settings) and in a standalone dialog reachable from the dock,
so nothing is written twice.
"""

from qgis.gui import QgsOptionsPageWidget, QgsOptionsWidgetFactory
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import ICON, connect, provider

MODES = ("Ask before writing", "Autonomous", "Read-only")


class NakshaSettings(QWidget):
    def __init__(self, parent=None, plugin=None):
        super().__init__(parent)
        self.plugin = plugin
        self.bridge = getattr(plugin, "bridge", None)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- which AI ---------------------------------------------------
        ai = QGroupBox("AI")
        form = QFormLayout(ai)
        self.provider_box = QComboBox()
        self.provider_box.addItem("Auto — use whatever is available", "")
        for pid, (label, _, _, _) in provider.PRESETS.items():
            self.provider_box.addItem(label, pid)
        self.provider_box.currentIndexChanged.connect(self._provider_changed)
        form.addRow("Provider", self.provider_box)

        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addRow("Detected", self.status)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("paste an API key (stored encrypted by QGIS)")
        # Typing a key or endpoint re-asks that endpoint what it offers, so the
        # model list always matches the key actually in use.
        self.key_edit.editingFinished.connect(self._endpoint_changed)
        form.addRow("API key", self.key_edit)

        self.model_edit = QComboBox()
        self.model_edit.setEditable(True)
        form.addRow("Model", self.model_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("leave blank to use the provider default")
        self.url_edit.editingFinished.connect(self._endpoint_changed)
        form.addRow("Endpoint", self.url_edit)

        test = QPushButton("Test connection")
        test.clicked.connect(self._test)
        self.test_result = QLabel()
        self.test_result.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(test)
        row.addWidget(self.test_result, 1)
        form.addRow("", self._wrap(row))
        layout.addWidget(ai)

        # --- behaviour --------------------------------------------------
        behave = QGroupBox("Behaviour")
        bform = QFormLayout(behave)
        self.mode_box = QComboBox()
        self.mode_box.addItems(MODES)
        bform.addRow("When Naksha wants to write", self.mode_box)
        self.steps = QSpinBox()
        self.steps.setRange(1, 100)
        bform.addRow("Max steps per request", self.steps)
        self.dev_mode = QCheckBox("Show developer tools")
        bform.addRow("", self.dev_mode)
        layout.addWidget(behave)

        # --- connected apps ---------------------------------------------
        apps = QGroupBox("Connect an AI app to QGIS")
        aform = QVBoxLayout(apps)
        hint = QLabel(
            "Use the AI you already pay for. These apps drive this QGIS session directly; "
            "nothing extra to install."
        )
        hint.setWordWrap(True)
        aform.addWidget(hint)

        self.bridge_toggle = QCheckBox("Allow connected apps to control this QGIS session")
        self.bridge_toggle.toggled.connect(self._toggle_bridge)
        aform.addWidget(self.bridge_toggle)
        self.bridge_status = QLabel()
        self.bridge_status.setWordWrap(True)
        self.bridge_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        aform.addWidget(self.bridge_status)
        # Rows are rebuilt on every refresh rather than built once here: apps get
        # installed while QGIS is running, and a row that only exists at start-up
        # cannot show that.
        self.app_rows = {}
        self.apps_rows_box = QVBoxLayout()
        self.apps_rows_box.setContentsMargins(0, 0, 0, 0)
        aform.addLayout(self.apps_rows_box)
        self.apps_summary = QLabel()
        self.apps_summary.setWordWrap(True)
        aform.addWidget(self.apps_summary)

        rescan = QPushButton("Refresh — scan for AI apps")
        rescan.setToolTip(
            "Look again for AI apps, IDEs and coding agents on this machine, and "
            "re-check which AI this plugin can reach."
        )
        rescan.clicked.connect(self._rescan)
        aform.addWidget(rescan)

        bundle = QPushButton("Build Claude connector (.mcpb)…")
        bundle.clicked.connect(self._build_connector)
        aform.addWidget(bundle)
        layout.addWidget(apps)

        layout.addStretch()
        self.load()

    @staticmethod
    def _wrap(inner):
        holder = QWidget()
        holder.setLayout(inner)
        inner.setContentsMargins(0, 0, 0, 0)
        return holder

    # --- state ----------------------------------------------------------
    def load(self):
        pid = str(provider.setting("provider") or "")
        self.provider_box.setCurrentIndex(max(0, self.provider_box.findData(pid)))
        self.key_edit.setText("")
        self.key_edit.setPlaceholderText(
            "•••• stored — type to replace" if provider.api_key() else "paste an API key"
        )
        self.url_edit.setText(str(provider.setting("base_url") or ""))
        self.mode_box.setCurrentText(str(provider.setting("mode", MODES[0]) or MODES[0]))
        self.steps.setValue(int(provider.setting("max_steps", 25) or 25))
        self.dev_mode.setChecked(str(provider.setting("dev_mode", "false")).lower() == "true")
        self._refresh_status()
        self._refresh_apps()

    def save(self):
        from qgis.core import QgsSettings

        s = QgsSettings()
        s.setValue("naksha/provider", self.provider_box.currentData() or "")
        s.setValue("naksha/base_url", self.url_edit.text().strip())
        s.setValue("naksha/model", self.model_edit.currentText().strip())
        s.setValue("naksha/mode", self.mode_box.currentText())
        s.setValue("naksha/max_steps", self.steps.value())
        s.setValue("naksha/dev_mode", "true" if self.dev_mode.isChecked() else "false")
        if self.key_edit.text().strip():
            provider.set_api_key(self.key_edit.text().strip())
        provider.invalidate()

    def _provider_changed(self):
        pid = self.provider_box.currentData()
        if pid in provider.PRESETS:
            _, url, model, _ = provider.PRESETS[pid]
            self.url_edit.setText(url)
            self.model_edit.setCurrentText(model)
        self._refresh_status()

    def _endpoint_changed(self):
        """Endpoint or key was edited — store both, then re-probe so the model
        list reflects what this key can actually reach."""
        from qgis.core import QgsSettings

        QgsSettings().setValue("naksha/base_url", self.url_edit.text().strip())
        if self.key_edit.text().strip():
            provider.set_api_key(self.key_edit.text().strip())
        provider.invalidate()
        self._refresh_status()

    def _refresh_status(self):
        self.status.setText("checking…")
        self.status.repaint()
        lines = []
        for _, label, ready, detail in provider.detect(self.bridge):
            lines.append(f"{'✓' if ready else '·'} {label} — {detail}")
        self.status.setText("\n".join(lines))

        # The real probe: ask the configured endpoint what it offers. Works for
        # OpenRouter, OpenAI, Groq, Ollama or any custom OpenAI-compatible URL.
        available = provider.models()
        if provider.active_base_url():
            lines.append(
                f"{'✓' if available else '·'} {provider.active_base_url()} — "
                + (f"{len(available)} models" if available
                   else "no model list (check the URL and key)")
            )
            self.status.setText("\n".join(lines))
        current = self.model_edit.currentText()
        self.model_edit.clear()
        if available:
            self.model_edit.addItems(available)
        self.model_edit.setCurrentText(current or provider.active_model())

    def _test(self):
        self.save()
        self.test_result.setText("testing…")
        self.test_result.repaint()
        ok, message = provider.test_connection()
        self.test_result.setText(("✓ " if ok else "✗ ") + message)

    # --- connected apps --------------------------------------------------
    def _toggle_bridge(self, on):
        if self.plugin is None:
            return
        self.plugin.set_bridge(on)
        self.bridge = self.plugin.bridge
        self._refresh_bridge()

    def _refresh_bridge(self):
        bridge = getattr(self.plugin, "bridge", None) if self.plugin else None
        self.bridge_toggle.blockSignals(True)
        self.bridge_toggle.setChecked(bridge is not None)
        self.bridge_toggle.blockSignals(False)
        if bridge is None:
            self.bridge_status.setText(
                "Off — turn this on before connecting an app, or it will have nothing to talk to."
            )
        else:
            self.bridge_status.setText(
                f"On — listening on 127.0.0.1:{bridge.port()} (this machine only).\n"
                f"Apps that take a URL instead: http://127.0.0.1:{bridge.port()}/mcp"
            )

    @staticmethod
    def _empty(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _refresh_apps(self, found=None):
        """Rebuild the app list from a fresh scan of this machine."""
        self._refresh_bridge()
        self._empty(self.apps_rows_box)
        self.app_rows = {}
        here, elsewhere = [], []
        for cid, label, installed, connected in (found or connect.status()):
            if not installed:
                elsewhere.append(label)
                continue
            here.append(label)
            btn = QPushButton("Disconnect" if connected else "Connect")
            btn.clicked.connect(lambda _=False, c=cid: self._toggle_app(c))
            line = QHBoxLayout()
            line.addWidget(QLabel(f"{'✓' if connected else '·'}  {label}"), 1)
            line.addWidget(btn)
            self.apps_rows_box.addWidget(self._wrap(line))
            self.app_rows[cid] = btn
        if here:
            self.apps_summary.setText(
                f"Found {len(here)}: {', '.join(here)}."
                + (f" Not on this machine: {', '.join(elsewhere)}." if elsewhere else "")
            )
        else:
            self.apps_summary.setText(
                "No AI app found yet. Looked for: " + ", ".join(elsewhere)
                + ".\nAny app that speaks MCP can also be pointed at the URL above by hand."
            )

    def _rescan(self):
        """The refresh button: re-detect both halves of 'what can drive QGIS'.

        Apps can be installed after QGIS started, and a provider can come up (or a
        key be pasted) after we last looked — so this also drops the model-list
        cache instead of reporting a stale 'nothing answered'.
        """
        self.apps_summary.setText("scanning…")
        self.apps_summary.repaint()
        found = connect.rescan()
        provider.invalidate()
        self._refresh_apps(found)
        self._refresh_status()

    def _toggle_app(self, client_id):
        connected = dict((c[0], c[3]) for c in connect.status())[client_id]
        try:
            message = connect.disconnect(client_id) if connected else connect.connect(client_id)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Naksha", f"{e}\n\nAdd this by hand instead:\n\n{connect.snippet()}")
            return
        QMessageBox.information(self, "Naksha", message)
        self._refresh_apps()

    def _build_connector(self):
        folder = QFileDialog.getExistingDirectory(self, "Where should the connector go?")
        if not folder:
            return
        try:
            path = connect.build_connector(folder)
        except OSError as e:
            QMessageBox.warning(self, "Naksha", str(e))
            return
        QMessageBox.information(
            self, "Naksha",
            f"Built {path.name}.\n\nDouble-click it, or drag it into Claude Desktop's "
            f"Settings → Extensions, to install Naksha as a connector.",
        )


class NakshaSettingsDialog(QDialog):
    """Standalone home for the same widget, opened from the dock or the plugin menu."""

    def __init__(self, parent=None, plugin=None):
        super().__init__(parent)
        self.setWindowTitle("Naksha settings")
        self.setWindowIcon(QIcon(ICON))
        self.setMinimumWidth(520)
        self.panel = NakshaSettings(self, plugin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.panel)
        layout.addWidget(buttons)

    def _accept(self):
        self.panel.save()
        self.accept()


class _OptionsPage(QgsOptionsPageWidget):
    def __init__(self, parent, plugin):
        super().__init__(parent)
        self.panel = NakshaSettings(self, plugin)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)

    def apply(self):
        self.panel.save()


class NakshaOptionsFactory(QgsOptionsWidgetFactory):
    """Puts Naksha into Settings → Options, alongside every other QGIS setting."""

    def __init__(self, plugin):
        super().__init__()
        self._plugin = plugin
        self.setTitle("Naksha")

    def icon(self):
        return QIcon(ICON)

    def createWidget(self, parent):
        return _OptionsPage(parent, self._plugin)
