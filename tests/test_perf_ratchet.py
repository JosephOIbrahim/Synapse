"""The perf-ratchet CI gate (I2 design, R304 lane R).

Pins the 98b556f (4x stage-hash) and H10 (volume-gate) wins as INTEGERS so a
refactor cannot silently give either back. Counted proxy, not wall-clock: CI
has no pxr (ci.yml installs [dev,websocket,mcp]; pyproject has no usd-core
extra), so a timer cannot gate this repo and a deterministic counter cannot
flake. Runs on a pxr-less interpreter by construction; the one pxr-gated test
(the fake-fidelity cross-check) SKIPS honestly where pxr is absent.

WHY THIS EXISTS (the hole, stated once): the two tests that pin 98b556f
behaviourally — tests/test_stage_hash_honesty.py:31 and
tests/test_scene_hash_gate.py:27 — both importorskip("pxr") and therefore
SKIP on every CI leg. The win looked covered and was not.

REGRESSION PROOFS are deleteable guards: each one simulates the named defect
THROUGH THE COUNTING SEAM (env pins / runtime monkeypatch of the bridge
seam), never by reverting code, and asserts the ratchet trips. Deleting one
deletes real protection — they are named accordingly.

The gate discipline (floor at merge-base, direction rule, waivers, promotion
shape) lives in harness/verify/perf_ratchet.py — the ONE comparator, shared
with harness checks so callers cannot drift.
"""
from __future__ import annotations

import copy
import datetime as _dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import perf_counters as pc
import shared.bridge as b
from shared.bridge import LosslessExecutionBridge

REPO = Path(__file__).resolve().parent.parent
FLOOR_PATH = REPO / "harness" / "verify" / "perf_baseline.json"


def _load_perf_ratchet():
    mod = sys.modules.get("perf_ratchet")
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(
        "perf_ratchet", REPO / "harness" / "verify" / "perf_ratchet.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["perf_ratchet"] = mod
    spec.loader.exec_module(mod)
    return mod


pr = _load_perf_ratchet()


@pytest.fixture(scope="module")
def floor_doc():
    return pr.parse_perf_baseline(FLOOR_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def measured():
    return pc.measure_all()


# ── the instrument itself ────────────────────────────────────────────────────

class TestInstrument:
    def test_all_scenarios_produce_full_vocabulary(self, measured):
        for name, counters in measured.items():
            assert set(counters) == set(pc.COUNTERS), name
            assert all(isinstance(v, int) and v >= 0
                       for v in counters.values()), name

    def test_determinism_same_dict_twice_in_process(self):
        """I2 acceptance: running measure() twice on the same scenario in the
        same process returns byte-identical dicts."""
        for name in pc.SCENARIOS:
            d1 = pc.counters_digest(pc.measure(name))
            d2 = pc.counters_digest(pc.measure(name))
            assert d1 == d2, f"{name}: nondeterministic counters"

    def test_env_independence_hostile_env_and_pxr_seam(self, monkeypatch):
        """Byte-identical counters regardless of operator env and regardless
        of what _import_pxr_composition would return outside the seam — the
        proof that a pxr-present machine counts the same as a pxr-less one
        (flake source #1: bridge.py's class_arcs_enabled branch pays one
        extra bounded traversal when Usd imports)."""
        clean = {n: pc.counters_digest(pc.measure(n)) for n in pc.SCENARIOS}
        # Hostile operator shell: all three knobs skewed.
        monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "999999999")
        monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "1")
        monkeypatch.setenv("SYNAPSE_STAGE_HASH_LARGE_MODE", "full")
        # Hostile pxr seam: whatever a machine's real import would produce.
        monkeypatch.setattr(b, "_import_pxr_composition",
                            lambda: (object(), object()))
        for name, digest in clean.items():
            assert pc.counters_digest(pc.measure(name)) == digest, (
                f"{name}: counters depend on ambient env/pxr state — the "
                f"determinism contract is broken")

    def test_seam_restores_module_state(self):
        before = (b._HOU_AVAILABLE, b.hou, b._import_pxr_composition)
        pc.measure("mcp_lop_op_above_gate")
        assert (b._HOU_AVAILABLE, b.hou, b._import_pxr_composition) == before

    def test_scenario_premise_violation_raises(self):
        """An instrument that half-ran must never return counts."""
        with pytest.raises(pc.PerfScenarioError):
            # Above-gate cell asked to expect 'full' at its normal params.
            pc.measure("mcp_lop_op_above_gate", expect_mode="full")


