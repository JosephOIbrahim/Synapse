#!/usr/bin/env python
"""Third-process scene verifier for the outside-in benchmark.

Opens the SAVED SCENE in a hython that is NEITHER arm's process and evaluates the
prompt's ``check`` block with plain ``hou``. It NEVER reads either arm's transcript,
final text, or success report -- the ONLY inputs are the scene path and the check
block. This is the outside-in form of SYNAPSE's truth contract: an arm that prints
"Task complete." over a scene that does not satisfy the check still FAILs here,
because its words never reach this process.

Producer / invocation (run.py drives this as a separate process):
    hython harness/outside_in/verify.py --scene <arm_scene.hip> --check @<check.json>

Output: one JSON object on stdout::
    {"verdict": "PASS"|"FAIL"|"ERROR", "checks": [{...}], "scene": "<path>", "reason": "..."}

verdict is decided ONLY from ``hou`` queries against the scene. No arm input exists.
Source: HARVEST_SPEC.md sec 'Target 3' (Verification independence); ADR-0001 Site 3.
"""
from __future__ import annotations

import argparse
import json
import sys

try:  # production: inside hython. standalone/CI: hou absent -> accessor is injected.
    import hou  # type: ignore
    HOU_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only outside Houdini
    hou = None  # type: ignore
    HOU_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Accessor: the ONLY bridge between a check and the scene. A check key maps to a
# high-level query here; nothing in this layer can see an arm's report because an
# arm's report is never passed to it. Tests inject a fake accessor with the same
# surface, so the pass/fail logic is provable without a live Houdini.
# --------------------------------------------------------------------------- #
class HouAccessor:
    """Wraps ``hou`` for the four check kinds. Every method fails soft to a clear
    detail string; a missing API never raises past this layer."""

    def __init__(self, root: str = "/"):
        self._root = root

    def _all(self):
        try:
            return hou.node(self._root).allSubChildren()
        except Exception:  # noqa: BLE001
            return []

    def _by_type(self, type_name: str, under: str | None):
        base = self._root if not under else under
        try:
            node = hou.node(base)
            nodes = node.allSubChildren() if node else []
        except Exception:  # noqa: BLE001
            nodes = []
        out = []
        for n in nodes:
            try:
                if n.type().name() == type_name:
                    out.append(n)
            except Exception:  # noqa: BLE001
                continue
        return out

    def count_type(self, type_name: str, under: str | None = None) -> int:
        return len(self._by_type(type_name, under))

    def parm_on_type(self, type_name: str, name: str):
        for n in self._by_type(type_name, None):
            try:
                p = n.parm(name)
                if p is not None:
                    return True, p.eval()
            except Exception:  # noqa: BLE001
                continue
        return False, None

    def cook_type(self, type_name: str):
        nodes = self._by_type(type_name, None)
        if not nodes:
            return False, False, "no node of that type"
        for n in nodes:
            try:
                n.cook(force=True)
                return True, True, ""
            except hou.Error as e:  # type: ignore  # cook error is the failure we test
                return True, False, str(e)[:200]
            except Exception as e:  # noqa: BLE001
                return True, False, f"{type(e).__name__}: {e}"[:200]
        return True, False, "uncooked"

    def attrib_on_type(self, type_name: str, geo_class: str, name: str):
        nodes = self._by_type(type_name, None)
        if not nodes:
            return False, False, "no node of that type"
        getter = {
            "point": "pointAttribs", "prim": "primAttribs",
            "vertex": "vertexAttribs", "detail": "globalAttribs",
        }.get(geo_class, "pointAttribs")
        for n in nodes:
            try:
                geo = n.geometry()
                if geo is None:
                    continue
                names = {a.name() for a in getattr(geo, getter)()}
                return True, (name in names), ("present" if name in names else f"have {sorted(names)[:8]}")
            except Exception as e:  # noqa: BLE001
                return True, False, f"{type(e).__name__}: {e}"[:200]
        return True, False, "no geometry"


# --------------------------------------------------------------------------- #
# Pure logic: check block + accessor -> verdict. No hou, no arm text.
# --------------------------------------------------------------------------- #
def evaluate_check(check: dict, acc) -> dict:
    results: list[dict] = []

    for spec in check.get("nodes", []) or []:
        tname = spec["type"]
        need = int(spec.get("min", 1))
        got = acc.count_type(tname, spec.get("under"))
        results.append({"kind": "nodes", "type": tname, "min": need, "got": got, "ok": got >= need})

    if "parm" in check:
        p = check["parm"]
        found, val = acc.parm_on_type(p["type"], p["name"])
        want = p.get("equals")
        tol = float(p.get("tol", 0.0))
        if not found:
            ok, detail = False, "parm/node not found"
        elif want is None:
            ok, detail = True, f"present={val!r}"
        else:
            try:
                ok = abs(float(val) - float(want)) <= tol
            except (TypeError, ValueError):
                ok = str(val) == str(want)
            detail = f"got={val!r} want={want!r} tol={tol}"
        results.append({"kind": "parm", "type": p["type"], "name": p["name"], "ok": ok, "detail": detail})

    if "cook" in check:
        c = check["cook"]
        found, ok, err = acc.cook_type(c["type"])
        results.append({"kind": "cook", "type": c["type"], "ok": bool(found and ok), "detail": err or "cooked"})

    if "attrib" in check:
        a = check["attrib"]
        found, present, detail = acc.attrib_on_type(a["type"], a.get("class", "point"), a["name"])
        results.append({"kind": "attrib", "type": a["type"], "class": a.get("class", "point"),
                        "name": a["name"], "ok": bool(found and present), "detail": detail})

    checked = [r for r in results]
    if not checked:
        return {"verdict": "ERROR", "checks": [], "reason": "empty check block"}
    verdict = "PASS" if all(r["ok"] for r in checked) else "FAIL"
    return {"verdict": verdict, "checks": checked,
            "reason": "all checks satisfied" if verdict == "PASS"
            else "; ".join(f"{r['kind']}:{r.get('type', r.get('name'))} failed" for r in checked if not r["ok"])}


def _load_check(raw: str) -> dict:
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as f:
            return json.load(f)
    return json.loads(raw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Independent third-process scene verifier.")
    ap.add_argument("--scene", required=True, help="path to the SAVED .hip written by an arm")
    ap.add_argument("--check", required=True, help="check block as JSON, or @path to a JSON file")
    ap.add_argument("--root", default="/", help="scene root to search (default /)")
    args = ap.parse_args(argv)

    check = _load_check(args.check)

    if not HOU_AVAILABLE:
        print(json.dumps({"verdict": "ERROR", "checks": [], "scene": args.scene,
                          "reason": "hou unavailable: verify.py must run under hython"}))
        return 2

    try:
        hou.hipFile.load(args.scene, suppress_save_prompt=True, ignore_load_warnings=True)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"verdict": "ERROR", "checks": [], "scene": args.scene,
                          "reason": f"could not open scene: {type(e).__name__}: {e}"[:300]}))
        return 2

    out = evaluate_check(check, HouAccessor(args.root))
    out["scene"] = args.scene
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
