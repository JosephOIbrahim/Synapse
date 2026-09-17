"""primary_repair.py -- de-duplicate the Moneta PRIMARY store (incident B2).

Why this file exists
--------------------
On 2026-09-15 15:09 local a ``MemoryStore`` went DEGRADED and refused **every**
write for ~2 days, until 2026-09-17 15:53. The trigger was one bad line:
``MemoryStore.add()`` appended a second JSONL line for an id that already
existed, with different content. ``MemoryStore._load`` (``store.py:355-362``)
raises ``conflicting duplicate memory identity`` on the second differing
canonical form, and ``store.py:396-401`` degrades the whole store on a
non-empty unreadable list -- ``len == 1`` qualifies. One line was enough.

That incident was repaired on 2026-09-17 by
``harness/notes/store-incident-2026-09-17/repair.py``, which this module
deliberately mirrors. **But that repair fixed the JSONL MIRROR, not the
PRIMARY.** Moneta is the primary substrate; the JSONL store is a dual-write
safety net (``moneta_store.py:_dual_write_jsonl``) that no read path consults.
All five conflicting ids are still resident, twice each, in
``<storage_dir>/.moneta/snapshot.json``::

    mem_596cf755cfbf  mem_d8486c1c0ee0  mem_ae38a9b2736d
    mem_adf58a52df9a  mem_d42816c8963c

Re-measured by the 2026-09-17 audit at snapshot mtime 16:16 -- each returns 2
rows. Three consequences chain off that, all of them live today:

(a) ``memory_lifecycle._records()`` raises ``"Source memory has duplicate
    identities"`` (``memory_lifecycle.py:174-175``) because it compares
    ``len(ids) != len(set(ids))``. The save-a-scene memory transition is
    therefore **broken right now**, and the exception is swallowed at
    ``memory_lifecycle.py:116-121`` into an attribute nothing reads. The artist
    saves, believes memory followed, and it did not.
(b) ``MonetaBackedStore.add_durable_if_absent`` raises on those five ids
    (``moneta_store.py:665-670``): its guard is ``len(matches) != 1``, so a
    second copy trips it even when both copies are byte-identical.
(c) Any Moneta -> JSONL backfill would re-emit the conflicting pair into the
    mirror and **re-degrade it on the next load** -- reproducing the original
    outage with the tool that was meant to heal it.

Order of operations
-------------------
Because of (c) this module MUST run, and be verified, **before**
:mod:`synapse.memory.backfill_from_moneta`. That is not advice: the backfill
imports :func:`scan_snapshot` from here and refuses to write while any
duplicate id remains in the primary.

Two ways this differs from the JSONL repair, both load-bearing
--------------------------------------------------------------
1. **Exact duplicates are fatal here, and were harmless there.** ``repair.py``
   skipped ids whose copies were byte-identical, with the comment "identical
   dupes: loader already tolerates" -- true of ``MemoryStore._load``, which
   ``continue``\\s on a matching canonical. It is NOT true of either primary
   consumer: (a) is content-blind and (b) fails on ``len(matches) != 1``. So
   **every** id with more than one row is a repair target here.
2. **The selection rule must match the mirror's, byte for byte.** The JSONL
   repair kept the RICHER copy, deliberately not last-write-wins -- in all five
   cases the later line was the metadata-stripped one, and keeping it would
   have destroyed 26 tags that feed retrieval. If this repair kept a different
   copy, the two stores would then disagree on the content of the same id, and
   ``_dual_write_jsonl(only_if_missing=True)`` re-appends whenever
   ``existing.to_json() != memory.to_json()`` (``moneta_store.py:768-780``) --
   which is precisely the poisoning case. Disagreement between the stores is
   itself a re-poisoning mechanism, so :func:`repair_primary` cross-checks the
   record it intends to keep against the record the mirror kept, and refuses on
   disagreement.

Safety contract
---------------
* **Dry run is the default.** Nothing is written without ``--apply``.
* **Never executed on import.** Everything is behind ``main()`` / ``__main__``.
* **Refuses to run while Houdini is live.** ``MonetaBackedStore.save()`` rewrites
  ``snapshot.json`` in full on every ``add()`` (``moneta_store.py:977-991``, and
  ``add()`` now saves per deposit), so a repair written under a live session is
  overwritten within one memory write -- or worse, interleaves with one.
  Two independent probes, because either alone can be blind: a process probe
  (psutil, else ``tasklist``/``pgrep``) and a snapshot-mtime freshness probe
  that needs no process table at all. Override is explicit: ``--allow-live-houdini``.
* **Backup before any write, verified by hash.** The copy is re-hashed and
  compared to the source; a mismatch is a BLOCK, not a warning.
* **Verify before install.** The repaired rows are re-read *from the tmp file on
  disk* and replayed against every predicate the primary's consumers apply. If
  any fails, the tmp file is discarded and the original is untouched -- the same
  refuse-to-install posture as ``repair.py``.
* **Additive-safe.** Only whole duplicate rows are dropped. Every surviving row
  is the original object, unmodified; no payload is re-serialized, no vector is
  recomputed. Top-level snapshot keys other than ``rows`` are preserved as-is.

CLI::

    python -m synapse.memory.primary_repair <storage_dir>            # dry run (default)
    python -m synapse.memory.primary_repair <storage_dir> --apply    # real repair
    python -m synapse.memory.primary_repair <storage_dir> --json     # machine-readable

``<storage_dir>`` is the ``.synapse`` directory -- the snapshot is resolved as
``<storage_dir>/.moneta/snapshot.json``. Pass ``--snapshot`` to point at one
directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# The five ids the 2026-09-17 audit measured as resident twice in the primary.
# This list is EVIDENCE, never the filter: :func:`scan_snapshot` finds duplicates
# structurally, so an id that was poisoned after the audit is still caught. The
# list exists so the report can say whether the known five were among the hits --
# a run that repairs zero of them is a signal that something moved underneath us.
KNOWN_DUPLICATE_IDS = (
    "mem_596cf755cfbf",
    "mem_d8486c1c0ee0",
    "mem_ae38a9b2736d",
    "mem_adf58a52df9a",
    "mem_d42816c8963c",
)

# Keys Moneta requires on every snapshot row. Mirrors
# ``MonetaBackedStore._SNAPSHOT_REQUIRED_KEYS`` (``moneta_store.py:372-375``);
# duplicated rather than imported so this recovery tool has no import-time
# dependency on a module that builds embedders and touches the Moneta runtime.
SNAPSHOT_REQUIRED_KEYS = (
    "entity_id", "payload", "semantic_vector", "utility",
    "attended_count", "protected_floor", "last_evaluated", "state",
)

# A snapshot touched more recently than this is treated as live. Moneta saves on
# every deposit and the store was measured growing ~111 records/day, so a gap of
# a couple of minutes is a strong "nothing is writing" signal without being so
# wide that a genuinely idle machine can never pass.
DEFAULT_QUIET_SECONDS = 120.0


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    """sha256 of a file, streamed. Mirrors ``migrate.py``'s backup verification:
    a backup is only a backup once its bytes have been proven equal."""
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(payload_obj: Dict[str, Any]) -> str:
    """The exact canonical form ``MemoryStore._load`` compares identities with.

    ``store.py:359`` computes ``json.dumps(data, sort_keys=True)`` and raises
    when a repeated id's canonical differs. Using the identical expression here
    means "differing copy" means the same thing in both stores -- if this used a
    looser notion, the repair could keep two copies the mirror considers a
    conflict, and the mirror would degrade again on the next load.
    """
    return json.dumps(payload_obj, sort_keys=True)


def richness(payload_obj: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
    """Higher = more metadata survived. Prefer the record that kept its tags.

    Copied deliberately, field for field and in the same order, from
    ``harness/notes/store-incident-2026-09-17/repair.py``. Do not "improve" it:
    its only job is to reproduce the choice the mirror already made, so the two
    stores agree on which copy of each id survived. See the module docstring,
    point 2 -- a divergence here is a re-poisoning mechanism, not a style
    preference.

    In all five measured cases the *later* copy is the stripped one, so
    last-write-wins -- the natural append-log instinct -- would have destroyed
    26 tags that feed the retrieval index.
    """
    return (
        len(payload_obj.get("tags") or []),
        1 if (payload_obj.get("hip_file") or "") else 0,
        0 if (payload_obj.get("source") or "") == "auto" else 1,
        1 if payload_obj.get("frame") is not None else 0,
        1 if (payload_obj.get("hip_version") or 0) else 0,
    )


def live_houdini_processes() -> Tuple[List[str], Optional[str]]:
    """Best-effort probe for a running Houdini. Returns ``(hits, probe_error)``.

    ``probe_error`` is non-None when the probe could not be *run* -- which is a
    different verdict from "no Houdini found" and is treated as such by
    :func:`repair_primary`: an unusable probe does not get to grant permission.
    The failure this prevents is a repair written into a snapshot that a live
    ``MonetaBackedStore.save()`` overwrites moments later, leaving the operator
    believing the primary is clean when it is not.

    psutil is optional in this tree (``panel/render_preflight.py:41-48`` guards
    it the same way), so there is a platform fallback.
    """
    names = ("houdini", "houdinifx", "houdinicore", "hindie", "hython", "houdini_bin")
    hits: List[str] = []
    try:
        import psutil  # type: ignore[import-untyped]
    except Exception:
        psutil = None  # type: ignore[assignment]

    if psutil is not None:
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                raw = (proc.info.get("name") or "")
                stem = raw.lower().rsplit(".", 1)[0]
                if stem in names:
                    hits.append(f"pid {proc.info.get('pid')} {raw}")
            return hits, None
        except Exception as exc:  # noqa: BLE001 -- fall through to the CLI probe
            logger.debug("psutil process probe failed (%s); trying platform probe", exc)

    try:
        if platform.system() == "Windows":
            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=30, check=False,
            ).stdout
            for line in out.splitlines():
                first = line.split('","')[0].lstrip('"').strip()
                if first.lower().rsplit(".", 1)[0] in names:
                    hits.append(first)
        else:
            out = subprocess.run(
                ["ps", "-eo", "pid=,comm="],
                capture_output=True, text=True, timeout=30, check=False,
            ).stdout
            for line in out.splitlines():
                parts = line.split(None, 1)
                if len(parts) == 2 and Path(parts[1].strip()).name.lower() in names:
                    hits.append(line.strip())
        return hits, None
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"


def seconds_since_touched(path: Path) -> Optional[float]:
    """Age of the snapshot's mtime in seconds, or None if it cannot be read.

    The second liveness probe, and the one that needs no process table: under
    the production env every ``add()`` calls ``save()``, which rewrites this file
    whole. A snapshot that moved seconds ago means something owns it, whatever
    the process list says -- including a hython session, a second SYNAPSE
    process, or a store object in a host this probe cannot see.
    """
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# report types
# ---------------------------------------------------------------------------

@dataclass
class DuplicateId:
    """One memory id that occupies more than one snapshot row."""

    memory_id: str
    row_indices: List[int] = field(default_factory=list)
    entity_ids: List[str] = field(default_factory=list)
    distinct_payloads: int = 0
    keep_index: int = -1
    keep_entity_id: str = ""
    keep_tags: int = 0
    drop_indices: List[int] = field(default_factory=list)
    drop_entity_ids: List[str] = field(default_factory=list)
    drop_tags: List[int] = field(default_factory=list)
    known: bool = False  # was this id one of the five the audit measured?

    @property
    def identical(self) -> bool:
        """True when every copy is byte-identical. Harmless to
        ``MemoryStore._load``; still fatal to both primary consumers."""
        return self.distinct_payloads <= 1

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["identical"] = self.identical
        return d


@dataclass
class RepairReport:
    """Everything the operator needs to decide whether to pass ``--apply``."""

    snapshot: str = ""
    dry_run: bool = True
    rows_total: int = 0
    rows_unreadable: int = 0
    unreadable_detail: List[str] = field(default_factory=list)
    distinct_ids: int = 0
    duplicates: List[DuplicateId] = field(default_factory=list)
    rows_to_drop: int = 0
    # The audit's five ids, split three ways rather than two. "Not duplicated"
    # and "not in this snapshot at all" look identical in a pass/fail column and
    # mean opposite things: the first is the repair landing, the second is the
    # tool pointed at the wrong store. Collapsing them would let a run against an
    # empty store report the incident as resolved.
    known_ids_duplicated: List[str] = field(default_factory=list)
    known_ids_single: List[str] = field(default_factory=list)
    known_ids_absent: List[str] = field(default_factory=list)
    liveness: Dict[str, Any] = field(default_factory=dict)
    mirror_crosscheck: Dict[str, Any] = field(default_factory=dict)
    backup: Optional[str] = None
    backup_sha256: Optional[str] = None
    backup_extra: List[str] = field(default_factory=list)
    verify: Dict[str, Any] = field(default_factory=dict)
    applied: bool = False
    refusals: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.refusals

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["duplicates"] = [x.to_dict() for x in self.duplicates]
        d["ok"] = self.ok
        return d


# ---------------------------------------------------------------------------
# scan / plan
# ---------------------------------------------------------------------------

def load_snapshot(snapshot_path: Path) -> Dict[str, Any]:
    """Read ``snapshot.json`` as plain JSON. Read-only, and deliberately NOT via
    ``MonetaBackedStore.from_storage_dir``.

    That factory looks like the obvious way in and is the wrong one for a
    recovery tool: it takes Moneta's single-owner URI lock (so it cannot run
    beside a live seat at all), and on the way in it can *rewrite this very
    file* -- ``_reconcile_snapshot_dim`` re-embeds and atomically replaces the
    snapshot when the persisted vector dim differs from the live embedder's
    (``moneta_store.py:538-646``), and ``_quarantine_if_corrupt`` renames it
    aside (``:413-443``). A tool whose job is to repair the primary must never
    mutate it as a side effect of reading it.
    """
    with open(snapshot_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError(
            f"{snapshot_path} is not a Moneta snapshot (expected a dict with a "
            f"'rows' list)"
        )
    return data


def scan_snapshot(snapshot_path: Path) -> RepairReport:
    """Group snapshot rows by SYNAPSE memory id and plan the de-duplication.

    Shared with :mod:`synapse.memory.backfill_from_moneta`, which calls this to
    enforce precondition (c) -- it refuses to write while this reports any
    duplicate. Keeping one implementation means the ordering contract between
    the two tools is executable, not a comment somebody can forget.
    """
    report = RepairReport(snapshot=str(snapshot_path))
    data = load_snapshot(snapshot_path)
    rows = data["rows"]
    report.rows_total = len(rows)

    # (memory_id -> [(row_index, canonical_payload, payload_obj, entity_id)])
    by_id: Dict[str, List[Tuple[int, str, Dict[str, Any], str]]] = {}
    for idx, row in enumerate(rows):
        entity_id = str(row.get("entity_id", "")) if isinstance(row, dict) else ""
        try:
            if not isinstance(row, dict):
                raise ValueError("row is not an object")
            missing = [k for k in SNAPSHOT_REQUIRED_KEYS if k not in row]
            if missing:
                raise ValueError(f"row missing required keys: {missing}")
            payload_obj = json.loads(row["payload"])
            if not isinstance(payload_obj, dict) or not payload_obj.get("id"):
                raise ValueError("payload carries no memory identity")
            mid = payload_obj["id"]
        except Exception as exc:  # noqa: BLE001
            # An unreadable row is reported, never silently dropped. It is not a
            # duplicate we can reason about, so it is left exactly where it is.
            report.rows_unreadable += 1
            if len(report.unreadable_detail) < 10:
                report.unreadable_detail.append(
                    f"row {idx} (entity {entity_id or '<unknown>'}): "
                    f"{type(exc).__name__}: {exc}"
                )
            continue
        by_id.setdefault(mid, []).append(
            (idx, canonical(payload_obj), payload_obj, entity_id)
        )

    report.distinct_ids = len(by_id)

    for mid, group in by_id.items():
        if len(group) <= 1:
            continue
        # Same key as repair.py: richest first, then the EARLIER row on a tie
        # (``-index`` under ``max``). Identical copies therefore keep the first.
        best = max(group, key=lambda g: (richness(g[2]), -g[0]))
        dup = DuplicateId(
            memory_id=mid,
            row_indices=[g[0] for g in group],
            entity_ids=[g[3] for g in group],
            distinct_payloads=len({g[1] for g in group}),
            keep_index=best[0],
            keep_entity_id=best[3],
            keep_tags=len(best[2].get("tags") or []),
            known=mid in KNOWN_DUPLICATE_IDS,
        )
        for g in group:
            if g[0] != best[0]:
                dup.drop_indices.append(g[0])
                dup.drop_entity_ids.append(g[3])
                dup.drop_tags.append(len(g[2].get("tags") or []))
        report.duplicates.append(dup)

    report.duplicates.sort(key=lambda d: d.row_indices[0])
    report.rows_to_drop = sum(len(d.drop_indices) for d in report.duplicates)
    for known in KNOWN_DUPLICATE_IDS:
        rows_for_id = len(by_id.get(known, ()))
        if rows_for_id > 1:
            report.known_ids_duplicated.append(known)
        elif rows_for_id == 1:
            report.known_ids_single.append(known)
        else:
            report.known_ids_absent.append(known)
    return report


# ---------------------------------------------------------------------------
# verification predicates
# ---------------------------------------------------------------------------

def verify_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Replay every predicate the primary's consumers apply, over ``rows``.

    Run against the bytes that are about to be installed, read back from disk --
    not against the in-memory list we built -- so what is verified is what lands.
    ``repair.py`` established this order (write tmp, verify tmp, replace) and the
    reason is that a serialization bug between "planned" and "written" is exactly
    the class of fault a verify-the-plan check cannot see.

    Replays, in order:
      * ``MonetaBackedStore._quarantine_if_corrupt`` -- every row carries the
        required keys, else Moneta renames the snapshot aside on next startup
        and the seat starts EMPTY (``moneta_store.py:413-443``).
      * ``MonetaBackedStore._iter_memories(strict=True)`` -- the payload identity
        and type validation ``add_durable_if_absent`` reads through
        (``moneta_store.py:829-841``).
      * ``memory_lifecycle._records()`` -- ``len(ids) != len(set(ids))``, the
        content-blind check that breaks the save transition (``:174-175``).
      * ``add_durable_if_absent`` -- ``len(matches) != 1`` per id
        (``moneta_store.py:665-670``). Equivalent to the previous check, asserted
        separately because they are separate consumers with separate call sites.
    """
    out: Dict[str, Any] = {
        "rows": len(rows),
        "rows_missing_keys": 0,
        "payloads_unreadable": 0,
        "payloads_invalid": 0,
        "distinct_ids": 0,
        "duplicate_ids_remaining": [],
        "problems": [],
    }
    ids: List[str] = []
    strict_required = {"id", "created_at", "content", "memory_type", "tags", "source"}

    for idx, row in enumerate(rows):
        if not isinstance(row, dict) or not all(k in row for k in SNAPSHOT_REQUIRED_KEYS):
            out["rows_missing_keys"] += 1
            if len(out["problems"]) < 10:
                out["problems"].append(f"row {idx}: missing required snapshot keys")
            continue
        try:
            payload = json.loads(row["payload"])
        except Exception as exc:  # noqa: BLE001
            out["payloads_unreadable"] += 1
            if len(out["problems"]) < 10:
                out["problems"].append(f"row {idx}: payload unreadable ({exc})")
            continue
        try:
            if not isinstance(payload, dict) or not strict_required <= set(payload):
                raise ValueError("Incomplete memory payload")
            if any(not isinstance(payload[k], str) for k in strict_required - {"tags"}):
                raise ValueError("Invalid memory field type")
            if not payload["id"] or not payload["created_at"]:
                raise ValueError("Missing stored memory identity or timestamp")
            if type(payload["tags"]) is not list or any(
                type(t) is not str for t in payload["tags"]
            ):
                raise ValueError("Invalid stored memory tags")
        except Exception as exc:  # noqa: BLE001
            # Strict validation failing is NOT automatically a repair failure --
            # a row that was already invalid before we touched it stays invalid,
            # and dropping it is not this tool's job. It is counted and surfaced
            # so the operator sees it; the install gate below only blocks on
            # conditions the repair itself is responsible for.
            out["payloads_invalid"] += 1
            if len(out["problems"]) < 10:
                out["problems"].append(f"row {idx}: {type(exc).__name__}: {exc}")
        ids.append(payload.get("id", ""))

    out["distinct_ids"] = len(set(ids))
    if len(ids) != len(set(ids)):
        seen: Dict[str, int] = {}
        for i in ids:
            seen[i] = seen.get(i, 0) + 1
        out["duplicate_ids_remaining"] = sorted(k for k, v in seen.items() if v > 1)
    return out


