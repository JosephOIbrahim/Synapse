"""FAKE-HOU RESIDENCY TRACER — a pytest plugin, not a test.

Producer for the residency map (Law 2). Records every identity transition of
``sys.modules['hou']`` across a run, tagged with the collection/run event that
was in flight when the swap became visible.

Usage (shipping interpreter):

    hython3.13 -m pytest tests/ -q --continue-on-collection-errors \
        -p no:cacheprovider -p harness.notes.residency_trace

Output path from ``$RESIDENCY_TRACE_OUT`` (default ``residency_trace.json``).

What it can report that would falsify the leg's hypothesis: a run in which the
resident never changes from the real ``hou`` yet the AttributeError still
fires. That would refute residency as the mechanism outright.
"""

from __future__ import annotations

import json
import os
import sys

_LOG: list[dict] = []
_state: dict = {"cur": "<unset>", "parm": "<unset>"}
_REAL: dict = {"mod": None}


def _sig(mod) -> dict:
    if mod is None:
        return {"kind": "None"}
    return {
        "kind": type(mod).__name__,
        "id": hex(id(mod)),
        "canonical": bool(getattr(mod, "__synapse_canonical__", False)),
        "file": getattr(mod, "__file__", None),
        "has_Parm": hasattr(mod, "Parm"),
        "Parm_has_set": hasattr(getattr(mod, "Parm", None), "set"),
    }


def _parm_sig() -> dict:
    """State of ``Parm`` ON THE REAL MODULE OBJECT captured at configure.

    Tracks class *mutation* independently of module *replacement*: a test may
    leave sys.modules['hou'] untouched and still rebind ``hou.Parm``.
    """
    real = _REAL["mod"]
    if real is None:
        return {"kind": "no-real-hou"}
    P = getattr(real, "Parm", None)
    return {
        "id": hex(id(P)) if P is not None else None,
        "name": getattr(P, "__name__", None),
        "has_set": hasattr(P, "set"),
        "n_attrs": len(dir(P)) if P is not None else 0,
    }


def _check(where: str) -> None:
    cur = sys.modules.get("hou")
    if cur is not _state["cur"]:
        _LOG.append(
            {
                "kind": "module_swap",
                "where": where,
                "from": _sig(_state["cur"]) if _state["cur"] != "<unset>" else None,
                "to": _sig(cur),
            }
        )
        _state["cur"] = cur
    pid = _parm_sig()
    if pid != _state["parm"]:
        _LOG.append(
            {
                "kind": "Parm_mutation",
                "where": where,
                "from": _state["parm"] if _state["parm"] != "<unset>" else None,
                "to": pid,
            }
        )
        _state["parm"] = pid


def pytest_configure(config):  # noqa: D103
    _state["cur"] = "<unset>"
    _state["parm"] = "<unset>"
    mod = sys.modules.get("hou")
    # Only a file-backed real `hou` is worth watching for class mutation.
    if mod is not None and getattr(mod, "__file__", None) and not getattr(mod, "__synapse_canonical__", False):
        _REAL["mod"] = mod
    _check("<configure>")


def pytest_collectstart(collector):  # noqa: D103
    _check(f"collectstart:{getattr(collector, 'nodeid', '?')}")


def pytest_itemcollected(item):  # noqa: D103
    _check(f"itemcollected:{item.nodeid}")


def pytest_collection_finish(session):  # noqa: D103
    _check("collection_finish")


def pytest_runtest_logstart(nodeid, location):  # noqa: D103
    _check(f"start:{nodeid}")


def pytest_runtest_logfinish(nodeid, location):  # noqa: D103
    _check(f"finish:{nodeid}")


def pytest_sessionfinish(session, exitstatus):  # noqa: D103
    _check("sessionfinish")
    out = os.environ.get("RESIDENCY_TRACE_OUT", "residency_trace.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"transitions": _LOG, "count": len(_LOG)}, fh, indent=2)
    print(f"\n[residency_trace] {len(_LOG)} transitions -> {out}")
