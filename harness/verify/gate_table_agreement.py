"""Do the risk-class tables agree on what a registered tool is allowed to do?

Six hand-maintained tables answer "what may this tool do, and what gate does
it deserve" independently, and nothing keeps them in step:

    TOOL_DEFS[..][5,6,7]   -> (read_only, destructive, idempotent) per tool,
                              the triple that becomes the MCP annotations an
                              external client acts on (_tool_registry.py)
    _TOOL_TO_OPERATION      -> tool name -> bridge operation type
                              (panel/bridge_adapter.py)
    OPERATION_GATES         -> operation type -> gate level
                              (shared/constants.py)
    _DISK_WRITING_TOOLS     -> R4 touches_disk elevation (panel/bridge_adapter.py)
    server/rbac.py          -> which studio role may run the command
    the bridge read-only set -> which ops skip the bridge entirely

When they disagree the failure is silent and expensive: a mutating tool with no
`_TOOL_TO_OPERATION` row takes the bridge's REVIEW default on one path and the
panel adapter's `set_parameter`/inform default on another, so the same tool
carries two different gates depending on which road it took. Today 16 non-read-
only tools have NO row at all -- including the three brakes
(synapse_render_stop / synapse_render_farm_cancel / synapse_emergency_halt) an
artist "can watch a render they cannot start and cannot kill" (U1), and five
Solaris composites (U4).

THIS SCRIPT ONLY SURFACES THE GAP. It never edits `_TOOL_TO_OPERATION`,
`OPERATION_GATES`, or any gate table -- adding the missing rows is a separate
human/forge decision (CLAUDE.md sec 2.3 loop F; sec 3.1 "never a table edit").
Advise, never promote.

Two checks:

  1. RATCHETED -- every non-read-only TOOL_DEFS tool should have a
     `_TOOL_TO_OPERATION` row. The 16 missing today are recorded as a committed
     baseline (gate_table_agreement_floor.json). The lint FAILS only when a
     tool goes missing that was NOT in that baseline -- a NEW un-mapped mutating
     tool. It stays GREEN at today's 16, and never reddens when a row gets fixed
     (it prints a "baseline can be tightened" advisory instead). The baseline
     names are the accepted-today ledger, NOT per-tool exemptions.

  2. HARD -- every op a tool maps to must be in `OPERATION_GATES` or a DECLARED
     exception. Clean today (only `insert_cache` is deliberately absent), so
     this one can gate directly: a new un-gated op is a real hole.

Prints cross-membership per non-read-only tool so a fix is a per-tool judgement,
then exits nonzero on any failure so it can gate. The pytest that pins it lives
at tests/test_gate_table_agreement.py, already inside CI's testpaths.
"""

from __future__ import annotations

import json
import os
import sys
import warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
BASELINE_PATH = os.path.join(_HERE, "gate_table_agreement_floor.json")


# Operation types deliberately ABSENT from OPERATION_GATES -- documented,
# compensated, and NOT a gap. `insert_cache` resolves to the REVIEW default via
# Operation.gate_level on purpose (bridge_adapter.py comment; pinned by
# tests/test_cache_insert_gates.py). A check that flags a correct decision gets
# ignored, so it is declared here, once, with its reason.
DECLARED_OPS: dict[str, str] = {
    "insert_cache": "intentionally not in OPERATION_GATES; Operation.gate_level "
                    "resolves it to the REVIEW default "
                    "(bridge_adapter.py; pinned by tests/test_cache_insert_gates.py)",
}


def _ensure_path() -> None:
    """Put repo root and python/ on sys.path, robust to the caller's cwd."""
    for p in (os.path.join(_ROOT, "python"), _ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)


def load_tables() -> tuple[list, dict, dict, set]:
    """Return (TOOL_DEFS, _TOOL_TO_OPERATION, OPERATION_GATES, _DISK_WRITING_TOOLS).

    The vendored-SDK ABI RuntimeWarning fired by _tool_registry import is
    silenced here -- it is a diagnostics signal, orthogonal to this lint.
    """
    _ensure_path()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from synapse.mcp import _tool_registry as reg
        from synapse.panel.bridge_adapter import (
            _TOOL_TO_OPERATION,
            _DISK_WRITING_TOOLS,
        )
        from shared.constants import OPERATION_GATES
    return (
        list(reg.TOOL_DEFS),
        dict(_TOOL_TO_OPERATION),
        dict(OPERATION_GATES),
        set(_DISK_WRITING_TOOLS),
    )


def _rbac_min_role(command: str):
    """Lowest studio role that may run `command`, or None if rbac won't import.

    Best-effort, informational column only. `command` is TOOL_DEFS[..][1]
    (the WS command), which is what rbac.py keys on -- NOT the tool name.
    """
    try:
        _ensure_path()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from synapse.server.rbac import Role, check_permission
    except Exception:
        return None
    for role in (Role.VIEWER, Role.ARTIST, Role.LEAD, Role.ADMIN):
        if check_permission(role, command):
            return role.value
    return "none"


