"""R1 stage-integrity hash: size-gate + instrumentation (INTEGRITY-CRITICAL).

The R1 scene hash drives scene_hash_before/after change-detection, delta_hash, and
the fidelity verdict. A hash that MISSES a mutation makes integrity verification
silently PASS when it should FAIL. This test pins two guarantees on the size-gate
added to shared/bridge.py:

  1. BELOW the prim threshold the stage hash is BYTE-IDENTICAL to the pre-change
     algorithm (sha256 of stage.Flatten().ExportToString()) — so normal stages and
     every existing test are unaffected.
  2. ABOVE the threshold the cheaper structural signature still changes for EVERY
     mutation class (prim add/remove/rename, type/specifier change, attribute
     add/remove, attribute VALUE change, metadata/composition-arc change, activation,
     visibility). Under-capture would be a defect; over-capture is safe.

Plus: the scene_hash_ms instrumentation sink records every _compute_scene_hash call.

pxr (OpenUSD) required for the stage-signature assertions; skipped if unavailable.
"""
import hashlib

import pytest

import shared.bridge as b
from shared.constants import HASH_LENGTH

pytest.importorskip("pxr")
from pxr import Usd, Sdf, UsdGeom  # noqa: E402


# ── stage builders ─────────────────────────────────────────────

def _base_stage():
    """A small composed stage: /root (Xform, default) with a typed child that has
    an authored attribute. Fresh instance per call so mutation tests are isolated."""
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    child = stage.DefinePrim("/root/child", "Sphere")
    child.CreateAttribute("radius", Sdf.ValueTypeNames.Double).Set(1.0)
    return stage


def _old_flatten_hash(stage):
    """The EXACT pre-change algorithm: sha256 of the flattened USDA string."""
    flat = stage.Flatten().ExportToString()
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def _sig(stage):
    return b.LosslessExecutionBridge()._structural_stage_signature(stage)


# ── TASK 1a: below-threshold byte-identical ────────────────────

def test_below_threshold_is_byte_identical_to_old_flatten(monkeypatch):
    """A small stage (< default 5000 prims) must hash to the EXACT old digest."""
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", raising=False)
    stage = _base_stage()
    gated = b.LosslessExecutionBridge()._hash_stage_signature(stage)
    assert gated == _old_flatten_hash(stage), (
        "below-threshold stage hash diverged from the pre-change Flatten algorithm"
    )


def test_gate_routes_to_flatten_below_and_structural_above(monkeypatch):
    """The gate itself: high threshold -> Flatten path; threshold 0 -> structural."""
    stage = _base_stage()
    old = _old_flatten_hash(stage)

    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "100000")
    assert b.LosslessExecutionBridge()._hash_stage_signature(stage) == old

    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "0")
    above = b.LosslessExecutionBridge()._hash_stage_signature(stage)
    assert above == _sig(stage), "above-threshold must use the structural signature"
    assert above != old, "structural signature must differ from the Flatten digest"


def test_threshold_env_parsing(monkeypatch):
    """Bad/absent env values fall back to the default (structural off / opt-in)."""
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", raising=False)
    assert b._stage_hash_prim_threshold() == b._DEFAULT_STAGE_HASH_PRIM_THRESHOLD
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "garbage")
    assert b._stage_hash_prim_threshold() == b._DEFAULT_STAGE_HASH_PRIM_THRESHOLD
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "-7")
    assert b._stage_hash_prim_threshold() == b._DEFAULT_STAGE_HASH_PRIM_THRESHOLD
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "250")
    assert b._stage_hash_prim_threshold() == 250


# ── TASK 1b: above-threshold signature stability + completeness ─

def test_structural_signature_is_stable():
    """Same stage -> same structural signature (no false-positive churn)."""
    stage = _base_stage()
    assert _sig(stage) == _sig(stage)


# Each mutator takes a freshly built base stage and applies ONE mutation class.
def _m_prim_add(s):
    s.DefinePrim("/root/added", "Cube")

def _m_prim_remove(s):
    s.RemovePrim("/root/child")

def _m_prim_rename(s):
    # rename == same content, different path (copy spec then drop the original)
    Sdf.CopySpec(s.GetRootLayer(), "/root/child", s.GetRootLayer(), "/root/child2")
    s.RemovePrim("/root/child")

def _m_type_change(s):
    s.GetPrimAtPath("/root/child").SetTypeName("Cube")

def _m_specifier_change(s):
    # flip /root/child def -> over in place (same path, specifier changes)
    s.GetRootLayer().GetPrimAtPath("/root/child").specifier = Sdf.SpecifierOver

def _m_attr_add(s):
    s.GetPrimAtPath("/root/child").CreateAttribute(
        "extra", Sdf.ValueTypeNames.Float
    ).Set(5.0)

def _m_attr_value_change(s):
    s.GetPrimAtPath("/root/child").GetAttribute("radius").Set(99.0)

def _m_attr_timesamples(s):
    # adding a time sample changes the attribute without touching the default value
    s.GetPrimAtPath("/root/child").GetAttribute("radius").Set(7.0, Usd.TimeCode(5.0))