# ── the headline invariants (98b556f + H10 as integers) ─────────────────────

class TestHeadlineInvariants:
    def test_98b556f_invariant_above_gate(self, measured):
        got = measured["mcp_lop_op_above_gate"]
        assert got["flatten_exports"] == 0, (
            "flatten_exports != 0 above the gate — the 4x win IS this zero")
        assert got["value_reads"] == 0
        # -1 traversal / -1001 prim_visits vs the pre-R302 figures
        # (5 / 17002): lane I's per-op _stage_exceeds cache made the
        # sweep gate reuse the hash gate's verdict, so the op walks the
        # stage once where it used to walk twice. Confirmed three ways:
        # lane I's own call-count test, its crucible's large->small and
        # small->large attack, and this ratchet reporting 'improved'.
        assert got["stage_traversals"] == 4
        assert got["prim_visits"] == 16001

    def test_slope_and_bounded_probes(self, measured):
        """The two bounded probes contribute ZERO to the slope — the property
        no test asserted before this file (I2 §4)."""
        n, n2 = measured["mcp_lop_op_above_gate"], \
            measured["mcp_lop_op_above_gate_2x"]
        assert n2["stage_traversals"] == n["stage_traversals"] == 4  # R302 cache
        assert (n2["prim_visits"] - n["prim_visits"]) == 3 * 5000
        assert n2["flatten_exports"] == n["flatten_exports"] == 0

    def test_live_envelope_never_flattens_with_stage_reachable(self, measured):
        """S-C: the include_stage=False skip is STRUCTURAL — the node carries
        a live stage() and it is never traversed nor flattened."""
        got = measured["live_ws_op"]
        assert got["stage_traversals"] == 0
        assert got["flatten_exports"] == 0
        assert got["prim_visits"] == 0
        assert got["geometry_intrinsic_reads"] == 6  # H1 residue, ratcheted

    def test_below_gate_pays_h10_volume_probe(self, measured):
        """S-A carries FOUR traversals since H10 (f60b5b0): prim probe +
        volume probe + composition probe + composition sweep. The I2 design
        (authored at 48bf572) derived three — the run wins, and this pin
        makes the H10 probe's boundedness part of the floor."""
        got = measured["mcp_lop_op_below_gate"]
        assert got["stage_traversals"] == 3  # was 4 pre-R302 cache
        assert got["flatten_exports"] == 2   # full mode: Flatten before+after
        assert got["attrs_examined"] == 100  # volume probe type peeks
        assert got["value_reads"] == 0       # scalar attrs: peek never reads


# ── floor shape (Law 1: stated failure conditions each raise) ───────────────

