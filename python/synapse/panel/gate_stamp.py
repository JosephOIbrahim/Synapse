"""M3-A: is the phantom-API gate armed for THIS Houdini build?

A Houdini build change silently disarms synapse_scout's membership gate —
the symbol table is build-stamped and a mismatch degrades every verdict to
None with one console warning. This module gives the panel a loud, honest
answer: a reason string when the gate is stale/down, None when it's fine
OR when we can't verify (claim nothing without observation — and never
block panel boot).

Qt-free; mirrors scout's own staleness logic so panel and tool can never
disagree.
"""

from typing import Optional


def phantom_gate_status(running_version: Optional[str] = None) -> Optional[str]:
    """Reason the phantom-API gate is stale/down, or None (armed or unknowable)."""
    try:
        if running_version is None:
            import hou  # host-side read; scout itself stays zero-hou
            running_version = hou.applicationVersionString()
        if not isinstance(running_version, str) or not running_version:
            return None

        from synapse.cognitive.tools import scout

        rec = scout._read_symbol_table(scout._symbol_table_path())
        if rec["stale"]:
            return rec["reason"]
        stamped = rec["meta"].get("houdini_version")
        if stamped != running_version:
            return f"symbol table {stamped} != running {running_version}"
        return None
    except Exception:
        return None  # cannot verify -> claim nothing; never break the panel
