"""Standalone tests for the SYNAPSE science harness.

NO Houdini, NO apex import. Everything runs against a FAKE namespace dict and
MOCK probe functions. Covers:

* probe()    — present / absent / missing-root / mis-shaped / callable+signature;
               never raises.
* Registry   — round-trip, dedup (record -> False on duplicate), known(),
               JSONL persistence in tmp_path, deposit_fn called once per new rec.
* run_search — rank-desc ordering, SKIP already-known (no re-walk), champion vs
               dead_end classification, second-seed gate holds an unconfirmed
               present, returns the right buckets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# --- Bootstrap: package root is <repo>/python -------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from synapse.science import (  # noqa: E402
    APEX_SEED,
    ProbeResult,
    ProbeSpec,
    Record,
    Registry,
    probe,
    run_search,
)


# ===========================================================================
# Fixtures: a FAKE namespace (no Houdini, no apex)
# ===========================================================================

class _FakeGraph:
    """Stand-in for an APEX Graph type with a callable mutator."""

    def addNode(self, name, node_type, position=None):  # noqa: N802 - mirror API
        return (name, node_type, position)

    not_callable = 42  # a present-but-non-callable attribute


class _FakeApex:
    Graph = _FakeGraph


@pytest.fixture
def namespace():
    return {
        "apex": _FakeApex(),
        # a plain dict root so we can exercise getattr-failure paths cleanly
        "weird": object(),
    }


# ===========================================================================
# probe()
# ===========================================================================

def test_probe_present_callable_with_signature(namespace):
    spec = ProbeSpec(surface="apex.Graph.addNode", kind="call", expect="present")
    res = probe(namespace, spec)
    assert isinstance(res, ProbeResult)
    assert res.present is True
    assert res.is_callable is True
    assert res.signature is not None
    assert "name" in res.signature
    assert res.error is None
    assert res.surface == "apex.Graph.addNode"
    assert res.kind == "call"


def test_probe_present_non_callable_attr(namespace):
    spec = ProbeSpec(surface="apex.Graph.not_callable", kind="attr")
    res = probe(namespace, spec)
    assert res.present is True
    assert res.is_callable is False
    # int has no inspectable signature -> None, but no error and present.
    assert res.signature is None
    assert res.error is None


def test_probe_present_type_object_callable(namespace):
    # apex.Graph is a class -> present + callable (classes are callable).
    spec = ProbeSpec(surface="apex.Graph", kind="attr", expect="present")
    res = probe(namespace, spec)
    assert res.present is True
    assert res.is_callable is True
    assert res.error is None


def test_probe_missing_root_key(namespace):
    spec = ProbeSpec(surface="nope.Whatever", kind="attr")
    res = probe(namespace, spec)
    assert res.present is False
    assert res.error is not None
    assert "nope" in res.error  # repr of the KeyError mentions the missing root


def test_probe_attr_absent_on_present_root(namespace):
    spec = ProbeSpec(surface="apex.DoesNotExist", kind="attr")
    res = probe(namespace, spec)
    assert res.present is False
    assert res.error is not None
    assert res.is_callable is False


def test_probe_mis_shaped_namespace_never_raises():
    # namespace whose root is not an object you can getattr meaningfully.
    ns = {"apex": 123}  # int has no .Graph
    spec = ProbeSpec(surface="apex.Graph.addNode", kind="call")
    res = probe(ns, spec)
    assert res.present is False
    assert res.error is not None


def test_probe_never_raises_across_shapes():
    bad_namespaces = [
        {},
        {"apex": None},
        {"apex": []},
        {"apex": "a string"},
        {"apex": object()},
    ]
    spec = ProbeSpec(surface="apex.Graph.addNode", kind="call")
    for ns in bad_namespaces:
        res = probe(ns, spec)  # must not raise
        assert res.present is False
        assert res.error is not None


def test_probe_empty_namespace_root_missing():
    spec = ProbeSpec(surface="apex", kind="attr")
    res = probe({}, spec)
    assert res.present is False
    assert res.error is not None


def test_probe_single_segment_present():
    ns = {"apex": _FakeApex()}
    res = probe(ns, ProbeSpec(surface="apex", kind="attr"))
    assert res.present is True
    # an instance is not callable
    assert res.is_callable is False


# ===========================================================================
# Registry
# ===========================================================================

def _rec(surface="apex.Graph", kind="attr", status="champion", **kw):
    return Record(surface=surface, kind=kind, status=status, **kw)


def test_registry_record_roundtrip_and_known():
    reg = Registry()
    rec = _rec(detail="sig", context="why", timestamp=7)
    assert reg.record(rec) is True
    got = reg.known("apex.Graph", "attr")
    assert got == rec
    assert reg.all() == [rec]


def test_registry_dedup_returns_false_on_duplicate():
    reg = Registry()
    first = _rec(status="champion")
    assert reg.record(first) is True
    # same (surface, kind), different status — must be rejected, not overwritten.
    dup = _rec(status="dead_end")
    assert reg.record(dup) is False
    # original survives
    assert reg.known("apex.Graph", "attr").status == "champion"
    assert reg.all() == [first]


def test_registry_known_returns_none_for_unknown():
    reg = Registry()
    assert reg.known("apex.Nope", "attr") is None


def test_registry_distinct_kind_is_distinct_key():
    reg = Registry()
    assert reg.record(_rec(kind="attr")) is True
    assert reg.record(_rec(kind="call")) is True  # different kind -> new key
    assert len(reg.all()) == 2


def test_registry_jsonl_persistence(tmp_path):
    path = tmp_path / "reg.jsonl"
    reg = Registry(jsonl_path=str(path))
    reg.record(_rec(surface="a.b", detail="d1"))
    reg.record(_rec(surface="c.d", detail="d2"))
    # duplicate must NOT append
    assert reg.record(_rec(surface="a.b", status="dead_end")) is False

    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2
    parsed = [json.loads(l) for l in lines]
    surfaces = {p["surface"] for p in parsed}
    assert surfaces == {"a.b", "c.d"}

    # a fresh Registry loads the existing JSONL into its dedup index
    reg2 = Registry(jsonl_path=str(path))
    assert reg2.known("a.b", "attr") is not None
    assert reg2.known("c.d", "attr") is not None
    # re-recording a loaded key is rejected (no double-write)
    assert reg2.record(_rec(surface="a.b")) is False
    after = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(after) == 2


def test_registry_deposit_fn_called_once_per_new_record():
    deposits = []
    reg = Registry(deposit_fn=lambda d: deposits.append(d))
    assert reg.record(_rec(surface="x.y", detail="dd")) is True
    assert reg.record(_rec(surface="x.y", status="dead_end")) is False  # dup
    assert len(deposits) == 1
    assert deposits[0]["surface"] == "x.y"
    assert deposits[0]["detail"] == "dd"
    # second NEW record -> deposit fires again
    assert reg.record(_rec(surface="z.w")) is True
    assert len(deposits) == 2


def test_registry_tolerates_malformed_jsonl(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        '\n'.join([
            "not json at all",
            json.dumps({"surface": "good.one", "kind": "attr", "status": "champion"}),
            "{ broken",
            json.dumps({"missing": "fields"}),
        ]),
        encoding="utf-8",
    )
    reg = Registry(jsonl_path=str(path))  # must not raise
    assert reg.known("good.one", "attr") is not None
    assert len(reg.all()) == 1


# ===========================================================================
# run_search — MOCK probe_fn
# ===========================================================================

def _mock_probe(present_surfaces):
    """Build a probe_fn that reports `present` for surfaces in the given set."""
    present_set = set(present_surfaces)

    def _fn(spec):
        present = spec.surface in present_set
        return ProbeResult(
            surface=spec.surface,
            kind=spec.kind,
            present=present,
            is_callable=present,
            signature="(x)" if present else None,
            error=None if present else "absent",
        )

    return _fn


def test_run_search_classifies_champion_and_dead_end():
    specs = [
        ProbeSpec(surface="a", kind="attr", rank=10),
        ProbeSpec(surface="b", kind="attr", rank=5),
    ]
    reg = Registry()
    out = run_search(specs, reg, _mock_probe({"a"}))
    by_surface = {r.surface: r for r in out["recorded"]}
    assert by_surface["a"].status == "champion"
    assert by_surface["b"].status == "dead_end"
    assert out["skipped"] == []
    assert out["held"] == []
    assert out["halted"] == []


def test_run_search_orders_by_rank_desc():
    order = []

    def _spy(spec):
        order.append(spec.surface)
        return ProbeResult(surface=spec.surface, kind=spec.kind, present=False)

    specs = [
        ProbeSpec(surface="low", kind="attr", rank=1),
        ProbeSpec(surface="high", kind="attr", rank=100),
        ProbeSpec(surface="mid", kind="attr", rank=50),
    ]
    run_search(specs, Registry(), _spy)
    assert order == ["high", "mid", "low"]


def test_run_search_skips_known_without_rewalk():
    walked = []

    def _spy(spec):
        walked.append(spec.surface)
        return ProbeResult(surface=spec.surface, kind=spec.kind, present=True)

    reg = Registry()
    # pre-seed "a" so it is already known
    reg.record(Record(surface="a", kind="attr", status="champion"))

    specs = [
        ProbeSpec(surface="a", kind="attr", rank=10),
        ProbeSpec(surface="b", kind="attr", rank=5),
    ]
    out = run_search(specs, reg, _spy)
    assert out["skipped"] == ["a"]
    assert walked == ["b"]  # "a" was never re-walked
    assert [r.surface for r in out["recorded"]] == ["b"]


def test_run_search_second_seed_gate_holds_unconfirmed_present():
    specs = [
        ProbeSpec(surface="champ", kind="attr", rank=10),
        ProbeSpec(surface="dead", kind="attr", rank=5),
    ]
    reg = Registry()
    out = run_search(
        specs,
        reg,
        _mock_probe({"champ"}),
        require_second_seed=True,
        confirmed=set(),  # nothing confirmed on a 2nd seed
    )
    # champion is HELD (not recorded); dead_end is recorded (gate only holds champions)
    assert out["held"] == ["champ"]
    assert [r.surface for r in out["recorded"]] == ["dead"]
    assert reg.known("champ", "attr") is None
    assert reg.known("dead", "attr") is not None


def test_run_search_second_seed_gate_records_when_confirmed():
    specs = [ProbeSpec(surface="champ", kind="attr", rank=10)]
    reg = Registry()
    out = run_search(
        specs,
        reg,
        _mock_probe({"champ"}),
        require_second_seed=True,
        confirmed={("champ", "attr")},
    )
    assert out["held"] == []
    assert [r.surface for r in out["recorded"]] == ["champ"]
    assert reg.known("champ", "attr").status == "champion"


def test_run_search_returns_all_buckets():
    reg = Registry()
    reg.record(Record(surface="known", kind="attr", status="champion"))
    specs = [
        ProbeSpec(surface="known", kind="attr", rank=10),
        ProbeSpec(surface="newchamp", kind="attr", rank=8),
        ProbeSpec(surface="newdead", kind="attr", rank=6),
    ]
    out = run_search(specs, reg, _mock_probe({"newchamp"}))
    assert set(out.keys()) == {"recorded", "skipped", "held", "halted"}
    assert out["skipped"] == ["known"]
    assert {r.surface for r in out["recorded"]} == {"newchamp", "newdead"}
    assert out["held"] == []
    assert out["halted"] == []


def test_run_search_empty_specs():
    out = run_search([], Registry(), _mock_probe(set()))
    assert out == {"recorded": [], "skipped": [], "held": [], "halted": []}


# ===========================================================================
# APEX_SEED sanity (no apex import required)
# ===========================================================================

def test_apex_seed_has_at_least_six_specs():
    assert len(APEX_SEED) >= 6
    assert all(isinstance(s, ProbeSpec) for s in APEX_SEED)


def test_apex_seed_specs_are_well_formed():
    for s in APEX_SEED:
        assert s.surface
        assert s.kind in {"attr", "call", "construct"}
        assert s.expect in {"present", "absent", "unknown"}
        assert isinstance(s.rank, int)


def test_apex_seed_drives_run_search_standalone():
    # With an empty namespace every surface probes absent -> all dead_end.
    reg = Registry()
    out = run_search(APEX_SEED, reg, lambda s: probe({}, s))
    assert len(out["recorded"]) == len(APEX_SEED)
    assert all(r.status == "dead_end" for r in out["recorded"])


# ===========================================================================
# CRUCIBLE — adversarial / hostile invariants
#
# These attack the falsifiability guarantees head-on:
#   1. Re-walk impossibility   — a known (surface,kind) is NEVER probed again.
#   2. Second-seed gate        — unconfirmed champion is HELD, not recorded;
#                                confirmed champion IS recorded.
#   3. Contradiction/overwrite — first record wins; duplicates never overwrite.
#   4. Partial-path probe      — root present, child absent -> present=False,
#                                error set, no crash.
#   5. Registry persistence    — a second Registry on the same path inherits
#                                the dedup index from disk (survives reload).
# ===========================================================================


def _raising_probe(forbidden):
    """probe_fn that FAILS the test if called for any surface in `forbidden`.

    Surfaces NOT in `forbidden` resolve as absent (dead_end). This makes any
    re-walk of a known surface a hard, loud test failure rather than a silent
    extra probe.
    """
    forbidden_set = set(forbidden)
    calls = []

    def _fn(spec):
        calls.append(spec.surface)
        if spec.surface in forbidden_set:
            pytest.fail(
                f"probe_fn was called for already-known surface {spec.surface!r} "
                "— re-walk barrier breached"
            )
        return ProbeResult(surface=spec.surface, kind=spec.kind, present=False)

    _fn.calls = calls
    return _fn


def test_crucible_rewalk_known_is_never_probed():
    """A (surface,kind) already in the registry must NEVER reach probe_fn."""
    reg = Registry()
    reg.record(Record(surface="apex.Graph", kind="attr", status="champion"))
    reg.record(Record(surface="apex.Graph.addNode", kind="call", status="dead_end"))

    probe_fn = _raising_probe(forbidden={"apex.Graph", "apex.Graph.addNode"})
    specs = [
        ProbeSpec(surface="apex.Graph", kind="attr", rank=100),       # known
        ProbeSpec(surface="apex.Graph.addNode", kind="call", rank=90),  # known
        ProbeSpec(surface="fresh.surface", kind="attr", rank=10),       # new
    ]
    out = run_search(specs, reg, probe_fn)

    # The two known surfaces were skipped, never probed.
    assert set(out["skipped"]) == {"apex.Graph", "apex.Graph.addNode"}
    # Only the fresh surface ever reached probe_fn.
    assert probe_fn.calls == ["fresh.surface"]
    # And it was recorded (dead_end), proving the loop kept running past skips.
    assert [r.surface for r in out["recorded"]] == ["fresh.surface"]


def test_crucible_rewalk_barrier_holds_even_when_only_kind_differs():
    """Skip is keyed on (surface,kind): same surface / different kind is NEW.

    The known (surface,'attr') must be skipped, but (surface,'call') is a
    distinct key and MUST be probed — proving the barrier is precise, not
    a blanket surface ban.
    """
    reg = Registry()
    reg.record(Record(surface="apex.Graph", kind="attr", status="champion"))

    walked = []

    def _fn(spec):
        walked.append((spec.surface, spec.kind))
        # the attr key is known -> must never arrive here
        assert (spec.surface, spec.kind) != ("apex.Graph", "attr")
        return ProbeResult(surface=spec.surface, kind=spec.kind, present=False)

    specs = [
        ProbeSpec(surface="apex.Graph", kind="attr", rank=10),   # known -> skip
        ProbeSpec(surface="apex.Graph", kind="call", rank=5),    # new key -> walk
    ]
    out = run_search(specs, reg, _fn)
    assert out["skipped"] == ["apex.Graph"]
    assert walked == [("apex.Graph", "call")]


def test_crucible_second_seed_unconfirmed_champion_is_held_not_recorded():
    """require_second_seed + empty confirmed: a 'present' champion is HELD."""
    reg = Registry()
    specs = [ProbeSpec(surface="champ", kind="attr", rank=10)]
    out = run_search(
        specs, reg, _mock_probe({"champ"}),
        require_second_seed=True,
        confirmed=set(),
    )
    assert out["held"] == ["champ"]
    assert out["recorded"] == []
    # Critically: nothing leaked into the registry — not as champion, not at all.
    assert reg.known("champ", "attr") is None
    assert reg.all() == []


def test_crucible_second_seed_confirmed_champion_is_recorded():
    """The SAME champion, once confirmed on a 2nd seed, IS recorded."""
    reg = Registry()
    specs = [ProbeSpec(surface="champ", kind="attr", rank=10)]
    out = run_search(
        specs, reg, _mock_probe({"champ"}),
        require_second_seed=True,
        confirmed={("champ", "attr")},
    )
    assert out["held"] == []
    assert [r.surface for r in out["recorded"]] == ["champ"]
    rec = reg.known("champ", "attr")
    assert rec is not None
    assert rec.status == "champion"


def test_crucible_contradiction_first_record_wins_no_overwrite():
    """Recording an existing (surface,kind) returns False and never overwrites.

    Drive it through the public record() API with a deliberately contradictory
    status, then prove the FIRST verdict still stands.
    """
    deposits = []
    reg = Registry(deposit_fn=lambda d: deposits.append(d))

    first = Record(surface="apex.Graph", kind="attr", status="champion", detail="orig")
    assert reg.record(first) is True

    # A later run claims the OPPOSITE verdict for the identical key.
    contradiction = Record(
        surface="apex.Graph", kind="attr", status="dead_end", detail="OVERWRITE_ATTEMPT"
    )
    assert reg.record(contradiction) is False  # rejected

    survivor = reg.known("apex.Graph", "attr")
    assert survivor == first                      # identity: first wins whole-record
    assert survivor.status == "champion"
    assert survivor.detail == "orig"
    assert reg.all() == [first]                   # no second row appended
    # And the contradiction never fired a deposit (no silent side effect).
    assert len(deposits) == 1
    assert deposits[0]["detail"] == "orig"


def test_crucible_contradiction_via_run_search_is_skipped_not_overwritten():
    """run_search hitting a contradicting seeded key skips it — no overwrite."""
    reg = Registry()
    # Seed a champion verdict.
    reg.record(Record(surface="champ", kind="attr", status="champion", detail="seed"))

    # A spec for the same key whose probe would say 'absent' (dead_end).
    specs = [ProbeSpec(surface="champ", kind="attr", rank=10)]
    out = run_search(specs, reg, _mock_probe(set()))  # probes absent

    assert out["skipped"] == ["champ"]
    assert out["recorded"] == []
    assert out["halted"] == []
    # Seeded champion is untouched — the dead_end verdict never landed.
    assert reg.known("champ", "attr").status == "champion"
    assert reg.known("champ", "attr").detail == "seed"


def test_crucible_probe_partial_path_root_present_child_absent():
    """Namespace has 'apex' but no 'apex.Graph' -> present=False, error, no crash."""

    class _NoGraph:
        # has SOMETHING, but not Graph
        other = 1

    ns = {"apex": _NoGraph()}

    # Probe one level deep: apex.Graph (the missing child itself).
    res = probe(ns, ProbeSpec(surface="apex.Graph", kind="attr"))
    assert res.present is False
    assert res.error is not None
    assert res.is_callable is False
    assert res.signature is None

    # Probe two levels deep through the missing child: apex.Graph.addNode.
    res2 = probe(ns, ProbeSpec(surface="apex.Graph.addNode", kind="call"))
    assert res2.present is False
    assert res2.error is not None
    # Error must reference the FIRST failing attribute ('Graph'), not a crash.
    assert "Graph" in res2.error

    # The root itself still probes present (sanity: only the child is absent).
    root = probe(ns, ProbeSpec(surface="apex", kind="attr"))
    assert root.present is True


def test_crucible_registry_persistence_survives_reload(tmp_path):
    """A second Registry on the same jsonl_path inherits the dedup index."""
    path = tmp_path / "persist.jsonl"

    reg1 = Registry(jsonl_path=str(path))
    assert reg1.record(Record(surface="a.b", kind="attr", status="champion", detail="d1")) is True
    assert reg1.record(Record(surface="c.d", kind="call", status="dead_end", detail="d2")) is True

    # Reconstruct from disk only — no shared in-memory state.
    reg2 = Registry(jsonl_path=str(path))
    assert reg2.known("a.b", "attr") is not None
    assert reg2.known("c.d", "call") is not None
    # Round-tripped fields survived.
    assert reg2.known("a.b", "attr").status == "champion"
    assert reg2.known("c.d", "call").status == "dead_end"
    assert reg2.known("a.b", "attr").detail == "d1"
    assert len(reg2.all()) == 2

    # The dedup index survived reload: re-recording a loaded key is rejected,
    # and the file is NOT double-appended.
    assert reg2.record(Record(surface="a.b", kind="attr", status="dead_end")) is False
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2

    # A genuinely new key on reg2 DOES persist and is visible to a third reload.
    assert reg2.record(Record(surface="e.f", kind="attr", status="champion")) is True
    reg3 = Registry(jsonl_path=str(path))
    assert reg3.known("e.f", "attr") is not None
    assert len(reg3.all()) == 3


def test_crucible_persistence_dedup_is_keyed_on_surface_and_kind(tmp_path):
    """Reload must NOT collapse same-surface/different-kind rows into one key."""
    path = tmp_path / "keys.jsonl"
    reg1 = Registry(jsonl_path=str(path))
    reg1.record(Record(surface="apex.Graph", kind="attr", status="champion"))
    reg1.record(Record(surface="apex.Graph", kind="call", status="dead_end"))

    reg2 = Registry(jsonl_path=str(path))
    assert reg2.known("apex.Graph", "attr").status == "champion"
    assert reg2.known("apex.Graph", "call").status == "dead_end"
    assert len(reg2.all()) == 2