class TestFloorShape:
    def test_worktree_floor_parses(self, floor_doc):
        assert floor_doc["schema"] == "perf_baseline/counts-v1"

    def test_floor_is_promoted_and_human_armed(self, floor_doc):
        """ARMED 2026-08-02. This test previously pinned the PROPOSED state
        (proposed is True / human_armed_by is None); it now pins the armed one.

        The point of the assertion never was which state the floor is in — it
        is that the floor cannot be in NEITHER state, i.e. that a floor always
        carries provenance. A floor promoted by nobody is not a floor, and
        arming by the thing being measured is exactly what the human gate
        exists to prevent.
        """
        assert floor_doc["proposed"] is False, (
            "the floor is armed; it must no longer advertise itself as a "
            "proposal")
        armed_by = (floor_doc.get("human_armed_by") or "").strip()
        promoted_by = (floor_doc.get("promoted_by") or "").strip()
        assert armed_by and promoted_by, (
            "an armed floor must name the human who armed and promoted it")
        assert armed_by == promoted_by, (
            "promotion and arming are one human act; two different names means "
            "one of them was not a human decision")

    def test_not_json_raises(self):
        with pytest.raises(pr.PerfBaselineShapeError):
            pr.parse_perf_baseline("not json {")

    def test_non_object_root_raises(self):
        with pytest.raises(pr.PerfBaselineShapeError):
            pr.parse_perf_baseline("[1, 2]")

    def test_wrong_schema_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        doc["schema"] = "perf_baseline/v0"
        with pytest.raises(pr.PerfBaselineShapeError):
            pr.parse_perf_baseline(json.dumps(doc))

    def test_missing_pinned_constants_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        del doc["pinned_constants"]
        with pytest.raises(pr.PerfBaselineShapeError,
                           match="pinned_constants"):
            pr.parse_perf_baseline(json.dumps(doc))

    def test_empty_scenarios_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        doc["scenarios"] = {}
        with pytest.raises(pr.PerfBaselineShapeError):
            pr.parse_perf_baseline(json.dumps(doc))

    @pytest.mark.parametrize("field", ["producer", "harness", "env_pins",
                                       "scale_term", "_why"])
    def test_cell_missing_required_field_raises(self, floor_doc, field):
        doc = copy.deepcopy(floor_doc)
        del doc["scenarios"]["mcp_lop_op_above_gate"][field]
        with pytest.raises(pr.PerfBaselineShapeError, match=field):
            pr.parse_perf_baseline(json.dumps(doc))

    def test_cell_without_intercept_counters_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        doc["scenarios"]["mcp_lop_op_above_gate"]["intercept"]["counters"] = {}
        with pytest.raises(pr.PerfBaselineShapeError, match="counters"):
            pr.parse_perf_baseline(json.dumps(doc))

    def test_unpinned_stub_without_what_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        doc["scenarios"]["execute_pdg_deferred"]["_what"] = ""
        with pytest.raises(pr.PerfBaselineShapeError, match="UNPINNED"):
            pr.parse_perf_baseline(json.dumps(doc))

    def test_waiver_missing_fields_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        doc["scenarios"]["mcp_lop_op_above_gate"]["waiver"] = {
            "reason": "temporary"}  # no expires, no granted_by
        with pytest.raises(pr.PerfBaselineShapeError, match="waiver"):
            pr.parse_perf_baseline(json.dumps(doc))

    def test_no_provenance_raises(self, floor_doc):
        doc = copy.deepcopy(floor_doc)
        doc["proposed"] = False
        doc["promoted_by"] = None
        with pytest.raises(pr.PerfBaselineShapeError, match="provenance"):
            pr.parse_perf_baseline(json.dumps(doc))


# ── promotion shape: a raised floor must say why ────────────────────────────

class TestPromotionShape:
    def _raised(self, floor_doc, **cell_updates):
        doc = copy.deepcopy(floor_doc)
        cell = doc["scenarios"]["mcp_lop_op_above_gate"]
        cell["intercept"]["counters"]["prim_visits"] += 5000
        cell.update(cell_updates)
        return doc

    def test_rose_without_new_why_raises(self, floor_doc):
        with pytest.raises(pr.PerfBaselineShapeError, match="ROSE"):
            pr.validate_promotion(floor_doc, self._raised(floor_doc))

    def test_rose_with_new_why_passes(self, floor_doc):
        pr.validate_promotion(
            floor_doc,
            self._raised(floor_doc,
                         _why="correctness fix X costs one traversal "
                              "while its cheap form is built"))

    def test_rose_with_valid_waiver_passes(self, floor_doc):
        expires = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        pr.validate_promotion(
            floor_doc,
            self._raised(floor_doc,
                         waiver={"reason": "temp regression", "ticket": "T-1",
                                 "expires": expires, "granted_by": "human"}))


# ── comparison semantics: direction rule, waivers, instrument asymmetry ─────

