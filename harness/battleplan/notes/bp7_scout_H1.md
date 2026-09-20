# SCOUT H1: panel-state waiting indicator not cleared after turn 1

**VERDICT: UNKNOWN**

## Mechanism

The hypothesis claims `_waiting_for_response` and the typing indicator persist after turn 1 because the route_chat response doesn't arrive with the required "response" or "tier" keys, causing it to be silently dropped instead of triggering _on_response. The panel sets the waiting state when sending (chat_panel.py:891-892) and only clears it in _on_response (914-915), so if the response is filtered, the spinner hangs. Code analysis shows this path EXISTS and is reachable, but I cannot trace it to a specific failure without runtime evidence.

## Evidence

**T1: Writers of `_waiting_for_response` / typing indicator**

| File:Line | Operation | Condition |
|-----------|-----------|-----------|
| chat_panel.py:141 | `self._waiting_for_response = False` | Initialization in __init__ |
| chat_panel.py:891 | `self._waiting_for_response = True` | In _send_message, after validating and sending |
| chat_panel.py:892 | `self._chat.show_typing_indicator()` | Same location |
| chat_panel.py:903 | `self._waiting_for_response = False` | Error path: socket died before send completed |
| chat_panel.py:904 | `self._chat.hide_typing_indicator()` | Same error path |
| chat_panel.py:914 | `self._waiting_for_response = False` | In _on_response, ONLY normal path that clears it |
| chat_panel.py:915 | `self._chat.hide_typing_indicator()` | Same _on_response call |

**Verbatim snippet from chat_panel.py:889-915:**
```python
self._last_sent_message = text
self._input.clear()
self._chat.append_user_message(text)
self._ensure_project_initialized()
self._waiting_for_response = True
self._chat.show_typing_indicator()
ctx = self._gather_context_if_stale()
sent = self._bridge.send_command(
    "route_chat",
    {"message": text, "context": ctx},
    queue_if_down=False,
)
if sent is False:
    # The socket died between the check and the send.
    self._waiting_for_response = False
    self._chat.hide_typing_indicator()
    ...

@Slot(dict)
def _on_response(self, response):
    """Handle server response from route_chat."""
    self._waiting_for_response = False
    self._chat.hide_typing_indicator()
```

**T2: Reply-matching mechanism in ws_bridge.py**

The panel sends route_chat. The server's handler.handle() wraps the result in SynapseResponse with `data={response, tier, ...}`. The panel receives this and filters it at ws_bridge.py:338-341:

```python
# Only emit chat responses (route_chat returns "response" + "tier")
if isinstance(inner, dict) and ("response" in inner or "tier" in inner):
    self.response_received.emit(inner)
    return

# Non-chat responses (project_setup, context, ping, etc.) are
# silently dropped -- they are internal bookkeeping, not messages.
```

If the response dict lacks both "response" AND "tier", it is silently dropped and response_received is never emitted. This is line 343-344 — a legal silent drop for non-chat messages.

**Connection confirmed** (chat_panel.py:223):
```python
self._bridge.response_received.connect(self._on_response)
```

The signal flows: response_received → _on_response → clears waiting state.

**T3: Proposal/consent card effects on send/receive paths**

Proposal cards are routed to a separate signal (chat_panel.py:227):
```python
self._bridge.gate_proposal.connect(self._gate_widget.handle_ws_proposal)
```

Grep of gate_widget.py shows zero references to `_waiting_for_response` or `hide_typing_indicator`. The gate_proposal signal path does not interact with chat state. **Refuted: proposal cards do not change the send/receive path.**

## Reproduction

**To test H1, Joe should:**

1. Open SYNAPSE panel in Houdini H22
2. Send turn 1 message ("scatter rocks")
3. Observe: message sends, spinner shows, response arrives, spinner clears ✓
4. Send turn 2 message ("add variation")
5. Observe: message sends, spinner shows, but **no response arrives and spinner never clears** ← H1 if this happens
6. Check ws_bridge logs or add breakpoint at ws_bridge.py:339 to see if the response dict contains "response" and "tier"

Observable that distinguishes H1 from H2 (transport): H1 spinner hangs on turn 2 send but the panel can still send turn 3. H2 would show connection error after turn 1.

## Smallest fix shape

If confirmed: add a timeout handler that calls _chat.hide_typing_indicator() and emits a "slow response" message if _waiting_for_response stays True after 10 seconds. This is a workaround, not a root fix. The real fix requires finding why the server's response lacks "response"/"tier" keys on turn 2+ (e.g., different exception path, cached state corruption, or memory owner rebind issue mentioned in handlers.py:1754-1785). The timeout ensures the UI recovers even if the underlying cause persists.

---

**Status:** Requires Houdini GUI to reproduce. Code analysis shows the silent-drop path exists (ws_bridge.py:343-344) and is reachable if the response dict format changes, but I cannot trace to a specific line that causes it without runtime output or exception logs.
