"""Measure what class-level introspection of hou.Node can and cannot see.

The release note for v5.97.7 argues that `dir(hou.Node)` is not a valid
phantom test: the class exposes 146 members, `hasattr(hou.Node, "parm")` is
False, and yet "parm" in dir(node_instance) is True and node.parm("snippet")
works. A phantom test written against the CLASS therefore produces false
positives and false negatives on the same class.

This probe does not argue that. It measures the live build and records what it
found, because the argument is only worth as much as its producer. Before this
probe the only producing records in the tree were stamped 22.0.368; the
22.0.400 attribution had none.

It also checks the repo's own committed symbol table - the file this project
treats as its existence authority - for the same blind spot.

WHAT THIS PROBE ESTABLISHED (Houdini 22.0.400):

  The committed receipt is harness/probes/hou_node_class_dir_receipt.json.
  Every number below is in it, with the build and the comparison that produced
  it. This docstring summarises; the receipt is the evidence.

  - The class-level dir() has 146 members. A live geo node's instance-level
    dir() has 347, and the class list is a STRICT SUBSET of the instance
    list on this build: every class member is also an instance member, and
    the instance list carries 201 that the class list does not. The
    disagreement is one-directional, and that is the point - a class-level
    phantom test produces FALSE NEGATIVES, members that exist and work and
    are missing from the class list.
  - `parm`, `setParms` and `cook` are three of those 201, and all three work
    when called on the instance.
  - `addParm` is missing from BOTH lists, for a different reason: it is not a
    hou.Node member at all. A parameter is added through
    parmTemplateGroup() - which is itself instance-only - and not through the
    node. Quoting it as an instance member would be a second, different
    error.
  - The committed symbol table carries 116 `hou.Node.*` names out of 36,472
    symbols, and `hou.Node.parm` is NOT one of them. The blind spot is in the
    authority itself, not only in an ad-hoc probe.

Run:
  hython -s -P harness/probes/hou_node_class_dir_probe.py --receipt harness/probes/hou_node_class_dir_receipt.json

Exit code 0 means the build was measured. The receipt is written only when
--receipt names a path; without it the probe prints its findings and writes
nothing. Exit code 1 means the build could not be measured - the receipt is
then not written, because a receipt nobody can stand behind is worse than none.

THE RECEIPT:
  --receipt <path> writes the findings as JSON. The receipt records the
  build, the class-level and instance-level member lists, which candidate
  members each one carries, and the symbol-table check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The members this project has actually been bitten by, plus one that is
# absent for a different reason. CANDIDATES is a list of NAMES, and the
# receipt records for each one where it appears - not what we hoped.
CANDIDATES = (
    "parm",
    "setParms",
    "cook",
    "addParm",
    "parmTemplateGroup",
    "children",
    "node",
)


def _receipt_path() -> Path | None:
    for i, arg in enumerate(sys.argv):
        if arg == "--receipt" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
    return None


def _symbol_table_check() -> dict:
    """Does the committed symbol table carry the members the class dir misses?"""
    table = ROOT / "python" / "synapse" / "cognitive" / "tools" / "data" / "h22_symbol_table.json"
    if not table.is_file():
        return {"checked": False, "reason": "symbol table not present at %s" % table}
    data = json.loads(table.read_text(encoding="utf-8"))
    symbols = data.get("symbols", [])
    node_symbols = [s for s in symbols if s.startswith("hou.Node.")]
    return {
        "checked": True,
        "path": str(table.relative_to(ROOT)).replace("\\", "/"),
        "houdini_version": data.get("houdini_version"),
        "total_symbols": len(symbols),
        "hou_node_symbol_count": len(node_symbols),
        "hou_node_symbols": sorted(node_symbols),
        "present": {name: ("hou.Node.%s" % name) in node_symbols for name in CANDIDATES},
    }


def main() -> int:
    try:
        import hou
    except ImportError:
        sys.stderr.write("hou is not importable - run this under hython 22.0.400\n")
        return 1

    try:
        class_members = set(dir(hou.Node))
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write("dir(hou.Node) failed: %s\n" % exc)
        return 1

    instance_members: set[str] = set()
    node = None
    try:
        node = hou.node("/obj").createNode("geo")
        instance_members = set(dir(node))
    except Exception as exc:
        sys.stderr.write("could not create a live node for the instance check: %s\n" % exc)

    # The instance check that decides the argument: not "is the name in the
    # dir()", but "does calling it work".
    callable_on_instance = {}
    if node is not None:
        for name, call in (
            ("parm", lambda: node.parm("snippet")),
            ("setParms", lambda: node.setParms({})),
            ("cook", lambda: node.cook(force=False)),
            ("addParm", lambda: node.addParm(hou.FloatParmTemplate("probe_p", "probe", 1))),
        ):
            try:
                call()
                callable_on_instance[name] = True
            except Exception:
                callable_on_instance[name] = False

    rec = {
        "probe": "hou_node_class_dir",
        "houdini_version": hou.applicationVersionString(),
        "houdini_build": "%d.%d.%d" % hou.applicationVersion(),
        "class_dir_len": len(class_members),
        "instance_dir_len": len(instance_members),
        "instance_probe": "a live geo node under /obj",
        "candidates": {
            name: {
                "in_class_dir": name in class_members,
                "in_instance_dir": name in instance_members,
                "callable_on_instance": callable_on_instance.get(name),
            }
            for name in CANDIDATES
        },
        "class_only": sorted(class_members - instance_members) if instance_members else [],
        "instance_only": sorted(instance_members - class_members) if instance_members else [],
        "symbol_table": _symbol_table_check(),
    }

    out = _receipt_path()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                       encoding="utf-8")
        print("receipt: %s" % out)

    print("hou.Node class dir: %d members" % rec["class_dir_len"])
    if instance_members:
        print("live instance dir: %d members" % rec["instance_dir_len"])
    for name, row in rec["candidates"].items():
        print("  %-18s class=%-5s instance=%-5s callable=%s"
              % (name, row["in_class_dir"], row["in_instance_dir"], row["callable_on_instance"]))
    st = rec["symbol_table"]
    if st.get("checked"):
        print("symbol table: %d hou.Node.* names, hou.Node.parm present=%s"
              % (st["hou_node_symbol_count"], st["present"].get("parm")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
