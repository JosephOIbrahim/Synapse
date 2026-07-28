"""Do the MCP annotations agree with what the server actually enforces?

E1-F9: seven tools advertise readOnlyHint=true while the server treats them as
MUTATING - for the C5 mutation lock, the live integrity envelope, and the audit
write. An MCP client reads readOnlyHint to decide what it may call without
confirmation, so a hint that contradicts the enforcement is worse than no hint:
it invites a caller to skip a confirmation the system will then demand.

Two independent declarations:
    TOOL_DEFS[..][5]        -> the _ro flag published as readOnlyHint
    _READ_ONLY_COMMANDS     -> what the server actually treats as read-only

Nothing kept them in step. This reports BOTH SIDES per tool so the fix is a
per-tool judgement - several of the seven read as obviously read-only by name,
and if the SERVER is wrong about those, flipping the annotation entrenches the
error.

Exits nonzero on any disagreement, so it can gate.
"""
import sys

sys.path.insert(0, "python")

from synapse.mcp import _tool_registry as reg
from synapse.server.handlers import _READ_ONLY_COMMANDS

# DECLARED EXCEPTIONS - deliberate, documented, and compensated.
#
# These three are annotated destructive AND classified read-only by the server,
# on purpose. handlers.py:220-234 states the reason and it is a good one:
#
#   "a running render holds the C5 mutation lock for its whole duration, so a
#    mutating-classified stop or halt would queue behind the very operation it
#    exists to interrupt -- which is the difference between a kill switch and a
#    decoration. Audit is written in-handler."
#
# Provenance is not skipped; it moves from the floor gate into the handler.
# A check that flags three correct decisions gets ignored (R129), and this one
# nearly caused a safety change on a misread (R173).
DECLARED = {
    "emergency_halt": "must bypass the C5 lock or it queues behind what it halts",
    "render_farm_cancel": "same argument - a cancel cannot wait on the render",
    "render_stop": "same argument - kill switch, not decoration",
}

rows, declared_seen = [], []
for d in reg.TOOL_DEFS:
    name, cmd, _builder, _desc, _schema, ro, destr, idemp = d
    server_ro = cmd in _READ_ONLY_COMMANDS
    if bool(ro) == bool(server_ro):
        continue
    if cmd in DECLARED:
        declared_seen.append((name, cmd, DECLARED[cmd]))
    else:
        rows.append((name, cmd, bool(ro), server_ro, bool(destr)))

print("%-34s %-26s %-10s %-10s" % ("TOOL", "COMMAND", "ANNOTATION", "SERVER"))
print("-" * 86)
for name, cmd, ro, sro, destr in sorted(rows):
    print("%-34s %-26s %-10s %-10s%s"
          % (name[:34], str(cmd)[:26],
             "read-only" if ro else "mutating",
             "read-only" if sro else "MUTATING",
             "   destructiveHint=True" if destr else ""))

print()
if declared_seen:
    print("  DECLARED EXCEPTIONS - deliberate, documented, compensated:")
    for name, cmd, why in sorted(declared_seen):
        print("    %-30s %s" % (name[:30], why))
    print()
print("  tools total        : %d" % len(reg.TOOL_DEFS))
print("  server read-only   : %d" % len(_READ_ONLY_COMMANDS))
print("  declared exceptions: %d" % len(declared_seen))
print("  UNDECLARED         : %d" % len(rows))
print()
if rows:
    print("  These claim READ-ONLY and the server treats them as MUTATING.")
    print("  A shallow read of each handler found no mutation - so the")
    print("  ANNOTATION is likely right and the server's omission is the gap.")
    print("  That is the OPPOSITE of R150's blanket 'server is the authority',")
    print("  and it is NOT changed on a 22-line grep: adding a command to")
    print("  _READ_ONLY_COMMANDS makes it execute with ZERO floor provenance.")
print()
print("RESULT:", "PASS - annotations match enforcement" if not rows
      else "FAIL - %d undeclared disagreement(s)" % len(rows))
sys.exit(0 if not rows else 1)
