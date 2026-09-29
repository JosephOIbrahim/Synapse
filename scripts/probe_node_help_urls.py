"""List every node type's help URL from inside Houdini, for the Identify sweep.

Run it with Houdini's Python::

    hython scripts/probe_node_help_urls.py <out.json>

or, in a live session (the Python Shell, or SYNAPSE's ``houdini_execute_python``)::

    import runpy
    probe = runpy.run_path(r"C:/Users/User/SYNAPSE/scripts/probe_node_help_urls.py")
    result = probe["dump"](r"C:/tmp/node_types.json")

It writes each node type's category, name, ``defaultHelpUrl()``, whether it is
an HDA, and the start of an HDA's embedded help, which is where a summary sits.
It only reads node types; it creates nothing and changes nothing in the scene.
The file feeds ``scripts/sweep_identify_summaries.py --types``.
"""
from __future__ import annotations

import json
import sys

#: Characters of embedded help kept per HDA.
HELP_CHARS = 1200


def node_types() -> list[dict]:
    """One row per node type in every category of this Houdini session."""
    import hou

    rows = []
    for category_name, category in sorted(hou.nodeTypeCategories().items()):
        for name, node_type in sorted(category.nodeTypes().items()):
            row = {"category": category_name, "name": name, "help_url": None,
                   "hda": False, "embedded_help": None}
            try:
                row["help_url"] = node_type.defaultHelpUrl()
                definition = node_type.definition()
                row["hda"] = definition is not None
                if definition is not None:
                    row["embedded_help"] = (definition.embeddedHelp() or "")[:HELP_CHARS] or None
            except hou.Error as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"[:200]
            rows.append(row)
    return rows


def dump(out_path: str) -> dict:
    """Write the node-type list to *out_path*; return a short count."""
    import hou

    rows = node_types()
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump({"houdini": hou.applicationVersionString(), "types": rows}, handle,
                  ensure_ascii=False)
    return {"types": len(rows), "hda": sum(1 for row in rows if row["hda"]),
            "with_help": sum(1 for row in rows if row["embedded_help"]),
            "errors": sum(1 for row in rows if "error" in row), "out": out_path}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: hython scripts/probe_node_help_urls.py <out.json>")
    print(dump(sys.argv[1]))