class TestCompareSemantics:
    def test_measured_matches_proposed_floor(self, measured, floor_doc):
        """While the floor is PROPOSED it is a measurement record: intercepts
        must EQUAL the live measurement (a stale proposal must not be
        promotable). Once promoted, the gate is compare() alone and counts
        may fall freely — this equality branch self-retires."""
        verdict = pr.compare(measured, floor_doc)
        assert verdict.ok, [r for r in verdict.rows if r["status"] == "FAIL"]
        if floor_doc.get("proposed"):
            for name, cell in floor_doc["scenarios"].items():
                if cell.get("status") == "UNPINNED":
                    continue
                assert measured[name] == cell["intercept"]["counters"], (
                    f"{name}: PROPOSED floor is stale vs the live measurement "
                    f"— re-run `python tests/perf_counters.py` and refresh "
                    f"harness/verify/perf_baseline.json + "
                    f"harness/notes/perf/PROPOSED_perf_baseline.json")

    def test_falls_are_free(self, measured, floor_doc):
        doc = copy.deepcopy(floor_doc)
        cell = doc["scenarios"]["mcp_lop_op_above_gate"]
        cell["intercept"]["counters"]["prim_visits"] += 1  # floor above live
        verdict = pr.compare(measured, doc)
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert row["status"] == "PASS"
        assert "improved" in row["detail"]

    def test_instrument_deleted_fails(self, measured, floor_doc):
        got = copy.deepcopy(measured)
        del got["mcp_lop_op_above_gate"]["flatten_exports"]
        verdict = pr.compare(got, floor_doc)
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert row["status"] == "FAIL"
        assert "instrument deleted" in row["detail"]

    def test_new_counter_reported_not_gating(self, measured, floor_doc):
        got = copy.deepcopy(measured)
        for name in got:
            got[name]["brand_new_counter"] = 12345
        verdict = pr.compare(got, floor_doc)
        assert verdict.ok
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert "NEW" in row["detail"]

    def test_missing_scenario_fails(self, measured, floor_doc):
        got = {k: v for k, v in measured.items() if k != "rollback_op"}
        verdict = pr.compare(got, floor_doc)
        row = next(r for r in verdict.rows if r["id"] == "PR:rollback_op")
        assert row["status"] == "FAIL"
        assert "instrument deleted" in row["detail"]

    def test_expired_waiver_fails_future_waiver_passes(self, measured,
                                                       floor_doc):
        got = copy.deepcopy(measured)
        got["mcp_lop_op_above_gate"]["prim_visits"] += 100  # regression
        base = copy.deepcopy(floor_doc)
        cell = base["scenarios"]["mcp_lop_op_above_gate"]

        cell["waiver"] = {"reason": "known temp", "ticket": "T-2",
                          "expires": "2026-01-01", "granted_by": "human"}
        verdict = pr.compare(got, base, today=_dt.date(2026, 8, 2))
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert row["status"] == "FAIL"
        assert "expired waiver" in row["detail"]

        cell["waiver"]["expires"] = "2026-12-31"
        verdict = pr.compare(got, base, today=_dt.date(2026, 8, 2))
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert row["status"] == "PASS"
        assert "WAIVED" in row["detail"]

    def test_rows_match_verify_py_contract(self, measured, floor_doc):
        """harness/latency/verify.py consumes {id,label,status,detail,
        producer} with status in PASS|FAIL|PENDING|UNKNOWN."""
        for r in pr.compare(measured, floor_doc).rows:
            assert set(r) == {"id", "label", "status", "detail", "producer"}
            assert r["status"] in ("PASS", "FAIL", "PENDING", "UNKNOWN")
            assert r["detail"] and r["producer"]


# ── the anchor: a branch cannot lower its own bar ───────────────────────────

