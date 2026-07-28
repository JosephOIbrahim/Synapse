"""What is the RUNNING Houdini actually loading?

Paste this into Houdini's Python Shell (Windows > Python Shell) and press Enter
twice. It reports which files the live process has imported, and whether they
contain the 2026-07-27 panel changes.

This answers the question from INSIDE the process rather than from the disk,
which is the only place the answer actually lives.
"""
import sys

print("=" * 66)
print("SYNAPSE PANEL - what this Houdini has loaded")
print("=" * 66)

import synapse
print("  synapse version   :", synapse.__version__, "   (expect 5.37.0)")
print("  synapse from      :", synapse.__file__)
print()

# The three modules today's changes live in.
for name, marker, what in (
    ("synapse.panel.chat_panel", "_SIZE_STEPS", "three A's size control"),
    ("synapse.panel.synapse_panel", "_turn_evidence", "result surface connected"),
    ("synapse.panel.quick_actions", "_pill_stylesheet", "action row padding"),
):
    mod = sys.modules.get(name)
    if mod is None:
        print("  %-34s NOT IMPORTED" % name)
        continue
    cls_has = False
    try:
        src = open(mod.__file__, encoding="utf-8", errors="replace").read()
        cls_has = marker in src
    except Exception:
        pass
    print("  %-34s %s" % (name, "loaded"))
    print("      file    : %s" % mod.__file__)
    print("      %-22s %s" % (what, "PRESENT" if cls_has else "ABSENT - stale file"))
print()

# The visible ones, read from the live token module.
from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import fontload
f = fontload.tracked_font("WORDMARK", 14, scale=1.0, weight=600)
print("  wordmark weight   :", f.weight(), "  (expect 700)")
print("  wordmark tracking : %.2f px" % t.tracking_px("WORDMARK", 14), "  (expect 2.24)")
print("  wordmark colour   :", t.TEXT_BRIGHT, "  (expect #DEDEDE)")
print()

from synapse.panel.chat_panel import SynapseChatPanel
print("  size steps        :", [n for _, _, n in SynapseChatPanel._SIZE_STEPS])
print("      (expect ['small', 'medium', 'large'] - if this errors, old code)")
print()
print("=" * 66)
print("  If every line above matches, the panel IS current and today's")
print("  changes are simply subtle. If any says NOT IMPORTED or ABSENT,")
print("  the running process is holding an older module.")
print("=" * 66)
