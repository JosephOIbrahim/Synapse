"""Synapse Hooks Bridge — Claude Code <-> Houdini event relay.

Reads Houdini events from a JSONL file and surfaces them as context
to Claude Code via hook stdout. Supports all hook event types.

Hook protocol: reads JSON from stdin, writes JSON or plain text to stdout.

Cook-error stop gate (BP9-STOPGATE, ruling 4). Cook errors used to live only
in the consume-on-prompt watermark: one UserPromptSubmit read them, moved the
watermark, and the next Stop saw nothing. Now every CookError lands in an
``unresolved`` set persisted beside the events file (UNRESOLVED_FILE, JSON,
one entry per node path with its message). An entry clears when a later
event reports a successful cook for the same node, or when the artist's
prompt carries an explicit ``resolved`` marker. On Stop and TaskCompleted a
non-empty set prints the one-line list to stderr and exits 2 (the blocking
code). Every other event keeps its exit code. A missing events file means no
cook errors: exit 0, never a false block.
"""

import json
import os
import re
import socket
import sys
import time

EVENTS_DIR = os.environ.get("SYNAPSE_HOOKS_EVENTS_DIR", "").strip() or os.path.join(
    os.environ.get("TEMP", "/tmp"), "synapse_hooks"
)
EVENTS_FILE = os.path.join(EVENTS_DIR, "houdini_events.jsonl")
LAST_READ_FILE = os.path.join(EVENTS_DIR, ".last_read_ts")
UNRESOLVED_FILE = os.path.join(EVENTS_DIR, ".unresolved_cook_errors.json")

BLOCK_EXIT = 2  # Claude Code: exit 2 blocks Stop / TaskCompleted, stderr is shown
RESOLVED_MARKER = re.compile(r"\bresolved\b", re.IGNORECASE)

MAX_EVENT_AGE = 300  # 5 minutes

# F6 (CLEAR P3.1): the SessionStart hook used to print "Synapse bridge
# connected." unconditionally -- a lying "connected" signal when Houdini / the
# Synapse server was not running at all. ping_bridge() is a real network probe
# (TCP connect to the Synapse WS port) so the connected report is ping-gated.
PING_TIMEOUT = 1.5  # seconds -- short, this runs on every session start


def ping_bridge(host=None, port=None, timeout=PING_TIMEOUT):
    """Probe the Synapse bridge WebSocket port.

    A real network probe, not a flag check. Returns True only if something is
    accepting TCP connections on the Synapse port (i.e. the Synapse server
    inside Houdini is actually listening). Returns False on any connection
    refusal, timeout, or error.

    This is a liveness ping, not a full WS handshake: a successful TCP connect
    proves the bridge is up; a refused/timeout proves it is not. The
    SessionStart "connected" report is gated on this so it can no longer lie
    when Houdini is not running.
    """
    host = host or os.environ.get("SYNAPSE_HOST", "localhost")
    port = port or int(os.environ.get("SYNAPSE_PORT", "9999"))
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def read_last_timestamp():
    try:
        with open(LAST_READ_FILE, "r", encoding="utf-8") as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0.0


def write_last_timestamp(ts):
    os.makedirs(EVENTS_DIR, exist_ok=True)
    with open(LAST_READ_FILE, "w", encoding="utf-8") as f:
        f.write(str(ts))


def read_new_events():
    if not os.path.exists(EVENTS_FILE):
        return []

    last_ts = read_last_timestamp()
    now = time.time()
    new_events = []

    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_ts = event.get("timestamp", 0)
                if event_ts <= last_ts:
                    continue
                if (now - event_ts) > MAX_EVENT_AGE:
                    continue
                new_events.append(event)
    except (OSError, IOError):
        return []

    if new_events:
        max_ts = max(e.get("timestamp", 0) for e in new_events)
        write_last_timestamp(max_ts)

    return new_events


def format_events(events):
    """Format events into readable context for Claude."""
    if not events:
        return ""

    lines = ["[Houdini Events]"]
    for event in events:
        event_type = event.get("type", "unknown")
        detail = event.get("detail", "")
        data = event.get("data", {})
        age = time.time() - event.get("timestamp", time.time())
        age_str = f"{int(age)}s ago" if age < 60 else f"{int(age / 60)}m ago"

        # Rich formatting for node events with parm data
        if event_type == "node_ParmTupleChanged" and data:
            parm = data.get("parm")
            value = data.get("value", "")
            if parm:
                lines.append(f"  parm {detail}.{parm} = {value} ({age_str})")
            else:
                lines.append(f"  bulk parm change on {detail} ({age_str})")
        elif event_type.startswith("pdg_") and data.get("message"):
            lines.append(f"  PDG {event_type}: {data['message']} ({age_str})")
        elif detail:
            lines.append(f"  {event_type}: {detail} ({age_str})")
        else:
            lines.append(f"  {event_type} ({age_str})")

    return "\n".join(lines)


def read_hook_input():
    """Read Claude Code hook JSON from stdin if available."""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def get_hook_event(hook_input):
    """Determine which hook event triggered us."""
    # Try stdin JSON first, then env var
    name = hook_input.get("hook_event_name", "")
    if not name:
        name = os.environ.get("CLAUDE_HOOK_EVENT", "unknown")
    return name


def get_cook_errors(events):
    """Extract cook-error events from a batch of events."""
    return [e for e in events if "CookError" in e.get("type", "")]


def _is_cook_success(event):
    t = event.get("type", "")
    return "CookError" not in t and ("CookComplete" in t or "Cooked" in t or "CookDone" in t)


