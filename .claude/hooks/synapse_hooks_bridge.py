"""Synapse Hooks Bridge — Claude Code <-> Houdini event relay.

Reads Houdini events from a JSONL file and surfaces them as context
to Claude Code via hook stdout. Supports all hook event types.

Hook protocol: reads JSON from stdin, writes JSON or plain text to stdout.
"""

import json
import os
import sys
import time

EVENTS_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "synapse_hooks")
EVENTS_FILE = os.path.join(EVENTS_DIR, "houdini_events.jsonl")
LAST_READ_FILE = os.path.join(EVENTS_DIR, ".last_read_ts")

MAX_EVENT_AGE = 300  # 5 minutes


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
    """Extract unresolved cook errors from events."""
    return [e for e in events if "CookError" in e.get("type", "")]


def main():
    hook_input = read_hook_input()
    hook_event = get_hook_event(hook_input)
    events = read_new_events()
    context = format_events(events)

    if hook_event in ("SessionStart", "startup", "resume"):
        print("Synapse bridge connected.")
        if context:
            print(context)
        else:
            print("No pending Houdini events.")

    elif hook_event == "UserPromptSubmit":
        if context:
            print(context)

    elif hook_event == "Stop":
        # Quality gate: block if unresolved cook errors
        errors = get_cook_errors(events)
        if errors:
            # Print to stderr so Claude sees the block reason
            print(
                f"BLOCKED: {len(errors)} unresolved Houdini cook error(s). "
                f"Last: {errors[-1].get('data', {}).get('message', 'unknown')}",
                file=sys.stderr,
            )
            sys.exit(1)
        if context:
            print(context)

    elif hook_event == "TaskCompleted":
        # Quality gate: block task completion if cook errors pending
        errors = get_cook_errors(events)
        if errors:
            print(
                f"Task blocked: {len(errors)} unresolved cook error(s)",
                file=sys.stderr,
            )
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


if __name__ == "__main__":
    main()
