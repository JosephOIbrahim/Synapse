"""QThread-based WebSocket bridge to the SYNAPSE server.

Connects to ws://localhost:9999/synapse (configurable via SYNAPSE_PORT
and SYNAPSE_PATH env vars). Sends chat messages with auto-gathered
scene context. Emits Qt signals on response/status change.

IMPORTANT: The ``hou`` module is NOT thread-safe. All ``hou.*`` calls
must happen on the main thread via ``hdefereval.executeInMainThreadWithResult()``.
WebSocket I/O runs on the QThread.
"""

import json
import os
import threading

try:
    from PySide6.QtCore import QThread, Signal, Slot, QMetaObject, Qt, Q_ARG
except ImportError:
    from PySide2.QtCore import QThread, Signal, Slot, QMetaObject, Qt, Q_ARG

# Default connection settings
_DEFAULT_PORT = 9999
_DEFAULT_PATH = "/synapse"
_RECONNECT_INTERVAL_MS = 3000


def _get_ws_url():
    """Build the WebSocket URL from environment or defaults."""
    port = os.environ.get("SYNAPSE_PORT", str(_DEFAULT_PORT))
    path = os.environ.get("SYNAPSE_PATH", _DEFAULT_PATH)
    return "ws://localhost:{port}{path}".format(port=port, path=path)


def _gather_context_on_main_thread():
    """Gather Houdini scene context. MUST run on the main thread.

    Returns a dict with keys: selected_nodes, current_network,
    scene_file, frame.
    """
    context = {
        "selected_nodes": [],
        "current_network": "",
        "scene_file": "",
        "frame": 1.0,
    }
    try:
        import hou

        # Selected nodes
        sel = hou.selectedNodes()
        context["selected_nodes"] = [n.path() for n in sel] if sel else []

        # Current network editor path
        editors = [
            p
            for p in hou.ui.paneTabs()
            if p.type() == hou.paneTabType.NetworkEditor
        ]
        if editors:
            context["current_network"] = editors[0].pwd().path()

        # Scene file
        context["scene_file"] = hou.hipFile.path()

        # Current frame
        context["frame"] = hou.frame()
    except Exception:
        pass

    return context


# HDA Progress stages (sent during hda_package execution)
HDA_STAGES = [
    "parsing_prompt",       # Understanding the request
    "selecting_recipe",     # Choosing HDA template
    "creating_subnet",      # Building the subnet container
    "building_nodes",       # Creating internal node network
    "wiring_connections",   # Connecting internal nodes
    "promoting_parameters", # Building the HDA interface
    "validating",           # Cook test + connection check
    "complete",             # Success
    "failed",               # Error occurred
]