class TestAnchor:
    def test_anchor_is_always_reported(self):
        raw, anchor, note = pr.read_floor(REPO)
        assert anchor and note  # no silent fallback path exists
        if raw is None:
            assert "absent" in note or "unresolvable" in note
        else:
            pr.parse_perf_baseline(raw)  # a floor at the anchor must parse

    def test_run_gate_honest_end_to_end(self):
        """Pre-promotion: floor absent at merge-base + not armed => PENDING
        (never PASS, never FAIL). Post-promotion: the same call IS the gate —
        a FAIL here after arming means the ratchet fired; fix the regression,
        do not touch the floor (deny-listed; merge-base wins anyway)."""
        verdict = pr.run_gate(REPO)
        assert verdict.ok, [r for r in verdict.rows
                            if r["status"] == "FAIL"]
        assert all(r["detail"] and r["producer"] for r in verdict.rows)

    def test_worktree_floor_edit_cannot_green_the_gate(self, measured,
                                                       floor_doc, tmp_path):
        """The comparison floor comes from `git show <merge-base>:...` — a
        lowered/raised WORKTREE copy is only consulted for promotion-shape
        validation, never as the bar. Proven here at the unit level: compare()
        against the anchor doc ignores a doctored worktree doc entirely."""
        doctored = copy.deepcopy(floor_doc)
        for cell in doctored["scenarios"].values():
            if cell.get("status") != "UNPINNED":
                for k in cell["intercept"]["counters"]:
                    cell["intercept"]["counters"][k] += 10 ** 6
        # The gate compares against floor_doc (the anchor's), not `doctored`;
        # nothing in compare() reads the filesystem.
        verdict = pr.compare(measured, floor_doc)
        assert verdict.ok
        src = (REPO / "harness" / "verify" / "perf_ratchet.py").read_text(
            encoding="utf-8")
        assert "merge-base" in src  # the P7 predicate greps for this literal


# ── REGRESSION PROOFS — deleteable guards (I2 §8 / acceptance 4-7) ──────────

class TestRegressionProofs:
    """Each proof simulates the named defect through the counting seam (env
    pin or runtime monkeypatch of the bridge seam) and asserts the ratchet
    TRIPS. Deleting any of these deletes real protection."""

    def test_proof1_threshold_above_stage_size_trips_flatten(self, floor_doc):
        """THE 98b556f DEFECT: gate threshold above the stage size => the op
        pays full Flatten again. The S-B cell must fail loudly on
        flatten_exports 2 > floor 0."""
        got = pc.measure("mcp_lop_op_above_gate",
                         threshold=1_000_000, expect_mode="full")
        assert got["flatten_exports"] == 2
        measured = pc.measure_all()
        measured["mcp_lop_op_above_gate"] = got
        verdict = pr.compare(measured, floor_doc)
        assert not verdict.ok
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert "flatten_exports 2 > floor 0" in row["detail"]

    def test_proof1b_default_revert_trips_pinned_constants(self, floor_doc,
                                                           monkeypatch,
                                                           measured):
        """Reverting _DEFAULT_STAGE_HASH_PRIM_THRESHOLD to 1 << 62 leaves
        every count cell green (they pin their own env) — the
        pinned_constants check is the ONLY closure, and it must fire."""
        monkeypatch.setattr(b, "_DEFAULT_STAGE_HASH_PRIM_THRESHOLD", 1 << 62)
        fails = pr.check_pinned_constants(floor_doc["pinned_constants"],
                                          bridge_mod=b)
        assert any("_DEFAULT_STAGE_HASH_PRIM_THRESHOLD" in f for f in fails)
        verdict = pr.compare(measured, floor_doc)
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:pinned_constants")
        assert row["status"] == "FAIL"
        assert not verdict.ok

    def test_proof2_deleting_short_circuit_trips_prim_visits(self, floor_doc,
                                                             monkeypatch):
        """Deleting the _stage_exceeds short-circuit (bridge.py:1085) makes
        both bounded probes consume the whole stage: prim_visits 16001 ->
        20000 at the S-B cell (4 full passes of 5000 -- one pass fewer than
        the pre-R302 figure, because the per-op _stage_exceeds cache removed
        a walk; the PROOF is that the gate still trips, asserted below)."""
        def _no_short_circuit(stage, threshold):
            n = 0
            for _ in stage.TraverseAll():
                n += 1
            return n > threshold

        monkeypatch.setattr(LosslessExecutionBridge, "_stage_exceeds",
                            staticmethod(_no_short_circuit))
        got = pc.measure("mcp_lop_op_above_gate")
        assert got["prim_visits"] == 20000  # 4 full passes of 5000
        measured = pc.measure_all()
        verdict = pr.compare(measured, floor_doc)
        assert not verdict.ok
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert "prim_visits" in row["detail"]

    def test_proof3_extra_traversal_trips_slope_even_if_intercept_promoted(
            self, floor_doc, monkeypatch):
        """Adding one more full-stage traversal per hash fails the intercept
        (stage_traversals 5 -> 7) AND the slope (prim_visits/prim 3.0 -> 5.0)
        — and the slope STILL fails after the intercept is independently
        promoted (I2 §4: the cell that catches scale-dependent work)."""
        orig = LosslessExecutionBridge._reduced_stage_signature

        def _with_extra_pass(stage):
            for _ in stage.TraverseAll():   # the refactor's extra pass
                pass
            return orig(stage)

        monkeypatch.setattr(LosslessExecutionBridge,
                            "_reduced_stage_signature",
                            staticmethod(_with_extra_pass))
        measured = pc.measure_all()
        got = measured["mcp_lop_op_above_gate"]
        assert got["stage_traversals"] == 6  # was 7 pre-R302 cache

        verdict = pr.compare(measured, floor_doc)
        assert not verdict.ok  # intercept trips

        promoted = copy.deepcopy(floor_doc)
        for name in ("mcp_lop_op_above_gate", "mcp_lop_op_above_gate_2x"):
            cell = promoted["scenarios"][name]
            cell["intercept"]["counters"] = dict(measured[name])
            cell["_why"] = "TEST: intercept independently promoted"
        verdict = pr.compare(measured, promoted)
        assert not verdict.ok, (
            "slope cell failed to catch scale-dependent work after an "
            "intercept-only promotion")
        row = next(r for r in verdict.rows
                   if r["id"] == "PR:mcp_lop_op_above_gate")
        assert "slope" in row["detail"] or "passes_per_op" in row["detail"]