def _dangling_entity_references(
    kept_rows: List[Dict[str, Any]], dropped_entity_ids: List[str]
) -> List[str]:
    """Any surviving row that still names an entity we are about to remove.

    Moneta's consolidation records ``consolidated_into`` against an entity, so a
    row pointing at a dropped entity would become a reference to nothing. The
    2026-09-17 audit measured all 1116 snapshot rows carrying ``state=0`` and
    ``consolidated_into=None``, so this is expected to find nothing TODAY -- it
    is here because that is a measurement of one moment, not a property of the
    format, and a prune between then and the repair would change it. A hit is a
    refusal: silently orphaning a reference is how a "clean" repair becomes the
    next incident.
    """
    if not dropped_entity_ids:
        return []
    targets = {e for e in dropped_entity_ids if e}
    if not targets:
        return []
    hits: List[str] = []
    for idx, row in enumerate(kept_rows):
        try:
            blob = json.dumps(row)
        except Exception:  # noqa: BLE001 -- unserializable row cannot be scanned
            continue
        for target in targets:
            if target in blob:
                hits.append(f"row {idx} still references dropped entity {target}")
    return hits


def crosscheck_mirror(
    report: RepairReport, snapshot_path: Path, mirror_path: Optional[Path]
) -> Dict[str, Any]:
    """Compare the copy we intend to keep against the copy the mirror kept.

    The mirror was repaired first, on 2026-09-17, and kept the richer copy of
    each of the five ids. If this repair keeps a different copy the two stores
    disagree on the content of one id, and ``_dual_write_jsonl`` re-appends on
    exactly that condition (``existing.to_json() != memory.to_json()``,
    ``moneta_store.py:776-777``) -- re-planting the poison line in the mirror.
    So a disagreement here is a refusal, not a note.

    A mirror that is absent, encrypted with an unavailable key, or degraded is
    reported as ``"unavailable"`` and does not block: the repair must be possible
    on a seat where the mirror is gone. Unavailable is recorded honestly rather
    than counted as agreement.
    """
    out: Dict[str, Any] = {"status": "unavailable", "checked": 0,
                           "agreed": 0, "disagreed": [], "absent_from_mirror": []}
    if mirror_path is None:
        mirror_path = snapshot_path.parent.parent / "memory.jsonl"
    out["mirror"] = str(mirror_path)
    if not mirror_path.exists():
        out["reason"] = "mirror file not present"
        return out

    try:
        from .store import _get_crypto
        crypto = _get_crypto()
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"crypto unavailable ({type(exc).__name__}: {exc})"
        return out

    wanted = {d.memory_id for d in report.duplicates}
    if not wanted:
        out["status"] = "not_needed"
        out["reason"] = "no duplicates to cross-check"
        return out

    mirror_canon: Dict[str, str] = {}
    try:
        with open(mirror_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    if crypto:
                        line = crypto.decrypt_line(line)
                    obj = json.loads(line)
                    mid = obj.get("id")
                    if mid in wanted:
                        # The mirror is append-only and was repaired to hold one
                        # line per id; if a later line ever appears, the LAST one
                        # is not what the loader keeps -- ``_load`` keeps the
                        # FIRST occurrence (``store.py:356-362``). Mirror that.
                        mirror_canon.setdefault(mid, canonical(obj))
                except Exception:  # noqa: BLE001 -- one bad line must not blind the check
                    continue
    except OSError as exc:
        out["reason"] = f"mirror unreadable ({exc})"
        return out

    data = load_snapshot(snapshot_path)
    rows = data["rows"]
    for dup in report.duplicates:
        keep_payload = json.loads(rows[dup.keep_index]["payload"])
        ours = canonical(keep_payload)
        theirs = mirror_canon.get(dup.memory_id)
        if theirs is None:
            out["absent_from_mirror"].append(dup.memory_id)
            continue
        out["checked"] += 1
        if ours == theirs:
            out["agreed"] += 1
        else:
            out["disagreed"].append(dup.memory_id)

    out["status"] = "disagreement" if out["disagreed"] else "ok"
    return out


# ---------------------------------------------------------------------------
# the repair
# ---------------------------------------------------------------------------

def repair_primary(
    snapshot_path,
    *,
    apply: bool = False,
    allow_live_houdini: bool = False,
    mirror_crosscheck: bool = True,
    mirror_path=None,
    backup_dir=None,
    quiet_seconds: float = DEFAULT_QUIET_SECONDS,
) -> RepairReport:
    """Scan, plan, and (only with ``apply=True``) install the de-duplication.

    Returns a :class:`RepairReport` in every case. ``report.refusals`` non-empty
    means nothing was written and why; ``report.applied`` True means the
    repaired snapshot is installed and was verified from disk first.
    """
    snapshot_path = Path(snapshot_path)
    if not snapshot_path.exists():
        r = RepairReport(snapshot=str(snapshot_path), dry_run=not apply)
        r.refusals.append(f"snapshot not found: {snapshot_path}")
        return r

    report = scan_snapshot(snapshot_path)
    report.dry_run = not apply

    # -- liveness ---------------------------------------------------------
    hits, probe_error = live_houdini_processes()
    age = seconds_since_touched(snapshot_path)
    report.liveness = {
        "processes": hits,
        "process_probe_error": probe_error,
        "snapshot_age_seconds": None if age is None else round(age, 1),
        "quiet_threshold_seconds": quiet_seconds,
        "override": allow_live_houdini,
    }
    blocking: List[str] = []
    if hits:
        blocking.append(f"Houdini appears to be running: {', '.join(hits[:5])}")
    if probe_error:
        # An unusable probe cannot grant permission. Treated as blocking so the
        # operator makes the call explicitly rather than inheriting a silent pass.
        blocking.append(f"could not determine whether Houdini is running ({probe_error})")
    if age is not None and age < quiet_seconds:
        blocking.append(
            f"snapshot was modified {age:.0f}s ago (< {quiet_seconds:.0f}s): "
            f"something is still writing the primary"
        )
    report.liveness["blocking"] = blocking
    if blocking and not allow_live_houdini:
        report.refusals.extend(blocking)
        report.refusals.append(
            "close Houdini and re-run, or pass --allow-live-houdini if you are "
            "certain nothing owns this snapshot (a live save() rewrites it whole)"
        )

    # -- mirror agreement -------------------------------------------------
    if mirror_crosscheck:
        report.mirror_crosscheck = crosscheck_mirror(
            report, snapshot_path, Path(mirror_path) if mirror_path else None
        )
        if report.mirror_crosscheck.get("status") == "disagreement":
            report.refusals.append(
                "the copy this repair would keep differs from the copy the JSONL "
                "mirror kept for: "
                + ", ".join(report.mirror_crosscheck["disagreed"])
                + " -- installing it would make the two stores disagree, and "
                "_dual_write_jsonl re-appends on exactly that condition"
            )
    else:
        report.mirror_crosscheck = {"status": "skipped",
                                    "reason": "--no-mirror-crosscheck"}

    if not report.duplicates:
        # Not a refusal: a clean primary is the success condition this tool
        # exists to reach, and the backfill's precondition check calls the same
        # scan to confirm it.
        return report

    if not apply:
        return report
    if report.refusals:
        return report

    # -- build the repaired rows -----------------------------------------
    data = load_snapshot(snapshot_path)
    rows = data["rows"]
    drop = {i for d in report.duplicates for i in d.drop_indices}
    dropped_entities = [e for d in report.duplicates for e in d.drop_entity_ids]
    kept_rows = [row for idx, row in enumerate(rows) if idx not in drop]

    dangling = _dangling_entity_references(kept_rows, dropped_entities)
    if dangling:
        report.refusals.extend(dangling)
        report.refusals.append(
            "a surviving row still references an entity this repair would remove; "
            "refusing rather than orphaning it"
        )
        return report

    # -- backup, verified by hash ----------------------------------------
    ts = int(time.time())
    source_sha = _sha256_file(snapshot_path)
    backup_targets = [snapshot_path.with_name(f"{snapshot_path.name}.pre-primary-repair-{ts}")]
    if backup_dir:
        bd = Path(backup_dir)
        bd.mkdir(parents=True, exist_ok=True)
        backup_targets.append(bd / f"snapshot.json.pre-primary-repair-{ts}")
    try:
        for target in backup_targets:
            shutil.copy2(snapshot_path, target)
            if _sha256_file(target) != source_sha:
                raise IOError(f"backup byte-mismatch for {target}")
    except Exception as exc:  # noqa: BLE001 -- a failed backup is a BLOCK
        report.refusals.append(f"backup failed, refusing to repair: {exc}")
        return report
    report.backup = str(backup_targets[0])
    report.backup_sha256 = source_sha
    report.backup_extra = [str(t) for t in backup_targets[1:]]

    # -- write tmp, verify tmp FROM DISK, then install --------------------
    data["rows"] = kept_rows
    tmp_path = snapshot_path.with_name(snapshot_path.name + ".repairtmp")
    try:
        # tmp + fsync + os.replace, mirroring ``_reconcile_snapshot_dim``'s
        # atomic rewrite (``moneta_store.py:625-646``): a crash mid-write leaves
        # the original snapshot intact.
        with open(tmp_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)
            fp.flush()
            os.fsync(fp.fileno())

        reread = load_snapshot(tmp_path)
        verify = verify_rows(reread["rows"])
        verify["expected_rows"] = len(rows) - len(drop)
        verify["rows_dropped"] = len(drop)
        report.verify = verify

        install_blockers: List[str] = []
        if verify["rows"] != verify["expected_rows"]:
            install_blockers.append(
                f"repaired file has {verify['rows']} rows, expected "
                f"{verify['expected_rows']}"
            )
        if verify["duplicate_ids_remaining"]:
            install_blockers.append(
                "duplicate ids survive the repair: "
                + ", ".join(verify["duplicate_ids_remaining"][:10])
            )
        if verify["rows_missing_keys"]:
            install_blockers.append(
                f"{verify['rows_missing_keys']} row(s) lack required snapshot "
                f"keys -- Moneta would quarantine this file and start empty"
            )
        if verify["payloads_unreadable"] > report.rows_unreadable:
            install_blockers.append(
                f"repair introduced unreadable payloads "
                f"({verify['payloads_unreadable']} > {report.rows_unreadable} before)"
            )
        if install_blockers:
            report.refusals.extend(install_blockers)
            report.refusals.append(
                "REFUSING to install the repair -- original untouched, backup at "
                f"{report.backup}"
            )
            return report

        os.replace(tmp_path, snapshot_path)
        report.applied = True

        # Belt after braces: re-read what actually landed. If the installed file
        # is not what we verified, put the backup back -- an unverified primary
        # is worse than an un-repaired one, because it reads as repaired.
        try:
            final = verify_rows(load_snapshot(snapshot_path)["rows"])
        except Exception as exc:  # noqa: BLE001
            final = {"error": f"{type(exc).__name__}: {exc}",
                     "duplicate_ids_remaining": ["<unreadable>"]}
        report.verify["post_install"] = final
        if final.get("duplicate_ids_remaining") or final.get("error"):
            shutil.copy2(backup_targets[0], snapshot_path)
            report.applied = False
            report.refusals.append(
                "post-install verification failed; restored the backup over the "
                f"snapshot ({final})"
            )
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass

    return report


# ---------------------------------------------------------------------------
# rendering + CLI
# ---------------------------------------------------------------------------

def render_report(report: RepairReport) -> str:
    """The full dry-run account. Complete on purpose: the brief for this tool is
    that nobody passes ``--apply`` before reading exactly what it would do."""
    lines: List[str] = []
    add = lines.append
    add("=" * 72)
    add("MONETA PRIMARY REPAIR -- %s" % ("DRY RUN" if report.dry_run else "APPLY"))
    add("=" * 72)
    add("snapshot            : %s" % report.snapshot)
    add("rows                : %d" % report.rows_total)
    add("distinct memory ids : %d" % report.distinct_ids)
    add("unreadable rows     : %d" % report.rows_unreadable)
    for detail in report.unreadable_detail:
        add("    %s" % detail)

    live = report.liveness
    add("")
    add("LIVENESS")
    add("  houdini processes : %s" % (", ".join(live.get("processes") or []) or "none found"))
    if live.get("process_probe_error"):
        add("  probe error       : %s" % live["process_probe_error"])
    age = live.get("snapshot_age_seconds")
    add("  snapshot last touched: %s" % ("unknown" if age is None else "%ss ago" % age))
    add("  verdict           : %s" % ("BLOCKED" if live.get("blocking") else "clear"))
    for b in live.get("blocking") or []:
        add("    - %s" % b)

    add("")
    add("DUPLICATE IDS       : %d  (rows to drop: %d)" %
        (len(report.duplicates), report.rows_to_drop))
    for dup in report.duplicates:
        add("  %s%s  rows=%s  distinct_payloads=%d%s" % (
            dup.memory_id,
            "  [audit-known]" if dup.known else "",
            dup.row_indices,
            dup.distinct_payloads,
            "  (byte-identical copies)" if dup.identical else "",
        ))
        add("      KEEP row %-5d tags=%-3d entity=%s" %
            (dup.keep_index, dup.keep_tags, dup.keep_entity_id))
        for i, (ridx, eid) in enumerate(zip(dup.drop_indices, dup.drop_entity_ids)):
            add("      DROP row %-5d tags=%-3d entity=%s" %
                (ridx, dup.drop_tags[i] if i < len(dup.drop_tags) else -1, eid))
    if not report.duplicates:
        add("  none -- the primary holds one row per memory id")

    add("")
    add("KNOWN AUDIT IDS (2026-09-17, measured resident twice in the primary)")
    add("  still duplicated  : %s" % (", ".join(report.known_ids_duplicated) or "none"))
    add("  present once (ok) : %s" % (", ".join(report.known_ids_single) or "none"))
    add("  ABSENT from this snapshot: %s"
        % (", ".join(report.known_ids_absent) or "none"))
    if report.known_ids_absent and not report.known_ids_duplicated:
        add("      all five absent usually means this is not the store the audit"
            " measured -- check the path before reading this as resolved")

    mc = report.mirror_crosscheck or {}
    add("")
    add("MIRROR CROSS-CHECK  : %s" % mc.get("status", "?"))
    if mc.get("mirror"):
        add("  mirror            : %s" % mc["mirror"])
    if mc.get("reason"):
        add("  reason            : %s" % mc["reason"])
    if mc.get("checked"):
        add("  agreed/checked    : %d/%d" % (mc.get("agreed", 0), mc["checked"]))
    if mc.get("disagreed"):
        add("  DISAGREED         : %s" % ", ".join(mc["disagreed"]))
    if mc.get("absent_from_mirror"):
        add("  absent from mirror: %s" % ", ".join(mc["absent_from_mirror"]))

    if report.backup:
        add("")
        add("BACKUP              : %s" % report.backup)
        add("  sha256 (verified) : %s" % report.backup_sha256)
        for extra in report.backup_extra:
            add("  also copied to    : %s" % extra)
    if report.verify:
        add("")
        add("VERIFY (repaired file, read back from disk)")
        for key in ("rows", "expected_rows", "rows_dropped", "distinct_ids",
                    "rows_missing_keys", "payloads_unreadable", "payloads_invalid"):
            if key in report.verify:
                add("  %-20s: %s" % (key, report.verify[key]))
        if report.verify.get("duplicate_ids_remaining"):
            add("  duplicates remaining: %s" % report.verify["duplicate_ids_remaining"])
        for p in report.verify.get("problems") or []:
            add("    %s" % p)
        if "post_install" in report.verify:
            pi = report.verify["post_install"]
            add("  post-install rows   : %s / distinct ids %s" %
                (pi.get("rows"), pi.get("distinct_ids")))

    add("")
    if report.refusals:
        add("RESULT              : REFUSED -- nothing was written")
        for r in report.refusals:
            add("  - %s" % r)
    elif report.applied:
        add("RESULT              : APPLIED and verified")
        add("  next step         : python -m synapse.memory.backfill_from_moneta "
            "<storage_dir>   (dry run)")
    elif not report.duplicates:
        add("RESULT              : nothing to repair")
        add("  the backfill's precondition is satisfied")
    else:
        add("RESULT              : DRY RUN -- re-run with --apply to install")
    add("=" * 72)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(
        description="De-duplicate the Moneta primary snapshot (incident B2). "
                    "Dry run unless --apply. Run this BEFORE backfill_from_moneta.",
    )
    ap.add_argument("storage_dir", nargs="?",
                    help="the .synapse storage dir (snapshot resolved as "
                         "<storage_dir>/.moneta/snapshot.json)")
    ap.add_argument("--snapshot", help="path to snapshot.json directly")
    ap.add_argument("--apply", action="store_true",
                    help="actually install the repair (default is a dry run)")
    ap.add_argument("--allow-live-houdini", action="store_true",
                    help="override the liveness refusal -- a live save() rewrites "
                         "the snapshot whole and will discard this repair")
    ap.add_argument("--no-mirror-crosscheck", action="store_true",
                    help="skip comparing the kept copy against the JSONL mirror "
                         "(you are asserting the two stores may disagree)")
    ap.add_argument("--mirror", help="path to memory.jsonl (default: "
                                     "<storage_dir>/memory.jsonl)")
    ap.add_argument("--backup-dir", help="also copy the pre-repair snapshot here "
                                         "(a tracked location survives a temp sweep)")
    ap.add_argument("--quiet-seconds", type=float, default=DEFAULT_QUIET_SECONDS,
                    help="how stale the snapshot mtime must be to count as idle")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    if args.snapshot:
        snapshot = Path(args.snapshot)
    elif args.storage_dir:
        snapshot = Path(args.storage_dir) / ".moneta" / "snapshot.json"
    else:
        ap.error("pass a storage_dir or --snapshot")
        return 2  # pragma: no cover -- argparse exits

    report = repair_primary(
        snapshot,
        apply=args.apply,
        allow_live_houdini=args.allow_live_houdini,
        mirror_crosscheck=not args.no_mirror_crosscheck,
        mirror_path=args.mirror,
        backup_dir=args.backup_dir,
        quiet_seconds=args.quiet_seconds,
    )

    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(render_report(report) + "\n")

    if report.refusals:
        return 2
    if args.apply and report.duplicates and not report.applied:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
