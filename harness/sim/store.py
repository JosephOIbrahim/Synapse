"""Append-only storage for the SIM ledger.

One file per cluster, one JSON object per line, nothing updatable. The store
refuses three things on purpose:

* a record that does not validate — on write *and* on read, so a hand edit is
  caught rather than absorbed;
* an attempt for a cluster that was never declared;
* a second concurrent writer, via an exclusive lock file rather than a merge.

There is no update and no delete. A correction is a new record.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

from .schema import AttemptRecord, ClusterStatus, ProblemCluster, SchemaError
from .setting import SettingFingerprint

DEFAULT_ROOT = Path(__file__).resolve().parent / "ledger"


class StoreError(RuntimeError):
    """The store refused a write, or the ledger on disk is not readable."""


class SIMStore:
    """A directory of per-cluster JSONL ledgers."""

    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)

    # -- paths ---------------------------------------------------------------

    def _cluster_path(self, cluster_id: str) -> Path:
        return self.root / f"{cluster_id}.cluster.json"

    def _attempts_path(self, cluster_id: str) -> Path:
        return self.root / f"{cluster_id}.attempts.jsonl"

    def _lock_path(self, cluster_id: str) -> Path:
        return self.root / f"{cluster_id}.lock"

    # -- clusters ------------------------------------------------------------

    def declare_cluster(self, cluster: ProblemCluster) -> None:
        """Record a cluster. Re-declaring an identical cluster is a no-op."""
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._cluster_path(cluster.cluster_id)
        payload = json.dumps(cluster.to_dict(), sort_keys=True, indent=2) + "\n"
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != payload:
                raise StoreError(
                    f"cluster {cluster.cluster_id} already declared with different content; "
                    "the ledger is append-only"
                )
            return
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def clusters(self) -> list[ProblemCluster]:
        if not self.root.exists():
            return []
        return [
            ProblemCluster.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self.root.glob("*.cluster.json"))
        ]

    # -- attempts ------------------------------------------------------------

    def append(self, record: AttemptRecord) -> None:
        """Append one attempt. Refuses if the cluster is unknown or a writer holds the lock."""
        if not self._cluster_path(record.cluster_id).exists():
            raise StoreError(
                f"no cluster {record.cluster_id} on disk; declare it before recording an attempt"
            )
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self._lock_path(record.cluster_id)
        try:
            handle = lock.open("x", encoding="utf-8")
        except FileExistsError as exc:
            raise StoreError(
                f"another writer holds {lock.name}; the store does not merge concurrent writes"
            ) from exc
        try:
            line = json.dumps(record.to_dict(), sort_keys=True) + "\n"
            with self._attempts_path(record.cluster_id).open("a", encoding="utf-8", newline="\n") as out:
                out.write(line)
                out.flush()
                os.fsync(out.fileno())
        finally:
            handle.close()
            lock.unlink(missing_ok=True)

    def attempts_for(self, cluster_id: str) -> list[AttemptRecord]:
        path = self._attempts_path(cluster_id)
        if not path.exists():
            return []
        records: list[AttemptRecord] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(AttemptRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, SchemaError) as exc:
                raise StoreError(f"{path.name}:{number} does not validate: {exc}") from exc
        return records

    def query_by_signature(self, symptom_signature: str) -> list[AttemptRecord]:
        from .schema import cluster_id_for

        return self.attempts_for(cluster_id_for(symptom_signature))

    def query_by_setting(self, setting: SettingFingerprint) -> list[AttemptRecord]:
        return [record for record in self.iter_attempts() if record.setting == setting]

    def iter_attempts(self) -> Iterator[AttemptRecord]:
        for cluster in self.clusters():
            yield from self.attempts_for(cluster.cluster_id)

    def known_negatives(self, target_artifact: str, setting: SettingFingerprint) -> list[AttemptRecord]:
        """Attempts on the same artifact, under the same setting, that were not retained.

        Phase 3 uses this to refuse re-proposing an edit that already failed here.
        """
        return [
            record
            for record in self.query_by_setting(setting)
            if record.target_artifact == target_artifact
            and record.selector_verdict.value != "RETAIN"
        ]


def cluster_status_counts(store: SIMStore) -> dict[str, int]:
    """Small helper for tests and for a future health view."""
    counts = {status.value: 0 for status in ClusterStatus}
    for cluster in store.clusters():
        counts[cluster.status.value] += 1
    return counts
