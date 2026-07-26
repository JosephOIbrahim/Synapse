"""
Synapse Core Foundation Tests

Tests for determinism, audit, and gates modules.
Run without Houdini to verify core logic.
"""

import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

# Import core modules directly (no hou dependency)
from synapse.core.determinism import (
    DeterministicConfig,
    DeterministicOperation,
    DeterministicRandom,
    get_config,
    set_config,
    round_float,
    round_vector,
    round_color,
    deterministic_uuid,
    deterministic_sort,
    deterministic_dict_items,
    deterministic,
)
from synapse.core.audit import (
    AuditLevel,
    AuditCategory,
    AuditEntry,
    AuditLog,
    audit_log,
)
from synapse.core.gates import (
    GateLevel,
    GateDecision,
    GateProposal,
    GateBatch,
    HumanGate,
    human_gate,
    propose_change,
)


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestRoundFloat:
    """Tests for round_float precision control"""

    def setup_method(self):
        """Reset config before each test"""
        set_config(DeterministicConfig())

    def test_default_precision(self):
        result = round_float(3.14159265)
        assert result == 3.141593  # 6 decimal places

    def test_custom_precision(self):
        result = round_float(3.14159265, precision=2)
        assert result == 3.14

    def test_strict_mode_uses_decimal(self):
        config = get_config()
        assert config.strict_mode is True
        # Banker's rounding: 2.5 rounds to 2 with ROUND_HALF_EVEN,
        # but we use ROUND_HALF_UP so 2.5 -> 3
        result = round_float(2.5, precision=0)
        assert result == 3.0

    def test_non_strict_mode(self):
        config = DeterministicConfig(strict_mode=False)
        set_config(config)
        result = round_float(3.14159, precision=2)
        assert result == 3.14

    def test_deterministic_same_input(self):
        """Same input always produces same output"""
        for _ in range(100):
            assert round_float(1.0 / 3.0) == round_float(1.0 / 3.0)


class TestRoundVector:
    def setup_method(self):
        set_config(DeterministicConfig())

    def test_basic_vector(self):
        result = round_vector((1.23456789, 2.34567890, 3.45678901))
        assert result == (1.2346, 2.3457, 3.4568)  # transform_precision=4

    def test_custom_precision(self):
        result = round_vector((1.23456, 2.34567), precision=2)
        assert result == (1.23, 2.35)


class TestRoundColor:
    def setup_method(self):
        set_config(DeterministicConfig())

    def test_basic_color(self):
        result = round_color((0.123456, 0.654321, 0.999999))
        assert result == (0.1235, 0.6543, 1.0)


class TestDeterministicUUID:
    def setup_method(self):
        set_config(DeterministicConfig())

    def test_same_content_same_uuid(self):
        uuid1 = deterministic_uuid("test_content")
        uuid2 = deterministic_uuid("test_content")
        assert uuid1 == uuid2

    def test_different_content_different_uuid(self):
        uuid1 = deterministic_uuid("content_a")
        uuid2 = deterministic_uuid("content_b")
        assert uuid1 != uuid2

    def test_namespace_affects_uuid(self):
        uuid1 = deterministic_uuid("test", namespace="synapse")
        uuid2 = deterministic_uuid("test", namespace="other")
        assert uuid1 != uuid2

    def test_default_namespace_is_synapse(self):
        """Verify the namespace default was changed from hyphae to synapse"""
        uuid1 = deterministic_uuid("test")
        uuid2 = deterministic_uuid("test", namespace="synapse")
        assert uuid1 == uuid2

    def test_uuid_length(self):
        uuid = deterministic_uuid("test")
        assert len(uuid) == 16
        assert all(c in '0123456789abcdef' for c in uuid)


class TestDeterministicSort:
    def test_sort_strings(self):
        result = deterministic_sort(["banana", "apple", "cherry"])
        assert result == ["apple", "banana", "cherry"]

    def test_sort_with_key(self):
        result = deterministic_sort([3, 1, 2], key=lambda x: x)
        assert result == [1, 2, 3]

    def test_sort_with_sort_key(self):
        items = [Mock(name="z"), Mock(name="a")]
        items[0].name = "z"
        items[1].name = "a"
        result = deterministic_sort(items, sort_key="name")
        assert result[0].name == "a"
        assert result[1].name == "z"

    def test_does_not_modify_original(self):
        original = [3, 1, 2]
        deterministic_sort(original)
        assert original == [3, 1, 2]


class TestDeterministicDictItems:
    def test_sorted_order(self):
        d = {"c": 3, "a": 1, "b": 2}
        result = deterministic_dict_items(d)
        assert result == [("a", 1), ("b", 2), ("c", 3)]


