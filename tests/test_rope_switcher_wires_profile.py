"""W5-ROPE — the CURIOUS/EXPERT/ML switcher's LIVE effect on the active composed
profile, OBSERVED headless (never asserted from wiring existence).

Why this file exists
--------------------
``tests/test_rope_switcher_state.py`` pins the Qt-free ``SwitcherState`` core and
``tests/test_rope_profile_composition.py`` pins the pure-data ``compositor``, but
BOTH explicitly defer the live half — "the tab strip's Qt behavior (live
recompose ...) is seat-verified per the task card's manual accept"
(test_rope_switcher_state.py docstring). That manual-only gap is exactly what a
live seat-walk (2026-08-16, item 1: "the switcher does nothing") flagged: nothing
machine-observed that selecting a profile actually re-composes the panel.

This test closes the gap. It drives the REAL ``SynapsePanel._select_profile`` ->
``_recompose`` -> ``compositor.compose`` chain (the production wiring, unbound on
a fake self — the tests/test_panel_stop_honest.py idiom) and OBSERVES, per
selection, that the active composed profile actually changes:

  * ``_layout_profile``            — the panel's single source of live profile truth
  * ``_system_prompt_overlay``     — the behavioral lever compose() stamps (distinct
                                     per profile: curious narration / expert "" / ml terse)
  * the panel-wide ``density``     — airy / standard / tight, stamped on the root
  * per-widget ``prominence``      — token_pill / token_meter: quiet / standard / hero
  * ``SwitcherState.profile``      — the persisted selection

It rides ON the composer (compositor.compose / resolve / manifests.get_manifest),
never forks it: the only fakes are the Qt widget/layout LEAVES, which carry no
logic. Runs headless via the ``qt_stub_window`` shim (stock CPython) and under a
real resident PySide (hython) alike — it never constructs a live QApplication.

Scope note (receipts, not claims): the pill ``clicked`` -> ``_select_profile``
SIGNAL wire and the Qt REPAINT that makes ``density`` visible cannot be exercised
under the stub (its signals are Mocks; no compositor repaint runs). The signal
wire is pinned statically below; the repaint is a separate seat concern.
"""

import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402

from synapse.panel import compositor  # noqa: E402
from synapse.panel.manifests import curious, expert, ml, get_manifest  # noqa: E402
from synapse.panel.settings import SwitcherState  # noqa: E402

_PANEL_SRC = Path(__file__).resolve().parents[1] / "python" / "synapse" / "panel" / "synapse_panel.py"


# --------------------------------------------------------------------------- #
# Fake Qt leaves — no logic, only the surface compose()/_recompose() duck-type.
# --------------------------------------------------------------------------- #

class _Item:
    def __init__(self, widget):
        self._w = widget

    def widget(self):
        return self._w


class _Layout:
    """Minimal QVBoxLayout stand-in: an ordered list of (item, stretch)."""

    def __init__(self):
        self._items = []

    def count(self):
        return len(self._items)

    def addWidget(self, w, stretch=0):
        self._items.append((_Item(w), stretch))

    def addItem(self, item):
        self._items.append((item, 0))

    def stretch(self, i):
        return self._items[i][1]

    def setStretch(self, i, s):
        item, _ = self._items[i]
        self._items[i] = (item, s)

    def takeAt(self, i):
        item, _ = self._items.pop(i)
        return item

    def itemAt(self, i):
        return self._items[i][0]


class _Style:
    def unpolish(self, w):
        pass

    def polish(self, w):
        pass


class _Widget:
    """A leaf widget: records the specs compose()/_apply_spec apply to it."""

    def __init__(self, name):
        self.name = name
        self._props = {}
        self._visible = True
        self._max_h = None

    def setVisible(self, v):
        self._visible = v

    def isVisible(self):
        return self._visible

    def setMaximumHeight(self, h):
        self._max_h = h

    def setProperty(self, key, value):
        self._props[key] = value

    def property(self, key):
        return self._props.get(key)

    def style(self):
        return _Style()

    def parentWidget(self):
        return None

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False


class _Chat:
    def append_system_message(self, *a, **k):
        pass


class _FakePanel:
    """Drives the REAL _select_profile / _mark_profile_pill / _recompose against
    fake Qt leaves. Every widget id in the compositor's registry resolves to a
    real leaf (built from WIDGET_ATTRS so it can never drift), so compose()
    applies every spec and logs no 'widget missing' skips."""

    _REGION_BUILDERS = tuple(compositor.REGION_BUILDERS.values())

    def __init__(self, state):
        self._layout_profile = "expert"          # boot default (== DEFAULT_PROFILE)
        self._profile_state = state
        self._profile_pills = {}                  # empty -> _mark_profile_pill is a no-op
        self._recompose_hidden = set()
        self._region_cache = {}
        self._chat = _Chat()
        self._system_prompt_overlay = ""
        self._density_stamp = "<unset>"
        self._lay = _Layout()
        # region widgets are build-once (like the real self._region_cache), so a
        # recompose re-sequences the SAME instances.
        self._region_widgets = {b: _Widget(b) for b in self._REGION_BUILDERS}
        # every widget id -> a leaf on the panel attribute compose() reaches for,
        # derived from the real registry (supports the 'attr.key' dict form).
        for wid, attrpath in compositor.WIDGET_ATTRS.items():
            attr, _, key = attrpath.partition(".")
            if key:
                holder = getattr(self, attr, None)
                if holder is None:
                    holder = {}
                    setattr(self, attr, holder)
                holder[key] = _Widget(wid)
            else:
                setattr(self, attr, _Widget(wid))

    # the three region builders compose() invokes by name, build-once.
    def _build_rail(self):
        return self._region_widgets["_build_rail"]

    def _build_context_ribbon(self):
        return self._region_widgets["_build_context_ribbon"]

    def _build_mode_bar(self):
        return self._region_widgets["_build_mode_bar"]

    def _build_faces(self):
        return self._region_widgets["_build_faces"]

    def layout(self):
        return self._lay

    def setProperty(self, key, value):
        if key == "density":
            self._density_stamp = value

    # the wiring under test, routed to the REAL production implementations.
    def _mark_profile_pill(self, profile):
        return SynapsePanel._mark_profile_pill(self, profile)

    def _recompose(self, profile):
        return SynapsePanel._recompose(self, profile)

    # observation helpers -------------------------------------------------- #
    def _widget(self, wid):
        return compositor._panel_widget(self, wid)

    def prominence(self, wid):
        return self._widget(wid).property("prominence")


