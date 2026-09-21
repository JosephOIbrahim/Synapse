"""PreToolUse hook: Block Edit/Write to deployed copies and protected paths.

Reads hook JSON from stdin, checks file_path against blocked patterns.

Decision protocol
    allow          -> exit 0, no output          (byte-identical to the original hook)
    policy deny    -> exit 0, JSON permissionDecision=deny on stdout
    fail-closed    -> exit 2 (DENY_EXIT), reason on stderr + JSON deny on stdout

Fail-closed (BP9-HOOKS): malformed JSON, missing file_path, or ANY exception
denies with a one-line reason. The old hook allowed on error; that let a
broken hook silently wave through edits to deployed copies.

Worktree fence (BP9-HOOKS, narrowed BP9-STOPGATE): when the cwd is under a
``.claude/worktrees/`` path, any Edit/Write whose file_path resolves INSIDE
the main checkout (the path prefix before ``/.claude/worktrees/``) but NOT
inside the current worktree is denied. This is the "worktree absolute path
hits main tree" trap: an agent dispatched into a worktree edits
``C:/Users/User/SYNAPSE/...`` and lands the change in the main checkout
instead. Paths outside both trees (``~/.claude/projects/*/memory/MEMORY.md``,
``~/.claude/skills``) stay allowed -- the wave-one fence denied those too,
which starved the auto-memory file from every worktree agent.

Every fire is recorded to the hook ledger (``_ledger.record``); the ledger
never raises and never influences the decision.
"""

import json
import os
import sys
import time

DENY_EXIT = 2
WORKTREES_MARKER = "/.claude/worktrees/"

BLOCKED_PATTERNS = [
    # Deployed copies (source of truth is the repo)
    ".synapse\\houdini\\",
    ".synapse/houdini/",
    # Houdini prefs (deployed by installer)
    "houdini21.0\\",
    "houdini21.0/",
    "houdini22.0\\",
    "houdini22.0/",
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
    "houdini22.0\\": "~/houdini22.0/ is Houdini prefs (deployed by installer). Edit source in SYNAPSE/ or ~/.synapse/houdini/.",
    "houdini22.0/": "~/houdini22.0/ is Houdini prefs (deployed by installer). Edit source in SYNAPSE/ or ~/.synapse/houdini/.",
    "site-packages\\": "site-packages/ is an installed copy. Edit the repo source instead.",
    "site-packages/": "site-packages/ is an installed copy. Edit the repo source instead.",
    "\\AppData\\": "AppData/ is a system path. Do not edit files here.",
    "/AppData/": "AppData/ is a system path. Do not edit files here.",
}


def _norm(path, base=None):
    """Absolute, normalised, forward-slash, case-folded path string."""
    if base and not os.path.isabs(path):
        path = os.path.join(base, path)
    path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    return path.replace("\\", "/")


def worktree_root(cwd):
    """Return the worktree root if cwd is under .claude/worktrees/, else None."""
    norm = _norm(cwd)
    idx = norm.find(WORKTREES_MARKER)
    if idx < 0:
        return None
    rest = norm[idx + len(WORKTREES_MARKER):]
    name = rest.split("/", 1)[0]
    if not name:
        return None
    return norm[: idx + len(WORKTREES_MARKER)] + name


def main_checkout(cwd):
    """Return the main checkout root (prefix before /.claude/worktrees/), else None.

    Path-derived, no git subprocess: the marker sits inside the main
    checkout's own .claude/ dir, so the prefix IS the parent of
    ``git rev-parse --git-common-dir``.
    """
    norm = _norm(cwd)
    idx = norm.find(WORKTREES_MARKER)
    if idx < 0:
        return None
    return norm[:idx]


def _inside(target, root):
    return target == root or target.startswith(root + "/")


def decide(data, cwd):
    """Pure decision: (decision, reason). Raises on malformed input."""
    if not isinstance(data, dict):
        raise ValueError("hook input is not a JSON object")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ValueError("hook input has no tool_input object")
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("hook input has no file_path")

    # Fence first: the most specific reason wins when cwd is a worktree.
    # Narrowed (BP9-STOPGATE): deny only main-checkout paths outside this
    # worktree. ~/.claude/**, memory files and other trees stay allowed.
    root = worktree_root(cwd)
    if root is not None:
        target = _norm(file_path, base=cwd)
        main = main_checkout(cwd)
        if main and _inside(target, main) and not _inside(target, root):
            return "deny", (
                f"Worktree fence: cwd is inside worktree {root} but file_path "
                f"resolves into the main checkout {main} ({target}). Use a relative "
                f"path inside the worktree; absolute paths into the main tree edit a "
                f"different checkout."
            )

    for pattern in BLOCKED_PATTERNS:
        if pattern in file_path:
            return "deny", BLOCKED_REASONS.get(pattern, f"Blocked path pattern: {pattern}")

    return "allow", ""


def _emit_deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)


def _ledger_record(*args, **kwargs):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _ledger  # noqa: E402
        _ledger.record(*args, **kwargs)
    except Exception:
        pass


def main():
    t0 = time.perf_counter()
    decision = "deny"
    reason = ""
    exit_code = DENY_EXIT
    file_path = ""
    session = None
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        if isinstance(data, dict):
            session = data.get("session_id")
            cwd = data.get("cwd") or os.getcwd()
            ti = data.get("tool_input")
            if isinstance(ti, dict):
                file_path = str(ti.get("file_path", ""))
        else:
            cwd = os.getcwd()
        decision, reason = decide(data, cwd)
        if decision == "deny":
            _emit_deny(reason)
        exit_code = 0
    except Exception as exc:  # fail-closed: any error denies
        decision = "deny"
        reason = f"guard-edit-targets fail-closed: {type(exc).__name__}: {exc}"
        exit_code = DENY_EXIT
        try:
            _emit_deny(reason)
            print(reason, file=sys.stderr)
        except Exception:
            pass
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        _ledger_record(
            "PreToolUse", "guard-edit-targets", decision, ms,
            extra={"file_path": file_path, "reason": reason, "exit": exit_code},
            session=session,
        )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