class TestDeterministicRandom:
    def test_reproducible_sequence(self):
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=42)
        for _ in range(10):
            assert rng1.random() == rng2.random()

    def test_different_seeds_different_output(self):
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=99)
        assert rng1.random() != rng2.random()

    def test_uniform_range(self):
        rng = DeterministicRandom(seed=42)
        for _ in range(100):
            val = rng.uniform(0.0, 1.0)
            assert 0.0 <= val <= 1.0

    def test_randint_range(self):
        rng = DeterministicRandom(seed=42)
        for _ in range(100):
            val = rng.randint(1, 6)
            assert 1 <= val <= 6

    def test_choice(self):
        rng = DeterministicRandom(seed=42)
        options = ["a", "b", "c"]
        result = rng.choice(options)
        assert result in options

    def test_shuffle_reproducible(self):
        rng1 = DeterministicRandom(seed=42)
        rng2 = DeterministicRandom(seed=42)
        items = [1, 2, 3, 4, 5]
        assert rng1.shuffle(items) == rng2.shuffle(items)

    def test_shuffle_does_not_modify_original(self):
        rng = DeterministicRandom(seed=42)
        items = [1, 2, 3, 4, 5]
        rng.shuffle(items)
        assert items == [1, 2, 3, 4, 5]

    def test_reset(self):
        rng = DeterministicRandom(seed=42)
        first = rng.random()
        rng.reset()
        assert rng.random() == first


class TestDeterministicDecorator:
    def setup_method(self):
        set_config(DeterministicConfig())

    def test_rounds_float_kwargs(self):
        @deterministic
        def func(name, intensity=1.0):
            return intensity

        result = func("test", intensity=3.14159265)
        assert result == 3.141593

    def test_rounds_tuple_kwargs(self):
        @deterministic
        def func(color=(0.0, 0.0, 0.0)):
            return color

        result = func(color=(1.23456789, 2.34567890, 3.45678901))
        # round_vector uses transform_precision=4 by default
        assert result == (1.2346, 2.3457, 3.4568)

    def test_passes_non_float_unchanged(self):
        @deterministic
        def func(name="default"):
            return name

        assert func(name="test") == "test"


class TestDeterministicOperation:
    def setup_method(self):
        set_config(DeterministicConfig())

    def test_auto_populates_metadata(self):
        op = DeterministicOperation()
        assert op.operation_id != ""
        assert op.tool_version != ""
        assert op.timestamp_utc != ""

    def test_reproducibility_dict(self):
        op = DeterministicOperation()
        rd = op.to_reproducibility_dict()
        assert "operation_id" in rd
        assert "seed" in rd
        assert rd["seed"] == 42  # default global seed

    def test_custom_seed(self):
        op = DeterministicOperation(seed=99)
        assert op.get_seed() == 99


# =============================================================================
# AUDIT TESTS
# =============================================================================


class TestAuditEntry:
    def test_hash_chain(self):
        entry = AuditEntry(
            timestamp_utc="2025-01-01T00:00:00Z",
            level=AuditLevel.INFO,
            category=AuditCategory.SYSTEM,
            operation="test",
            message="test message",
            previous_hash="genesis",
        )
        assert entry.entry_hash != ""
        assert len(entry.entry_hash) == 64  # SHA-256 hex

    def test_same_content_same_hash(self):
        kwargs = dict(
            timestamp_utc="2025-01-01T00:00:00Z",
            level=AuditLevel.INFO,
            category=AuditCategory.SYSTEM,
            operation="test",
            message="test",
            previous_hash="genesis",
        )
        entry1 = AuditEntry(**kwargs)
        entry2 = AuditEntry(**kwargs)
        assert entry1.entry_hash == entry2.entry_hash

    def test_to_dict_roundtrip(self):
        entry = AuditEntry(
            timestamp_utc="2025-01-01T00:00:00Z",
            level=AuditLevel.INFO,
            category=AuditCategory.SYSTEM,
            operation="test",
            message="test message",
        )
        d = entry.to_dict()
        restored = AuditEntry.from_dict(d)
        assert restored.operation == "test"
        assert restored.message == "test message"
        assert restored.entry_hash == entry.entry_hash

    def test_human_readable(self):
        entry = AuditEntry(
            timestamp_utc="2025-01-01T00:00:00Z",
            level=AuditLevel.INFO,
            category=AuditCategory.SYSTEM,
            operation="test_op",
            message="hello",
        )
        readable = entry.to_human_readable()
        assert "INFO" in readable
        assert "test_op" in readable
        assert "hello" in readable