# ── fake-fidelity cross-check (I2 §12) — pxr-gated, SKIPS in CI ─────────────

class TestPxrFidelity:
    """A counting PROXY over a REAL Usd.Stage must produce the SAME counter
    dict as the pure fake — the only guard against the fake drifting from
    the real pxr API. Reports SKIPPED (not passed) where pxr is absent:
    CI green does NOT cover this."""

    @staticmethod
    def _proxy_factory():
        pxr = pytest.importorskip("pxr")
        from pxr import Sdf, Usd  # noqa: F401

        class _ProxyAttr:
            def __init__(self, attr, c):
                self._a, self._c = attr, c

            def GetName(self):
                return self._a.GetName()

            def GetTypeName(self):
                self._c["attrs_examined"] += 1
                return self._a.GetTypeName()

            def Get(self, *a):
                self._c["value_reads"] += 1
                return self._a.Get(*a)

            def GetTimeSamples(self):
                self._c["value_reads"] += 1
                return self._a.GetTimeSamples()

            def GetNumTimeSamples(self):
                return self._a.GetNumTimeSamples()

        class _ProxyPrim:
            def __init__(self, prim, c):
                self._p, self._c = prim, c

            def GetPath(self):
                return self._p.GetPath()

            def GetTypeName(self):
                self._c["prim_state_reads"] += 1
                return self._p.GetTypeName()

            def GetSpecifier(self):
                self._c["prim_state_reads"] += 1
                return self._p.GetSpecifier()

            def IsActive(self):
                self._c["prim_state_reads"] += 1
                return self._p.IsActive()

            def IsValid(self):
                self._c["prim_state_reads"] += 1
                return self._p.IsValid()

            def GetAuthoredPropertyNames(self):
                self._c["prop_name_reads"] += 1
                return self._p.GetAuthoredPropertyNames()

            def GetAuthoredRelationships(self):
                self._c["rel_target_reads"] += 1
                return list(self._p.GetAuthoredRelationships())

            def GetAuthoredAttributes(self):
                return [_ProxyAttr(a, self._c)
                        for a in self._p.GetAuthoredAttributes()]

            def HasAuthoredReferences(self):
                self._c["arc_queries"] += 1
                return self._p.HasAuthoredReferences()

            def HasAuthoredPayloads(self):
                self._c["arc_queries"] += 1
                return self._p.HasAuthoredPayloads()

            def HasAuthoredInherits(self):
                self._c["arc_queries"] += 1
                return self._p.HasAuthoredInherits()

            def HasAuthoredSpecializes(self):
                self._c["arc_queries"] += 1
                return self._p.HasAuthoredSpecializes()

        class _ProxyLayer:
            def __init__(self, layer, c):
                self._l, self._c = layer, c

            def ExportToString(self):
                self._c["flatten_exports"] += 1
                return self._l.ExportToString()

        class _ProxyStage:
            def __init__(self, stage, c):
                self._s, self._c = stage, c

            def _wrap(self, it):
                for prim in it:
                    self._c["prim_visits"] += 1
                    yield _ProxyPrim(prim, self._c)

            def TraverseAll(self):
                self._c["stage_traversals"] += 1
                return self._wrap(self._s.TraverseAll())

            def Traverse(self):
                self._c["stage_traversals"] += 1
                return self._wrap(self._s.Traverse())

            def Flatten(self):
                return _ProxyLayer(self._s.Flatten(), self._c)

        def factory(counters, prims):
            stage = Usd.Stage.CreateInMemory()
            for i in range(prims):
                p = stage.DefinePrim(f"/p{i}", "Sphere")
                p.CreateAttribute(
                    "radius", Sdf.ValueTypeNames.Double).Set(1.0)
            return _ProxyStage(stage, counters)

        return factory

    def test_real_stage_counts_equal_fake_counts(self):
        factory = self._proxy_factory()
        # Small params: the PATTERN equality is the claim, not the magnitude.
        for scenario, kw in (
            ("mcp_lop_op_above_gate",
             dict(prims=50, threshold=10, expect_mode="reduced")),
            ("mcp_lop_op_below_gate",
             dict(prims=20, threshold=100, expect_mode="full")),
        ):
            fake = pc.measure(scenario, **kw)
            real = pc.measure(scenario, stage_factory=factory, **kw)
            assert pc.counters_digest(real) == pc.counters_digest(fake), (
                f"{scenario}: the counting fake has drifted from the real "
                f"pxr call pattern — the ratchet is counting a fiction")