def _event_node(event):
    detail = event.get("detail") or ""
    data = event.get("data") or {}
    return str(detail or data.get("node") or data.get("node_path") or "").strip()


def read_unresolved():
    """Load the persisted unresolved set: {node_path: {message, timestamp}}."""
    try:
        with open(UNRESOLVED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def write_unresolved(unresolved):
    try:
        if not unresolved:
            try:
                os.remove(UNRESOLVED_FILE)
            except FileNotFoundError:
                pass
            return
        os.makedirs(EVENTS_DIR, exist_ok=True)
        with open(UNRESOLVED_FILE, "w", encoding="utf-8") as f:
            json.dump(unresolved, f, sort_keys=True)
    except OSError:
        pass


def update_unresolved(events, prompt=""):
    """Fold new events + the artist prompt into the persisted unresolved set.

    - CookError                                  -> add/refresh entry for that node
    - successful cook on a node already in the set -> clear that node
    - explicit 'resolved' marker in the prompt    -> clear everything
    - events file missing                         -> no cook errors: set emptied
    Returns the resulting dict.
    """
    if not os.path.exists(EVENTS_FILE):
        write_unresolved({})
        return {}
    unresolved = read_unresolved()
    for e in events:
        node = _event_node(e)
        if "CookError" in e.get("type", ""):
            msg = (e.get("data") or {}).get("message") or e.get("detail") or "unknown"
            unresolved[node or "<unknown>"] = {
                "message": str(msg),
                "timestamp": e.get("timestamp", 0),
            }
        elif _is_cook_success(e) and node in unresolved:
            del unresolved[node]
    if prompt and RESOLVED_MARKER.search(prompt):
        unresolved = {}
    write_unresolved(unresolved)
    return unresolved


def format_unresolved(unresolved):
    """One line: 'BLOCKED: N unresolved Houdini cook error(s): /a (msg); /b (msg)'."""
    items = "; ".join(
        f"{node} ({entry.get('message', 'unknown')})" for node, entry in sorted(unresolved.items())
    )
    return f"BLOCKED: {len(unresolved)} unresolved Houdini cook error(s): {items}"


_LAST_HOOK = {"event": "unknown", "session": None, "unresolved": 0}


def main():
    hook_input = read_hook_input()
    hook_event = get_hook_event(hook_input)
    # Ledger bookkeeping only -- no decision lives here.
    _LAST_HOOK["event"] = hook_event
    if isinstance(hook_input, dict):
        _LAST_HOOK["session"] = hook_input.get("session_id")
    events = read_new_events()
    context = format_events(events)
    prompt = hook_input.get("prompt", "") if isinstance(hook_input, dict) else ""
    unresolved = update_unresolved(
        events, prompt if hook_event == "UserPromptSubmit" else ""
    )
    _LAST_HOOK["unresolved"] = len(unresolved)

    if hook_event in ("SessionStart", "startup", "resume"):
        # F6: ping BEFORE reporting connected. Only claim "connected" if the
        # Synapse bridge is actually reachable; otherwise report honestly.
        if ping_bridge():
            print("Synapse bridge connected.")
        else:
            print(
                "Synapse bridge not reachable — "
                "Houdini/Synapse server may not be running (ping failed)."
            )
        if context:
            print(context)
        else:
            print("No pending Houdini events.")

    elif hook_event == "UserPromptSubmit":
        if context:
            print(context)

    elif hook_event == "Stop":
        # Quality gate: block while the persisted unresolved set is non-empty.
        if unresolved:
            # stderr so Claude sees the block reason; exit 2 is the blocking code
            print(format_unresolved(unresolved), file=sys.stderr)
            sys.exit(2)
        if context:
            print(context)

    elif hook_event == "TaskCompleted":
        # Same gate as Stop: task completion blocks on unresolved cook errors.
        if unresolved:
            print(format_unresolved(unresolved), file=sys.stderr)
            sys.exit(2)

    elif hook_event == "PreCompact":
        # Snapshot state before context compaction
        if events:
            snapshot = {
                "event_count": len(events),
                "types": list(set(e.get("type", "") for e in events)),
                "latest": events[-1] if events else None,
            }
            print(f"[Pre-Compact Snapshot] {json.dumps(snapshot, sort_keys=True)}")

    elif hook_event == "SessionEnd":
        # Final cleanup
        if context:
            print(context)
        # Clear watermark for next session
        try:
            os.remove(LAST_READ_FILE)
        except OSError:
            pass

    else:
        # PostToolUse, PreToolUse, TeammateIdle, etc — surface events if any
        if context:
            print(context)


def _ledger_record(decision, ms):
    """Record this fire to the hook ledger. Never raises, never decides."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _ledger  # noqa: E402
        _ledger.record(
            _LAST_HOOK["event"], "synapse_hooks_bridge", decision, ms,
            extra={"unresolved": _LAST_HOOK["unresolved"]},
            session=_LAST_HOOK["session"],
        )
    except Exception:
        pass


def _run():
    """Wrap main() so every fire records decision + duration.

    Exit codes pass through unchanged: Stop and TaskCompleted exit 2 on a
    non-empty unresolved set (BP9-STOPGATE, ruling 4); everything else exit 0.
    """
    t0 = time.perf_counter()
    decision = "ok"
    try:
        main()
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 0
        decision = "exit:%s" % code
        raise
    except Exception as exc:
        decision = "error:%s" % type(exc).__name__
        raise
    finally:
        _ledger_record(decision, (time.perf_counter() - t0) * 1000.0)


if __name__ == "__main__":
    _run()
