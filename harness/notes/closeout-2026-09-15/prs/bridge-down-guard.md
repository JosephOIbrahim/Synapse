## What and why

**FR-1** (`harness/notes/closeout-2026-09-15/artist_findings.json`, lens `firstrun`; `PLAN.md:598` and `:707` "fix the send guard regardless"). A message typed while the bridge was down was accepted, spun on, queued with no visible signal, and replayed into whatever scene was open when the bridge came back.

Root cause, confirmed by reading the code: `chat_panel._send_message` guarded on `self._bridge is not None` (object existence), not the socket. The only "Not connected" branch was reachable when no bridge object existed at all. With the object alive and the socket down, `ws_bridge.send_command` fell through to `self._send_queue.append(...)` with no return value, and `_drain_queue` replayed it on the next connect. `_on_quick_action` (`chat_panel.py:~997`) had the identical shape for the same `route_chat` command.

`AUDIT.md` (`harness/notes/first-principles-2026-09-15/`) has no row for FR-1 (`grep -n -i "FR-1|bridge-down|bridge down"` hits only `PLAN.md`).

## The fix (smallest honest one; no thread, no gate, no timer)

- **New `python/synapse/panel/send_guard.py`** (pure Python, no Qt, no `hou`): `decide_send(text, bridge_present, bridge_connected) -> SendDecision`. Bridge down + text -> `refuse_bridge_down`, `keep_text=True`, a status line. It never returns `send` while down.
- **`chat_panel._send_message`**: decides on the socket first. Bridge down -> status line in the chat stream, text stays in the input box, no user bubble, no typing indicator, `send_command` never called. The send is the no-replay flavour (`queue_if_down=False`); if the socket dies between the check and the send, the spinner stops, the text is put back in the box, and a line says so.
- **`chat_panel._on_quick_action`**: same guard, decided *before* the selection check (so a down bridge is not misreported as "select a node"). Pill wording, since there is no box to hand text back to.
- **`ws_bridge.send_command(..., queue_if_down=True)`**: default behaviour unchanged (queue + replay on reconnect; the `test_hda_panel.py` pins are deliberate and stay green). Now returns `True` when sent over the live socket now, `False` otherwise; with `queue_if_down=False` an unsendable message is dropped, never queued.

## What the artist sees

| | Before | Now |
|---|---|---|
| Type "make a box", bridge down, press Send | Box clears, "make a box" bubble appears, three dots spin forever, nothing else. Twenty minutes later the box appears in whatever scene is open. | Box keeps "make a box". No bubble, no dots. One line in the stream: **"Not connected to SYNAPSE -- that message wasn't sent. It's still in the box: press Connect, then Send again."** Nothing is queued; nothing ever replays. |
| Same, but the socket dies mid-send | Silently queued, replayed later. | Dots stop, text is handed back to the box, line: "The connection dropped as that message went out -- it wasn't sent and won't be replayed. It's back in the box: press Connect, then Send again." |
| Quick-action pill, bridge down | "[Explain] ..." bubble appears, silently queued, replayed later. | No bubble. Line: "Not connected to SYNAPSE -- that action wasn't sent. Press Connect, then the pill again." |
| No bridge object at all (standalone) | Box cleared, bubble appended, then "Not connected to SYNAPSE server." | Box kept, no bubble, "Not connected to SYNAPSE server -- that message wasn't sent. It's still in the box." |

## Ruling needed

**refuse-and-keep-text or hold-with-visible-release -- which UX?** Built: **refuse-and-keep-text** (Send again is the release; zero held state). Named, not built: **hold-with-visible-release** ("held until the bridge is back -- Send again to release"), which needs held-message state and a release path; the swap point is `send_guard.py` (see its docstring).

## Evidence

- Baseline before any change: `python -m pytest tests/test_chat_panel.py tests/test_hda_panel.py -q` -> `110 passed, 18 skipped`.
- Final, on the committed tree (working tree == HEAD, `git status` clean): `python -m pytest tests/test_send_guard.py tests/test_chat_panel.py tests/test_hda_panel.py -q` -> `137 passed, 18 skipped` (+17 in `test_send_guard.py`, +4 bridge pins in `test_hda_panel.py`, +6 panel-level pins in `test_chat_panel.py`).
- Other stock-pytest files touching `send_command`/`ws_bridge`: `tests/test_context_poll_offmain.py tests/test_panel_faces.py tests/test_passthrough_hygiene.py tests/test_w2_s5_context_offmain.py tests/test_port_wave_scene1.py` -> `58 passed, 41 skipped`.
- Pre-change search for pins: `git grep -n "drain\|replay\|_send_queue" tests/` -> two deliberate bridge-level pins in `test_hda_panel.py` (`:484`, `:781`); both kept, both green. No test pinned the panel-side guard.
- `git log master..HEAD --oneline` -> `81a36a51 fix(panel): refuse chat sends while the bridge is down (FR-1)`; `git diff --stat master..HEAD` -> 6 files, +495/-24.

## NOT checked / not done (on purpose)

- **Not run in Houdini.** No hython, no live PySide `QTextEdit`: the hand-back cursor move (`QtGui.QTextCursor.End`) and the real `ChatDisplay` rendering of the status lines were exercised only through MagicMocks. The `tests/panel/*` PySide-gated files skip under stock CPython (skip exits 0, proves nothing).
- **Full suite not run** (by law; eleven agents share the rotating log). CI not run.
- **Typing-indicator wall-clock ceiling** and **disconnect-while-waiting spinner clear** from the finding's scaffold: not built (would need a timer / a status-slot change). Follow-ups.
- **Other bridge callers still queue and replay by design**: `send()`, `send_chat()`, the HDA panel. `send_chat()` has no caller under `python/synapse/panel/` (not grepped repo-wide).
- **`synapse_panel.py`** (the sibling, worker-based panel; `_send` at `:3085`) was not audited -- it does not use `send_command` for chat, so this defect shape was not observed there, but that is a glance, not a claim.
- The reconnect-and-ask ("You typed 3 messages while disconnected. Send them now?") option from the scaffold is superseded by refusing at send time; nothing is queued, so there is nothing to ask about.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## CTO ruling (pre-approved 2026-09-15; overrule by comment)

**Accept refuse-and-keep-text.** It has no hidden state: nothing is queued, nothing replays later, the artist's words stay in the composer and the surface says why. Hold-with-visible-release reintroduces a queue the artist has to remember exists — the exact failure class FR-1 named — so it stays unbuilt unless a real session shows artists losing text to the refusal.
