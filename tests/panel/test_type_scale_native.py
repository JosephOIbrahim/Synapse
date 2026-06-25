"""Goalpost — the chat transcript + consent gate must render at Houdini-NATIVE
font sizes (single source), not the machine-local side-channel's huge scale.

Contract: typography-consolidate (order 1). Root cause:

    panel/tokens.py re-exports SIZE_* from ~/.synapse/design/tokens.py
    (BODY=26 UI=24 LABEL=22 TITLE=32 HERO=44). That dir is inserted onto
    sys.path INSIDE tokens.py at import (lines ~13-15), so _HAS_DESIGN=True
    at runtime and the home scale shadows the repo. chat_display.py and
    gate_widget.py read t.SIZE_BODY / t.SIZE_LABEL from there, so text
    renders ~2x native and crops the buttons/labels.

The fix sources the native scale from synapse.panel.designsystem.tokens
(SIZE_UI=12 SIZE_BODY=12 SIZE_TITLE=15 SIZE_HERO=19) and drops the home
side-channel dependency.

PURE PYTHON by design: both tokens modules are stdlib-only (no PySide), so
these run as REAL assertions under stock CPython *and* hython — no
QApplication required. That is deliberate: this is the dependable pass/fail
signal under the harness's stock `pytest -q` (a skip would exit 0 = false
green). The save/restore of sys.modules / sys.path mirrors the residency-safe
pattern in test_token_seeding.py (which does the same for 'hou').
"""

import importlib
import os
import sys

# Make the package importable from a source checkout (no install), matching the
# sys.path bootstrap the existing panel tests use.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_PANEL_TOKENS = "synapse.panel.tokens"
_DESIGN_TOKENS = "synapse.panel.designsystem.tokens"

# The machine-local side-channel dir that tokens.py currently re-exports from.
_DESIGN_DIR = os.path.join(os.path.expanduser("~"), ".synapse", "design")


def test_chat_gate_scale_matches_native():
    """SINGLE-NATIVE-SOURCE signal. The panel's SIZE_* (what chat_display.py and
    gate_widget.py actually read via `tokens as t`) must equal the vendored
    designsystem native scale.

    FAILS now: panel/tokens.py re-exports the home side-channel (SIZE_BODY=26,
    SIZE_UI=24, SIZE_LABEL=22) while designsystem is native (12/12/12-with-
    SIZE_LABEL=10). PASSES once the worker sources SIZE_* from designsystem.
    """
    pt = importlib.import_module(_PANEL_TOKENS)
    dt = importlib.import_module(_DESIGN_TOKENS)

    # Guard against not-yet-defined names so this is an ASSERTION failure, never
    # an AttributeError. (All six exist today, but stay defensive per the rules.)
    pt_body = getattr(pt, "SIZE_BODY", None)
    pt_ui = getattr(pt, "SIZE_UI", None)
    pt_label = getattr(pt, "SIZE_LABEL", None)
    dt_body = getattr(dt, "SIZE_BODY", None)
    dt_ui = getattr(dt, "SIZE_UI", None)

    assert None not in (pt_body, pt_ui, pt_label, dt_body, dt_ui), (
        "expected SIZE_BODY/SIZE_UI/SIZE_LABEL on both tokens modules; got "
        "pt=(%r,%r,%r) dt=(%r,%r)" % (pt_body, pt_ui, pt_label, dt_body, dt_ui)
    )

    assert pt_body == dt_body, (
        "panel SIZE_BODY must match the native designsystem scale; got "
        "panel=%r designsystem=%r — panel/tokens.py still re-exports the "
        "~/.synapse/design side-channel (BODY=26)" % (pt_body, dt_body)
    )
    assert pt_ui == dt_ui, (
        "panel SIZE_UI must match the native designsystem scale; got "
        "panel=%r designsystem=%r — still the side-channel (UI=24)"
        % (pt_ui, dt_ui)
    )
    assert pt_label <= dt_ui, (
        "panel SIZE_LABEL (gate badges/labels) must not exceed the native UI "
        "size; got SIZE_LABEL=%r > SIZE_UI=%r — labels still oversized (22) "
        "and crop the gate cards" % (pt_label, dt_ui)
    )


def test_no_home_side_channel_dependency():
    """The native scale must hold even with ~/.synapse/design removed from
    sys.path. Today tokens.py RE-INSERTS that dir itself at import, so the home
    scale (SIZE_BODY=26) wins regardless of sys.path — stripping the dir is not
    enough. The fix drops that dependency and sources SIZE_* from designsystem.

    We reload panel/tokens.py with the home dir stripped from sys.path AND the
    cached top-level 'tokens' module evicted, then assert SIZE_BODY is native
    (<=14). save/restore mirrors test_token_seeding.py's 'hou' handling so we
    never leak a reloaded module / mutated sys.path to neighbours.

    FAILS now (SIZE_BODY stays 26 because tokens.py re-adds _DESIGN_DIR);
    PASSES once the side-channel re-export is removed.
    """
    # Save the exact state we will mutate, so restore is lossless.
    saved_modules = {
        k: sys.modules.get(k)
        for k in (_PANEL_TOKENS, "tokens")
    }
    saved_path = list(sys.path)

    try:
        # Strip every sys.path entry pointing at the home design dir.
        norm_design = os.path.normcase(os.path.abspath(_DESIGN_DIR))
        sys.path[:] = [
            p for p in sys.path
            if os.path.normcase(os.path.abspath(p)) != norm_design
        ]
        # Evict any cached side-channel 'tokens' and the panel module so the
        # reload re-runs the import-time re-export path from scratch.
        sys.modules.pop("tokens", None)
        sys.modules.pop(_PANEL_TOKENS, None)

        pt = importlib.import_module(_PANEL_TOKENS)
        size_body = getattr(pt, "SIZE_BODY", None)

        assert size_body is not None, (
            "panel tokens must define SIZE_BODY; got None")
        assert size_body <= 14, (
            "with the ~/.synapse/design side-channel removed from sys.path, "
            "panel SIZE_BODY must resolve to the NATIVE scale (<=14); got %r — "
            "panel/tokens.py still depends on the home side-channel (it "
            "re-inserts _DESIGN_DIR and re-exports BODY=26)" % (size_body,)
        )
    finally:
        # Restore sys.path and sys.modules to their exact pre-test state and
        # reload the panel module so neighbours see the canonical instance.
        sys.path[:] = saved_path
        for k, v in saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        importlib.import_module(_PANEL_TOKENS)