class TestAuditLog:
    def setup_method(self):
        """Create temp dir and reset singleton"""
        AuditLog.reset_instance()
        self.tmp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up"""
        AuditLog.reset_instance()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_log_creates_entry(self):
        log = AuditLog(log_dir=self.tmp_dir)
        entry = log.log("test_op", "test message")
        assert entry.operation == "test_op"
        assert entry.message == "test message"
        assert entry.entry_hash != ""

    def test_hash_chain_integrity(self):
        log = AuditLog(log_dir=self.tmp_dir)
        log.log("op1", "msg1")
        log.log("op2", "msg2")
        log.log("op3", "msg3")

        valid, invalid_idx = log.verify_chain()
        assert valid is True
        assert invalid_idx is None

    def test_entry_filtering(self):
        log = AuditLog(log_dir=self.tmp_dir)
        log.log("op1", "msg1", category=AuditCategory.LIGHTING)
        log.log("op2", "msg2", category=AuditCategory.SYSTEM)
        log.log("op3", "msg3", category=AuditCategory.LIGHTING)

        results = log.get_entries(category=AuditCategory.LIGHTING)
        assert len(results) == 2
        assert all(e.category == AuditCategory.LIGHTING for e in results)

    def test_singleton_behavior(self):
        log1 = AuditLog.get_instance(log_dir=self.tmp_dir)
        log2 = AuditLog.get_instance()
        assert log1 is log2

    def test_callback_notification(self):
        log = AuditLog(log_dir=self.tmp_dir)
        received = []
        log.add_callback(lambda e: received.append(e))
        log.log("test", "msg")
        assert len(received) == 1
        assert received[0].operation == "test"

    def test_callback_error_doesnt_break_logging(self):
        log = AuditLog(log_dir=self.tmp_dir)

        def bad_callback(e):
            raise RuntimeError("callback error")

        log.add_callback(bad_callback)
        entry = log.log("test", "msg")
        assert entry is not None

    def test_persists_to_disk(self):
        log = AuditLog(log_dir=self.tmp_dir)
        log.log("test", "msg")

        # Check that a file was written
        jsonl_files = list(self.tmp_dir.glob("audit_*.jsonl"))
        assert len(jsonl_files) == 1

    def test_export_session(self):
        log = AuditLog(log_dir=self.tmp_dir)
        log.log("op1", "msg1")
        log.log("op2", "msg2")

        exported = log.export_session()
        assert len(exported) == 2

    def test_storage_path_is_synapse(self):
        """Verify storage path was changed from .hyphae to .synapse"""
        log = AuditLog()
        expected_parent = Path.home() / ".synapse" / "audit"
        assert log._log_dir == expected_parent
        AuditLog.reset_instance()


# =============================================================================
# GATES TESTS
# =============================================================================


class TestGateProposal:
    def test_auto_generates_id(self):
        proposal = GateProposal(
            proposal_id="",
            gate_id="gate1",
            sequence_id="shot_010",
            operation="test_op",
            description="test",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        assert proposal.proposal_id != ""

    def test_to_dict_roundtrip(self):
        proposal = GateProposal(
            proposal_id="test_id",
            gate_id="gate1",
            sequence_id="shot_010",
            operation="create_light",
            description="Create key light",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
            confidence=0.85,
        )
        d = proposal.to_dict()
        restored = GateProposal.from_dict(d)
        assert restored.proposal_id == "test_id"
        assert restored.operation == "create_light"
        assert restored.confidence == 0.85

    def test_human_summary(self):
        proposal = GateProposal(
            proposal_id="test_id",
            gate_id="gate1",
            sequence_id="shot_010",
            operation="create_light",
            description="Create key light",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
            confidence=0.85,
            reasoning="Three-point lighting",
        )
        summary = proposal.to_human_summary()
        assert "REVIEW" in summary
        assert "create_light" in summary
        assert "Three-point lighting" in summary


class TestHumanGate:
    def setup_method(self):
        """Reset singletons and create temp dir"""
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.gate_dir = self.tmp_dir / "gates"
        self.audit_dir = self.tmp_dir / "audit"

    def teardown_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_gate(self):
        """Create gate with audit log pointing to temp dirs"""
        # Set up audit log first (gates depend on it)
        AuditLog.reset_instance()
        AuditLog.get_instance(log_dir=self.audit_dir)
        return HumanGate(storage_dir=self.gate_dir)

    def test_inform_auto_approves(self):
        gate = self._make_gate()
        proposal = gate.propose(
            operation="minor_change",
            description="Small adjustment",
            sequence_id="shot_010",
            category=AuditCategory.LIGHTING,
            level=GateLevel.INFORM,
        )
        assert proposal.decision == GateDecision.APPROVED
        assert proposal.decided_by == "system:inform"

    def test_review_stays_pending(self):
        gate = self._make_gate()
        proposal = gate.propose(
            operation="major_change",
            description="Big change",
            sequence_id="shot_010",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        assert proposal.decision == GateDecision.PENDING

    def test_review_collects_in_batch(self):
        gate = self._make_gate()
        gate.propose(
            operation="op1",
            description="desc1",
            sequence_id="shot_010",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        gate.propose(
            operation="op2",
            description="desc2",
            sequence_id="shot_010",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        batch = gate.get_batch("shot_010")
        assert batch is not None
        assert len(batch.proposals) == 2
        assert batch.pending_count() == 2

    def test_decide_proposal(self):
        gate = self._make_gate()
        proposal = gate.propose(
            operation="test",
            description="test",
            sequence_id="shot_010",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        result = gate.decide(
            proposal.proposal_id,
            GateDecision.APPROVED,
            user_id="artist",
            notes="looks good",
        )
        assert result.decision == GateDecision.APPROVED
        assert result.decided_by == "artist"

    def test_approve_all(self):
        gate = self._make_gate()
        gate.propose(
            operation="op1", description="d1",
            sequence_id="shot_010", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        gate.propose(
            operation="op2", description="d2",
            sequence_id="shot_010", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        batch = gate.approve_all("shot_010", "artist", "all good")
        assert batch.status == "completed"
        assert batch.pending_count() == 0
        for p in batch.proposals:
            assert p.decision == GateDecision.APPROVED

    def test_reject_all(self):
        gate = self._make_gate()
        gate.propose(
            operation="op1", description="d1",
            sequence_id="shot_010", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        batch = gate.reject_all("shot_010", "artist", "nope")
        assert batch.status == "completed"
        for p in batch.proposals:
            assert p.decision == GateDecision.REJECTED

    def test_storage_path_is_synapse(self):
        """Verify storage path was changed from .hyphae to .synapse"""
        gate = HumanGate()
        expected_parent = Path.home() / ".synapse" / "gates"
        assert gate._storage_dir == expected_parent

    def test_singleton_behavior(self):
        gate1 = HumanGate.get_instance(storage_dir=self.gate_dir)
        gate2 = HumanGate.get_instance()
        assert gate1 is gate2

    def test_get_pending(self):
        gate = self._make_gate()
        gate.propose(
            operation="op1", description="d1",
            sequence_id="shot_010", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        gate.propose(
            operation="op2", description="d2",
            sequence_id="shot_020", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        all_pending = gate.get_pending()
        assert len(all_pending) == 2

        shot_010_pending = gate.get_pending(sequence_id="shot_010")
        assert len(shot_010_pending) == 1

    def test_proposal_callback(self):
        gate = self._make_gate()
        received = []
        gate.on_proposal(lambda p: received.append(p))
        gate.propose(
            operation="test", description="test",
            sequence_id="shot_010", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        assert len(received) == 1

    def test_clear_batch(self):
        gate = self._make_gate()
        gate.propose(
            operation="op1", description="d1",
            sequence_id="shot_010", category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
        )
        assert gate.get_batch("shot_010") is not None
        gate.clear_batch("shot_010")
        assert gate.get_batch("shot_010") is None


class TestGateBatch:
    def test_summary(self):
        batch = GateBatch(batch_id="test", sequence_id="shot_010")
        p1 = GateProposal(
            proposal_id="p1", gate_id="g1", sequence_id="shot_010",
            operation="op1", description="d1",
            category=AuditCategory.LIGHTING, level=GateLevel.REVIEW,
        )
        p2 = GateProposal(
            proposal_id="p2", gate_id="g2", sequence_id="shot_010",
            operation="op2", description="d2",
            category=AuditCategory.LIGHTING, level=GateLevel.REVIEW,
            decision=GateDecision.APPROVED,
        )
        batch.add_proposal(p1)
        batch.add_proposal(p2)

        summary = batch.summary()
        assert summary["pending"] == 1
        assert summary["approved"] == 1

    def test_pending_count(self):
        batch = GateBatch(batch_id="test", sequence_id="shot_010")
        assert batch.pending_count() == 0
        p = GateProposal(
            proposal_id="p1", gate_id="g1", sequence_id="shot_010",
            operation="op1", description="d1",
            category=AuditCategory.LIGHTING, level=GateLevel.REVIEW,
        )
        batch.add_proposal(p)
        assert batch.pending_count() == 1


# =============================================================================
# BACKWARDS COMPATIBILITY TESTS
# =============================================================================


class TestBackwardsCompat:
    """Verify Hyphae backwards-compatibility aliases exist"""

    def test_hyphae_audit_log_alias(self):
        from synapse import HyphaeAuditLog
        assert HyphaeAuditLog is AuditLog

    def test_hyphae_gate_alias(self):
        from synapse import HyphaeGate
        assert HyphaeGate is HumanGate


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
