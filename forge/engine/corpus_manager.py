"""
FORGE Corpus Manager — Institutional knowledge accumulation and evolution.

Implements the Pokémon evolution model:
  OBSERVATION → PATTERN → RULE

Each cycle, new observations are added, existing entries are validated,
and entries that meet promotion criteria evolve to the next stage.
Rules are crystallized into SYNAPSE's knowledge layer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schemas import (
    AgentRole,
    CorpusEntry,
    CorpusStage,
    FailureCategory,
    ScenarioDomain,
    ScenarioResult,
    load_json,
    save_json,
)


class CorpusManager:
    """Manages the FORGE institutional knowledge corpus."""

    def __init__(self, corpus_dir: Path):
        self.corpus_dir = corpus_dir
        self.observations_dir = corpus_dir / "observations"
        self.patterns_dir = corpus_dir / "patterns"
        self.rules_dir = corpus_dir / "rules"
        self.manifest_path = corpus_dir / "manifest.json"

        # Ensure directories exist
        for d in [self.observations_dir, self.patterns_dir, self.rules_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Load manifest
        self.manifest: dict = load_json(self.manifest_path, {"entries": {}, "stats": {}})

    # =========================================================================
    # Core Operations
    # =========================================================================

    def add_observation(
        self,
        result: ScenarioResult,
        category: FailureCategory | None = None,
        pattern: str = "",
        context: str = "",
    ) -> CorpusEntry:
        """Create a new observation from a scenario result."""
        entry_id = self._generate_id(result)

        # Check for existing similar entry
        existing = self._find_similar(pattern, result.scenario_id)
        if existing:
            existing.record_recurrence(result.scenario_id)
            self._save_entry(existing)
            return existing

        entry = CorpusEntry(
            id=entry_id,
            created_cycle=result.cycle,
            created_by=result.agent,
            category=category.value if category else "unknown",
            pattern=pattern or result.corpus_contribution,
            context=context or f"Discovered during {result.scenario_id}",
            domain=ScenarioDomain.GENERAL,  # Refined by caller
            derived_from=[result.scenario_id],
        )

        self._save_entry(entry)
        self._update_manifest(entry)
        return entry

    def validate_entry(self, entry_id: str, scenario_id: str) -> CorpusEntry | None:
        """Record that a scenario validated an existing corpus entry."""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None
        entry.validate(scenario_id)
        self._save_entry(entry)
        return entry

    def get_entry(self, entry_id: str) -> CorpusEntry | None:
        """Load a single corpus entry by ID."""
        for stage_dir in [self.observations_dir, self.patterns_dir, self.rules_dir]:
            path = stage_dir / f"{entry_id}.json"
            if path.exists():
                data = load_json(path)
                return CorpusEntry.from_dict(data)
        return None

    def get_all_entries(self, stage: CorpusStage | None = None) -> list[CorpusEntry]:
        """Load all corpus entries, optionally filtered by stage."""
        entries = []
        dirs = (
            [self._stage_dir(stage)]
            if stage
            else [self.observations_dir, self.patterns_dir, self.rules_dir]
        )
        for d in dirs:
            for path in sorted(d.glob("*.json")):
                try:
                    data = load_json(path)
                    entries.append(CorpusEntry.from_dict(data))
                except (KeyError, ValueError):
                    continue
        return entries

    def get_entries_for_domain(self, domain: ScenarioDomain) -> list[CorpusEntry]:
        """Get corpus entries relevant to a specific domain."""
        all_entries = self.get_all_entries()
        return [
            e
            for e in all_entries
            if e.domain == domain or e.domain == ScenarioDomain.GENERAL
        ]

    def evolve_all(self) -> list[tuple[str, CorpusStage]]:
        """Check all entries for promotion eligibility and promote.
        
        Returns list of (entry_id, new_stage) for promoted entries.
        """
        promotions = []
        for entry in self.get_all_entries():
            new_stage = entry.promote()
            if new_stage:
                # Move file to new stage directory
                old_path = self._entry_path(entry.id, self._prev_stage(new_stage))
                new_path = self._entry_path(entry.id, new_stage)
                self._save_entry(entry)  # Save to new location
                if old_path.exists():
                    old_path.unlink()  # Remove from old location
                promotions.append((entry.id, new_stage))
                self._update_manifest(entry)
        return promotions

    def search(self, query: str, top_k: int = 10) -> list[CorpusEntry]:
        """Simple keyword search across corpus entries."""
        query_lower = query.lower()
        scored: list[tuple[float, CorpusEntry]] = []

        for entry in self.get_all_entries():
            text = f"{entry.pattern} {entry.context} {entry.category}".lower()
            # Simple term frequency scoring
            score = sum(1 for word in query_lower.split() if word in text)
            if score > 0:
                # Boost by confidence and stage
                stage_boost = {
                    CorpusStage.OBSERVATION: 1.0,
                    CorpusStage.PATTERN: 1.5,
                    CorpusStage.RULE: 2.0,
                }
                score *= stage_boost.get(entry.stage, 1.0) * (1 + entry.confidence)
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    # =========================================================================
    # Statistics
    # =========================================================================

    @property
    def stats(self) -> dict[str, Any]:
        """Aggregate corpus statistics."""
        all_entries = self.get_all_entries()
        by_stage = {}
        by_domain = {}
        by_category = {}

        for entry in all_entries:
            stage = entry.stage.value
            by_stage[stage] = by_stage.get(stage, 0) + 1
            domain = entry.domain.value
            by_domain[domain] = by_domain.get(domain, 0) + 1
            by_category[entry.category] = by_category.get(entry.category, 0) + 1

        return {
            "total": len(all_entries),
            "by_stage": by_stage,
            "by_domain": by_domain,
            "by_category": by_category,
            "avg_confidence": (
                sum(e.confidence for e in all_entries) / len(all_entries)
                if all_entries
                else 0.0
            ),
        }

    # =========================================================================
    # Internals
    # =========================================================================

    def _generate_id(self, result: ScenarioResult) -> str:
        """Generate a unique, deterministic entry ID."""
        content = f"{result.cycle}:{result.agent.value}:{result.scenario_id}:{result.timestamp}"
        return f"CE-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _find_similar(self, pattern: str, scenario_id: str) -> CorpusEntry | None:
        """Find an existing entry with a similar pattern."""
        if not pattern:
            return None
        target_hash = hashlib.sha256(pattern.encode()).hexdigest()[:16]
        for entry in self.get_all_entries():
            if entry.content_hash == target_hash:
                return entry
        return None

    def _save_entry(self, entry: CorpusEntry) -> None:
        """Save an entry to the appropriate stage directory."""
        path = self._entry_path(entry.id, entry.stage)
        save_json(entry.to_dict(), path)

    def _entry_path(self, entry_id: str, stage: CorpusStage) -> Path:
        """Get the file path for an entry at a given stage."""
        return self._stage_dir(stage) / f"{entry_id}.json"

    def _stage_dir(self, stage: CorpusStage) -> Path:
        """Map stage to directory."""
        return {
            CorpusStage.OBSERVATION: self.observations_dir,
            CorpusStage.PATTERN: self.patterns_dir,
            CorpusStage.RULE: self.rules_dir,
        }[stage]

    def _prev_stage(self, stage: CorpusStage) -> CorpusStage:
        """Get the stage before this one."""
        return {
            CorpusStage.PATTERN: CorpusStage.OBSERVATION,
            CorpusStage.RULE: CorpusStage.PATTERN,
        }.get(stage, CorpusStage.OBSERVATION)

    def _update_manifest(self, entry: CorpusEntry) -> None:
        """Update the manifest with entry metadata."""
        self.manifest["entries"][entry.id] = {
            "stage": entry.stage.value,
            "content_hash": entry.content_hash,
            "confidence": entry.confidence,
            "updated": datetime.utcnow().isoformat(),
        }
        self.manifest["stats"] = self.stats
        save_json(self.manifest, self.manifest_path)
