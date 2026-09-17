"""backfill_from_moneta.py -- re-mirror the records the outage stranded (incident B5).

Why this file exists
--------------------
Between 2026-09-15 19:09Z and 2026-09-17 19:53Z the JSONL mirror was DEGRADED
and refused every write (one conflicting duplicate line was enough --
``store.py:355-362`` raises, ``store.py:396-401`` degrades on a non-empty
unreadable list). The Moneta primary kept accepting deposits throughout, because
``MonetaBackedStore.add`` commits the deposit and ``save()`` FIRST and only then
attempts the mirror, swallowing the mirror's failure with no retry and no queue
(``moneta_store.py:744-751`` and ``:784-785``). Every write during those two days
diverged by construction.

The 2026-09-17 audit triangulated the result three times independently:

===========================  ======  ======  ===============  ==============
read                         moneta  jsonl   only in moneta   only in jsonl
===========================  ======  ======  ===============  ==============
M1                           1111    862     253              4
M2                           1111    862     253              4
M3 (an hour later)           1114    865     253              4
===========================  ======  ======  ===============  ==============

**253 records exist only in the primary**, 245 of them created inside the outage
window, 0 before it, 8 after. By kind: 219 ``loop_*`` feedback, 18 note, 16
action. The control against "loop records just do not mirror" is that ``loop_*``
appears 305 times in the JSONL spanning 08 Sep to 17 Sep -- they normally do
mirror. These are stranded, not excluded.

That matters because of B1: an ungated automatic prune is armed over the primary
(``moneta_store.py:729-731`` fires ``run_sleep_pass()`` every 100th non-durable
``add`` once ``ecs.n > 1000``; it is over 1119). A prune of a MIRRORED record is
recoverable -- ``backfill.py`` runs JSONL -> Moneta. A prune of one of the 253 is
permanent, because **no Moneta -> JSONL path exists in this tree**. This module is
that path. The mirror is precisely the thing that makes a prune survivable, and
the 253 are precisely the records that lack it.

**4 records exist only in the mirror**, including ``mem_e2e9749cb3c3`` -- the
decision binding *"Create a Solaris Network"* and *"Basic Studio Lighting Setup"*
to the v4 recipe. It is absent from the primary and from ``cortex_root.usda``, and
recall defaults to DECISION-only (``store.py:1560-1562``) against a primary that
holds three decisions, none of them that one. So this tool **reports both
directions** even though it only writes one: the mirror-only set is the more
interesting half and would be invisible if the report only counted what it fixes.
Depositing those 4 into the primary needs ``add_durable_if_absent`` and Moneta's
single-owner URI lock, which is a different operation with a different blast
radius; it is named here, deliberately not performed here.

Order of operations
-------------------
:mod:`synapse.memory.primary_repair` MUST run first. The primary still holds five
ids twice each; backfilling one of those would re-emit the conflicting pair into
the mirror and **re-degrade it on the next load** -- reproducing the original
outage with the tool meant to heal it. That precondition is enforced in code:
:func:`check_preconditions` calls ``primary_repair.scan_snapshot`` and refuses on
any duplicate, so the two tools cannot be run out of order by accident.

Safety contract
---------------
* **Dry run is the default.** Nothing is written without ``--apply``.
* **Never executed on import.** Everything is behind ``main()`` / ``__main__``.
* **The primary is only READ, and never through the store class.**
  ``MonetaBackedStore.from_storage_dir`` takes Moneta's URI lock and can rewrite
  ``snapshot.json`` on the way in (``_reconcile_snapshot_dim``,
  ``_quarantine_if_corrupt``). This module parses the snapshot as plain JSON via
  ``primary_repair.load_snapshot`` -- no lock, no mutation, no embedder.
* **Writes go through the store's own ``add()`` path.** Never a hand-appended
  line. ``MemoryStore.add`` encrypts with the live key and emits
  ``memory.to_json()``, so the bytes cannot drift from the canonical form
  ``_load`` will read back. A hand-rolled append is how you write a line the
  loader rejects, which is the incident.
* **Idempotent by construction.** The unit of work is the id-set difference,
  recomputed on every run, plus a per-record ``store.get(id)`` re-check taken
  immediately before each add. Running twice writes nothing the second time.
  This is the whole class of bug being repaired -- an operation that is not
  idempotent is how one id ended up on two lines.
* **Refuses to run while Houdini is live.** A live ``MemoryStore.save()`` rewrites
  memory.jsonl whole from its own in-memory dict (``store.py:462-505``), which
  would silently delete every line this tool appended. Same two probes and the
  same explicit override as ``primary_repair``.
* **Verified by cold load, with rollback.** After writing, a FRESH ``MemoryStore``
  is opened over the file -- the paired-control lesson from the 2026-09-17 repair
  record, where "the repaired file loads clean" was only trustworthy because a
  control arm proved the un-repaired file still failed. If the cold load is
  degraded or the diff does not close, the pre-write backup is restored.

CLI::

    python -m synapse.memory.backfill_from_moneta <storage_dir>          # dry run
    python -m synapse.memory.backfill_from_moneta <storage_dir> --apply  # write
    python -m synapse.memory.backfill_from_moneta <storage_dir> --json
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import Memory
from .primary_repair import (
    DEFAULT_QUIET_SECONDS,
    canonical,
    live_houdini_processes,
    load_snapshot,
    scan_snapshot,
    seconds_since_touched,
    _sha256_file,
)

logger = logging.getLogger(__name__)


# The window in which the mirror refused writes. Local time was 2026-09-15 15:09
# -> 2026-09-17 15:53; Memory.created_at is UTC and lexicographically sortable
# (``time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())``), so plain string
# comparison is the right comparison here. Used only to CLASSIFY the gap in the
# report -- never to filter what gets written. A stranded record outside the
# window is still stranded.
OUTAGE_START_UTC = "2026-09-15T19:09:00Z"
OUTAGE_END_UTC = "2026-09-17T19:53:59Z"

# The mirror-only decision the audit called out by name. Reported specially
# because it is the record that answers the artist's most common trigger phrase,
# and because a count of "4" hides which 4.
NOTABLE_MIRROR_ONLY_ID = "mem_e2e9749cb3c3"


# ---------------------------------------------------------------------------
# report types
# ---------------------------------------------------------------------------

@dataclass
class DiffReport:
    """The id-set difference, both directions, measured before anything moves."""

    snapshot: str = ""
    mirror: str = ""
    primary_rows: int = 0
    primary_distinct_ids: int = 0
    primary_unreadable_rows: int = 0
    mirror_records: int = 0
    only_in_primary: List[str] = field(default_factory=list)
    only_in_mirror: List[str] = field(default_factory=list)
    intersection: int = 0
    only_in_primary_inside_outage: int = 0
    only_in_primary_before_outage: int = 0
    only_in_primary_after_outage: int = 0
    only_in_primary_by_type: Dict[str, int] = field(default_factory=dict)
    notable_mirror_only_present: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class BackfillReport:
    """What the run did, or would do, and why it stopped if it stopped."""

    storage_dir: str = ""
    dry_run: bool = True
    diff: Optional[DiffReport] = None
    liveness: Dict[str, Any] = field(default_factory=dict)
    preconditions: Dict[str, Any] = field(default_factory=dict)
    would_write: int = 0
    written: int = 0
    skipped_already_present: int = 0
    skipped_not_roundtrippable: List[str] = field(default_factory=list)
    backup: Optional[str] = None
    backup_sha256: Optional[str] = None
    verify: Dict[str, Any] = field(default_factory=dict)
    rolled_back: bool = False
    refusals: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.refusals

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["diff"] = self.diff.to_dict() if self.diff else None
        d["ok"] = self.ok
        return d


# ---------------------------------------------------------------------------
# reading both stores
# ---------------------------------------------------------------------------

def read_primary(snapshot_path: Path) -> Tuple[Dict[str, Memory], int, int]:
    """Read every memory out of ``snapshot.json``. Returns ``(by_id, rows, unreadable)``.

    Plain JSON, read-only -- see the module docstring on why this does not go
    through ``MonetaBackedStore``. A row whose payload will not deserialize is
    counted and skipped rather than raising, mirroring
    ``_iter_memories``'s non-strict posture (``moneta_store.py:843-849``): one bad
    entry must never hide every other memory.

    On a duplicate id the FIRST row wins, matching ``MemoryStore._load``'s
    keep-the-first rule. That only matters if the caller skipped
    :func:`check_preconditions`, which refuses on duplicates -- the tie-break
    exists so this function has defined behaviour, not so the precondition can be
    bypassed.
    """
    data = load_snapshot(snapshot_path)
    rows = data["rows"]
    by_id: Dict[str, Memory] = {}
    unreadable = 0
    for row in rows:
        try:
            memory = Memory.from_json(row["payload"])
            if not memory.id:
                raise ValueError("payload carries no memory identity")
        except Exception as exc:  # noqa: BLE001
            unreadable += 1
            logger.warning(
                "Skipping unreadable primary row %s: %s",
                (row or {}).get("entity_id", "<unknown>") if isinstance(row, dict) else "<unknown>",
                exc,
            )
            continue
        by_id.setdefault(memory.id, memory)
    return by_id, len(rows), unreadable


def open_mirror(storage_dir: Path):
    """Open the JSONL mirror through its own tested loader.

    ``background_load=False`` on purpose: the default spawns a loader thread, and
    a caller that reads ``_degraded_load`` immediately afterwards can see the
    pre-load ``False`` and conclude the store is healthy when it is not. A
    recovery tool asking "is this store degraded?" must get the answer, not a
    race. ``backfill.py`` handles the same hazard with ``_wait_loaded()``; a
    synchronous load is the stronger form.
    """
    from .store import MemoryStore
    return MemoryStore(storage_dir, background_load=False)


def diff_stores(snapshot_path: Path, storage_dir: Path) -> Tuple[DiffReport, Dict[str, Memory], Any]:
    """Compute the id-set difference both ways, and classify the gap.

    Returns the report plus the two live handles the caller needs, so the diff
    is measured exactly once and the write phase acts on the same reading.
    """
    primary, rows, unreadable = read_primary(snapshot_path)
    mirror_store = open_mirror(storage_dir)
    mirror_ids = {m.id for m in mirror_store.all()}

    only_primary = sorted(set(primary) - mirror_ids)
    only_mirror = sorted(mirror_ids - set(primary))

    diff = DiffReport(
        snapshot=str(snapshot_path),
        mirror=str(storage_dir / "memory.jsonl"),
        primary_rows=rows,
        primary_distinct_ids=len(primary),
        primary_unreadable_rows=unreadable,
        mirror_records=len(mirror_ids),
        only_in_primary=only_primary,
        only_in_mirror=only_mirror,
        intersection=len(set(primary) & mirror_ids),
        notable_mirror_only_present=NOTABLE_MIRROR_ONLY_ID in only_mirror,
    )

    for mid in only_primary:
        memory = primary[mid]
        created = memory.created_at or ""
        if created < OUTAGE_START_UTC:
            diff.only_in_primary_before_outage += 1
        elif created > OUTAGE_END_UTC:
            diff.only_in_primary_after_outage += 1
        else:
            diff.only_in_primary_inside_outage += 1
        kind = getattr(memory.memory_type, "value", str(memory.memory_type))
        diff.only_in_primary_by_type[kind] = diff.only_in_primary_by_type.get(kind, 0) + 1

    return diff, primary, mirror_store


# ---------------------------------------------------------------------------
# preconditions
# ---------------------------------------------------------------------------

def check_preconditions(
    snapshot_path: Path,
    mirror_store,
    *,
    allow_live_houdini: bool = False,
    quiet_seconds: float = DEFAULT_QUIET_SECONDS,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Everything that must be true before a single line is appended.

    Returns ``(preconditions, liveness, refusals)``. A non-empty ``refusals``
    means the run stops with nothing written.
    """
    refusals: List[str] = []
    pre: Dict[str, Any] = {}

    # (c) -- the ordering contract with primary_repair, enforced by calling its
    # scan rather than restating its rule. A duplicate id in the primary means a
    # backfill would append a conflicting pair to the mirror and re-degrade it on
    # the next load: the original outage, re-created by the repair tool.
    scan = scan_snapshot(snapshot_path)
    pre["primary_duplicate_ids"] = [d.memory_id for d in scan.duplicates]
    pre["primary_duplicate_rows"] = scan.rows_to_drop
    if scan.duplicates:
        refusals.append(
            "the primary still holds %d duplicate id(s) (%s%s) -- backfilling "
            "them would re-emit the conflicting pair into the mirror and degrade "
            "it again. Run: python -m synapse.memory.primary_repair <storage_dir> "
            "--apply" % (
                len(scan.duplicates),
                ", ".join(d.memory_id for d in scan.duplicates[:5]),
                ", ..." if len(scan.duplicates) > 5 else "",
            )
        )

    # The mirror must be able to accept writes at all. ``MemoryStore.add`` calls
    # ``_require_writable_load()``, which raises on a degraded load -- so without
    # this check the first add() would raise mid-batch, leaving a partial run.
    degraded = bool(getattr(mirror_store, "_degraded_load", False))
    pre["mirror_degraded"] = degraded
    pre["mirror_degraded_reason"] = getattr(mirror_store, "_degraded_reason", "")
    if degraded:
        refusals.append(
            "the mirror loaded DEGRADED and refuses writes (%s) -- repair it "
            "first; %s is the producer that did it in September"
            % (pre["mirror_degraded_reason"] or "no reason recorded",
               "harness/notes/store-incident-2026-09-17/repair.py")
        )

    # Liveness. A live MemoryStore.save() rewrites memory.jsonl whole from its own
    # in-memory dict, so every line appended here would vanish without a trace.
    hits, probe_error = live_houdini_processes()
    snap_age = seconds_since_touched(snapshot_path)
    mirror_path = Path(mirror_store.memory_file)
    mirror_age = seconds_since_touched(mirror_path)
    liveness = {
        "processes": hits,
        "process_probe_error": probe_error,
        "snapshot_age_seconds": None if snap_age is None else round(snap_age, 1),
        "mirror_age_seconds": None if mirror_age is None else round(mirror_age, 1),
        "quiet_threshold_seconds": quiet_seconds,
        "override": allow_live_houdini,
    }
    blocking: List[str] = []
    if hits:
        blocking.append(f"Houdini appears to be running: {', '.join(hits[:5])}")
    if probe_error:
        blocking.append(f"could not determine whether Houdini is running ({probe_error})")
    for label, age in (("snapshot", snap_age), ("mirror", mirror_age)):
        if age is not None and age < quiet_seconds:
            blocking.append(
                f"{label} was modified {age:.0f}s ago (< {quiet_seconds:.0f}s): "
                f"something is still writing this store"
            )
    liveness["blocking"] = blocking
    if blocking and not allow_live_houdini:
        refusals.extend(blocking)
        refusals.append(
            "close Houdini and re-run, or pass --allow-live-houdini -- a live "
            "save() rewrites memory.jsonl from memory and would delete every "
            "line this tool appends"
        )

    return pre, liveness, refusals


