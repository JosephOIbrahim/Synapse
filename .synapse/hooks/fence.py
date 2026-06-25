#!/usr/bin/env python3
"""
SYNAPSE harness PreToolUse hook — the hard fence.

Runs before every Claude Code tool call. A `permissionDecision: "deny"` here is honored
even under --dangerously-skip-permissions, so it is a genuine boundary the worker cannot
talk its way past.

Four fences (the first three are ANVIL's; the fourth is the SYNAPSE addition):
  1. IP fence        — patent-core / substrate-internal paths off-limits; no publish/push/tag.
  2. Scope fence     — the worker edits only its contract's `owns`.
  3. Test-integrity  — test files denied unless the contract sets allow_test_edits: true.
  4. PHANTOM-API     — denies an edit that INTRODUCES a hou.* / pdg.* call which is a known
     phantom in this Houdini build (denylist mode), or which is absent from the verified
     runtime manifest (allowlist mode, for use once the dir() audit has produced a complete
     manifest). Best-effort, token-level; the authoritative check is the gate-time
     `verify.py symbols-in-runtime`. This targets SYNAPSE's #1 failure class.

Dependency-free on purpose. Reads .synapse/ip_fence.yaml, .synapse/phantom_fence.yaml,
.synapse/state.json, and the runtime manifest (plain JSON). decide() is pure + unit-tested.
"""
import json
import os
import re
import sys

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Create"}
_WRITE_SHELL = re.compile(r"(>|>>|\btee\b|\bsed\b\s+-i|\bcp\b|\bmv\b|\brm\b|\bdd\b)")


# ---------- glob matching (gitignore-ish, ** aware, no deps) ----------
def _glob_to_regex(pattern):
    p = pattern.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    out, i, n = "", 0, len(p)
    while i < n:
        c = p[i]
        if c == "*":
            if i + 1 < n and p[i + 1] == "*":
                if i + 2 < n and p[i + 2] == "/":
                    out += "(?:.*/)?"; i += 3; continue
                out += ".*"; i += 2; continue
            out += "[^/]*"; i += 1; continue
        if c == "?":
            out += "[^/]"
        elif c in ".^$+{}()[]|":
            out += "\\" + c
        else:
            out += c
        i += 1
    return re.compile("^" + out + "$")


def _match(path, pattern):
    return bool(_glob_to_regex(pattern).match(path))


def _norm(fp, root=None):
    if not fp:
        return ""
    p = str(fp).replace("\\", "/")
    if root:
        try:
            p = os.path.relpath(p, root).replace("\\", "/")
        except Exception:
            pass
    if p.startswith("./"):
        p = p[2:]
    return p


# ---------- phantom-API scan (the SYNAPSE addition, pure + testable) ----------
def scan_phantom(content, phantom):
    """Scan NEW edit content for hou.* / pdg.* tokens. Return (ok, reason).

    denylist mode (default, safe): deny only if a KNOWN phantom appears.
    allowlist mode (post-audit): deny any first-level host symbol absent from the manifest.
    """
    if not content or not phantom:
        return True, ""
    prefixes = phantom.get("deny_unverified_prefixes", ["hou.", "pdg."]) or []
    known = phantom.get("known_phantoms", []) or []
    mode = (phantom.get("mode") or "denylist").strip()
    allowed = set(phantom.get("allowed_symbols", []) or [])

    # denylist: confirmed phantoms are always denied, in any mode
    for ph in known:
        if re.search(r"(?<![\w.])" + re.escape(ph) + r"(?![\w])", content):
            return False, (
                f"PHANTOM-API: '{ph}' is a CONFIRMED phantom in this Houdini build "
                f"(runtime-verified absent). Do not call it. Use hou.ui/hou.qt "
                f"feature-detection or a verified symbol instead."
            )

    if mode == "allowlist" and allowed:
        for pref in prefixes:
            base = pref.rstrip(".")
            for m in re.finditer(re.escape(pref) + r"([A-Za-z_][A-Za-z0-9_]*)", content):
                first = pref + m.group(1)            # e.g. hou.foo
                full = base + "." + m.group(1)
                if first not in allowed and full not in allowed:
                    return False, (
                        f"PHANTOM-API (allowlist): '{first}' is not in the verified runtime "
                        f"manifest. Re-run the dir() audit and add it if it truly exists, "
                        f"or use a verified symbol."
                    )
    return True, ""


def _new_text(tool_input):
    """Collect candidate NEW content from a write tool's input (Write/Edit/MultiEdit)."""
    parts = []
    for k in ("content", "file_text", "new_string", "new_str"):
        v = tool_input.get(k)
        if isinstance(v, str):
            parts.append(v)
    for e in tool_input.get("edits", []) or []:
        if isinstance(e, dict):
            v = e.get("new_string") or e.get("new_str")
            if isinstance(v, str):
                parts.append(v)
    return "\n".join(parts)


