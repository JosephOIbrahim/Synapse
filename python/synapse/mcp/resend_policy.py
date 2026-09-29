"""May the stdio bridge send a SYNAPSE command again after its connection failed? (Level 1, M0, F2)

A command whose bytes never left may always be sent again. Once the send completed, the command
may have run inside Houdini, and sending it again could apply a change twice: the server keeps no
record of command ids. After that point only a command that cannot change anything is sent again:

* a protocol command (ping, heartbeat, health, context, authenticate);
* a stop control, because stopping twice is harmless and stopping is never fenced;
* a tool that is read-only under both of SYNAPSE's gating sets.

Anything else, including a command this module cannot classify, is not sent again. The caller
then reports that the command may have run, and the artist checks the scene first.
"""
from __future__ import annotations

from synapse.mcp.read_only_mode import STOPS_ALWAYS_PASS, tool_for_command

#: WebSocket commands that are protocol rather than tools. Answering one twice changes nothing.
PROTOCOL_COMMANDS = frozenset({"ping", "heartbeat", "get_health", "context", "authenticate"})


def may_resend(cmd_type: str, sent: bool) -> bool:
    """True when sending *cmd_type* again cannot apply a change twice."""
    if not sent:
        return True
    if cmd_type in PROTOCOL_COMMANDS:
        return True
    tool = tool_for_command(cmd_type)
    if tool is None:
        return False
    if tool in STOPS_ALWAYS_PASS:
        return True
    try:
        from synapse.mcp.server import is_transport_fast_path
    except ImportError:
        return False  # cannot classify it, so it is not sent again
    return bool(is_transport_fast_path(tool))
