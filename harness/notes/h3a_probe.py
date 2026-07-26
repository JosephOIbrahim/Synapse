"""H3a symbol-existence probe — read-only, controlled, interpreter-agnostic.

Answers exactly ONE question per symbol: **does it exist on this build?**
It does not judge whether the symbol should be used. (Article IV — `assayer`
answers existence; disposition is somebody else's job.)

Producer path (Law 2): this file. Invoke as

    hython3.13 harness/notes/h3a_probe.py --symbols <manifest.json> --out <result.json>

or, inside a live Houdini session, import it and call ``probe_all(...)``.

WHY THE CONTROLS EXIST (Law 1 — state the condition under which this fails):

  * POSITIVE control — ``hou.node`` must resolve to EXISTS. If it does not,
    the resolver itself is broken and every ABSENT verdict in the run is a
    false negative. This is the L1.F1 error class: nine probe failures that
    were one misconfigured probe.
  * NEGATIVE control — ``hou.zzz_h3a_control_must_not_exist`` and the four
    quarantined phantoms (``hou.pdg``, ``hou.secure``, ``hou.lopNetworks``,
    ``hou.updateGraphTick``) must all resolve to ABSENT. If any reports
    EXISTS, the resolver is answering yes to everything and every CONFIRMED
    verdict is worthless.

If EITHER control set fails, the run is stamped ``controls_ok: false`` and the
process exits non-zero. A result file with ``controls_ok: false`` is
UNINTERPRETABLE and must not be cited as evidence.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import platform
import sys
import threading

# --- controls -------------------------------------------------------------

POSITIVE_CONTROLS = [
    "hou.node",              # the most-used HOM entry point in the tree
    "hou.Node.type",         # bound-method resolution through a class
    "hou.undos.group",       # resolution through a submodule
]

# Four quarantined phantoms (AGENT_CONSTITUTION Article II) + one synthetic
# name that cannot exist by construction.
NEGATIVE_CONTROLS = [
    "hou.zzz_h3a_control_must_not_exist",
    "hou.pdg",
    "hou.secure",
    "hou.lopNetworks",
    "hou.updateGraphTick",
]

# Root modules the resolver is permitted to import.
_ROOTS = ("hou", "pdg", "hdefereval", "husk", "toolutils", "loputils")


def _import_root(name):
    """Import a root module. Returns (module, error_string_or_None)."""
    try:
        return __import__(name), None
    except Exception as exc:  # noqa: BLE001 - the error text IS the evidence
        return None, "%s: %s" % (type(exc).__name__, exc)


def _near_misses(parent, missing_name, limit=5):
    """dir()-anchored evidence for an ABSENT verdict.

    Returns the closest existing names on the parent. This is what makes an
    ABSENT verdict citable: not 'I looked and did not find it' but 'here is
    the namespace I looked in and the nearest things actually in it'.
    """
    try:
        names = dir(parent)
    except Exception:  # noqa: BLE001
        return [], 0
    return difflib.get_close_matches(missing_name, names, n=limit, cutoff=0.5), len(names)


def probe_symbol(dotted):
    """Resolve one dotted symbol. Returns a verdict dict.

    verdict is one of:
      EXISTS        — every segment resolved; final object obtained
      ABSENT        — a segment resolved cleanly to 'not present' (AttributeError)
      UNVERIFIABLE  — the root module would not import, or a segment raised
                      something other than AttributeError (cannot distinguish
                      'missing' from 'broken here')
    """
    parts = dotted.split(".")
    root_name = parts[0]
    rec = {
        "symbol": dotted,
        "verdict": None,
        "resolved_through": root_name,
        "evidence": None,
        "type": None,
        "signature": None,
        "dir_size_of_parent": None,
        "near_misses": None,
    }

    if root_name not in _ROOTS:
        rec["verdict"] = "UNVERIFIABLE"
        rec["evidence"] = "root module %r not in the probe allowlist %r" % (root_name, _ROOTS)
        return rec

    obj, err = _import_root(root_name)
    if obj is None:
        rec["verdict"] = "UNVERIFIABLE"
        rec["evidence"] = "import %s failed -> %s" % (root_name, err)
        return rec

    walked = root_name
    for seg in parts[1:]:
        parent = obj
        try:
            has = hasattr(parent, seg)
        except Exception as exc:  # noqa: BLE001
            rec["verdict"] = "UNVERIFIABLE"
            rec["evidence"] = "hasattr(%s, %r) raised %s: %s" % (
                walked, seg, type(exc).__name__, exc
            )
            return rec
        if not has:
            misses, dirsize = _near_misses(parent, seg)
            rec["verdict"] = "ABSENT"
            rec["resolved_through"] = walked
            rec["dir_size_of_parent"] = dirsize
            rec["near_misses"] = misses
            rec["evidence"] = (
                "%r not in dir(%s) (%d names); nearest existing: %s"
                % (seg, walked, dirsize, misses or "none within cutoff 0.5")
            )
            return rec
        try:
            obj = getattr(parent, seg)
        except Exception as exc:  # noqa: BLE001
            rec["verdict"] = "UNVERIFIABLE"
            rec["evidence"] = "getattr(%s, %r) raised %s: %s" % (
                walked, seg, type(exc).__name__, exc
            )
            return rec
        walked = walked + "." + seg

    rec["verdict"] = "EXISTS"
    rec["resolved_through"] = walked
    try:
        rec["type"] = type(obj).__name__
    except Exception:  # noqa: BLE001
        pass
    try:
        import inspect

        rec["signature"] = str(inspect.signature(obj))
    except Exception:  # noqa: BLE001
        # HOM is SWIG-wrapped; many callables have no introspectable
        # signature. That is not a failure of the existence question.
        rec["signature"] = None
    try:
        doc = getattr(obj, "__doc__", None)
        if doc:
            rec["evidence"] = "resolved; __doc__[:160]=%r" % (doc[:160],)
        else:
            rec["evidence"] = "resolved; type=%s" % (rec["type"],)
    except Exception:  # noqa: BLE001
        rec["evidence"] = "resolved"
    return rec


def _interpreter_fingerprint():
    fp = {
        "executable": sys.executable,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "thread_is_main": threading.current_thread() is threading.main_thread(),
        "hfs": os.environ.get("HFS"),
    }
    try:
        import hou

        fp["houdini_build"] = hou.applicationVersionString()
        try:
            fp["ui_available"] = bool(hou.isUIAvailable())
        except Exception:  # noqa: BLE001
            fp["ui_available"] = None
        fp["has_hou_ui"] = hasattr(hou, "ui")
    except Exception as exc:  # noqa: BLE001
        fp["houdini_build"] = None
        fp["hou_import_error"] = "%s: %s" % (type(exc).__name__, exc)
    return fp


def probe_all(symbols, group=None):
    """Probe a list of dotted symbols with controls. Returns the full record."""
    pos = [probe_symbol(s) for s in POSITIVE_CONTROLS]
    neg = [probe_symbol(s) for s in NEGATIVE_CONTROLS]

    pos_ok = all(r["verdict"] == "EXISTS" for r in pos)
    neg_ok = all(r["verdict"] == "ABSENT" for r in neg)
    controls_ok = pos_ok and neg_ok

    results = [probe_symbol(s) for s in symbols]

    return {
        "schema": "h3a_probe/v1",
        "producer": "harness/notes/h3a_probe.py",
        "group": group,
        "interpreter": _interpreter_fingerprint(),
        "controls_ok": controls_ok,
        "controls": {
            "positive_ok": pos_ok,
            "negative_ok": neg_ok,
            "positive": pos,
            "negative": neg,
            "failure_condition": (
                "positive_ok is False if any of %s reports != EXISTS; "
                "negative_ok is False if any of %s reports != ABSENT. "
                "controls_ok False => the whole run is UNINTERPRETABLE."
                % (POSITIVE_CONTROLS, NEGATIVE_CONTROLS)
            ),
        },
        "counts": {
            "total": len(results),
            "EXISTS": sum(1 for r in results if r["verdict"] == "EXISTS"),
            "ABSENT": sum(1 for r in results if r["verdict"] == "ABSENT"),
            "UNVERIFIABLE": sum(1 for r in results if r["verdict"] == "UNVERIFIABLE"),
        },
        "results": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="H3a symbol-existence probe")
    ap.add_argument("--symbols", help="path to a JSON file: {group: [dotted, ...]} or [dotted, ...]")
    ap.add_argument("--group", help="probe only this group key from the manifest")
    ap.add_argument("--symbol", action="append", default=[], help="probe a single dotted symbol (repeatable)")
    ap.add_argument("--out", help="write the JSON record here (also printed to stdout)")
    ap.add_argument("--self-test", action="store_true",
                    help="run controls only and assert they behave; exits 1 if the probe cannot fail")
    args = ap.parse_args(argv)

    symbols = list(args.symbol)
    group = args.group
    if args.symbols:
        with open(args.symbols, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        if isinstance(manifest, dict):
            entries = manifest.get("groups", manifest)
            if args.group:
                symbols.extend([e["symbol"] if isinstance(e, dict) else e
                                for e in entries[args.group]])
            else:
                for key in entries:
                    symbols.extend([e["symbol"] if isinstance(e, dict) else e
                                    for e in entries[key]])
        else:
            symbols.extend([e["symbol"] if isinstance(e, dict) else e for e in manifest])

    if args.self_test:
        rec = probe_all([])
        print(json.dumps(rec, indent=2))
        return 0 if rec["controls_ok"] else 1

    rec = probe_all(symbols, group=group)
    payload = json.dumps(rec, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
    print(payload)
    return 0 if rec["controls_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
