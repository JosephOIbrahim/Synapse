"""QThread-based WebSocket bridge to the SYNAPSE server.

Connects to ws://localhost:9999/synapse (configurable via SYNAPSE_PORT
and SYNAPSE_PATH env vars). Sends chat messages with auto-gathered
scene context. Emits Qt signals on response/status change.

IMPORTANT: The ``hou`` module is NOT thread-safe. All ``hou.*`` calls must
happen on the main thread. Marshal them with
``synapse.server.main_thread.run_on_main`` -- NEVER with
``hdefereval.executeInMainThreadWithResult``. The latter is a blocking
primitive with no thread test: called from the main thread it enqueues work
for the main thread and then parks in ``_condition.wait()``, which only the
main thread's own event loop could ever notify. That is a permanent,
unrecoverable self-deadlock, and panel code runs on the Qt main thread most
of the time. ``run_on_main`` detects a main-thread caller and executes
directly instead. WebSocket I/O runs on the QThread.
"""

import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QThread, Signal, Slot, QMetaObject, Qt, Q_ARG
except ImportError:
    from PySide2.QtCore import QThread, Signal, Slot, QMetaObject, Qt, Q_ARG

# Default connection settings
_DEFAULT_PORT = 9999
_DEFAULT_PATH = "/synapse"
_RECONNECT_INTERVAL_MS = 3000


def _get_ws_url():
    """Build the WebSocket URL, preferring the resolved (published) endpoint.

    Self-healing port discovery: the server publishes its real bound port to a
    sidecar after a :9999 failover. We resolve it here so the panel connects to
    the live server, not a stale zombie on :9999. Falls back to
    SYNAPSE_PORT / 9999 when no sidecar exists (exactly the prior behavior).
    """
    path = os.environ.get("SYNAPSE_PATH", _DEFAULT_PATH)
    default_port = int(os.environ.get("SYNAPSE_PORT", str(_DEFAULT_PORT)))
    host = "localhost"
    port = default_port
    try:
        from ..server.bridge_endpoint import resolve_endpoint
        host, port = resolve_endpoint(default_port=default_port)
    except Exception:
        host, port = "localhost", default_port
    return "ws://{host}:{port}{path}".format(host=host, port=port, path=path)


def _empty_context():
    """The neutral context dict.

    Single source for the "we could not read the scene" value, so the
    unreachable-hou path inside the payload and the main-thread-timeout path
    in ``gather_context`` return the same shape.
    """
    return {
        "selected_nodes": [],
        "current_network": "",
        "scene_file": "",
        "frame": 1.0,
    }


def _gather_context_on_main_thread():
    """Gather Houdini scene context. MUST run on the main thread.

    Returns a dict with keys: selected_nodes, current_network,
    scene_file, frame.
    """
    context = _empty_context()
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
    gate_proposal = Signal(dict)     # Gate proposal for artist decision
    session_report = Signal(dict)    # Bridge integrity report

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
        are routed to their dedicated signals. Chat responses (route_chat)
        are unwrapped from the protocol envelope and emitted via
        ``response_received``. Non-chat responses (project_setup, context,
        ping, etc.) are silently dropped to avoid polluting the chat display.
        """
        msg_type = data.get("msg_type", "")

        if msg_type == "hda_progress":
            self.hda_progress.emit(data)
            return
        if msg_type == "hda_result":
            self.hda_result.emit(data)
            return
        if msg_type == "gate_proposal":
            self.gate_proposal.emit(data)
            return
        if msg_type == "session_report":
            self.session_report.emit(data)
            return

        # Unwrap protocol envelope: {data: {...}, success, error, ...}
        inner = data.get("data", data)

        # Surface server errors
        error = data.get("error")
        if error:
            self.response_received.emit({
                "status": "error",
                "message": str(error),
            })
            return

        # Only emit chat responses (route_chat returns "response" + "tier")
        if isinstance(inner, dict) and ("response" in inner or "tier" in inner):
            self.response_received.emit(inner)
            return

        # Non-chat responses (project_setup, context, ping, etc.) are
        # silently dropped -- they are internal bookkeeping, not messages.

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
            "type": "execute_python",
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
            "type": command,
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

        Marshals the read onto Houdini's MAIN THREAD via
        ``synapse.server.main_thread.run_on_main``. Returns the context dict
        and also emits the context_updated signal.

        Previously this called ``hdefereval.executeInMainThreadWithResult``
        directly with no thread test. Because this is panel code -- reachable
        from a Qt slot, i.e. already on the main thread -- that was a live
        permanent self-deadlock: the main thread would enqueue the payload for
        itself and then park forever in hdefereval's ``_condition.wait()``.
        ``run_on_main`` short-circuits a main-thread caller and runs the
        payload directly, so that freeze is structurally impossible now.

        Returns
        -------
        dict
            Scene context with selected_nodes, current_network,
            scene_file, frame. On a main-thread timeout, the neutral
            ``_empty_context()`` value (same shape the payload itself returns
            when ``hou`` is unreachable) and no context_updated emission.
        """
        # Import boundary: verified OK. synapse.panel already imports from
        # synapse.server in this same module (``..server.bridge_endpoint``
        # in _get_ws_url), and synapse.server.main_thread imports only
        # threading/time/logging at module scope -- hdefereval is imported
        # lazily inside the off-main path only. Guarded anyway so a panel
        # running against a trimmed install degrades instead of failing.
        try:
            from ..server.main_thread import run_on_main
        except Exception:
            run_on_main = None

        if run_on_main is None:
            return self._emit_context(_gather_context_on_main_thread())

        try:
            # TIMEOUT CHOICE: 10.0s, explicit.
            #
            # This site was previously UNBOUNDED. It is NOT a long-running
            # operation, so the "generous budget" rule for renders/captures
            # /flipbooks does not apply here: the payload is four cheap scene
            # reads (hou.selectedNodes, hou.ui.paneTabs, hou.hipFile.path,
            # hou.frame). That is exactly the "scene queries, parm reads"
            # class run_on_main sizes its 10s _DEFAULT_TIMEOUT for, so 10.0s
            # is stated explicitly rather than inherited -- if the default
            # ever moves for another reason, this read keeps its own budget.
            # Ten seconds to answer "what is selected" already means the main
            # thread is wedged; waiting longer buys the panel nothing.
            #
            # record_stall is left at its default (True) deliberately. This is
            # a user-triggered foreground read, not a background poll, so it
            # cannot spam the 2-strike stall detector, and a timeout here is
            # honest evidence that the main thread is genuinely unresponsive.
            ctx = run_on_main(_gather_context_on_main_thread, timeout=10.0)
        except ImportError:
            # Off the main thread AND no hdefereval -- i.e. outside Houdini
            # (tests). Preserves the pre-migration ImportError fallback
            # exactly: read directly, since there is no main thread to
            # marshal to and no real hou to be unsafe with.
            ctx = _gather_context_on_main_thread()
        except RuntimeError:
            # run_on_main timed out. Do NOT fall back to a direct call: that
            # would touch hou off the main thread, trading a bounded failure
            # for a thread-safety violation. Return the neutral value and
            # stay quiet on context_updated -- nothing fresh was read.
            logger.warning(
                "gather_context: Houdini's main thread didn't respond within "
                "10s; returning empty scene context."
            )
            return _empty_context()

        return self._emit_context(ctx)

    def _emit_context(self, ctx):
        """Emit context_updated for a freshly-read context and return it."""
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
