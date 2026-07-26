"""FAKE-HOU PLANTER CENSUS — producer for the planter classification (Law 2).

Walks ``tests/`` with the AST and classifies every ``sys.modules["hou"] = ...``
assignment by the protection around it:

    deferred          guarded by ``if "hou" not in sys.modules`` -> safe under
                      hython, because real ``hou`` is already resident and the
                      branch is not taken.
    restore_sentinel  swap-and-restore whose restore is guarded on the
                      ``__synapse_canonical__`` sentinel. Real ``hou`` does not
                      carry that sentinel, so the restore is SKIPPED under
                      hython and the fake stays resident. POISONER.
    restore_plain     swap-and-restore with an unconditional restore. Safe.
    bare              unconditional plant with no visible restore. POISONER.

Run:  python harness/notes/residency_census.py [--json out.json]

Falsifier: a file classified ``deferred`` that the live residency trace shows
swapping the resident is a classification bug, and the trace outranks this
script (Article II: observed beats derived).
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


def _is_sys_modules_hou(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "modules"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "hou"
    )


def _is_hou_assign(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign):
        return False
    return any(_is_sys_modules_hou(t) for t in node.targets)


def _is_hou_eviction(node: ast.AST) -> str | None:
    """EVICTIONS, which the first version of this census could not see.

    It censused ``sys.modules["hou"] = X`` only, so ``sys.modules.pop("hou")``
    and ``del sys.modules["hou"]`` were invisible — and an eviction is the
    strictly more dangerous idiom, because it is the one that lets `hou.py`
    re-execute. `tests/test_marshal_hostile.py` was a live offender that this
    file reported nothing about; the run-level guard caught it instead. An
    instrument that cannot see the worse half of the defect it is named for.
    """
    # del sys.modules["hou"]
    if isinstance(node, ast.Delete) and any(_is_sys_modules_hou(t) for t in node.targets):
        return "del"
    # sys.modules.pop("hou", ...)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pop"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "modules"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "sys"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "hou"
    ):
        return "pop"
    # monkeypatch.delitem(sys.modules, "hou", ...)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "delitem"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "hou"
    ):
        return "monkeypatch.delitem"
    return None


def _classify(path: pathlib.Path) -> list[dict]:
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(path))
    lines = src.splitlines()

    # map: node -> chain of ancestors
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    def ancestors(node: ast.AST):
        cur = node
        while id(cur) in parents:
            cur = parents[id(cur)]
            yield cur

    out: list[dict] = []
    for node in ast.walk(tree):
        kind = _is_hou_eviction(node)
        if kind is not None:
            out.append(
                {
                    "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "line": node.lineno,
                    "src": lines[node.lineno - 1].strip(),
                    "eviction": kind,
                }
            )
            continue
        if not _is_hou_assign(node):
            continue
        chain = list(ancestors(node))
        in_func = any(isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef)) for a in chain)

        # deferred: an enclosing `if "hou" not in sys.modules`
        deferred = False
        for a in chain:
            if isinstance(a, ast.If):
                test = ast.dump(a.test)
                if "'hou'" in test.replace('"', "'") and "NotIn" in test and "modules" in test:
                    deferred = True
        # restore: is this assignment inside a `finally:` / does the file carry
        # a sentinel-guarded restore?
        in_finally = any(
            isinstance(a, ast.Try) and any(node is n or node in ast.walk(n) for n in a.finalbody)
            for a in chain
        )

        out.append(
            {
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "line": node.lineno,
                "src": lines[node.lineno - 1].strip(),
                "module_level": not in_func and not any(isinstance(a, ast.ClassDef) for a in chain),
                "deferred": deferred,
                "in_finally": in_finally,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()

    rows: list[dict] = []
    for path in sorted(TESTS.rglob("*.py")):
        try:
            rows.extend(_classify(path))
        except SyntaxError as exc:  # pragma: no cover
            rows.append({"file": str(path), "error": str(exc)})

    evictions = [r for r in rows if r.get("eviction")]
    rows = [r for r in rows if not r.get("eviction")]

    # File-level verdict.
    by_file: dict[str, dict] = {}
    for r in rows:
        f = r["file"]
        d = by_file.setdefault(f, {"file": f, "plants": 0, "deferred": 0, "restores": 0, "sentinel_restore": False, "lines": []})
        d["plants"] += 1
        d["lines"].append(r["line"])
        if r.get("deferred"):
            d["deferred"] += 1
        if r.get("in_finally"):
            d["restores"] += 1

    for f, d in by_file.items():
        src = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        d["sentinel_restore"] = "__synapse_canonical__" in src and "finally" in src
        plants_unguarded = d["plants"] - d["deferred"] - d["restores"]
        if d["sentinel_restore"] and d["restores"]:
            d["verdict"] = "restore_sentinel_POISONER"
        elif d["restores"] and plants_unguarded <= d["restores"]:
            d["verdict"] = "restore_plain"
        elif d["deferred"] == d["plants"]:
            d["verdict"] = "deferred"
        elif plants_unguarded > 0:
            d["verdict"] = "bare_POISONER"
        else:
            d["verdict"] = "mixed"

    verdicts: dict[str, list[str]] = {}
    for f, d in sorted(by_file.items()):
        verdicts.setdefault(d["verdict"], []).append(f)

    print(f"planter files: {len(by_file)}   assignments: {len(rows)}\n")
    for v in sorted(verdicts):
        print(f"== {v}  ({len(verdicts[v])}) ==")
        for f in verdicts[v]:
            d = by_file[f]
            print(f"   {f}:{d['lines']}  plants={d['plants']} deferred={d['deferred']} restores={d['restores']}")
        print()

    # The half that matters most: an eviction is what lets `hou.py` re-execute.
    sanctioned = "tests/test_hou_reimport_guard.py"
    live = [e for e in evictions if not e["file"].endswith(sanctioned)]
    print(f"== EVICTIONS ({len(evictions)} total, {len(live)} outside the sanctioned exerciser) ==")
    for e in evictions:
        tag = "  [sanctioned]" if e["file"].endswith(sanctioned) else ""
        print(f"   {e['file']}:{e['line']}  {e['eviction']}{tag}\n      {e['src']}")
    if not live:
        print("   none — every eviction outside the pin file is gone.")
    print()

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(
                {"rows": rows, "by_file": by_file,
                 "evictions": evictions, "evictions_outside_sanctioned": live},
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