# ---------------------------------------------------------------------------
# R304 crucible follow-up — the anchor must not weaken on a PR checkout
# ---------------------------------------------------------------------------

def test_anchor_resolves_via_origin_master_when_no_local_master(tmp_path):
    """The GitHub PR checkout shape: origin/master exists, local master does not.

    The crucible's landed attack (severity 3/5): read_floor looked up only a
    LOCAL `master`, so on actions/checkout — which fetches the PR ref and
    leaves no local master — it silently fell through to HEAD-committed, and a
    branch's own committed doctored floor became its bar. A ratchet whose
    anchor weakens exactly in CI is not a ratchet.
    """
    import subprocess
    src = Path(__file__).resolve().parent.parent
    clone = tmp_path / "pr-checkout"

    def git(*args, cwd):
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    rc = git("clone", "--no-local", "--quiet", str(src), str(clone), cwd=src)
    if rc.returncode != 0:
        pytest.skip(f"clone unavailable in this environment: {rc.stderr[:120]}")
    # Reproduce the PR shape: a feature branch, no local master at all.
    git("checkout", "--quiet", "-b", "pr-branch", cwd=clone)
    git("branch", "-D", "master", cwd=clone)

    assert git("rev-parse", "--verify", "--quiet", "master",
               cwd=clone).returncode != 0, "fixture must have NO local master"
    assert git("rev-parse", "--verify", "--quiet", "origin/master",
               cwd=clone).returncode == 0, "fixture must have origin/master"

    _raw, anchor, note = _load_perf_ratchet().read_floor(clone)
    assert "merge-base" in note, (
        f"anchor degraded on a PR checkout — the branch would gate against its "
        f"own floor. note={note!r}")
    assert anchor and anchor != "HEAD-committed"
    # And it must say WHICH ref it used, so the weaker tier is never silent.
    assert "origin/master" in note, f"anchor note must name the ref: {note!r}"
