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

import pytest

from synapse.panel.compositor import known_widget_ids
from synapse.panel.settings import PROFILES, SwitcherState, load_settings

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "harness" / "battleplan" / "notes" / "bp2_paneltruth_profile_diff.py"
ART = REPO / "harness" / "battleplan" / "runs" / "2026-09-01" / "profile_diff.json"
# The artist's 2026-09-22 removal retires only these home controls. Their
# compatibility registry IDs remain; every surviving control is still required.
RETIRED_HOME_SWITCHES = frozenset({"chat_pill", "token_pill"})


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
    three, and equals the registry minus the two explicitly retired controls."""
    diff = _load_gen().build_diff()
    sets = {}
    for p, block in diff["profiles"].items():
        sets[p] = frozenset(
            wid for wid in block["widget_specs"] if not wid.startswith("@region:"))
    assert sets["curious"] == sets["expert"] == sets["ml"]
    assert sets["expert"] == frozenset(known_widget_ids()) - RETIRED_HOME_SWITCHES


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
    # bc-wave, direction B (2026-09-05): the telemetry chrome curious used to
    # FOLD is now a hidden owner in every profile (the overflow reads it), so
    # curious no longer collapses anything. The artist's 2026-09-22 TOKEN
    # removal also retires its only prominence delta; ML keeps exactly the
    # surviving author-token emphasis. All other knobs remain unchanged.
    assert dve["curious"]["widget_knobs_that_moved"] == []
    assert dve["curious"]["widget_deltas"] == {}
    assert dve["ml"]["widget_knobs_that_moved"] == ["prominence"]
    assert dve["ml"]["widget_deltas"] == {
        "author_token": {"prominence": {"expert": "standard", "ml": "hero"}}}


@pytest.mark.parametrize("mutation", ["restore_chat", "restore_token", "drop_stop", "drop_one_connect"])
def test_capability_pin_rejects_retired_controls_and_unrelated_losses(monkeypatch, mutation):
    generator = _load_gen()
    diff = generator.build_diff()
    if mutation.startswith("restore_"):
        widget_id = "chat_pill" if mutation == "restore_chat" else "token_pill"
        for block in diff["profiles"].values():
            block["widget_specs"][widget_id] = {
                "visible": True, "collapsed": False, "stretch": 0, "prominence": "standard"}
    elif mutation == "drop_stop":
        for block in diff["profiles"].values():
            del block["widget_specs"]["stop"]
    else:
        del diff["profiles"]["curious"]["widget_specs"]["connect"]
    monkeypatch.setattr(generator, "build_diff", lambda: diff)
    monkeypatch.setitem(globals(), "_load_gen", lambda: generator)
    with pytest.raises(AssertionError):
        test_capability_identical_widget_id_set_across_profiles()


@pytest.mark.parametrize("mutation", ["visible", "stretch", "collapsed", "curious_token", "overlay"])
def test_profile_difference_pin_rejects_unapproved_drift(monkeypatch, mutation):
    generator = _load_gen()
    diff = generator.build_diff()
    if mutation == "curious_token":
        curious = diff["diff_vs_expert"]["curious"]
        curious["widget_knobs_that_moved"] = ["prominence"]
        curious["widget_deltas"] = {
            "token_pill": {"prominence": {"expert": "standard", "curious": "quiet"}}}
    elif mutation == "overlay":
        diff["diff_vs_expert"]["ml"]["system_prompt_overlay_changed"] = False
    else:
        ml = diff["diff_vs_expert"]["ml"]
        ml["widget_knobs_that_moved"].append(mutation)
        ml["widget_deltas"]["author_token"][mutation] = {"expert": 0, "ml": 1}
    monkeypatch.setattr(generator, "build_diff", lambda: diff)
    monkeypatch.setitem(globals(), "_load_gen", lambda: generator)
    with pytest.raises(AssertionError):
        test_diff_vs_expert_moves_only_prominence_collapse_density_overlay()


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


def test_artifact_pin_rejects_a_changed_surviving_control(monkeypatch, tmp_path):
    changed = json.loads(ART.read_text(encoding="utf-8"))
    changed["profiles"]["expert"]["widget_specs"]["stop"]["visible"] = False
    path = tmp_path / "changed_profile_diff.json"
    path.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
    monkeypatch.setitem(globals(), "ART", path)
    with pytest.raises(AssertionError):
        test_committed_artifact_exists_and_matches_the_producer()


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
