"""test_loop_contracts.py — pins the LOOP V0.0 contract surface.

Mirrors what the probe mission exercises, as fast hermetic pytest: the §4
port signatures verbatim, the mapper truth table (expected column hardcoded
here — never read back from the seam), precommit-authored-BEFORE-mutation
every turn, StagePort zero side effects, and closure_rate = 1.0 all-EXPOSED.

Hermetic: every test that touches the ledger points SYNAPSE_LOOP_LEDGER_DIR
at a tmp_path via the `tmp_ledger` fixture, so nothing writes into the repo.
"""

import itertools
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.loop import mapper  # noqa: E402
from synapse.loop import ports  # noqa: E402
from synapse.loop.recipe import build_recipe, run_recipe  # noqa: E402


@pytest.fixture
def tmp_ledger(tmp_path, monkeypatch):
    """Point the seam's ledger oracle at a tmp dir; return the file path."""
    monkeypatch.setenv("SYNAPSE_LOOP_LEDGER_DIR", str(tmp_path))
    return tmp_path / "v00_precommits.jsonl"


# ---------------------------------------------------------------------------
# §4 PortResult + STATUS
# ---------------------------------------------------------------------------

def test_portresult_is_namedtuple_with_contract_fields():
    assert hasattr(ports.PortResult, "_fields")
    assert set(ports.PortResult._fields) == {"status", "payload", "error_message"}


def test_status_enum_covers_contract():
    assert {"SUCCESS", "UNAVAILABLE", "BLOCKED"} <= set(ports.STATUS)


def test_portresult_helpers_produce_valid_statuses():
    assert ports.PortResult.ok({"k": 1}).status == "SUCCESS"
    assert ports.PortResult.unavailable("why").status == "UNAVAILABLE"
    assert ports.PortResult.blocked("why").status == "BLOCKED"
    for r in (ports.PortResult.ok(), ports.PortResult.unavailable("x"), ports.PortResult.blocked("x")):
        assert r.status in ports.STATUS


# ---------------------------------------------------------------------------
# §4 method signatures verbatim
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port,method,expected", [
    ("SafetyPort", "evaluate_path",
     ["agent_id", "path_history_hash", "recent_actions", "proposed_action", "scene_state_digest"]),
    ("MemoryPort", "query_and_filter",
     ["relation_keys", "task_context_tokens"]),
    ("LedgerPort", "author_precommit",
     ["claim_predicate", "probability", "world_ref"]),
    ("StagePort", "compose_sanitized_stage",
     ["stage_identifier"]),
])
def test_contract_signature_verbatim(port, method, expected):
    import inspect

    cls = getattr(ports, port)
    fn = getattr(cls, method)
    params = [p for p in inspect.signature(fn).parameters if p not in ("self", "cls")]
    assert params == expected, f"{port}.{method} params drifted: {params} != {expected}"


# ---------------------------------------------------------------------------
# Mapper truth table — expected hardcoded, never read back from the seam
# ---------------------------------------------------------------------------

def test_mapper_truth_table_all_27_combos():
    rows = []
    for combo in itertools.product([True, False, None], repeat=3):
        expected = mapper.ALLOW if all(v is True for v in combo) else mapper.BLOCK
        got = mapper.GATE_POLICY(list(combo))
        rows.append((combo, expected, got))
        assert got == expected, f"GATE_POLICY({combo}) = {got}, expected {expected}"
    assert len(rows) == 27
    assert any(g == mapper.ALLOW for _, _, g in rows)  # the all-True row exists
    # every None-containing combo blocks (unevaluable blocks)
    assert all(g == mapper.BLOCK for combo, _, g in rows if None in combo)


def test_mapper_rejects_non_bool_non_none():
    with pytest.raises(TypeError):
        mapper.GATE_POLICY([True, 1])


# ---------------------------------------------------------------------------
# Precommit-before-mutation, every turn
# ---------------------------------------------------------------------------

def _ledger_lines(ledger: Path):
    if not ledger.exists():
        return []
    return [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_precommit_authored_before_mutation_every_turn(tmp_ledger):
    recipe = build_recipe("test-order", turns=3)
    results = run_recipe(recipe)
    lines = _ledger_lines(tmp_ledger)

    assert len(lines) == 3, "one precommit per turn, all durable before return"
    for t in results:
        kinds = [s.kind for s in t.steps]
        assert kinds[0] == "precommit"
        assert kinds.count("precommit") == 1
        assert kinds.index("precommit") < kinds.index("mutation"), \
            f"turn {t.id} mutated before its precommit"
        assert t.verdict == "EXPOSED"


def test_precommit_lines_are_durable_json(tmp_ledger):
    import json

    run_recipe(build_recipe("test-durable", turns=2))
    for ln in _ledger_lines(tmp_ledger):
        rec = json.loads(ln)
        assert rec["event"] == "precommit"
        assert rec["probability"] == 0.0
        assert rec["claim_predicate"]
        assert rec["world_ref"]
        assert isinstance(rec["seq"], int)


# ---------------------------------------------------------------------------
# StagePort zero side effects
# ---------------------------------------------------------------------------

def test_stageport_unavailable_with_zero_side_effects(tmp_ledger, monkeypatch):
    scope = Path(__file__).resolve().parents[1] / "harness" / "loop"

    def snapshot(root):
        if not root.exists():
            return []
        return sorted(f"{p.relative_to(root)}:{p.stat().st_size}"
                      for p in root.rglob("*") if p.is_file())

    before = snapshot(scope)
    before_ledger = _ledger_lines(tmp_ledger)

    result = ports.StagePort().compose_sanitized_stage("/stage")

    after = snapshot(scope)
    after_ledger = _ledger_lines(tmp_ledger)

    assert result.status == "UNAVAILABLE"
    assert "Octavius" in result.error_message
    assert after == before, "compose_sanitized_stage wrote to disk"
    assert after_ledger == before_ledger, "compose_sanitized_stage touched the ledger"


# ---------------------------------------------------------------------------
# Closure rate: 1.0, zero HIT/MISS, all EXPOSED
# ---------------------------------------------------------------------------

def test_closure_rate_goalpost(tmp_ledger):
    results = run_recipe(build_recipe("test-closure", turns=5))
    verdicts = [t.verdict for t in results]
    counts = {v: verdicts.count(v) for v in ("HIT", "MISS", "EXPOSED", "UNRESOLVABLE")}
    closure_rate = sum(counts.values()) / len(verdicts)
    assert closure_rate == 1.0
    assert counts["HIT"] == 0 and counts["MISS"] == 0
    assert counts["EXPOSED"] == len(verdicts)


def test_safetyport_and_memoryport_unavailable_with_reason():
    assert ports.SafetyPort().evaluate_path(
        "a1", "h1", [], {"type": "noop"}, "d1").status == "UNAVAILABLE"
    assert ports.MemoryPort().query_and_filter(["rel"], 128).status == "UNAVAILABLE"
