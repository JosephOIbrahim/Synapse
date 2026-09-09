"""Panel-owned Ollama names. Discovery never authorizes or runs a model."""
from concurrent.futures import ThreadPoolExecutor
from functools import partial

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

from . import connections as cn


def current_endpoint():
    from .providers.ollama_provider import _ollama_endpoint
    scheme, host, path = _ollama_endpoint()
    endpoint = "%s://%s%s/v1/chat/completions" % (scheme, host, path)
    cn.validate_endpoint(endpoint)
    return endpoint


def _shutdown(executor, *_):
    # Destruction holds only the executor, never a deleted QObject.
    executor.shutdown(wait=False, cancel_futures=True)


class OllamaDiscovery(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.closed = False
        self._endpoint = None
        self._names = None
        self._error = False
        self._revision = 0
        self._future = None
        self._request = None
        self._refresh_queued = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synapse-model-list")
        self.destroyed.connect(partial(_shutdown, self._executor))
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)

    def _current(self):
        try:
            return current_endpoint()
        except ValueError:
            return None

    @property
    def loading(self):
        return self._future is not None

    def names(self):
        return self._names if self._endpoint == self._current() else None

    def message(self):
        if self.loading:
            return "Loading Ollama models…"
        if self._error:
            return "Model list unavailable · check connection" if self.names() is None else "Last model list · service unavailable"
        if self.names() == ():
            return "No models listed by Ollama"
        return "" if self.names() is not None else "Refresh to discover Ollama models"

    def refresh(self):
        if self.closed:
            return
        endpoint = self._current()
        if endpoint != self._endpoint:
            self._endpoint, self._names = endpoint, None
            self._revision += 1
        self._error = endpoint is None
        if endpoint is None:
            self.changed.emit()
            return
        if self._future is None:
            self._refresh_queued = False
            self._request = (endpoint, self._revision)
            # Only immutable endpoint text crosses into the worker. No Qt/HOM.
            self._future = self._executor.submit(cn.list_ollama_models, endpoint)
            self._timer.start()
        elif self._request != (endpoint, self._revision):
            self._refresh_queued = True
        self.changed.emit()

    def remember(self, endpoint, names):
        """Share a completed setup list, independently of its selected-model facts."""
        if self.closed or endpoint != self._current():
            return
        self._endpoint, self._names = endpoint, tuple(names)
        self._error = False
        self._revision += 1  # older in-flight enumeration cannot replace this check
        self._refresh_queued = False
        self.changed.emit()

    def _poll(self):
        if self.closed or self._future is None or not self._future.done():
            return
        future, request = self._future, self._request
        self._future = None
        self._timer.stop()
        if self._refresh_queued:
            # Preserve the newest explicit request, including an A -> B -> A switch.
            self.refresh()
            return
        if request != (self._current(), self._revision):
            self.changed.emit()
            return
        try:
            self._names = future.result()
            self._error = False
        except Exception:
            # Retain the last list for this endpoint; never display response bodies.
            self._error = True
        self.changed.emit()

    def close(self):
        self.closed = True
        self._timer.stop()
        if self._future is not None:
            self._future.cancel()
        self._future = None
        _shutdown(self._executor)


class MenuRefresh(QtCore.QObject):
    """A real Qt receiver: deleting a menu disconnects its pending updates."""
    def __init__(self, menu, discovery, callback):
        super().__init__(menu)
        self._discovery = discovery
        self._callback = callback
        self._connection = discovery.changed.connect(self._refresh)

    @QtCore.Slot()
    def _refresh(self):
        self._callback()

    def close(self):
        if self._connection is not None:
            # The connection handle remains safe after Qt deletes sender/receiver.
            QtCore.QObject.disconnect(self._connection)
            self._connection = None