def _roundtrips(memory: Memory, source_payload: str) -> bool:
    """Does this record survive primary -> Memory -> mirror unchanged?

    The mirror will store ``memory.to_json()``. If that is not equivalent to the
    payload the primary holds, the backfill is a silent content mutation dressed
    as a copy. Compared under :func:`canonical` (``sort_keys=True``) because key
    ORDER is not part of the record's identity -- that is the same comparison
    ``MemoryStore._load`` uses to decide two lines conflict.

    This is expected to pass for every record: ``Memory`` is serialized whole and
    round-trips byte-for-byte per ``moneta_store``'s mapping contract. It is here
    because that contract is a property of the CURRENT model, and this model has
    grown fields before -- W3-KIND added ``reasoning``/``alternatives``/``status``/
    ``ref_uri``. A field added to ``to_dict`` but not read by ``from_dict`` (or the
    reverse) would make this fire, and the alternative to firing is writing
    quietly lossy copies of 253 records that exist nowhere else.
    """
    try:
        return canonical(json.loads(source_payload)) == canonical(json.loads(memory.to_json()))
    except Exception:  # noqa: BLE001 -- unparseable means "do not trust it"
        return False


# ---------------------------------------------------------------------------
# the backfill
# ---------------------------------------------------------------------------

def backfill_from_moneta(
    storage_dir,
    *,
    dry_run: bool = True,
    backup: bool = True,
    allow_live_houdini: bool = False,
    quiet_seconds: float = DEFAULT_QUIET_SECONDS,
    snapshot_path=None,
) -> BackfillReport:
    """Copy primary-only records into the JSONL mirror. Dry run by default.

    Returns a :class:`BackfillReport` in every case. ``report.refusals`` non-empty
    means nothing was written and why.
    """
    storage_dir = Path(storage_dir)
    snapshot = Path(snapshot_path) if snapshot_path else storage_dir / ".moneta" / "snapshot.json"
    report = BackfillReport(storage_dir=str(storage_dir), dry_run=dry_run)

    if not snapshot.exists():
        report.refusals.append(f"primary snapshot not found: {snapshot}")
        return report

    mirror_store = None
    try:
        diff, primary, mirror_store = diff_stores(snapshot, storage_dir)
        report.diff = diff

        pre, liveness, refusals = check_preconditions(
            snapshot, mirror_store,
            allow_live_houdini=allow_live_houdini,
            quiet_seconds=quiet_seconds,
        )
        report.preconditions = pre
        report.liveness = liveness
        report.refusals.extend(refusals)

        # Round-trip screening happens in the dry run too, so the operator sees
        # the true would-write count before deciding, not a number that shrinks
        # on the real run.
        rows_by_id: Dict[str, str] = {}
        for row in load_snapshot(snapshot)["rows"]:
            try:
                obj = json.loads(row["payload"])
                rows_by_id.setdefault(obj["id"], row["payload"])
            except Exception:  # noqa: BLE001 -- already counted as unreadable
                continue

        writable: List[Memory] = []
        for mid in diff.only_in_primary:
            memory = primary[mid]
            if _roundtrips(memory, rows_by_id.get(mid, "")):
                writable.append(memory)
            else:
                report.skipped_not_roundtrippable.append(mid)
        report.would_write = len(writable)

        if report.refusals or dry_run:
            return report
        if not writable:
            # Already converged. This is the idempotent second run: the diff is
            # empty, so there is nothing to do and nothing to back up.
            return report

        # -- backup, verified by hash -------------------------------------
        mirror_path = Path(mirror_store.memory_file)
        if backup and mirror_path.exists():
            ts = int(time.time())
            bak = mirror_path.with_name(f"{mirror_path.name}.pre-backfill-{ts}")
            source_sha = _sha256_file(mirror_path)
            try:
                shutil.copy2(mirror_path, bak)
                if _sha256_file(bak) != source_sha:
                    raise IOError(f"backup byte-mismatch for {bak}")
            except Exception as exc:  # noqa: BLE001 -- a failed backup is a BLOCK
                report.refusals.append(f"backup failed, refusing to write: {exc}")
                return report
            report.backup = str(bak)
            report.backup_sha256 = source_sha

        # -- write through the store's own add path ------------------------
        for memory in writable:
            # Second belt on idempotency. The diff above is a point-in-time
            # reading; this asks the store itself, per record, immediately before
            # appending. An id that is already present must never be appended
            # again -- that append IS the incident.
            if mirror_store.get(memory.id) is not None:
                report.skipped_already_present += 1
                continue
            mirror_store.add(memory)
            report.written += 1
        mirror_store.flush()
        mirror_store._shutdown_flush()  # stop the daemon flusher and drain

        # -- verify by COLD LOAD, with rollback ----------------------------
        report.verify = _verify_cold(snapshot, storage_dir, diff, report.written)
        if report.verify.get("problems"):
            if report.backup:
                shutil.copy2(report.backup, mirror_path)
                report.rolled_back = True
            report.refusals.extend(report.verify["problems"])
            report.refusals.append(
                "post-write verification failed; "
                + ("restored the pre-backfill backup" if report.rolled_back
                   else "NO BACKUP EXISTED to restore -- inspect the mirror by hand")
            )
        return report
    finally:
        if mirror_store is not None:
            try:
                mirror_store._shutdown_flush()
            except Exception as exc:  # noqa: BLE001 -- teardown must not mask the report
                logger.warning("mirror flusher shutdown failed: %s", exc)


