"""L4 ORACLE: every token name in panel_token_inventory_before.json must still
exist after the skin pass. Additive-only is legal; deletion is not.

Run:  python harness/notes/assert_panel_tokens.py
Exit 0 = all 162 accounted for.
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEFORE = os.path.join(ROOT, "harness", "notes", "panel_token_inventory_before.json")
DS_TOKENS = os.path.join(ROOT, "python", "synapse", "panel", "designsystem", "tokens.py")


def _module_names(path):
    """Top-level assigned/def/imported names in a module (no import required)."""
    src = open(path, "r", encoding="utf-8").read()
    tree = ast.parse(src, filename=path)
    names = set()
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, (ast.Try, ast.If)):
            stack.extend(node.body)
            stack.extend(node.orelse)
            stack.extend(getattr(node, "handlers", []))
        elif isinstance(node, ast.ExceptHandler):
            stack.extend(node.body)
    if re.search(r"^from .*tokens import \*", src, re.M) and path != DS_TOKENS:
        names |= _module_names(DS_TOKENS)
    return names


def main():
    inv = json.load(open(BEFORE, encoding="utf-8"))
    missing = []
    checked = 0   # the 162: 86 ds tokens + 40 tokens_py tokens + 36 styles refs
    extra_ok = 0  # re-exports — asserted too, but NOT part of the 162 count

    for key in ("designsystem_tokens_py", "tokens_py"):
        sec = inv[key]
        have = _module_names(os.path.join(ROOT, *sec["path"].split("/")))
        for name in sec.get("tokens", []):
            checked += 1
            if name not in have:
                missing.append("%s :: %s" % (sec["path"], name))
        for name in sec.get("reexported_from_user_design_dir", []):
            extra_ok += 1
            if name not in have:
                missing.append("%s :: reexport %s" % (sec["path"], name))

    sec = inv["styles_py"]
    src = open(os.path.join(ROOT, *sec["path"].split("/")), encoding="utf-8").read()
    for ref in sec["token_references"]:
        checked += 1
        if not re.search(r"(?<![\w.])" + re.escape(ref) + r"\b", src):
            missing.append("%s :: reference %s" % (sec["path"], ref))

    print("token inventory before : %d names (commit %s)" % (inv["count"], inv["commit"]))
    print("names asserted         : %d  (+%d re-exports)" % (checked, extra_ok))
    print("missing after L4       : %d" % len(missing))
    for m in missing:
        print("   MISSING  " + m)
    if checked != inv["count"]:
        print("COUNT MISMATCH: asserted %d != inventory count %d" % (checked, inv["count"]))
        return 2
    print("RESULT: " + ("ALL %d PRESENT" % checked if not missing else "REGRESSION"))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