# --------------------------------------------------------------------------- #
# Expected per-profile active state — grounded in the manifests, not the wiring.
# --------------------------------------------------------------------------- #

# density (panel-wide) and overlay (behavioral) are distinct across all three.
_DENSITY = {"curious": "airy", "expert": "standard", "ml": "tight"}
_OVERLAY = {
    "curious": curious.MANIFEST["system_prompt_overlay"],
    "expert": expert.MANIFEST["system_prompt_overlay"],
    "ml": ml.MANIFEST["system_prompt_overlay"],
}
# token_pill / token_meter prominence — distinct across all three, and reset in
# BOTH directions (unlike collapse, which _apply_spec applies one-way).
_TOKEN_PILL_PROM = {"curious": "quiet", "expert": "standard", "ml": "hero"}
_TOKEN_METER_PROM = {"curious": "quiet", "expert": "standard", "ml": "hero"}


def _make_panel():
    tmp = tempfile.mkdtemp()
    state = SwitcherState(Path(tmp) / "panel_settings.json")
    panel = _FakePanel(state)
    # Mirror _build_ui's boot composition (synapse_panel.py:484): the panel opens
    # already composed to its restored profile, so a switch is a transition FROM a
    # real composed state, not from a blank one.
    compositor.compose(panel, panel.layout(), get_manifest(panel._layout_profile))
    return panel


def _assert_active(panel, profile):
    """Every independent observable of the ACTIVE composed profile matches."""
    assert panel._layout_profile == profile, "live profile attr"
    assert panel._density_stamp == _DENSITY[profile], "panel-wide density"
    assert panel._system_prompt_overlay == _OVERLAY[profile], "system-prompt overlay"
    assert panel._profile_state.profile == profile, "persisted selection"
    assert panel.prominence("token_pill") == _TOKEN_PILL_PROM[profile], "token_pill prominence"
    assert panel.prominence("token_meter") == _TOKEN_METER_PROM[profile], "token_meter prominence"


# --------------------------------------------------------------------------- #
# The core acceptance: selection composes AND applies the profile, per selection.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("profile", ["curious", "expert", "ml"])
def test_selecting_a_profile_makes_it_the_active_composed_profile(profile):
    """From the expert boot state, selecting each mode re-composes to it."""
    panel = _make_panel()
    if profile == "expert":
        # boot is already expert; select a different one first so this is a real
        # transition, not the no-op guard path.
        SynapsePanel._select_profile(panel, "ml")
    SynapsePanel._select_profile(panel, profile)
    _assert_active(panel, profile)


def test_switcher_changes_active_profile_across_a_full_sequence():
    """A live walk across every mode AND back — proves the switch is real in
    both directions (the density/prominence resets on switch-back too), and that
    each selection lands the corresponding rope profile."""
    panel = _make_panel()
    _assert_active(panel, "expert")                       # boot
    for profile in ("curious", "ml", "expert", "ml", "curious", "expert"):
        SynapsePanel._select_profile(panel, profile)
        _assert_active(panel, profile)


def test_reselecting_the_active_profile_is_a_noop():
    """The handler's guard (synapse_panel.py:506): selecting the already-active
    profile does not re-compose or re-persist — no spurious churn."""
    panel = _make_panel()
    SynapsePanel._select_profile(panel, "curious")
    density_before = panel._density_stamp
    overlay_before = panel._system_prompt_overlay
    persist_before = panel._profile_state.persist_ok
    # Corrupt the observable state; a no-op must leave it corrupted (proving the
    # early return fired, not a silent re-compose that would restore it).
    panel._density_stamp = "<sentinel>"
    SynapsePanel._select_profile(panel, "curious")
    assert panel._density_stamp == "<sentinel>", "re-select must not re-compose"
    assert panel._system_prompt_overlay == overlay_before
    assert panel._profile_state.profile == "curious"
    assert panel._profile_state.persist_ok == persist_before


# --------------------------------------------------------------------------- #
# Static pin: the SIGNAL wire (pill.clicked -> _select_profile) cannot regress.
# The stub's signals are Mocks, so the connect itself is source-pinned here and
# behaviorally covered above at the slot.
# --------------------------------------------------------------------------- #

def test_profile_pills_are_connected_to_the_select_handler():
    src = _PANEL_SRC.read_text(encoding="utf-8")
    # the pill loop connects each pill's clicked signal to _select_profile(pid).
    assert re.search(
        r"\.clicked\.connect\(\s*lambda[^\n]*:\s*self\._select_profile\(",
        src,
    ), "the CURIOUS/EXPERT/ML pills must wire clicked -> _select_profile"
    # and _select_profile must drive the live recompose (rides on the composer).
    handler = src[src.index("def _select_profile"):src.index("def _mark_profile_pill")]
    assert "self._recompose(" in handler, "_select_profile must call _recompose"