def _verify_cold(
    snapshot: Path, storage_dir: Path, before: DiffReport, written: int
) -> Dict[str, Any]:
    """Re-open the mirror in a FRESH store and re-measure. Problems are fatal.

    The cold load is the point. The live handle that just wrote these records
    already holds them in ``_memories`` and will report them present whether or
    not the bytes on disk can be read back -- which is exactly how a store can be
    broken for two days while every in-process check reads green. This asks the
    loader, from cold, the same question the next Houdini launch will ask.
    """
    out: Dict[str, Any] = {"problems": []}
    try:
        fresh = open_mirror(storage_dir)
    except Exception as exc:  # noqa: BLE001
        out["problems"].append(f"cold re-open of the mirror failed: {exc}")
        return out
    try:
        out["cold_degraded"] = bool(getattr(fresh, "_degraded_load", False))
        out["cold_degraded_reason"] = getattr(fresh, "_degraded_reason", "")
        out["cold_records"] = len(fresh.all())
        out["expected_records"] = before.mirror_records + written
        after_ids = {m.id for m in fresh.all()}
        primary_ids = set(read_primary(snapshot)[0])
        out["only_in_primary_after"] = len(primary_ids - after_ids)
        out["only_in_mirror_after"] = len(after_ids - primary_ids)

        if out["cold_degraded"]:
            out["problems"].append(
                "the mirror loads DEGRADED after the backfill: "
                + (out["cold_degraded_reason"] or "no reason recorded")
            )
        if out["cold_records"] != out["expected_records"]:
            out["problems"].append(
                "mirror holds %d records, expected %d (%d before + %d written)"
                % (out["cold_records"], out["expected_records"],
                   before.mirror_records, written)
            )
        if out["only_in_primary_after"] != 0:
            out["problems"].append(
                "%d record(s) still exist only in the primary after the backfill"
                % out["only_in_primary_after"]
            )
        if out["only_in_mirror_after"] != len(before.only_in_mirror):
            out["problems"].append(
                "mirror-only count moved (%d -> %d); this tool writes one "
                "direction and must not have changed it"
                % (len(before.only_in_mirror), out["only_in_mirror_after"])
            )
    finally:
        try:
            fresh._shutdown_flush()
        except Exception:  # noqa: BLE001
            pass
    return out


