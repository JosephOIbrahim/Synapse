"""Guard — the chat transcript + consent gates render from the vendored design
system, NOT the ~/.synapse/design bridge (contract: chat-gate-off-bridge).

`synapse.panel.tokens` (the bridge) re-exports colors from the off-repo
``~/.synapse/design`` side-channel and pins the legacy cyan accent; the live
panel's chrome already renders from the vendored ``synapse.panel.designsystem``.
chat_display.py / gate_widget.py and the chat/gate stylesheet functions must
source from the design system too, so the panel is repo-driven and
colour-consistent. Pure source-scan + Qt-free style() calls, so this runs under
stock ``pytest -q`` (no PySide) — a real pass/fail, never a skip.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_PANEL = os.path.join(_ROOT, "python", "synapse", "panel")
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _read(name):
    with open(os.path.join(_PANEL, name), encoding="utf-8") as f:
        return f.read()


def test_chat_and_gate_import_designsystem_not_bridge():
    """The two widgets must import the vendored tokens, never the bridge."""
    for fname in ("chat_display.py", "gate_widget.py"):
        src = _read(fname)
        assert "from synapse.panel import tokens" not in src, (
            "%s still imports the panel.tokens bridge (the ~/.synapse/design "
            "side-channel); route it to synapse.panel.designsystem.tokens" % fname
        )
        assert "from synapse.panel.designsystem import tokens" in src, (
            "%s must source tokens from the vendored design system" % fname
        )


def test_chat_gate_backgrounds_use_seeded_surfaces():
    """The chat + gate backgrounds must render the SEEDED surface roles
    (GROUND/SURFACE), NOT the near-black base VOID and NOT the bridge — so they
    sit in Houdini's pane grey and theme-flip with the host scheme. GROUND
    (#262626), designsystem VOID (#0A0A0A) and bridge VOID (#252525) are all
    distinct, a clean three-way discriminator."""
    from synapse.panel import styles
    import synapse.panel.tokens as bridge
    import synapse.panel.designsystem.tokens as ds

    assert len({ds.GROUND.lower(), ds.VOID.lower(), bridge.VOID.lower()}) == 3, (
        "test premise broken: GROUND / designsystem VOID / bridge VOID must differ"
    )
    for fn in (styles.get_chat_display_stylesheet, styles.get_gate_widget_stylesheet):
        qss = fn().lower()
        assert ds.GROUND.lower() in qss, (
            "%s must render the seeded GROUND surface (%s)" % (fn.__name__, ds.GROUND)
        )
        assert ds.VOID.lower() not in qss, (
            "%s still renders the near-black base VOID (%s) — repoint the "
            "background to a seeded surface role" % (fn.__name__, ds.VOID)
        )
        assert bridge.VOID.lower() not in qss, (
            "%s still renders the bridge VOID (%s)" % (fn.__name__, bridge.VOID)
        )
