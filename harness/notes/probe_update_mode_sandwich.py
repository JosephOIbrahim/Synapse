#!/usr/bin/env python
"""F1 probe — gate before the update-mode sandwich ships (spec: probe items a-d).

RUN-BY-JOE, live on Houdini 22.0.400 GUI session:

    From a Hython GUI session (or the Houdini Python shell in a GUI session):
        exec(open("<repo>/harness/notes/probe_update_mode_sandwich.py",
                  encoding="utf-8").read())

    Headless hython is a SKIP by design — the sandwich is GUI-only, so the
    probe requires hou.isUIAvailable(). It still validates (a) symbol
    existence headlessly, then reports the rest as SKIP-needs-GUI.

What it establishes, per spec:

    (a) symbols exist on 22.0.400:
        hou.updateModeSetting, hou.setUpdateMode, hou.updateMode.Manual,
        hou.ui.triggerUpdate, hou.isUIAvailable, hou.undos.group.
    (b) Manual -> mutate -> restore + hou.ui.triggerUpdate() produces
        exactly ONE consolidated downstream cook (cookCount delta == 1 on
        the probe chain's display node).
    (c) a hou.undos.group open ACROSS the sandwich does not swallow artist
        edits: an edit made inside (undo-group outer, sandwich inner) is
        present after the group closes and is undone by ONE performUndo.
    (d) nested payload setUpdateMode restores to the PRE-SANDWICH mode,
        not to Manual's default: payload sets a THIRD mode mid-sandwich
        (OnMouseUp vs Auto), exit still lands on the pre-sandwich mode.

Mutations: a single throwaway geo chain under /obj (namespaced
"synapse_f1_probe_*"), created and destroyed inside the run. On any failure
the chain destroy is still attempted. Nothing else is touched; the session
update mode is restored at the end whatever happens.

Verdict: PASS counts per item; overall F1 VERDICT line at the end.
(b)/(c) failing = F1 descope-and-report per the spec — stop, keep the
evidence, do not fix-forward.
"""

import hou

_RESULTS = []  # [(item, name, ok, detail)]


def _record(item, name, ok, detail):
    _RESULTS.append((item, name, bool(ok), str(detail)))
    print(("PASS" if ok else "FAIL") + f" [{item}] {name}: {detail}")


def _skip(item, name, detail):
    _RESULTS.append((item, name, None, str(detail)))
    print(f"SKIP [{item}] {name}: {detail}")


def _make_chain():
    """geo -> box -> null (display on null). Returns (geo, box, out)."""
    geo = hou.node("/obj").createNode("geo", "synapse_f1_probe_geo")
    box = geo.createNode("box", "synapse_f1_probe_box")
    out = geo.createNode("null", "synapse_f1_probe_out")
    out.setInput(0, box)
    out.setDisplayFlag(True)
    return geo, box, out


def probe_a():
    item = "a"
    syms = {
        "hou.updateModeSetting": lambda: callable(getattr(hou, "updateModeSetting", None)),
        "hou.setUpdateMode": lambda: callable(getattr(hou, "setUpdateMode", None)),
        "hou.updateMode.Manual": lambda: getattr(getattr(hou, "updateMode", None), "Manual", None) is not None,
        "hou.isUIAvailable": lambda: callable(getattr(hou, "isUIAvailable", None)),
        "hou.undos.group": lambda: callable(getattr(getattr(hou, "undos", None), "group", None)),
        "hou.ui.triggerUpdate": lambda: callable(getattr(getattr(hou, "ui", None), "triggerUpdate", None)),
    }
    for name, check in syms.items():
        try:
            ok = bool(check())
        except Exception as e:
            ok, extra = False, f" (raised {e})"
        else:
            extra = ""
        _record(item, name, ok, "present" + extra if ok else "MISSING" + extra)


def probe_b():
    item = "b"
    if not hou.isUIAvailable():
        _skip(item, "one consolidated cook", "no GUI session — probe is GUI-only")
        return
    geo, box, out = _make_chain()
    try:
        out.cook(force=True)
        base = out.cookCount()
        prior = hou.updateModeSetting()
        calls = []

        def _record_mode(_msg):
            # Track setUpdateMode calls for the detail line only.
            calls.append(str(hou.updateModeSetting()))

        hou.setUpdateMode(hou.updateMode.Manual)
        _record_mode("manual")
        try:
            # The flood: several mutations that each auto-cook under Auto.
            box.parm("tx").set(1.0)
            box.parm("sizex").set(2.0)
            box.parm("sizey").set(3.0)
        finally:
            hou.setUpdateMode(prior)
            hou.ui.triggerUpdate()
        after = out.cookCount()
        delta = after - base
        _record(
            item, "one consolidated cook",
            delta == 1,
            f"cookCount {base} -> {after} (delta {delta}, expected 1); "
            f"prior mode {prior}",
        )
    finally:
        geo.destroy()


