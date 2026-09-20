# test_jev_shape.py - biting tests for the JEV-SHAPE guard (mile 1 of JEV_HELM.md).
# Same contract as test_jev_guards.py: every test asserts an exact decision, so a broken
# policy reddens it; the mutation that reddens each test is named in its docstring.
# Pure + hermetic: decide()/expand()/derive_shape() make no call and touch no ledger.
from __future__ import annotations

import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_client as jc  # noqa: E402
import jev_shape as js  # noqa: E402

POLICY = jc.load_questions()["guards"]["shape"]["policy"]
SHAPES = js.load_workflows()["shapes"]


def _a(choice, conf, known=0.9, det=0.1, breadth=0.0):
    return {"choices": {"shape": {"choice": choice, "confidence": conf, "probabilities": {}}},
            "nouls": {"cause_known": {"noul": known}, "deterministic": {"noul": det}},
            "scores": {"breadth": {"score": breadth, "confidence": 0.9, "probabilities": {}}}}


def test_none_answer_is_manual():
    """Mutation: return a template on answers=None -> a wave gets shaped with no judgment."""
    assert js.decide(None, POLICY, SHAPES)["shape"] == "manual"


def test_unknown_shape_is_manual():
    """Mutation: drop the `choice not in shapes` check -> Jev can invent a shape name."""
    d = js.decide(_a("swarm", 0.99), POLICY, SHAPES)
    assert d["shape"] == "manual" and "unknown shape" in d["reason"]


def test_low_confidence_is_manual():
    """Mutation: compare with <= 0 or drop the threshold -> a coin-flip shapes a wave."""
    assert js.decide(_a("solo", POLICY["min_shape_confidence"] - 0.01), POLICY, SHAPES)["shape"] == "manual"


def test_scout_synth_needs_unknown_cause():
    """Mutation: drop the cause_known cross-check -> scouts spawned for an already-named fix."""
    assert js.decide(_a("scout-synth", 0.9, known=0.8), POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("scout-synth", 0.9, known=0.1, breadth=2.0), POLICY, SHAPES)["shape"] == "scout-synth"


def test_build_shapes_need_known_cause():
    """Mutation: drop the build-side cross-check -> builders dispatched at an undiagnosed bug."""
    assert js.decide(_a("build-screen-crux", 0.9, known=0.2, breadth=2.0), POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("solo", 0.9, known=0.2), POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("build-screen-crux", 0.9, known=0.9, breadth=2.0), POLICY, SHAPES)["shape"] == "build-screen-crux"


def test_probe_only_needs_deterministic():
    """Mutation: skip the deterministic check (or treat None as pass) -> model work routed to zero-model legs."""
    assert js.decide(_a("probe-only", 0.9, det=0.5), POLICY, SHAPES)["shape"] == "manual"
    a = _a("probe-only", 0.9)
    a["nouls"]["deterministic"] = {"noul": None}
    assert js.decide(a, POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("probe-only", 0.9, det=0.9), POLICY, SHAPES)["shape"] == "probe-only"


def test_solo_refused_when_broad():
    """Mutation: drop the breadth check -> five deliverables crammed into one leg."""
    assert js.decide(_a("solo", 0.9, breadth=1.6), POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("solo", 0.9, breadth=0.2), POLICY, SHAPES)["shape"] == "solo"


def test_leg_count_rounds_down_on_doubt():
    """Mutation: return hi when breadth is None -> unknown breadth spends the maximum legs."""
    assert js.leg_count(2, 4, None) == 2
    assert js.leg_count(2, 4, 0.0) == 2
    assert js.leg_count(2, 4, 2.0) == 4
    assert js.leg_count(2, 4, 9.0) == 4  # clamped


def test_expand_scout_synth_wires_deps_and_respects_cap():
    """Mutation: forget deps_on -> SYNTH runs before its scouts; ignore caps -> unbounded wave."""
    sk = js.expand("scout-synth", "bp9", breadth=2.0)
    scouts = [m for m in sk if m["class"] == "truth"]
    synth = [m for m in sk if m["class"] == "build"]
    assert len(scouts) == 4 and len(synth) == 1
    assert synth[0]["deps"] == [m["id"] for m in scouts]
    assert all(m["readonly"] for m in scouts)
    assert len(sk) <= js.load_workflows()["caps"]["max_legs_per_wave"]
    assert js.expand("manual", "bp9") == [] and js.expand("swarm", "bp9") == []


def test_expand_never_names_a_model_and_crux_is_referee():
    """Mutation: put a model string in a template -> invariant 1 (rails names models) breaks."""
    sk = js.expand("build-screen-crux", "bp9", breadth=1.0)
    assert [m["tier"] for m in sk if m["class"] == "crucible"] == ["referee"]
    rails = set(jc.rails_tiers()) | {"auto", "none"}
    assert all(m["tier"] in rails for shape in SHAPES for m in js.expand(shape, "bp9", 2.0))


def test_derive_shape_on_real_waves():
    """Mutation: break derive_shape -> the shadow grades Jev against a wrong answer key."""
    import json
    def wave(w):
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(js.MISSIONS.glob(f"{w}-*.json"))]
    assert js.derive_shape(wave("BP4")) == "build-screen-crux"
    assert js.derive_shape(wave("BP6")) == "solo"
    assert js.derive_shape(wave("BP7")) == "scout-synth"


def test_fix_crux_needs_known_cause_and_one_piece():
    """Mutation: leave fix-crux out of the cross-checks -> a referee'd single leg aimed at an
    undiagnosed bug, or at five deliverables."""
    assert js.decide(_a("fix-crux", 0.9, known=0.2), POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("fix-crux", 0.9, known=0.9, breadth=1.7), POLICY, SHAPES)["shape"] == "manual"
    assert js.decide(_a("fix-crux", 0.9, known=0.9, breadth=0.6), POLICY, SHAPES)["shape"] == "fix-crux"
    sk = js.expand("fix-crux", "bp9")
    assert [m["class"] for m in sk] == ["build", "crucible"] and sk[1]["deps"] == [sk[0]["id"]]


def test_few_means_three_not_four_regression():
    """Regression, 2026-09-20: the BP8 objective named THREE changes, Jev scored breadth 1.01
    ('Few') and the old linear map produced FOUR builders. Mutation: restore the linear map."""
    assert js.leg_count(2, 5, 1.01) == 3
    assert js.leg_count(2, 4, 1.84) == 4           # BP7: 'Many' -> the four scouts it really had
    assert js.leg_count(2, 5, 1.01, legs=2) == 2   # the author's count wins ...
    assert js.leg_count(2, 5, 0.0, legs=9) == 5    # ... but never past the template's bounds
    assert len([m for m in js.expand("build-screen-crux", "bp9", 1.01) if m["class"] == "build"]) == 3


def test_templates_obey_the_mission_schema():
    """Regression, 2026-09-20: the first catalog gave TIDY a band the schema does not have and
    readonly:false under TRUST. Mutation: put any band outside mission_schema.BANDS in a template."""
    bp = str(js.REPO / "harness" / "battleplan")
    if bp not in sys.path:
        sys.path.insert(0, bp)
    import mission_schema as ms
    for shape in SHAPES:
        for m in js.expand(shape, "bp9", 2.0):
            assert m["band"] in ms.BANDS, (shape, m["id"], m["band"])
            assert m["band"] != "TRUST" or m["readonly"] is True, (shape, m["id"])
            assert ms.ID_RE.match(m["id"]), m["id"]