# ---------- the decision (pure, testable) ----------
def decide(tool_name, tool_input, fence, contract, phantom=None):
    """Return (allow: bool, reason: str). Paths in tool_input should be repo-relative."""
    fence = fence or {}
    contract = contract or {}
    forbidden_paths = fence.get("forbidden_paths", []) or []

    if tool_name in WRITE_TOOLS:
        rel = _norm(tool_input.get("file_path") or tool_input.get("path") or "")
        if not rel:
            return True, ""
        for pat in forbidden_paths:
            if _match(rel, pat):
                return False, (
                    f"IP-FENCE: '{rel}' is patent-core / substrate-internal (matched '{pat}'). "
                    f"This path is off-limits to autonomous work — human + counsel gate."
                )
        if not contract.get("allow_test_edits"):
            for pat in fence.get("protected_test_globs", []) or []:
                if _match(rel, pat):
                    return False, (
                        f"TEST-INTEGRITY: '{rel}' is a test file (matched '{pat}'). You cannot "
                        f"weaken or delete tests to make the gate pass. If this task legitimately "
                        f"changes tests, the contract must set allow_test_edits: true."
                    )
        for pat in contract.get("do_not_touch", []) or []:
            if _match(rel, pat):
                return False, f"CONTRACT do_not_touch: '{rel}' (matched '{pat}'). This is the floor."
        owns = contract.get("owns")
        if owns and not any(_match(rel, pat) for pat in owns):
            return False, (
                f"SCOPE-FENCE: '{rel}' is outside this task's file ownership. "
                f"This contract may only edit: {owns}"
            )
        # SYNAPSE phantom-API fence — scan the NEW content being written
        ok, why = scan_phantom(_new_text(tool_input), phantom)
        if not ok:
            return False, why
        return True, ""

    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        for pat in fence.get("forbidden_command_patterns", []) or []:
            if pat in cmd:
                return False, (
                    f"IP-FENCE: command contains forbidden operation '{pat}'. "
                    f"No autonomous publish / push / tag — that is a human gate."
                )
        for pat in forbidden_paths:
            base = pat.split("*")[0].rstrip("/")
            if base and base in cmd and _WRITE_SHELL.search(cmd):
                return False, f"IP-FENCE: shell command appears to write into protected path '{base}'."
        return True, ""

    return True, ""


# ---------- tiny YAML-subset loader (lists + scalars only, no deps) ----------
def load_yaml_subset(path):
    d, key = {}, None
    if not os.path.exists(path):
        return d
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            raw = line.rstrip("\n")
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if raw.lstrip().startswith("- "):
                if key is not None:
                    d.setdefault(key, []).append(raw.lstrip()[2:].strip().strip('"').strip("'"))
            elif ":" in raw and not raw[0].isspace():
                k, _, v = raw.partition(":")
                key = k.strip()
                v = v.strip()
                if v:
                    d[key] = v.strip('"').strip("'"); key = None
                else:
                    d[key] = []
    return d


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def load_phantom(cwd):
    """Merge phantom_fence.yaml with the runtime manifest's known_phantoms + allowed_symbols."""
    ph = load_yaml_subset(os.path.join(cwd, ".synapse", "phantom_fence.yaml"))
    manifest_rel = ph.get("runtime_manifest")
    if manifest_rel:
        man = load_json(os.path.join(cwd, manifest_rel))
        ph["known_phantoms"] = list(set((ph.get("known_phantoms") or []) + (man.get("known_phantoms") or [])))
        ph["allowed_symbols"] = man.get("allowed_symbols", []) or []
    return ph


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    tool_name = data.get("tool_name", "")
    tool_input = dict(data.get("tool_input", {}) or {})
    cwd = data.get("cwd") or os.getcwd()

    if tool_input.get("file_path"):
        tool_input["file_path"] = _norm(tool_input["file_path"], cwd)
    if tool_input.get("path"):
        tool_input["path"] = _norm(tool_input["path"], cwd)

    fence = load_yaml_subset(os.path.join(cwd, ".synapse", "ip_fence.yaml"))
    phantom = load_phantom(cwd)
    state = load_json(os.path.join(cwd, ".synapse", "state.json"))
    contract = state.get("contract") if isinstance(state, dict) else None

    allow, reason = decide(tool_name, tool_input, fence, contract, phantom)
    if allow:
        sys.exit(0)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    print("SYNAPSE fence: " + reason, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
