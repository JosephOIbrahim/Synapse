"""Send-time guard for the chat panel (FR-1: sends while the bridge is down).

Pure Python, no Qt, no ``hou``: the decision the panel makes *before* it
hands a message to the WebSocket bridge, factored out so stock pytest can
pin it (``tests/test_send_guard.py``).

Why this exists
---------------
``SynapseWSBridge.send_command`` queues any message it cannot send and
replays the whole queue on the next successful connect
(``ws_bridge.py::_drain_queue``). That is the right default for the HDA
panel and other fire-and-forget callers, and ``tests/test_hda_panel.py``
pins it. It is the wrong default for chat: a message typed while the
bridge was down was accepted, spun on, queued with no visible signal, and
replayed into whatever scene was open when the bridge came back
(``harness/notes/closeout-2026-09-15/artist_findings.json``, lens
"firstrun", id FR-1).

The rule this module enforces: **a chat message is never queued silently.**
When the bridge cannot carry it right now, the panel refuses the send,
keeps the text in the input box, and says so on the surface. Nothing is
held, nothing replays later; pressing Send again is the release.

The alternative UX -- hold the text with a visible "held until the bridge
is back, Send again to release" affordance -- was named but not built. It
needs held-message state and a release path, which is more than the
smallest honest fix. If a human rules for it, the swap lives here.
"""

from dataclasses import dataclass

__all__ = [
    "ACTION_EMPTY",
    "ACTION_SEND",
    "ACTION_REFUSE_NO_BRIDGE",
    "ACTION_REFUSE_BRIDGE_DOWN",
    "BRIDGE_DOWN_LINE",
    "NO_BRIDGE_LINE",
    "SEND_FAILED_LINE",
    "QUICK_ACTION_DOWN_LINE",
    "QUICK_ACTION_FAILED_LINE",
    "SendDecision",
    "decide_send",
]

ACTION_EMPTY = "empty"
ACTION_SEND = "send"
ACTION_REFUSE_NO_BRIDGE = "refuse_no_bridge"
ACTION_REFUSE_BRIDGE_DOWN = "refuse_bridge_down"

#: Bridge object exists but the socket is down -- the reported FR-1 case.
BRIDGE_DOWN_LINE = (
    "Not connected to SYNAPSE -- that message wasn't sent. "
    "It's still in the box: press Connect, then Send again."
)
#: No bridge object at all (no Qt / standalone). Same wording family.
NO_BRIDGE_LINE = (
    "Not connected to SYNAPSE server -- that message wasn't sent. "
    "It's still in the box."
)
#: The socket died between the connected check and the send. Nothing was
#: queued (the panel sends with ``queue_if_down=False``), so nothing replays.
SEND_FAILED_LINE = (
    "The connection dropped as that message went out -- it wasn't sent "
    "and won't be replayed. It's back in the box: press Connect, then "
    "Send again."
)
#: Quick-action pills are chat messages too (``route_chat``), but there is
#: no input box to hand the text back to: pressing the pill again is the
#: release. Same rule, pill wording.
QUICK_ACTION_DOWN_LINE = (
    "Not connected to SYNAPSE -- that action wasn't sent. "
    "Press Connect, then the pill again."
)
QUICK_ACTION_FAILED_LINE = (
    "The connection dropped as that action went out -- it wasn't sent "
    "and won't be replayed. Press Connect, then the pill again."
)


@dataclass(frozen=True)
class SendDecision:
    """What the panel does with the text in the input box right now.

    ``action`` is one of the ``ACTION_*`` constants. ``keep_text`` is
    ``True`` whenever the text must stay in the box (every refusal).
    ``status_line`` is the artist-facing line to put on the surface, empty
    when there is nothing to say.
    """

    action: str
    keep_text: bool
    status_line: str

    @property
    def sends(self):
        return self.action == ACTION_SEND


def decide_send(text, bridge_present, bridge_connected):
    """Decide whether a chat message may leave the panel right now.

    Parameters
    ----------
    text : str or None
        The raw input-box text.
    bridge_present : bool
        Whether a bridge object exists at all.
    bridge_connected : bool
        Whether that bridge's socket is up *now*
        (``SynapseWSBridge.connected``). This -- not object existence -- is
        the FR-1 guard.
    """
    if not (text or "").strip():
        return SendDecision(ACTION_EMPTY, keep_text=False, status_line="")
    if not bridge_present:
        return SendDecision(
            ACTION_REFUSE_NO_BRIDGE, keep_text=True, status_line=NO_BRIDGE_LINE
        )
    if not bridge_connected:
        return SendDecision(
            ACTION_REFUSE_BRIDGE_DOWN, keep_text=True, status_line=BRIDGE_DOWN_LINE
        )
    return SendDecision(ACTION_SEND, keep_text=False, status_line="")