def compute(tool_defs: list, tool_to_op: dict, operation_gates: dict) -> dict:
    """Pure over its inputs so a test can inject a mutated `tool_to_op`.

    A tool is non-read-only when its TOOL_DEFS read_only flag (index 5) is
    falsey.
    """
    non_ro = [d for d in tool_defs if not d[5]]
    non_ro_names = sorted(d[0] for d in non_ro)
    missing = sorted(n for n in non_ro_names if n not in tool_to_op)
    ungated = sorted(
        (name, op)
        for name, op in tool_to_op.items()
        if op not in operation_gates and op not in DECLARED_OPS
    )
    return {
        "non_ro_count": len(non_ro),
        "non_ro_names": non_ro_names,
        "missing": missing,
        "missing_count": len(missing),
        "ungated_ops": ungated,
    }


def load_baseline(path: str = BASELINE_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate(result: dict, baseline: dict) -> dict:
    """Ratchet verdict. FAIL on a NEW missing row or any undeclared un-gated op.

    Green today (all current-missing names are in the baseline set, no un-gated
    op). Never reddens on an improvement -- a fixed row only prints an advisory.
    """
    base_names = set(baseline.get("missing_names", []))
    base_count = int(baseline.get("missing_count", 0))
    current = set(result["missing"])

    new_missing = sorted(current - base_names)   # a tool went missing that wasn't accepted
    fixed = sorted(base_names - current)          # a row got mapped since the baseline
    count_regressed = result["missing_count"] > base_count
    undeclared_ungated = result["ungated_ops"]

    ok = (not new_missing) and (not count_regressed) and (not undeclared_ungated)
    return {
        "ok": ok,
        "new_missing": new_missing,
        "fixed": fixed,
        "current_count": result["missing_count"],
        "baseline_count": base_count,
        "count_regressed": count_regressed,
        "undeclared_ungated": undeclared_ungated,
        "can_tighten": bool(fixed) and not new_missing,
    }


def _print_cross_membership(tool_defs, tool_to_op, operation_gates, disk) -> None:
    """One row per non-read-only tool: where it lives across the tables."""
    by_name = {d[0]: d for d in tool_defs}
    non_ro = sorted(d[0] for d in tool_defs if not d[5])
    print("%-38s %-18s %-12s %-5s %-5s %-6s %s"
          % ("TOOL", "OPERATION", "GATE", "DISK", "DEST", "IDEMP", "RBAC-MIN"))
    print("-" * 104)
    for name in non_ro:
        d = by_name[name]
        cmd, destr, idemp = d[1], d[6], d[7]
        op = tool_to_op.get(name)
        if op is None:
            op_s, gate_s = "-- MISSING --", "(bridge REVIEW / panel inform)"
        else:
            op_s = op
            gate_s = operation_gates.get(op) or (
                "(REVIEW default)" if op in DECLARED_OPS else "(!! UN-GATED)")
        print("%-38s %-18s %-12s %-5s %-5s %-6s %s"
              % (name[:38], op_s[:18], str(gate_s)[:12],
                 "yes" if name in disk else "-",
                 "yes" if destr else "-",
                 "yes" if idemp else "-",
                 _rbac_min_role(cmd) or "n/a"))


def main() -> int:
    tool_defs, tool_to_op, operation_gates, disk = load_tables()
    result = compute(tool_defs, tool_to_op, operation_gates)
    baseline = load_baseline()
    verdict = evaluate(result, baseline)

    _print_cross_membership(tool_defs, tool_to_op, operation_gates, disk)
    print()

    print("  non-read-only tools     : %d" % result["non_ro_count"])
    print("  mapped in _TOOL_TO_OP   : %d" % (result["non_ro_count"] - result["missing_count"]))
    print("  MISSING a mapping       : %d  (baseline floor %d)"
          % (result["missing_count"], verdict["baseline_count"]))
    print("  undeclared un-gated ops : %d" % len(result["ungated_ops"]))
    print()

    if result["missing"]:
        print("  These non-read-only tools have NO _TOOL_TO_OPERATION row.")
        print("  Surfacing them is the deliverable; adding the rows is a")
        print("  separate human/forge decision -- this lint never edits a table.")
        for name in result["missing"]:
            tag = "  <-- NEW" if name in verdict["new_missing"] else ""
            print("      %-40s%s" % (name, tag))
        print()

    if verdict["undeclared_ungated"]:
        print("  Operations mapped by a tool but ABSENT from OPERATION_GATES")
        print("  (and not declared): these resolve to a silent default gate.")
        for name, op in verdict["undeclared_ungated"]:
            print("      %-40s -> %s" % (name, op))
        print()

    if verdict["can_tighten"]:
        print("  ADVISORY: %d baseline row(s) now mapped -- the floor can be")
        print("  tightened in a human-promoted commit: %s" % ", ".join(verdict["fixed"]))
        print()

    if verdict["ok"]:
        print("RESULT: PASS - no new gate-table drift (%d known-missing at floor)"
              % result["missing_count"])
        return 0

    reasons = []
    if verdict["new_missing"]:
        reasons.append("%d NEW un-mapped tool(s): %s"
                       % (len(verdict["new_missing"]), ", ".join(verdict["new_missing"])))
    if verdict["count_regressed"]:
        reasons.append("missing count %d rose above floor %d"
                       % (verdict["current_count"], verdict["baseline_count"]))
    if verdict["undeclared_ungated"]:
        reasons.append("%d undeclared un-gated op(s)" % len(verdict["undeclared_ungated"]))
    print("RESULT: FAIL - " + "; ".join(reasons))
    return 1


if __name__ == "__main__":
    sys.exit(main())
