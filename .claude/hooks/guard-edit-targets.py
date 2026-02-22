"""PreToolUse hook: Block Edit/Write to deployed copies and protected paths.

Reads hook JSON from stdin, checks file_path against blocked patterns.
Exit 0 with JSON deny = block the edit. Exit 0 with no output = allow.
"""

import json
import sys

BLOCKED_PATTERNS = [
    # Deployed copies (source of truth is the repo)
    ".synapse\\houdini\\",
    ".synapse/houdini/",
    # Houdini prefs (deployed by installer)
    "houdini21.0\\",
    "houdini21.0/",
    # Installed packages
    "site-packages\\",
    "site-packages/",
    # System paths
    "\\AppData\\",
    "/AppData/",
]

BLOCKED_REASONS = {
    ".synapse\\houdini\\": "~/.synapse/houdini/ is a deployed copy. Edit the repo source in SYNAPSE/ instead.",
    ".synapse/houdini/": "~/.synapse/houdini/ is a deployed copy. Edit the repo source in SYNAPSE/ instead.",
    "houdini21.0\\": "~/houdini21.0/ is Houdini prefs (deployed by installer). Edit source in SYNAPSE/ or ~/.synapse/houdini/.",
    "houdini21.0/": "~/houdini21.0/ is Houdini prefs (deployed by installer). Edit source in SYNAPSE/ or ~/.synapse/houdini/.",
    "site-packages\\": "site-packages/ is an installed copy. Edit the repo source instead.",
    "site-packages/": "site-packages/ is an installed copy. Edit the repo source instead.",
    "\\AppData\\": "AppData/ is a system path. Do not edit files here.",
    "/AppData/": "AppData/ is a system path. Do not edit files here.",
}

try:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")

    for pattern in BLOCKED_PATTERNS:
        if pattern in file_path:
            reason = BLOCKED_REASONS.get(pattern, f"Blocked path pattern: {pattern}")
            json.dump({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, sys.stdout)
            break

except Exception:
    pass  # On error, allow (don't block work)

sys.exit(0)
