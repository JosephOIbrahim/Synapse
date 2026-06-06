"""Tests for the agent.usd Ledger (python/synapse/memory/ledger.py).

Pins the RFC §11 acceptance contract:
  1. Round-trip fidelity = 1.0 on the per-record FILES, per kind (pxr-independent).
  2. Mandatory verified_by — empty/missing rejected at deposit.
  3. One-file-per-record idempotence (same record → same <kind>_<ts>_<sha8>.json).
  4. No-pxr fallback — deposit still writes the file, never raises.
  5. USD projection — deposit authors /SYNAPSE/agent/ledger/<...> via the FakeStage
     harness; initialize_agent_usd authors the ledger group prim.
  6. REAL-DATA backfill — parse docs/SCIENCE_HARNESS_LEDGER.md and prove every
     captured field survives a deposit→read-back round-trip with ZERO loss.

Run: python -m pytest tests/test_agent_usd_ledger.py -v
"""

import json
import os
import sys
import glob
import shutil
import tempfile
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

# Add package to path (mirrors tests/test_agent_state.py).
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.memory import ledger
from synapse.memory import agent_state

# The real markdown Ledger this build backfills.
LEDGER_MD = os.path.join(package_root, "docs", "SCIENCE_HARNESS_LEDGER.md")


# ═════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
def ledger_tmp(monkeypatch):
    """Point the Ledger root at a throwaway dir via $SYNAPSE_LEDGER_DIR."""
    d = tempfile.mkdtemp(prefix="synapse_ledger_test_")
    monkeypatch.setenv("SYNAPSE_LEDGER_DIR", d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def no_pxr():
    """Force the no-pxr path on the ledger module (env may ship pxr)."""
    with patch.object(ledger, "PXR_AVAILABLE", False):
        yield


def _read_back(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _record_of_kind(kind, **overrides):
    """Build a fully-populated LedgerRecord of a given kind (all fields set)."""
    base = dict(
        kind=kind,
        verified_by="V1",
        against_build="21.0.631",
        change_applied="wired the ledger subtree",
        measured_delta="before=0 after=1 / quote\"slash\\newline\nsurvives",
        artifact_path=["shared/bridge.py", "tests/test_x.py"],
        probe=[".scout/probe.py"],
        question="does it round-trip?",
        direction="the call this entry sets",
        crucible="confirmed + safe",
        notes="why it matters: lossless or bust",
        timestamp="2026-06-06",
        title=f"{kind} — sample",
        session="Session 2026-06-06 — Phase X",
        claim_text="the doc claim, verbatim",
        claim_locus="CLAUDE.md:812",
        code_locus="agent_state.py:41",
        bound_by="value",
        holds="true",
        area="the subsystem",
        stakes="high",
        probed="false",
        extra={"root_cause": "the cause", "weird/key": "kept verbatim"},
    )
    base.update(overrides)
    return ledger.LedgerRecord(**base)


# ═════════════════════════════════════════════════════════════════
# 1. Round-trip fidelity = 1.0 on FILES (pxr-INDEPENDENT)
# ═════════════════════════════════════════════════════════════════

class TestFileRoundTrip:
    @pytest.mark.parametrize("kind", ledger.KNOWN_KINDS)
    def test_every_field_byte_identical(self, kind, ledger_tmp, no_pxr):
        rec = _record_of_kind(kind)
        res = ledger.deposit(rec)
        loaded = _read_back(res["path"])
        # asdict(rec) is exactly what was serialized — must round-trip verbatim.
        assert loaded == asdict(rec), f"field loss for kind={kind}"
        # spot-check the gnarly value survived (slashes/quotes/newlines).
        assert loaded["measured_delta"] == rec.measured_delta
        assert loaded["extra"]["weird/key"] == "kept verbatim"

    def test_lists_preserved(self, ledger_tmp, no_pxr):
        rec = _record_of_kind("Confirmation")
        res = ledger.deposit(rec)
        loaded = _read_back(res["path"])
        assert loaded["artifact_path"] == ["shared/bridge.py", "tests/test_x.py"]
        assert loaded["probe"] == [".scout/probe.py"]


# ═════════════════════════════════════════════════════════════════
# 2. Mandatory verified_by
# ═════════════════════════════════════════════════════════════════

class TestMandatoryVerifiedBy:
    def test_empty_verified_by_raises(self, ledger_tmp, no_pxr):
        rec = _record_of_kind("Confirmation", verified_by="")
        with pytest.raises(ValueError):
            ledger.deposit(rec)
        # No file written.
        assert glob.glob(os.path.join(ledger_tmp, "*.json")) == []

    def test_whitespace_verified_by_raises(self, ledger_tmp, no_pxr):
        rec = _record_of_kind("Confirmation", verified_by="   ")
        with pytest.raises(ValueError):
            ledger.deposit(rec)


# ═════════════════════════════════════════════════════════════════
# 3. One-file-per-record idempotence
# ═════════════════════════════════════════════════════════════════

class TestIdempotence:
    def test_same_record_one_file(self, ledger_tmp, no_pxr):
        rec = _record_of_kind("DeadEnd")
        r1 = ledger.deposit(rec)
        r2 = ledger.deposit(rec)
        # Same stem/filename both times.
        assert r1["filename"] == r2["filename"]
        # Exactly one .json (a .bak may exist from backup rotation — not a record).
        jsons = glob.glob(os.path.join(ledger_tmp, "*.json"))
        assert len(jsons) == 1

    def test_distinct_records_distinct_files(self, ledger_tmp, no_pxr):
        a = _record_of_kind("Confirmation", question="A")
        b = _record_of_kind("Confirmation", question="B")
        ledger.deposit(a)
        ledger.deposit(b)
        jsons = glob.glob(os.path.join(ledger_tmp, "*.json"))
        assert len(jsons) == 2


# ═════════════════════════════════════════════════════════════════
# 4. No-pxr fallback
# ═════════════════════════════════════════════════════════════════

class TestNoPxrFallback:
    def test_deposit_writes_file_without_pxr(self, ledger_tmp, no_pxr):
        assert not ledger.PXR_AVAILABLE
        rec = _record_of_kind("Confirmation")
        # Even with an agent_usd_path requested, no pxr → projection skipped, no raise.
        res = ledger.deposit(rec, agent_usd_path=os.path.join(ledger_tmp, "agent.usd"))
        assert res["ok"] is True
        assert res["usd_projected"] is False
        assert os.path.exists(res["path"])
        assert _read_back(res["path"]) == asdict(rec)


# ═════════════════════════════════════════════════════════════════
# 5. USD projection (FakeStage harness) + ledger group at init
# ═════════════════════════════════════════════════════════════════

# Reuse the agent_state test harness mocks (FakeStage/FakePrim/FakeAttribute).
from test_agent_state import (  # noqa: E402
    FakeStage, FakeSdf, FakeVt, _fake_create_new, _fake_open, _fake_stages,
)


@pytest.fixture
def mock_pxr_ledger(ledger_tmp):
    """Patch BOTH ledger and agent_state to the fake pxr objects."""
    _fake_stages.clear()
    fake_usd = MagicMock()
    fake_usd.Stage.CreateNew = _fake_create_new
    fake_usd.Stage.Open = _fake_open

    with patch.object(ledger, "PXR_AVAILABLE", True), \
         patch.object(ledger, "Usd", fake_usd), \
         patch.object(ledger, "Sdf", FakeSdf), \
         patch.object(agent_state, "PXR_AVAILABLE", True), \
         patch.object(agent_state, "Usd", fake_usd), \
         patch.object(agent_state, "Sdf", FakeSdf), \
         patch.object(agent_state, "Vt", FakeVt):
        yield
    _fake_stages.clear()


class TestUsdProjection:
    def test_initialize_authors_ledger_group(self, ledger_tmp, mock_pxr_ledger):
        agent_usd = os.path.join(ledger_tmp, "agent.usd")
        agent_state.initialize_agent_usd(agent_usd)
        stage = _fake_stages[os.path.normpath(agent_usd)]
        assert stage.GetPrimAtPath("/SYNAPSE/agent/ledger").IsValid()

    def test_deposit_authors_ledger_prim(self, ledger_tmp, mock_pxr_ledger):
        agent_usd = os.path.join(ledger_tmp, "agent.usd")
        agent_state.initialize_agent_usd(agent_usd)

        rec = _record_of_kind("DocConformance")
        res = ledger.deposit(rec, agent_usd_path=agent_usd)
        assert res["usd_projected"] is True

        stage = _fake_stages[os.path.normpath(agent_usd)]
        prim = stage.GetPrimAtPath(f"/SYNAPSE/agent/ledger/{res['stem']}")
        assert prim.IsValid()
        assert prim.GetAttribute("synapse:kind").Get() == "DocConformance"
        assert prim.GetAttribute("synapse:verified_by").Get() == "V1"
        assert prim.GetAttribute("synapse:claim_text").Get() == "the doc claim, verbatim"
        # list field joined; extras namespaced.
        assert "shared/bridge.py" in prim.GetAttribute("synapse:artifact_path").Get()
        assert prim.GetAttribute("synapse:extra_root_cause").Get() == "the cause"

    def test_file_still_written_when_usd_projects(self, ledger_tmp, mock_pxr_ledger):
        agent_usd = os.path.join(ledger_tmp, "agent.usd")
        agent_state.initialize_agent_usd(agent_usd)
        rec = _record_of_kind("Confirmation")
        res = ledger.deposit(rec, agent_usd_path=agent_usd)
        assert os.path.exists(res["path"])
        assert _read_back(res["path"]) == asdict(rec)


# ═════════════════════════════════════════════════════════════════
# 6. REAL-DATA backfill (the strong pin)
# ═════════════════════════════════════════════════════════════════

class TestRealDataBackfill:
    def test_parses_sane_record_count(self):
        recs = ledger.parse_ledger_markdown(LEDGER_MD)
        assert len(recs) >= 15

    def test_covers_real_kinds(self):
        recs = ledger.parse_ledger_markdown(LEDGER_MD)
        kinds = {r.kind for r in recs}
        # The kinds the live Ledger actually carries (RFC §3.3 enumeration).
        for expected in ("Confirmation", "DeadEnd", "DocConformance",
                         "Deferred", "SubstrateAssumption"):
            assert expected in kinds, f"missing kind {expected}: saw {kinds}"

    def test_every_field_survives_round_trip(self, ledger_tmp, no_pxr):
        recs = ledger.parse_ledger_markdown(LEDGER_MD)
        fields_lost = 0
        deposited = 0
        for rec in recs:
            if not rec.verified_by.strip():
                continue  # genuinely lacks verified_by → cannot deposit
            res = ledger.deposit(rec)
            loaded = _read_back(res["path"])
            if loaded != asdict(rec):
                fields_lost += 1
            deposited += 1
        assert deposited >= 15
        assert fields_lost == 0

    def test_backfill_summary(self, ledger_tmp, no_pxr):
        summary = ledger.backfill(LEDGER_MD)
        assert summary["records"] >= 15
        assert summary["files_written"] >= 15
        # Every written record landed as exactly one .json file.
        jsons = glob.glob(os.path.join(ledger_tmp, "*.json"))
        assert len(jsons) == summary["files_written"]
        # Kinds dict covers the real kinds.
        assert "Confirmation" in summary["kinds"]