# ---------------------------------------------------------------------------
# rendering + CLI
# ---------------------------------------------------------------------------

def render_report(report: BackfillReport) -> str:
    """The full account, both directions, before anyone passes ``--apply``."""
    lines: List[str] = []
    add = lines.append
    add("=" * 72)
    add("MONETA -> JSONL BACKFILL -- %s" % ("DRY RUN" if report.dry_run else "APPLY"))
    add("=" * 72)
    add("storage dir         : %s" % report.storage_dir)

    d = report.diff
    if d:
        add("primary (snapshot)  : %s" % d.snapshot)
        add("mirror  (jsonl)     : %s" % d.mirror)
        add("")
        add("DIVERGENCE (measured now, both directions)")
        add("  primary rows      : %d  (%d distinct ids, %d unreadable rows)"
            % (d.primary_rows, d.primary_distinct_ids, d.primary_unreadable_rows))
        add("  mirror records    : %d" % d.mirror_records)
        add("  intersection      : %d" % d.intersection)
        add("  only in PRIMARY   : %d   <- this tool writes these" % len(d.only_in_primary))
        add("      inside outage window : %d" % d.only_in_primary_inside_outage)
        add("      before outage        : %d" % d.only_in_primary_before_outage)
        add("      after outage         : %d" % d.only_in_primary_after_outage)
        if d.only_in_primary_by_type:
            add("      by type              : %s" % ", ".join(
                "%s=%d" % kv for kv in sorted(d.only_in_primary_by_type.items())))
        add("  only in MIRROR    : %d   <- reported, NOT written by this tool"
            % len(d.only_in_mirror))
        for mid in d.only_in_mirror[:20]:
            note = ""
            if mid == NOTABLE_MIRROR_ONLY_ID:
                note = "   <- the decision binding 'Create a Solaris Network' to the v4 recipe"
            add("      %s%s" % (mid, note))
        if len(d.only_in_mirror) > 20:
            add("      ... and %d more" % (len(d.only_in_mirror) - 20))
        if d.only_in_mirror:
            add("      depositing these into the primary needs "
                "add_durable_if_absent + the Moneta URI lock -- out of this "
                "tool's lane, named so it is not forgotten")

    pre = report.preconditions or {}
    add("")
    add("PRECONDITIONS")
    add("  primary duplicate ids : %s" % (
        ", ".join(pre.get("primary_duplicate_ids") or []) or "none  (ok)"))
    add("  mirror degraded       : %s" % pre.get("mirror_degraded", "?"))
    if pre.get("mirror_degraded_reason"):
        add("      reason            : %s" % pre["mirror_degraded_reason"])

    live = report.liveness or {}
    add("  houdini processes     : %s" % (
        ", ".join(live.get("processes") or []) or "none found"))
    if live.get("process_probe_error"):
        add("      probe error       : %s" % live["process_probe_error"])
    add("  snapshot last touched : %s" % _age(live.get("snapshot_age_seconds")))
    add("  mirror last touched   : %s" % _age(live.get("mirror_age_seconds")))
    add("  liveness verdict      : %s" % ("BLOCKED" if live.get("blocking") else "clear"))

    add("")
    add("PLAN")
    add("  would write         : %d" % report.would_write)
    if report.skipped_not_roundtrippable:
        add("  NOT round-trippable : %d  %s" % (
            len(report.skipped_not_roundtrippable),
            ", ".join(report.skipped_not_roundtrippable[:10])))
        add("      these would be written LOSSY, so they are skipped; the "
            "Memory model and the stored payload disagree")
    if not report.dry_run:
        add("  written             : %d" % report.written)
        add("  skipped (present)   : %d" % report.skipped_already_present)
    if report.backup:
        add("  backup              : %s" % report.backup)
        add("      sha256 (verified): %s" % report.backup_sha256)

    if report.verify:
        add("")
        add("VERIFY (fresh cold load of the mirror)")
        for key in ("cold_degraded", "cold_records", "expected_records",
                    "only_in_primary_after", "only_in_mirror_after"):
            if key in report.verify:
                add("  %-22s: %s" % (key, report.verify[key]))

    add("")
    if report.refusals:
        add("RESULT              : REFUSED -- nothing was written"
            if not report.written else
            "RESULT              : FAILED after writing")
        if report.rolled_back:
            add("  rolled back to the pre-backfill backup")
        for r in report.refusals:
            add("  - %s" % r)
    elif report.dry_run:
        add("RESULT              : DRY RUN -- re-run with --apply to write")
    elif report.written:
        add("RESULT              : WROTE %d record(s), verified by cold load"
            % report.written)
    else:
        add("RESULT              : nothing to write -- the stores already agree")
        add("  (a second run reaching here is the idempotency guarantee working)")
    add("=" * 72)
    return "\n".join(lines)


