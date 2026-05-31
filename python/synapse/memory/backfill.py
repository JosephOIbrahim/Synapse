"""One-time backfill: JSONL memory store -> Moneta engine (Mile 8).

Reads the existing memories through the tested ``MemoryStore`` loader (so
encryption/format are handled for us), deposits each into a Moneta-backed
store, and verifies the count round-trips. Count-agnostic: it backfills however
many entries exist (38, 176, 0 — whatever is there).

Safety (harness invariant #6 — backup-first, reversible):
  * The source JSONL is only READ. It is left intact, and a ``.backfill.bak``
    copy is taken before a real run.
  * Reverting the cutover is just flipping ``SYNAPSE_MEMORY_BACKEND`` back to
    ``jsonl`` — the JSONL store is untouched and authoritative.
  * Default is ``dry_run=True``: nothing is written until you pass
    ``--execute`` / ``dry_run=False``.

CLI:
    python -m synapse.memory.backfill <storage_dir>            # dry run (default)
    python -m synapse.memory.backfill <storage_dir> --execute  # real backfill
"""

from __future__ import annotations

import argparse
import logging
import shutil
from collections import Counter
from pathlib import Path
from typing import Optional

from .store import MemoryStore

logger = logging.getLogger(__name__)


def backfill_to_moneta(
    storage_dir,
    *,
    dry_run: bool = True,
    backup: bool = True,
    embedder=None,
) -> dict:
    """Backfill the JSONL store at ``storage_dir`` into a Moneta-backed store.

    Returns a report dict with the source count, deposited count, verification
    result, and a per-type breakdown.
    """
    storage_dir = Path(storage_dir)
    source = MemoryStore(storage_dir)
    source._wait_loaded()
    memories = source.all()

    report = {
        "storage_dir": str(storage_dir),
        "source_count": len(memories),
        "by_type": dict(Counter(m.memory_type.value for m in memories)),
        "dry_run": dry_run,
        "backup": None,
        "deposited": 0,
        "verified": None,
    }

    if dry_run:
        report["would_deposit"] = len(memories)
        return report

    if backup:
        jsonl = storage_dir / "memory.jsonl"
        if jsonl.exists():
            bak = jsonl.with_name("memory.jsonl.backfill.bak")
            shutil.copy2(jsonl, bak)
            report["backup"] = str(bak)

    from .moneta_store import MonetaBackedStore

    target = MonetaBackedStore.from_storage_dir(storage_dir, embedder=embedder)
    try:
        for memory in memories:
            target.add(memory)
        target.save()
        report["deposited"] = target.count()
        report["embedder_id"] = target.embedder_id
    finally:
        target.close()

    report["verified"] = report["deposited"] == report["source_count"]
    return report


def main(argv: Optional[list] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill JSONL memories into Moneta.")
    parser.add_argument("storage_dir", help="Path to the .synapse storage dir")
    parser.add_argument("--execute", action="store_true",
                        help="Actually write (default is a dry run)")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip backing up memory.jsonl (not recommended)")
    args = parser.parse_args(argv)

    report = backfill_to_moneta(
        args.storage_dir,
        dry_run=not args.execute,
        backup=not args.no_backup,
    )

    logger.info("=== Moneta backfill report ===")
    for key, value in report.items():
        logger.info("  %s: %s", key, value)
    if not args.execute:
        logger.info("  (dry run -- re-run with --execute to write)")
        return 0
    if not report["verified"]:
        logger.error("  VERIFICATION FAILED: deposited != source_count")
        return 1
    logger.info("  OK: every memory backfilled and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
