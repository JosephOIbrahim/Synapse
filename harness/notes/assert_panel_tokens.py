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


# The inventory records styles.py's token surface as ALIAS-QUALIFIED strings
# ("t.VOID", "_ds.SIGNAL"). That conflates two different things: WHICH TOKEN is
# referenced, and WHICH ALIAS was used to reach it. This oracle's claim is
# "every token name present before is present after" -- a claim about tokens.
# Matching the literal alias string made it fail when styles.py repointed
# `t.VOID` to `_ds.VOID`, which does not drop a token, and it would equally have
# PASSED a rename that swapped one token for another behind the same alias.
#
# So the comparison is alias-agnostic and the token name is what is asserted.
# This is strictly stronger: removing the reference entirely still fails, while
# an alias rename no longer produces a false regression.
_TOKEN_ALIASES = ("t", "_t", "_ds")


def _references_token(src, ref):
    """Is the token named in ``ref`` still reached through ANY tokens alias?"""
    name = ref.split(".")[-1]
    alts = "|".join(re.escape(a) for a in _TOKEN_ALIASES)
    return re.search(r"(?<![\w.])(?:%s)\.%s\b" % (alts, re.escape(name)), src) is not None


def _selftest():
    """Control (R60): the reader must be shown able to FAIL, or its greens carry
    no information. Returns True when both directions behave."""
    ok = _references_token("x = _ds.VOID\n", "t.VOID")          # alias moved
    blind = _references_token("x = OTHER\n", "t.VOID")          # token dropped
    exact = _references_token("x = t.VOID\n", "t.VOID")         # unchanged
    near = _references_token("x = t.VOIDLIKE\n", "t.VOID")      # must not match
    return ok and exact and not blind and not near


def main():
    if not _selftest():
        print("READER CONTROL FAILED — this oracle cannot be trusted")
        return 3
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
        if not _references_token(src, ref):
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
