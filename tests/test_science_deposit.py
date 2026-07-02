"""The science → Ledger deposit adapter (RFC_agent_usd_ledger §7.2 deposit_fn seam).

Pins the closure of the long-open "deposit_fn still None at the science
entrypoint" gap: fresh probe verdicts flow Registry → LedgerDeposit →
memory.ledger.deposit (file-first), champions as Confirmation, dead-ends as
DeadEnd, both at the honest V0_membership rung. A deposit failure never
breaks the probe run (the JSONL fallback is the count authority).
"""
import json

import pytest

from synapse.science.deposit import LedgerDeposit
from synapse.science.registry import Record, Registry


@pytest.fixture
def ledger_dir(tmp_path, monkeypatch):
    d = tmp_path / "ledger"
    d.mkdir()
    monkeypatch.setenv("SYNAPSE_LEDGER_DIR", str(d))
    return d


def _rec(status="champion", surface="apex.Graph.addNode"):
    return Record(surface=surface, kind="callable", status=status,
                  detail="probed ok", context="apex", timestamp=1750000000)


def test_champion_deposits_confirmation(ledger_dir):
    sink = LedgerDeposit()
    reg = Registry(deposit_fn=sink)
    assert reg.record(_rec("champion"))
    assert sink.deposited == 1
    assert not sink.failures
    files = list(ledger_dir.glob("Confirmation_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["verified_by"] == "V0_membership"  # membership, NOT a verifying rung
    assert data["title"] == "apex.Graph.addNode"
    assert data["against_build"]  # stamped: live session or CUTOVER_BUILD
    assert data["extra"]["science_status"] == "champion"


def test_dead_end_deposits_deadend(ledger_dir):
    sink = LedgerDeposit()
    reg = Registry(deposit_fn=sink)
    assert reg.record(_rec("dead_end", surface="hou.pdg.phantom"))
    assert len(list(ledger_dir.glob("DeadEnd_*.json"))) == 1


def test_deposit_failure_never_breaks_the_run(ledger_dir, monkeypatch):
    import synapse.science.deposit as dep

    def boom(rec):
        raise OSError("disk full")

    monkeypatch.setattr(dep, "deposit", boom)
    sink = LedgerDeposit()
    reg = Registry(deposit_fn=sink)
    assert reg.record(_rec())  # record() itself must still succeed
    assert sink.deposited == 0
    assert len(sink.failures) == 1
    assert "disk full" in sink.failures[0]


def test_dedup_means_no_double_deposit(ledger_dir):
    sink = LedgerDeposit()
    reg = Registry(deposit_fn=sink)
    assert reg.record(_rec())
    assert not reg.record(_rec())  # (surface, kind) already known
    assert sink.deposited == 1
