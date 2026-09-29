"""Live check for the Identify overlay (BP12 item 2), run inside a Houdini GUI.

It identifies the current selection in the network editor's network, or the
first few nodes there when nothing is selected, through the same steps as the
panel button: facts on the main thread, library summary, bubble model, then the
overlay. It draws the overlay, times the tracking tick, and saves what the
overlay painted to a PNG, so the paint can be checked without a screen capture.
It never writes to the scene: the legacy comment cleanup is not called.

From Houdini's Python shell, or SYNAPSE's ``houdini_execute_python``:

    import runpy
    probe = runpy.run_path(r"C:/Users/User/SYNAPSE/scripts/probe_identify_overlay.py")
    report = probe["run"](out_png=r"C:/tmp/identify_overlay.png")

``run(clear_after=True)`` takes the bubbles away again after the grab.
"""
from __future__ import annotations

import importlib
import time


def _fresh(module):
    """Reload *module* when this session loaded it before the overlay existed."""
    if not hasattr(module, "here_line"):
        importlib.reload(module)
    return module


def run(out_png=None, clear_after=False, limit=8, reload=False):
    """Draw the overlay for the selection (or the network) and report on it.

    *reload* picks up edited overlay code in a live session: it clears the
    bubbles the old code drew, then reloads the bubble, layout and overlay
    modules before drawing again.
    """
    import hou
    from synapse.identify import compose
    _fresh(compose)
    from synapse.identify import bubble, facts, layout, library, overlay
    if reload:
        overlay.clear()
        for module in (bubble, layout, overlay):
            importlib.reload(module)
    from synapse.panel.designsystem import fontload

    editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    if editor is None:
        return {"ok": False, "reason": "no network editor"}
    here = editor.pwd()
    nodes = [n for n in hou.selectedNodes()
             if n.parent() is not None and n.parent().sessionId() == here.sessionId()]
    source = "selection"
    if not nodes:
        nodes, source = list(here.children())[:limit], "network"
    paths = [n.path() for n in nodes][:limit]

    started = time.perf_counter()
    facts_list = facts.read_selection_facts(paths)
    facts_s = time.perf_counter() - started
    entries = []
    for node_facts in facts_list:
        summary, origin = library.summarize(node_facts.get("help_url"), node_facts.get("hda_help"))
        node_facts["summary"], node_facts["summary_source"] = summary, origin
        entries.append((hou.node(node_facts["path"]).sessionId(), bubble.bubble_model(node_facts)))

    shown = overlay.show(entries, total=len(paths), editor=editor)
    window = overlay._OVERLAY
    report = {"ok": window is not None, "source": source, "paths": paths, "show": shown,
              "facts_s": round(facts_s, 4), "fonts": fontload.load_application_fonts()}
    if window is None:
        return report
    ticks = []
    for _ in range(5):
        window.signature = None        # force the layout to run every time
        tick_start = time.perf_counter()
        window.tick()
        ticks.append(round((time.perf_counter() - tick_start) * 1000.0, 2))
    idle_start = time.perf_counter()
    window.tick()                      # nothing moved: the cheap path
    report.update({
        "tick_ms": ticks,
        "idle_tick_ms": round((time.perf_counter() - idle_start) * 1000.0, 2),
        "geometry": [window.x(), window.y(), window.width(), window.height()],
        "visible": window.isVisible(),
        "scale": window.style_.scale,
        "placed": [(p.key, round(p.x), round(p.y), round(p.w), round(p.h), p.marker)
                   for p in window.placed],
        "models": [model for _key, model in entries],
    })
    from PySide6 import QtWidgets
    QtWidgets.QApplication.processEvents()
    if out_png:
        report["png"] = bool(window.grab().save(out_png))
    if clear_after:
        report["clear"] = overlay.clear()
    return report
