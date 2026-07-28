"""Control for long_operation - the freeze becomes legible, and hython is unharmed.

The riskiest thing about this utility is not the UI path. It is that a handler
wrapping its payload in it must behave IDENTICALLY in hython, where there is no
UI to interrupt. Get that wrong and every wrapped handler breaks headless - the
suite runs there, and so does the shipping interpreter.

Asserts, in order of what would hurt most:

  1. NO UI -> NO-OP, NO RAISE. hython has no interrupt dialog. step() must be
     safe to call and must never raise there.
  2. The API exists on 22.0.368 with the methods this depends on.
  3. OperationCancelled is distinct from a failure - a cancel is not a bug and
     a caller must be able to tell them apart.
  4. It degrades rather than explodes when hou is absent entirely.
"""
import sys

sys.path.insert(0, "python")

ok = {}

from synapse.server.long_operation import (
    long_operation, OperationCancelled, _NullOperation,
)

# 1 - the headless path, which is where the suite lives
op = long_operation("probe")
ok["no UI -> null operation"] = isinstance(op, _NullOperation)
try:
    with long_operation("probe") as o:
        o.step(0.5, "half")
        o.step()
        o.step(None, None)
    ok["step() never raises headless"] = True
except Exception as e:
    ok["step() never raises headless"] = False
    print("  raised:", type(e).__name__, e)

# 2 - the API this depends on, on the build we ship against
try:
    import hou
    ok["hou.InterruptableOperation present"] = hasattr(hou, "InterruptableOperation")
    meths = dir(hou.InterruptableOperation)
    ok["updateProgress present"] = "updateProgress" in meths
    ok["updateLongProgress present"] = "updateLongProgress" in meths
    ok["hou.OperationInterrupted present"] = hasattr(hou, "OperationInterrupted")
except ImportError:
    ok["hou.InterruptableOperation present"] = None

# 3 - a cancel is not a failure
ok["cancel is its own exception"] = (
    issubclass(OperationCancelled, RuntimeError)
    and OperationCancelled is not RuntimeError
)

# 4 - no hou at all
import synapse.server.long_operation as lo
_saved = lo.hou
try:
    lo.hou = None
    ok["degrades with no hou"] = isinstance(lo.long_operation("x"), lo._NullOperation)
finally:
    lo.hou = _saved

print("%-38s %s" % ("ASSERTION", "RESULT"))
print("-" * 52)
for k, v in ok.items():
    print("%-38s %s" % (k, v))

allok = all(v for v in ok.values() if v is not None)
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
