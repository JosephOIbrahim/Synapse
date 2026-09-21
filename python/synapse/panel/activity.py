"""Readable labels for observed worker/tool events, never inferred reasoning.

``tool_label`` receives a TOOL NAME -- column 1 of the registry tuples in
``synapse/mcp/_tool_registry.py``, which is what ``claude_worker`` emits as
``tool_status(tool_name, status, summary)``. It is NOT the wire command name,
column 2. Four curated keys were written against column 2 and so matched nothing;
``test_activity_labels.py`` now pins every key against the live registry so the
map cannot go stale in silence again.

The derivation below is the label for the other ~120 tools. It has to be right,
because it is what an artist reads for almost everything: the curated map is the
exception, not the rule.
"""

from synapse.core.tool_results import UNDO_RECEIPT_PREFIX, undo_receipt_line

#: Separates the undo receipt from the rest of a tool's detail string.
UNDO_RECEIPT_SEP = " \u00b7 "

#: Namespaces an artist never needs to read. ``houdini_`` alone was stripped
#: before, so ``synapse_``/``cops_``/``tops_`` tools led with a namespace.
_PREFIXES = ("houdini_", "synapse_", "cops_", "tops_")

#: Domain words a naive ``.capitalize()`` destroys -- it lowercases everything
#: after the first character, so ``houdini_create_usd_prim`` shipped to artists
#: as "Create usd prim".
_PROPER = {
    "usd": "USD", "hda": "HDA", "hdas": "HDAs", "vex": "VEX", "xpu": "XPU",
    "aovs": "AOVs", "opencl": "OpenCL", "materialx": "MaterialX",
    "karma": "Karma", "solaris": "Solaris", "megascans": "Megascans",
    "pdg": "PDG", "mcp": "MCP", "cop": "COP", "cops": "COPs", "top": "TOP",
    "tops": "TOPs", "lop": "LOP", "sop": "SOP", "rop": "ROP",
    "python": "Python",
}

#: Abbreviations expanded to the word an artist would say. TONE.md: use the
#: technical term when it is the right word, never as a barrier. ``primvar``
#: is deliberately absent -- it IS the right word and has no plain synonym.
_PLAIN = {
    "parm": "parameter", "parms": "parameters",
    "prim": "primitive", "prims": "primitives",
    "matlib": "material library", "copnet": "COP network",
    "info": "information", "stats": "statistics",
    "shotsetup": "shot setup", "loadstate": "load state",
}

#: Curated only where the derivation would read worse than a human sentence.
#: Every key is asserted live against the registry by the pinning test.
_TOOLS = {
    "synapse_ping": "Check the Houdini connection",
    "houdini_scene_info": "Read scene context",
    "houdini_create_node": "Create a node",
    "houdini_set_parm": "Set a parameter",
    "houdini_network_explain": "Read the network",
    "houdini_undo": "Undo the last change",
    "houdini_capture_viewport": "Capture the viewport",
    "synapse_recall": "Recall saved context",
}


def tool_label(name):
    """A tool name as an artist should read it.

    Namespace stripped, abbreviations expanded, domain capitals restored, and
    only the first word capitalised -- capitalising a later word yields Title
    Case fragments like "HDA Create".

    The result stays mechanically reversible to the tool id for every tool
    whose words survive unexpanded, which is what keeps a label citable.
    """
    text = str(name or "tool")
    curated = _TOOLS.get(text)
    if curated:
        return curated
    for prefix in _PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    words = []
    for word in text.split("_"):
        words.extend(_PLAIN.get(word, word).split())
    out = [_PROPER.get(word.lower(), word) for word in words]
    if out and out[0] == out[0].lower():
        out[0] = out[0][:1].upper() + out[0][1:]
    return " ".join(out)


def with_undo_receipt(detail, result):
    """Put a result's undo receipt in front of a tool's detail string.

    The worker's ``tool_status`` signal carries one string. The receipt rides
    at the front so ``tool_status`` can show it; the original detail (the
    request summary, node paths) survives after the separator for review.
    """
    receipt = undo_receipt_line(result)
    text = "" if detail is None else str(detail)
    if not receipt:
        return text
    return receipt + (UNDO_RECEIPT_SEP + text if text else "")


def split_undo_receipt(detail):
    """``(receipt, rest)`` -- receipt is ``""`` unless the detail leads with one."""
    text = "" if detail is None else str(detail)
    if not text.startswith(UNDO_RECEIPT_PREFIX):
        return "", text
    receipt, _sep, rest = text.partition(UNDO_RECEIPT_SEP)
    return receipt, rest


def tool_status(name, phase, detail=None):
    """The status line for a tool event; carries the undo receipt when the
    detail leads with one (TRUST-2), otherwise exactly the old prefix + label.

    BP9-WORKER: on the error/failed phase the detail is the failure REASON
    (``translate_tool_error`` output from the worker) and is rendered as
    ``Failed: <label> - <detail>`` so the artist sees why. Receipts unchanged.
    """
    prefix = {"running": "Running", "done": "Finished", "ok": "Finished",
              "error": "Failed", "failed": "Failed"}.get(phase, "Status")
    line = "%s: %s" % (prefix, tool_label(name))
    receipt, rest = split_undo_receipt(detail)
    if receipt:
        line = "%s \u2014 %s" % (line, receipt)
    elif phase in ("error", "failed") and rest:
        line = "%s - %s" % (line, rest)
    return line
