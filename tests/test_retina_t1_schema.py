"""RETINA T1 — schema / honesty / governance tests (cv2-FREE).

These pin the T1 CONTRACT with zero pixels, so they run everywhere CI runs
(ubuntu/macos, no cv2/OIIO) — exactly like ``test_retina_t0.py`` runs everywhere
via synthetic headers. The pixel-metric tests that need real OpenCV live in
``test_retina_t1.py`` behind a skipif; the OIIO ingest tests in
``test_retina_ingest.py``.

What is pinned here:
* T1 events are schema-SIBLINGS of T0's (same envelope, ``tier=1``).
* Roll-up: fail > inconclusive > pass (shared ``retina.events.roll_up``).
* Honesty (§7): a ``pass=None`` check never rolls up to green.
* Determinism: same inputs → byte-identical event (no clock read).
* Persistence (§7): sidecar JSONL append, NO USD.
* Governance (§7): qc_profiles load + inheritance; every required knob present.
"""

from __future__ import annotations

import json

from retina import EVENT_VERSION, PERCEPTION_CHANNEL
from retina import qc_profiles
from retina.events import make_check, make_event, roll_up
from retina.t0 import check_manifest_against_disk
from retina.t1 import TIER, build_t1_event, emit_verdict

NOW = "2026-07-17T00:00:00+00:00"


def _named(event, name):
    for c in event["checks"]:
        if c["name"] == name:
            return c
    return None


# --- envelope / sibling shape ---------------------------------------------

def test_t1_event_is_t0_sibling():
    checks = [make_check("delta_containment", True, "leak within eps", leak_px=3, eps=32)]
    ev = build_t1_event(claim="material_swap:/geo/crystal", checks=checks, proof=None, now=NOW)
    assert ev["ch"] == PERCEPTION_CHANNEL == "perception"
    assert ev["v"] == EVENT_VERSION == 1
    assert ev["tier"] == TIER == 1
    assert ev["claim"] == "material_swap:/geo/crystal"
    assert ev["at"] == NOW
    assert ev["verdict"] == "pass"


def test_t0_and_t1_share_identical_envelope_keys():
    """The sibling conformance pin: a T0 event and a T1 event must carry exactly
    the same envelope keys — only ``tier`` differs in value."""
    t0_event = check_manifest_against_disk(
        {"schema": "retina_manifest/v1", "products": [], "claim": "render:file_truth"},
        now=NOW,
    )
    t1_event = build_t1_event(claim="c", checks=[make_check("x", True, "ok")], proof=None, now=NOW)
    assert set(t0_event.keys()) == set(t1_event.keys())
    assert t0_event["tier"] == 0 and t1_event["tier"] == 1


def test_t1_check_carries_numeric_evidence():
    """T1 checks attach measured value + threshold as extra keys (blueprint §3
    illustration: leak_px/eps, val/min)."""
    ev = build_t1_event(
        claim="c",
        checks=[
            make_check("delta_containment", True, "ok", leak_px=14, eps=32),
            make_check("ssim_outside", True, "ok", val=0.9971, min=0.995),
        ],
        proof="<qc>/f0001_delta.png",
        now=NOW,
    )
    dc = _named(ev, "delta_containment")
    assert dc["leak_px"] == 14 and dc["eps"] == 32
    so = _named(ev, "ssim_outside")
    assert so["val"] == 0.9971 and so["min"] == 0.995
    assert ev["proof"] == "<qc>/f0001_delta.png"


# --- roll-up + honesty -----------------------------------------------------

def test_roll_up_fail_dominates():
    checks = [make_check("a", True, ""), make_check("b", False, ""), make_check("c", None, "")]
    assert roll_up(checks) == "fail"


def test_roll_up_inconclusive_over_pass():
    checks = [make_check("a", True, ""), make_check("c", None, "cannot run")]
    assert roll_up(checks) == "inconclusive"


def test_inconclusive_never_masquerades_as_pass():
    """The RETINA thesis: a check that could not run (None) makes the event
    inconclusive, never a silent pass."""
    ev = build_t1_event(
        claim="c",
        checks=[make_check("ssim", None, "no baseline yet", min=0.995)],
        proof=None,
        now=NOW,
    )
    assert ev["verdict"] == "inconclusive"
    assert _named(ev, "ssim")["pass"] is None


def test_all_pass_is_pass():
    ev = build_t1_event(
        claim="c",
        checks=[make_check("a", True, ""), make_check("b", True, "")],
        proof=None,
        now=NOW,
    )
    assert ev["verdict"] == "pass"


# --- determinism + persistence --------------------------------------------

def test_deterministic_given_same_inputs():
    checks = [make_check("delta_containment", True, "ok", leak_px=0, eps=32)]
    e1 = build_t1_event(claim="c", checks=list(checks), proof=None, now=NOW)
    e2 = build_t1_event(claim="c", checks=list(checks), proof=None, now=NOW)
    assert e1 == e2


def test_emit_verdict_appends_jsonl(tmp_path):
    jsonl = tmp_path / "verdicts.jsonl"
    ev = build_t1_event(claim="c", checks=[make_check("a", True, "")], proof=None, now=NOW)
    emit_verdict(ev, jsonl)
    emit_verdict(ev, jsonl)
    lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["ch"] == "perception"
    assert parsed["tier"] == 1


def test_emit_verdict_is_the_same_function_as_t0():
    """Persistence is single-sourced: T1's emit_verdict IS T0's (both re-export
    retina.events.emit_verdict) — the sidecar-JSONL rule can't drift between
    tiers."""
    from retina.t0 import emit_verdict as t0_emit
    assert emit_verdict is t0_emit


# --- governance: qc_profiles ----------------------------------------------

def test_profiles_load_and_have_every_required_knob():
    profiles = qc_profiles.load_profiles()
    prof = qc_profiles.resolve_profile(profiles)
    for key in qc_profiles.REQUIRED_KEYS:
        assert key in prof, f"default profile missing {key}"


def test_profile_inheritance_overrides_only_named_knobs():
    profiles = qc_profiles.load_profiles()
    base = qc_profiles.resolve_profile(profiles)
    xpu = qc_profiles.resolve_profile(
        profiles, renderer="karma_xpu", denoiser_policy="denoised", sample_tier="low"
    )
    # The override table narrows ssim_min + diff_threshold, inherits the rest.
    assert xpu["ssim_min"] == 0.990
    assert xpu["diff_threshold"] == 0.03
    assert xpu["leak_eps"] == base["leak_eps"]
    assert xpu["firefly_std_devs"] == base["firefly_std_devs"]


def test_unknown_profile_falls_back_to_default_cleanly():
    profiles = qc_profiles.load_profiles()
    base = qc_profiles.resolve_profile(profiles)
    unknown = qc_profiles.resolve_profile(
        profiles, renderer="nonexistent", denoiser_policy="whatever", sample_tier="huge"
    )
    assert unknown == base


def test_missing_default_table_fails_loud(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('schema = "x"\n', encoding="utf-8")
    try:
        qc_profiles.load_profiles(bad)
    except qc_profiles.ProfileError:
        return
    raise AssertionError("expected ProfileError for a profile TOML with no [default]")
