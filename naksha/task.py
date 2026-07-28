"""Threading: the agent turn runs in a QgsTask (native progress + cancel);
every QGIS touch marshals back to the main thread through MainThreadBridge."""

from qgis.core import QgsTask
from qgis.PyQt.QtCore import QMutex, QObject, QThread, QWaitCondition, pyqtSignal

from . import agent


class MainThreadBridge(QObject):
    """call(fn) from any thread; fn executes on the thread this object lives on
    (create it on the main thread). Exceptions propagate to the caller."""

    _request = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._done = False
        self._result = None
        self._request.connect(self._run)  # queued when emitted from another thread

    def _run(self, fn):
        self._mutex.lock()
        try:
            self._result = fn()
        except Exception as e:
            self._result = e
        self._done = True
        self._wait.wakeAll()
        self._mutex.unlock()

    def call(self, fn):
        if QThread.currentThread() is self.thread():
            return fn()
        self._mutex.lock()
        self._done = False
        self._request.emit(fn)
        while not self._done:
            self._wait.wait(self._mutex)
        result = self._result
        self._mutex.unlock()
        if isinstance(result, Exception):
            raise result
        return result


class AgentTask(QgsTask):
    tool_started = pyqtSignal(str)
    turn_finished = pyqtSignal(str)

    def __init__(self, history, gate, bridge):
        super().__init__("Naksha is working…", QgsTask.CanCancel)
        self._history = history
        self._gate = gate
        self._bridge = bridge
        self._reply = ""

    def run(self):
        try:
            self._reply = agent.run_turn(
                self._history,
                on_event=lambda kind, text: self.tool_started.emit(text),
                main=self._bridge.call,
                cancelled=self.isCanceled,
                gate=self._gate,
            )
        except Exception as e:
            self._reply = f"Error: {e}"
        return True

    def finished(self, ok):  # main thread
        self.turn_finished.emit(self._reply)
