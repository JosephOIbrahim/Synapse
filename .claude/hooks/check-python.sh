#!/bin/bash
# Post-edit syntax check for Python files
# Reads hook input JSON from stdin, extracts file_path, runs py_compile.
# BP9-HOOKS: the work runs in a tiny inline python shim so the fire is
# recorded to the hook ledger (_ledger.record) with its decision + duration.
# Exit code is unchanged (always 0 -- advisory only).

INPUT=$(cat)
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python -c '
import json, os, sys, time, py_compile
hook_dir = sys.argv[1]
t0 = time.perf_counter()
decision, file_path, session = "skip", "", None
try:
    data = json.loads(sys.stdin.read() or "{}")
    if isinstance(data, dict):
        session = data.get("session_id")
        ti = data.get("tool_input") or {}
        file_path = str(ti.get("file_path", "")) if isinstance(ti, dict) else ""
    if file_path.endswith(".py") and os.path.isfile(file_path):
        try:
            py_compile.compile(file_path, doraise=True)
            decision = "ok"
        except Exception as exc:
            decision = "syntax_error"
            print(str(exc))
            print("SYNTAX ERROR in " + file_path)
except Exception as exc:
    decision = "error:" + type(exc).__name__
finally:
    try:
        sys.path.insert(0, hook_dir)
        import _ledger
        _ledger.record("PostToolUse", "check-python", decision,
                       (time.perf_counter() - t0) * 1000.0,
                       extra={"file_path": file_path}, session=session)
    except Exception:
        pass
' "$HOOK_DIR" <<<"$INPUT"

exit 0