class SynapseWSBridge(QThread):
    """QThread-based WebSocket client to the SYNAPSE server.

    Signals
    -------
    response_received : dict
        Emitted when a server response arrives (chat messages).
    status_changed : bool
        Emitted when connection status changes (True = connected).
    context_updated : dict
        Emitted when scene context is refreshed (for UI updates).
    hda_progress : dict
        Emitted when an HDA build progress update arrives.
    hda_result : dict
        Emitted when an HDA build completes (success or failure).
    """

    response_received = Signal(dict)
    status_changed = Signal(bool)
    context_updated = Signal(dict)
    hda_progress = Signal(dict)
    hda_result = Signal(dict)
    connection_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws = None
        self._running = False
        self._send_queue = []
        self._queue_lock = threading.Lock()

    @property
    def connected(self):
        """Whether the WebSocket is currently connected."""
        return self._ws is not None

    def run(self):
        """Thread main loop -- maintain WebSocket with auto-reconnect."""
        self._running = True
        attempts = 0

        while self._running:
            try:
                self._connect_and_listen()
                attempts = 0  # Reset on successful connection
            except Exception as exc:
                attempts += 1
                err_msg = str(exc) if str(exc) else type(exc).__name__
                if attempts <= 3:
                    self.connection_error.emit(
                        "Couldn't connect ({n}/3): {e}".format(
                            n=attempts, e=err_msg,
                        )
                    )

            self.status_changed.emit(False)

            if not self._running:
                break

            # Back off: 2s first retry, 3s second, 5s thereafter
            delay = 2000 if attempts <= 1 else (3000 if attempts <= 2 else 5000)
            self.msleep(delay)

    def _connect_and_listen(self):
        """Establish connection and process messages until disconnect."""
        url = _get_ws_url()

        try:
            from websockets.sync.client import connect

            with connect(
                url,
                open_timeout=3.0,
                close_timeout=2.0,
            ) as ws:
                self._ws = ws
                self.status_changed.emit(True)

                # Drain any queued messages
                self._drain_queue()

                # Listen for responses
                while self._running:
                    try:
                        raw = ws.recv(timeout=0.5)
                    except TimeoutError:
                        # Check for queued outgoing messages
                        self._drain_queue()
                        continue

                    try:
                        data = json.loads(raw)
                        self._dispatch_message(data)
                    except (json.JSONDecodeError, ValueError):
                        self.response_received.emit(
                            {"status": "error", "message": str(raw)}
                        )

        except ImportError:
            # websockets not installed -- try QWebSocket if available
            self._connect_qt_websocket(url)
        except Exception as exc:
            err = str(exc) if str(exc) else type(exc).__name__
            self.connection_error.emit(err)
        finally:
            self._ws = None

    def _connect_qt_websocket(self, url):
        """Fallback: try Qt's QWebSocket (available in some PySide6 builds)."""
        # Not all PySide6 builds ship QtWebSockets; this is a best-effort
        # fallback. If unavailable, the bridge simply stays disconnected.
        try:
            from PySide6.QtWebSockets import QWebSocket
        except ImportError:
            try:
                from PySide2.QtWebSockets import QWebSocket
            except ImportError:
                return

        # QWebSocket requires an event loop; for simplicity we emit
        # disconnected and let the reconnect loop retry.
        self.status_changed.emit(False)

    def _dispatch_message(self, data):
        """Route incoming WebSocket message to the appropriate signal.

        Messages with ``msg_type`` of ``hda_progress`` or ``hda_result``
        are routed to their dedicated signals. Everything else (including
        messages with no ``msg_type``) goes to ``response_received`` for
        backward compatibility.
        """
        msg_type = data.get("msg_type", "chat")

        if msg_type == "hda_progress":
            self.hda_progress.emit(data)
        elif msg_type == "hda_result":
            self.hda_result.emit(data)
        else:
            # Default: treat as chat message (backward compatible)
            self.response_received.emit(data)

    def _drain_queue(self):
        """Send all queued messages over the active WebSocket."""
        with self._queue_lock:
            pending = list(self._send_queue)
            self._send_queue.clear()

        for msg_json in pending:
            try:
                if self._ws is not None:
                    self._ws.send(msg_json)
            except Exception:
                pass

    def send_chat(self, message, context=None):
        """Send a chat message to SYNAPSE. Thread-safe.

        Parameters
        ----------
        message : str
            The user's message text.
        context : dict, optional
            Scene context to include. If None, context will be gathered
            automatically (requires main-thread callback).
        """
        payload = {
            "command": "execute_python",
            "payload": {
                "content": message,
            },
        }

        if context:
            payload["context"] = context

        msg_json = json.dumps(payload, sort_keys=True)

        if self._ws is not None:
            try:
                self._ws.send(msg_json)
                return
            except Exception:
                pass

        # Queue for later if not connected
        with self._queue_lock:
            self._send_queue.append(msg_json)

    def send_command(self, command, payload=None):
        """Send a raw SYNAPSE command. Thread-safe.

        Parameters
        ----------
        command : str
            The SYNAPSE command name (e.g., ``inspect_scene``).
        payload : dict, optional
            Command payload.
        """
        msg = {
            "command": command,
            "payload": payload or {},
        }
        msg_json = json.dumps(msg, sort_keys=True)

        if self._ws is not None:
            try:
                self._ws.send(msg_json)
                return
            except Exception:
                pass

        with self._queue_lock:
            self._send_queue.append(msg_json)

    def gather_context(self):
        """Auto-gather current Houdini state for context.

        Runs on the MAIN THREAD via hdefereval. Returns the context dict
        and also emits context_updated signal.

        Returns
        -------
        dict
            Scene context with selected_nodes, current_network,
            scene_file, frame.
        """
        try:
            import hdefereval

            ctx = hdefereval.executeInMainThreadWithResult(
                _gather_context_on_main_thread
            )
        except ImportError:
            # Outside Houdini (e.g., testing) -- return empty context
            ctx = _gather_context_on_main_thread()

        if ctx:
            self.context_updated.emit(ctx)
        return ctx

    def send(self, payload):
        """Send an arbitrary JSON payload over the WebSocket. Thread-safe.

        Parameters
        ----------
        payload : dict
            The message to send. Serialized to JSON with sorted keys.
        """
        msg_json = json.dumps(payload, sort_keys=True)

        if self._ws is not None:
            try:
                self._ws.send(msg_json)
                return
            except Exception:
                pass

        with self._queue_lock:
            self._send_queue.append(msg_json)

    def stop(self):
        """Signal the thread to stop and close the WebSocket."""
        self._running = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        self.wait(5000)
