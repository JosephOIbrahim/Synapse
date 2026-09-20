# BP7-TRANSPORT Scout H2 — Socket Closes but `connected` Stays True

**VERDICT: CONFIRMED**

## Mechanism

The WebSocket bridge in `ws_bridge.py` disconnects after the first turn, but the `connected` property never reflects the disconnection. When the socket closes (server-side or exception), the `with` context manager exits and the WebSocket is closed, **but `self._ws` is never set to `None`**. The `connected` property returns `self._ws is not None`, so it remains `True` even on a dead socket. Later sends attempt to write to a closed socket and fail silently, with no BRIDGE_DOWN_LINE shown to the artist because the send_guard check passed.

## Evidence

**T1 — `connected` state machine (ws_bridge.py:210–254)**

```python
@property
def connected(self):
    """Whether the WebSocket is currently connected."""
    return self._ws is not None

def _connect_and_listen(self):
    """Establish connection and process messages until disconnect."""
    ...
    with connect(
        url,
        open_timeout=3.0,
        close_timeout=2.0,
    ) as ws:
        self._ws = ws
        self.status_changed.emit(True)
        ...
        # Listen loop exits here on timeout, exception, or server close
    # <-- BUG: self._ws is NEVER set to None when with block exits
```

The `connected` property checks `self._ws is not None` at line 212, but there is no line that sets `self._ws = None` after the socket closes. When the `with` context manager exits (line 253), the WebSocket is closed but `self._ws` still holds the closed object reference.

**T2 — Server-side close (no explicit timeout in handler, but 30s slow-op timeout on the transport layer per harness/CLAUDE.md Identity)**

Route_chat handler at `handlers.py:1739–1805` calls `self._router.route(message, context=context)` with no explicit timeout or close condition. The transport layer timeout (30s) could trigger if the router blocks, closing the socket server-side. But the client's `connected` property does not detect this closure.

**T3 — BRIDGE_DOWN_LINE visibility (send_guard.py:100–124, chat_panel.py:872–884)**

```python
decision = decide_send(
    text,
    bridge_present=self._bridge is not None,
    bridge_connected=bool(self._bridge is not None and self._bridge.connected),
)
...
self._chat.append_system_message(decision.status_line)
```

At `send_guard.py:120–123`:
```python
if not bridge_connected:
    return SendDecision(
        ACTION_REFUSE_BRIDGE_DOWN, keep_text=True, status_line=BRIDGE_DOWN_LINE
    )
```

BRIDGE_DOWN_LINE ("Not connected to SYNAPSE -- that message wasn't sent...") is correctly appended to the chat widget as a system message at `chat_panel.py:884`. **But it is never shown because the guard check passes**: `bridge_connected` evaluates to `True` even on a dead socket, so `decide_send()` returns ACTION_SEND and the message is sent (or silently dropped if the socket is actually dead) without showing the user any feedback.

## Reproduction

1. Open the Houdini panel with SYNAPSE running.
2. Send a chat message (turn 1) — it works, you see a response.
3. Wait 2–3 seconds (or trigger a server-side close via a timeout).
4. Send a second message (turn 2) — **the message disappears silently**. No "Not connected" message, no spinner, no error. The input box clears but nothing happens.
5. Check the bridge state: `print(self._bridge.connected)` would still be `True` even though the socket is dead.

Observable that distinguishes H2: the message is rejected with **no visible feedback** (no system message, no error indicator) because the guard check passes. H1 would show a spinner. H3/H4 would block all turns. H5/H6 would show a server error or timeout.

## Smallest Fix Shape

After the `with` context manager exits in `_connect_and_listen()`, explicitly set `self._ws = None` to signal the disconnection to the `connected` property. This forces the send_guard check to fail and show BRIDGE_DOWN_LINE to the artist. The fix is a single assignment at module scope (no exception handling changes, no transport-layer changes), so the reconnect loop and auto-retry remain intact. Verification: confirm `self._ws` is None after the socket closes, and that a subsequent send_guard check correctly shows BRIDGE_DOWN_LINE.