def _age(seconds) -> str:
    return "unknown" if seconds is None else "%ss ago" % seconds


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(
        description="Backfill Moneta-primary-only memories into the JSONL mirror "
                    "(incident B5). Dry run unless --apply. Run primary_repair FIRST.",
    )
    ap.add_argument("storage_dir", help="the .synapse storage dir")
    ap.add_argument("--snapshot", help="path to snapshot.json (default: "
                                       "<storage_dir>/.moneta/snapshot.json)")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default is a dry run)")
    ap.add_argument("--no-backup", action="store_true",
                    help="skip backing up memory.jsonl (not recommended -- the "
                         "backup is what a failed verification rolls back to)")
    ap.add_argument("--allow-live-houdini", action="store_true",
                    help="override the liveness refusal -- a live save() would "
                         "delete every line this tool appends")
    ap.add_argument("--quiet-seconds", type=float, default=DEFAULT_QUIET_SECONDS,
                    help="how stale the store mtimes must be to count as idle")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    report = backfill_from_moneta(
        args.storage_dir,
        dry_run=not args.apply,
        backup=not args.no_backup,
        allow_live_houdini=args.allow_live_houdini,
        quiet_seconds=args.quiet_seconds,
        snapshot_path=args.snapshot,
    )

    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(render_report(report) + "\n")

    if report.refusals:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