def probe_c():
    item = "c"
    if not hou.isUIAvailable():
        _skip(item, "undo-group non-swallow", "no GUI session — probe is GUI-only")
        return
    geo, box, out = _make_chain()
    try:
        prior = hou.updateModeSetting()
        pre_tx = box.parm("tx").eval()
        # Undo group OPEN ACROSS the sandwich (spec's probed nesting).
        with hou.undos.group("synapse_f1_probe_c"):
            hou.setUpdateMode(hou.updateMode.Manual)
            try:
                box.parm("tx").set(pre_tx + 10.0)   # the "artist edit"
            finally:
                hou.setUpdateMode(prior)
                hou.ui.triggerUpdate()
        # Group closed: edit must be present (not swallowed)...
        survives = abs(box.parm("tx").eval() - (pre_tx + 10.0)) < 1e-6
        # ...and exactly ONE performUndo must reverse it.
        hou.undos.performUndo()
        undone = abs(box.parm("tx").eval() - pre_tx) < 1e-6
        _record(
            item, "undo-group non-swallow",
            survives and undone,
            f"edit present after group close: {survives}; "
            f"one performUndo reversed it: {undone}",
        )
    finally:
        try:
            hou.undos.performUndo()  # undo the chain creation itself
        except Exception:
            pass
        try:
            if geo.path() and hou.node(geo.path()) is not None:
                geo.destroy()
        except Exception:
            pass


def probe_d():
    item = "d"
    if not hou.isUIAvailable():
        _skip(item, "nested-mode restore", "no GUI session — probe is GUI-only")
        return
    prior = hou.updateModeSetting()
    other = (hou.updateMode.OnMouseUp
             if prior != hou.updateMode.OnMouseUp else hou.updateMode.Auto)
    try:
        hou.setUpdateMode(hou.updateMode.Manual)       # sandwich entry
        try:
            # Nested payload calls setUpdateMode itself — the realistic
            # collision the snapshot restore must survive.
            hou.setUpdateMode(other)
        finally:
            hou.setUpdateMode(prior)                 # snapshot restore
            hou.ui.triggerUpdate()
        restored = hou.updateModeSetting() == prior
        _record(
            item, "nested-mode restore",
            restored,
            f"pre-sandwich {prior}, payload set {other}, "
            f"after exit {hou.updateModeSetting()}",
        )
    finally:
        if hou.updateModeSetting() != prior:
            hou.setUpdateMode(prior)
            hou.ui.triggerUpdate()


def main():
    print("=" * 72)
    print("F1 probe — update-mode sandwich gate (Houdini 22.0.400 target)")
    print(f"hou build: {hou.applicationVersionString()}  "
          f"GUI session: {hou.isUIAvailable()}")
    print("=" * 72)

    probe_a()
    geo_marker = hou.node("/obj/synapse_f1_probe_geo")
    assert geo_marker is None, "leftover probe chain — remove it first"

    probe_b()
    probe_c()
    probe_d()

    failed = [r for r in _RESULTS if r[2] is False]
    skipped = [r for r in _RESULTS if r[2] is None]
    passed = [r for r in _RESULTS if r[2] is True]
    print("-" * 72)
    print(f"results: {len(passed)} PASS / {len(failed)} FAIL / "
          f"{len(skipped)} SKIP")
    gate_items = {r[0] for r in failed} & {"b", "c"}
    if gate_items:
        print(f"F1 VERDICT: FAIL on gate item(s) {sorted(gate_items)} — "
              "descope-and-report per spec; do NOT fix-forward.")
    elif failed:
        print("F1 VERDICT: FAIL on non-gate item(s) "
              f"{sorted({r[0] for r in failed})} — see lines above.")
    elif skipped:
        print("F1 VERDICT: SKIPPED items present — rerun in a GUI session "
              "for the full gate.")
    else:
        print("F1 VERDICT: PASS — sandwich may ship behind "
              "SYNAPSE_COOK_SANDWICH=1.")


main()