def _m_attr_remove(s):
    s.GetPrimAtPath("/root/child").RemoveProperty("radius")

def _m_metadata_change(s):
    s.GetPrimAtPath("/root/child").SetMetadata("comment", "mutated")

def _m_arc_inherit(s):
    # composition arc: inherit from a class path (authors `inheritPaths` metadata)
    s.GetPrimAtPath("/root/child").GetInherits().AddInherit("/_class_thing")

def _m_activation(s):
    s.GetPrimAtPath("/root/child").SetActive(False)

def _m_visibility(s):
    UsdGeom.Imageable(s.GetPrimAtPath("/root/child")).CreateVisibilityAttr("invisible")


@pytest.mark.parametrize("mutator", [
    _m_prim_add,
    _m_prim_remove,
    _m_prim_rename,
    _m_type_change,
    _m_specifier_change,
    _m_attr_add,
    _m_attr_value_change,
    _m_attr_timesamples,
    _m_attr_remove,
    _m_metadata_change,
    _m_arc_inherit,
    _m_activation,
    _m_visibility,
], ids=lambda f: f.__name__[3:])
def test_structural_signature_changes_per_mutation_class(mutator):
    """The structural signature MUST change for every mutation class. Under-capture
    here would let an integrity check silently pass on a real scene change."""
    stage = _base_stage()
    before = _sig(stage)
    mutator(stage)
    after = _sig(stage)
    assert after != before, (
        f"{mutator.__name__}: structural signature did NOT change for this "
        "mutation class -- integrity verification would silently pass"
    )


def test_structural_signature_catches_relationship_retarget():
    """Relationship RETARGET (material:binding rebind, light-linking, collections):
    the property NAME and prim metadata stay identical — only the targets move.
    Flatten catches this, so the structural signature MUST digest rel targets or an
    integrity check silently passes on a real material/light rebind above threshold."""
    stage = _base_stage()
    stage.DefinePrim("/root/matA", "Material")
    stage.DefinePrim("/root/matB", "Material")
    rel = stage.GetPrimAtPath("/root/child").CreateRelationship("material:binding")
    rel.SetTargets(["/root/matA"])
    before = _sig(stage)
    # Rebind to a different target — name unchanged, only targets move.
    stage.GetPrimAtPath("/root/child").GetRelationship(
        "material:binding"
    ).SetTargets(["/root/matB"])
    after = _sig(stage)
    assert after != before, (
        "relationship retarget did NOT change the structural signature — a material "
        "rebind / light-link change would silently pass integrity above threshold"
    )


def test_structural_signature_survives_huge_stage_cheaply():
    """A >threshold stage routes to the structural path and produces a stable,
    mutation-sensitive 16-hex digest without Flatten()."""
    stage = Usd.Stage.CreateInMemory()
    stage.SetDefaultPrim(stage.DefinePrim("/root", "Xform"))
    for i in range(50):
        stage.DefinePrim(f"/root/p{i}", "Sphere")
    bridge = b.LosslessExecutionBridge()
    assert bridge._stage_exceeds(stage, 10) is True
    assert bridge._stage_exceeds(stage, 1000) is False
    sig0 = _sig(stage)
    assert len(sig0) == HASH_LENGTH
    stage.GetPrimAtPath("/root/p7").CreateAttribute(
        "k", Sdf.ValueTypeNames.Int
    ).Set(3)
    assert _sig(stage) != sig0


# ── TASK 2: instrumentation sink ───────────────────────────────

def test_scene_hash_instrumentation_records_and_resets():
    """Every _compute_scene_hash call records a sample into the scene_hash_ms sink;
    reset zeroes it. Works without hou (the standalone fallback is timed too)."""
    b.reset_scene_hash_stats()
    try:
        bridge = b.LosslessExecutionBridge()
        start = b.scene_hash_stats()["count"]
        bridge._compute_scene_hash("/obj")
        bridge._compute_scene_hash(None)
        stats = b.scene_hash_stats()
        assert stats["count"] == start + 2
        assert stats["sum_ms"] >= 0.0
        assert set(stats["buckets"]) == set(b._SCENE_HASH_BUCKETS_MS)
    finally:
        b.reset_scene_hash_stats()
    assert b.scene_hash_stats()["count"] == 0


def test_scene_hash_value_unchanged_by_timing_wrapper(monkeypatch):
    """The timed wrapper must return the implementation's value VERBATIM (and still
    record a sample). A deterministic stub is used because the standalone fallback is
    time-based, so two raw calls legitimately differ."""
    bridge = b.LosslessExecutionBridge()
    monkeypatch.setattr(bridge, "_compute_scene_hash_impl", lambda tp: f"SENTINEL::{tp}")
    b.reset_scene_hash_stats()
    try:
        out = bridge._compute_scene_hash("/some/path")
        assert out == "SENTINEL::/some/path"
        assert b.scene_hash_stats()["count"] == 1
    finally:
        b.reset_scene_hash_stats()
