"""
Tests for the pass-4 fixes to shared/evolution.py and shared/bridge.py.

Covers:
  E1/E2 -- file handles closed via context manager + utf-8 encoding
  E3    -- archive is preserved across rollback (immutable backup)
  B1    -- _operation_log is a bounded deque (no unbounded memory growth)
  B2    -- public accessors for operation history
  B3    -- operation_stats() exposes counters previously private
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.evolution import (  # noqa: E402
    AssetRef,
    Decision,
    LosslessEvolution,
    ParameterRecord,
    ParsedMemory,
    SessionEntry,
    check_evolution_triggers,
    parse_markdown_memory,
    parse_markdown_memory_from_string,
)
from shared.bridge import (  # noqa: E402
    LosslessExecutionBridge,
    Operation,
    IntegrityBlock,
)
from shared.types import AgentID  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# E1/E2: file handles + utf-8 encoding
# ─────────────────────────────────────────────────────────────────

class TestEvolutionFileHandling:
    def test_utf8_content_round_trips(self, tmp_path):
        # Em-dashes, smart quotes, an emoji — all non-ASCII. On Windows
        # the platform default encoding (cp1252) cannot encode 🟢, so a
        # missing encoding= would raise.
        md = tmp_path / "memory.md"
        md.write_text(
            "# SYNAPSE Memory\n\n"
            "## Session 2026-04-08\n"
            "Worked on “lossless evolution” — shipped fixes 🟢\n"
            "**Decision:** keep the archive on rollback\n",
            encoding="utf-8",
        )

        check = check_evolution_triggers(str(md))
        # Should not raise; content should be decoded
        assert check is not None

        parsed = parse_markdown_memory(str(md))
        assert len(parsed.sessions) == 1
        assert "lossless evolution" in parsed.sessions[0].text or \
               any("archive" in d.lower() for d in parsed.sessions[0].decisions)

    def test_no_open_file_handles_after_check(self, tmp_path):
        # Sanity: the file should be closeable/deletable immediately after
        # check_evolution_triggers — proves no lingering handle on Windows.
        md = tmp_path / "memory.md"
        md.write_text("# empty\n", encoding="utf-8")
        check_evolution_triggers(str(md))
        # On Windows, deleting a file with an open handle raises PermissionError
        os.remove(str(md))
        assert not md.exists()


# ─────────────────────────────────────────────────────────────────
# E3: archive must survive rollback
# ─────────────────────────────────────────────────────────────────

class TestArchivePreservedOnRollback:
    def _seed_rich_memory(self, md_path: Path) -> None:
        # Build content that meets several evolution triggers so we actually
        # enter the pipeline. Doesn't need to round-trip perfectly — we want
        # the path that REACHES the verification step.
        lines = ["# SYNAPSE Memory\n"]
        for i in range(12):
            lines.append(f"## Session 2026-04-{i+1:02d}\n")
            lines.append(f"Did some work on /obj/geo{i}\n")
            lines.append(f"**Decision:** choice number {i}\n")
            lines.append("Reasoning here.\n")
            lines.append(f"### Parameter: param_{i}\n")
            lines.append(f"@/scene/asset_{i}.usd@\n")
        md_path.write_text("".join(lines), encoding="utf-8")

    def test_archive_persists_on_success(self, tmp_path):
        md = tmp_path / "memory.md"
        usd = tmp_path / "memory.usd"
        self._seed_rich_memory(md)

        ev = LosslessEvolution()
        result = ev.evolve_to_structured(str(md), str(usd))

        archive = tmp_path / "memory_pre_evolution.md"
        assert archive.exists(), "Archive must exist after evolution"
        # Whether evolved or not, archive is the audit trail
        if result.evolved:
            assert result.archive_path == str(archive)

    def test_archive_persists_on_rollback(self, tmp_path, monkeypatch):
        md = tmp_path / "memory.md"
        usd = tmp_path / "memory.usd"
        self._seed_rich_memory(md)

        ev = LosslessEvolution()

        # Force a verification failure by stubbing the verifier to return
        # degraded fidelity. This drives the rollback path.
        from shared.evolution import EvolutionIntegrity

        def _fake_verify(orig, recon):
            return EvolutionIntegrity(fidelity=0.5, failures=["forced_for_test"])

        monkeypatch.setattr(ev, "_verify_lossless", _fake_verify)

        result = ev.evolve_to_structured(str(md), str(usd))
        assert result.evolved is False
        assert "forced_for_test" in result.reason

        archive = tmp_path / "memory_pre_evolution.md"
        # E3 fix: archive is the immutable backup — it MUST survive rollback.
        assert archive.exists(), (
            "Archive was deleted on rollback — this destroys the audit trail "
            "and contradicts CLAUDE.md §6 'PRESERVE — immutable backup'"
        )
        # The failed USD should NOT survive
        assert not usd.exists(), "Failed USD output must be removed on rollback"
        # The archive_path field on the result should also point at it
        assert result.archive_path == str(archive)


# ─────────────────────────────────────────────────────────────────
# B1: bounded operation log
# ─────────────────────────────────────────────────────────────────

class TestBoundedOperationLog:
    def test_default_cap(self):
        bridge = LosslessExecutionBridge()
        assert bridge._operation_log.maxlen == bridge.DEFAULT_LOG_MAX_SIZE

    def test_custom_cap(self):
        bridge = LosslessExecutionBridge(log_max_size=50)
        assert bridge._operation_log.maxlen == 50

    def test_cap_drops_oldest(self):
        bridge = LosslessExecutionBridge(log_max_size=5)

        def _noop():
            return "ok"

        for i in range(10):
            op = Operation(
                agent_id=AgentID.SUBSTRATE,
                operation_type="read_network",
                summary=f"op{i}",
                fn=_noop,
            )
            bridge.execute(op)

        assert len(bridge._operation_log) == 5
        # Counters keep the true totals even though log is capped
        assert bridge._operations_total == 10
        assert bridge._operations_verified == 10


# ─────────────────────────────────────────────────────────────────
# B2: public accessors
# ─────────────────────────────────────────────────────────────────

class TestOperationLogAccessors:
    def _seed(self, bridge: LosslessExecutionBridge, n: int = 5) -> None:
        def _noop():
            return "ok"
        for i in range(n):
            op = Operation(
                agent_id=AgentID.OBSERVER,
                operation_type="read_network",
                summary=f"op{i}",
                fn=_noop,
            )
            bridge.execute(op)

    def test_recent_operations_returns_blocks(self):
        bridge = LosslessExecutionBridge()
        self._seed(bridge, 5)
        recent = bridge.recent_operations()
        assert len(recent) == 5
        assert all(isinstance(b, IntegrityBlock) for b in recent)

    def test_recent_operations_respects_n(self):
        bridge = LosslessExecutionBridge()
        self._seed(bridge, 10)
        assert len(bridge.recent_operations(n=3)) == 3
        assert len(bridge.recent_operations(n=0)) == 0

    def test_recent_operations_returns_copy(self):
        bridge = LosslessExecutionBridge()
        self._seed(bridge, 3)
        copy = bridge.recent_operations()
        copy.clear()
        # Internal state untouched
        assert len(bridge._operation_log) == 3

    def test_clear_operation_log(self):
        bridge = LosslessExecutionBridge()
        self._seed(bridge, 7)
        dropped = bridge.clear_operation_log()
        assert dropped == 7
        assert len(bridge._operation_log) == 0
        # Lifetime counters survive clear
        assert bridge._operations_total == 7


# ─────────────────────────────────────────────────────────────────
# B3: operation_stats exposes private counters
# ─────────────────────────────────────────────────────────────────

class TestOperationStats:
    def test_stats_shape(self):
        bridge = LosslessExecutionBridge()
        stats = bridge.operation_stats()
        for key in (
            "operations_total", "operations_verified", "anchor_violations",
            "success_rate", "log_size", "log_capacity",
            "per_agent", "per_operation_type", "session_id",
        ):
            assert key in stats, f"missing key: {key}"

    def test_stats_track_per_agent(self):
        bridge = LosslessExecutionBridge()

        def _noop():
            return "ok"

        for agent in (AgentID.HANDS, AgentID.HANDS, AgentID.OBSERVER):
            bridge.execute(Operation(
                agent_id=agent,
                operation_type="read_network",
                summary="t",
                fn=_noop,
            ))

        stats = bridge.operation_stats()
        assert stats["per_agent"][AgentID.HANDS.value] == 2
        assert stats["per_agent"][AgentID.OBSERVER.value] == 1
        assert stats["operations_total"] == 3
        assert stats["operations_verified"] == 3
        assert stats["success_rate"] == 1.0

    def test_stats_zero_division_safe(self):
        bridge = LosslessExecutionBridge()
        stats = bridge.operation_stats()
        assert stats["success_rate"] == 0.0
        assert stats["operations_total"] == 0


# ─────────────────────────────────────────────────────────────────
# E5: Content-aware lossless verification
# ─────────────────────────────────────────────────────────────────

class TestContentAwareVerification:
    """The previous verifier checked counts/slugs only — content drift went
    silently undetected. These tests prove the new hash-based verifier
    catches the cases the old one missed."""

    def _rich_parsed(self) -> ParsedMemory:
        return ParsedMemory(
            sessions=[SessionEntry(
                id="session_2026_04_08",
                date="2026-04-08",
                text="kickoff",
                decisions=["use Karma XPU"],
            )],
            decisions=[
                Decision(
                    slug="render_engine",
                    choice="use Karma XPU",
                    reasoning="GPU speed",
                    date="2026-04-08",
                    alternatives=["Mantra", "Renderman"],
                ),
            ],
            assets=[
                AssetRef(
                    name="hero",
                    path="/scene/hero.usd",
                    notes="hero asset",
                    variants=["red", "blue"],
                ),
            ],
            parameters=[
                ParameterRecord(
                    slug="samples",
                    node="/stage/karma",
                    name="samples",
                    before="64",
                    after="256",
                    result="clean",
                    date="2026-04-08",
                ),
            ],
        )

    def test_clean_parsed_round_trip_passes(self):
        """A round-trip of the canonical fields preserves fidelity 1.0."""
        ev = LosslessEvolution()
        original = self._rich_parsed()
        companion = ev._generate_companion(original)
        recon = parse_markdown_memory_from_string(companion)
        integrity = ev._verify_lossless(original, recon)
        assert integrity.fidelity == 1.0, integrity.failures

    def test_decision_date_drift_caught(self):
        """E5: previously this passed silently — date got dropped."""
        ev = LosslessEvolution()
        original = self._rich_parsed()
        recon = self._rich_parsed()
        recon.decisions[0].date = ""  # simulate companion writer dropping date
        integrity = ev._verify_lossless(original, recon)
        assert integrity.fidelity < 1.0
        assert any("Decision content drift" in f for f in integrity.failures)

    def test_decision_alternatives_drift_caught(self):
        ev = LosslessEvolution()
        original = self._rich_parsed()
        recon = self._rich_parsed()
        recon.decisions[0].alternatives = []
        integrity = ev._verify_lossless(original, recon)
        assert integrity.fidelity < 1.0

    def test_decision_reasoning_drift_caught(self):
        """A 'lossless' verifier must catch this — silent corruption is the
        worst possible failure mode for memory evolution."""
        ev = LosslessEvolution()
        original = self._rich_parsed()
        recon = self._rich_parsed()
        recon.decisions[0].reasoning = ""
        integrity = ev._verify_lossless(original, recon)
        assert integrity.fidelity < 1.0
        assert any("Decision content drift" in f for f in integrity.failures)

    def test_asset_variants_drift_caught(self):
        ev = LosslessEvolution()
        original = self._rich_parsed()
        recon = self._rich_parsed()
        recon.assets[0].variants = []
        integrity = ev._verify_lossless(original, recon)
        assert integrity.fidelity < 1.0
        assert any("Asset content drift" in f for f in integrity.failures)

    def test_parameter_value_drift_caught(self):
        ev = LosslessEvolution()
        original = self._rich_parsed()
        recon = self._rich_parsed()
        recon.parameters[0].after = "9999"
        integrity = ev._verify_lossless(original, recon)
        assert integrity.fidelity < 1.0
        assert any("Parameter content drift" in f for f in integrity.failures)

    def test_decision_round_trip_through_companion(self):
        """End-to-end: write companion, parse it back, hashes still match."""
        ev = LosslessEvolution()
        original = self._rich_parsed()
        companion = ev._generate_companion(original)

        # The companion must contain the canonical fields E5 added
        assert "Date: 2026-04-08" in companion
        assert "Alternatives: Mantra | Renderman" in companion
        assert "Variants: red | blue" in companion

        recon = parse_markdown_memory_from_string(companion)
        # Reconstructed objects must hash to the same values. The companion
        # may emit a session-attached **Decision:** stub in addition to the
        # top-level ### Decision section, so we look up by slug.
        recon_by_slug = {d.slug: d for d in recon.decisions}
        assert "render_engine" in recon_by_slug
        assert ev._decision_hash(original.decisions[0]) == \
               ev._decision_hash(recon_by_slug["render_engine"])
        assert ev._asset_hash(original.assets[0]) == \
               ev._asset_hash(recon.assets[0])

    def test_fidelity_is_now_binary(self):
        """E7: graduated 0.1-per-failure was meaningless. Verify it's binary."""
        ev = LosslessEvolution()
        original = self._rich_parsed()
        recon = self._rich_parsed()
        recon.decisions[0].reasoning = ""
        recon.assets[0].variants = []
        recon.parameters[0].after = "9999"
        integrity = ev._verify_lossless(original, recon)
        # Three failures, but fidelity is exactly 0.0 — not 0.7
        assert integrity.fidelity == 0.0
        assert len(integrity.failures) == 3
