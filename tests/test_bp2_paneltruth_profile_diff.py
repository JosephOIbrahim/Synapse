"""BP2-PANELTRUTH T1 — the profile-diff receipt + the persist round-trip.

Two acceptance predicates, both Qt-free (they run in the stock-CPython suite):

  * profile_diff.json states EXACTLY what differs across curious/expert/ml —
    the resolved widget tree (visible/collapsed/stretch/prominence + the density
    root property), the composed system prompt (base sha + overlay + composed
    sha), and defaults. This pins the machine-independent half of that receipt
    (manifests + overlay join — not TONE.md, which varies by seat) and that the
    committed artifact equals the producer's output.
  * profile persist: select -> save -> load -> same profile (settings.py v3
    SwitcherState). test_rope_switcher_state.py already pins SwitcherState; this
    is the BP2 acceptance restatement, held next to the diff it belongs with.
"""

import importlib.util
import json
from pathlib import Path

from synapse.panel.compositor import known_widget_ids
from synapse.panel.settings import PROFILES, SwitcherState, load_settings

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "harness" / "battleplan" / "notes" / "bp2_paneltruth_profile_diff.py"
ART = REPO / "harness" / "battleplan" / "runs" / "2026-09-01" / "profile_diff.json"


def _load_gen():
    spec = importlib.util.spec_from_file_location(
        "bp2_paneltruth_profile_diff_undertest", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# The diff, recomputed from the shipped manifests + prompt builder.
# --------------------------------------------------------------------------- #

def test_producer_reports_three_profiles_with_the_required_facets():
    diff = _load_gen().build_diff()
    assert set(diff["profiles"]) == {"curious", "expert", "ml"}
    for p, block in diff["profiles"].items():
        assert set(block) >= {"density", "defaults", "system_prompt", "widget_specs"}
        sp = block["system_prompt"]
        assert set(sp) >= {"base_sha256_16", "overlay_text",
                           "overlay_sha256_16", "composed_sha256_16"}


def test_densities_are_airy_standard_tight():
    diff = _load_gen().build_diff()
    got = {p: diff["profiles"][p]["density"] for p in diff["profiles"]}
    assert got == {"curious": "airy", "expert": "standard", "ml": "tight"}


def test_capability_identical_widget_id_set_across_profiles():
    """L5: composition may reorder / fold / re-emphasise, never remove. The
    widget-id set (dropping the synthetic @region keys) is identical across the
    three, and equals the compositor's registry."""
    diff = _load_gen().build_diff()
    sets = {}
    for p, block in diff["profiles"].items():
        sets[p] = frozenset(
            wid for wid in block["widget_specs"] if not wid.startswith("@region:"))
    assert sets["curious"] == sets["expert"] == sets["ml"]
    assert sets["expert"] == frozenset(known_widget_ids())


def test_composed_prompt_differs_only_by_overlay():
    diff = _load_gen().build_diff()
    assert diff["composed_differs_only_by_overlay"] is True
    base = {diff["profiles"][p]["system_prompt"]["base_sha256_16"]
            for p in diff["profiles"]}
    assert len(base) == 1, "the base prompt must be identical across profiles"
    # expert has NO overlay -> its composed prompt IS the base; the other two
    # diverge, and only because of the overlay.
    exp = diff["profiles"]["expert"]["system_prompt"]
    assert exp["overlay_text"] == ""
    assert exp["composed_sha256_16"] == exp["base_sha256_16"]
    for p in ("curious", "ml"):
        sp = diff["profiles"][p]["system_prompt"]
        assert sp["overlay_text"] != ""
        assert sp["composed_sha256_16"] != exp["composed_sha256_16"]


def test_diff_vs_expert_moves_only_prominence_collapse_density_overlay():
    """The headline finding, asserted: the ONLY per-widget knobs that move are
    collapse + prominence; plus density + overlay. No visible/stretch drift."""
    diff = _load_gen().build_diff()
    dve = diff["diff_vs_expert"]
    assert set(dve) == {"curious", "ml"}
    all_knobs = set()
    for p, d in dve.items():
        all_knobs |= set(d["widget_knobs_that_moved"])
        assert d["system_prompt_overlay_changed"] is True
        # no widget ever flips visibility or stretch between profiles
        for wid, deltas in d["widget_deltas"].items():
            assert "visible" not in deltas, (p, wid)
            assert "stretch" not in deltas, (p, wid)
    assert all_knobs <= {"collapsed", "prominence"}
    # and specifically: curious folds (collapse) + re-emphasises, ml re-emphasises
    assert "collapsed" in set(dve["curious"]["widget_knobs_that_moved"])
    assert dve["ml"]["widget_knobs_that_moved"] == ["prominence"]


# --------------------------------------------------------------------------- #
# The committed artifact IS the producer's output (receipt integrity).
# --------------------------------------------------------------------------- #

def test_committed_artifact_exists_and_matches_the_producer():
    assert ART.is_file(), "profile_diff.json receipt is missing"
    committed = json.loads(ART.read_text(encoding="utf-8"))
    fresh = _load_gen().build_diff()
    # machine-independent halves (manifests + overlay join, not TONE.md)
    assert committed["diff_vs_expert"] == fresh["diff_vs_expert"]
    for p in ("curious", "expert", "ml"):
        assert committed["profiles"][p]["density"] == fresh["profiles"][p]["density"]
        assert (committed["profiles"][p]["system_prompt"]["overlay_text"]
                == fresh["profiles"][p]["system_prompt"]["overlay_text"])
        assert (committed["profiles"][p]["widget_specs"]
                == fresh["profiles"][p]["widget_specs"])


# --------------------------------------------------------------------------- #
# Persist round-trip: select -> save -> load -> same profile (v3 SwitcherState).
# --------------------------------------------------------------------------- #

def test_profile_persists_select_save_load_same(tmp_path):
    path = tmp_path / "panel_settings.json"
    st = SwitcherState(path)
    assert st.profile == "expert"               # restore-on-construct default
    assert st.select("ml") is True              # select -> save (write-through)
    assert st.persist_ok is True
    assert load_settings(path)["profile"] == "ml"   # load sees it
    # reopen (a fresh SwitcherState) lands on the saved profile
    assert SwitcherState(path).profile == "ml"


def test_profiles_is_the_closed_three():
    assert PROFILES == ("curious", "expert", "ml")
