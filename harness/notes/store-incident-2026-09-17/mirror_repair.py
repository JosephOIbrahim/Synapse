"""Dedupe conflicting identities out of a JSONL memory store (the mirror side).

Companion to ``python/synapse/memory/primary_repair.py``, which does the same job
for a Moneta ``snapshot.json``. This one repairs ``memory.jsonl``.

WHY THIS EXISTS
---------------
``MemoryStore._load`` (store.py:353-358) raises ``conflicting duplicate memory
identity`` when one id appears twice with a DIFFERENT canonical payload, and
store.py:396-401 then degrades the WHOLE store and refuses EVERY write. One bad
line is enough. A machine-wide census on 2026-09-17 found SIX stores in that
state, so a one-off script was the wrong shape.

TWO CONFLICT SHAPES, ONE REPAIR
-------------------------------
* **Shape A -- metadata-stripped twin.** Adjacent pair, identical content and
  ``created_at``, second copy stripped (``tags=[]``, ``hip_file=''``,
  ``frame=None``, ``source 'ai'->'auto'``). Caused by one logical add emitting
  two records; fixed at source in ``scene_memory.write_memory_entry``.
* **Shape B -- timestamp-only collision.** Non-adjacent repeats, byte-identical
  content, differing only in ``created_at``/``updated_at``/``hip_file``. A
  historical defect: ids were once content-only, so the same content logged
  twice collided. The current formula (``models.py:157-162``) already fixes it.
  These files are fossils.

Both are repaired the same way: keep the RICHEST record for each id, drop the
rest. NEVER last-write-wins -- in Shape A the later copy is the stripped one, so
the instinctive repair destroys the tags that feed retrieval. The ordering is
identical to ``primary_repair.py`` on purpose, so the two tools can never
disagree about which twin is authoritative.

SAFETY
------
* Dry run is the default. Nothing is written without ``--apply``.
* Refuses while a Houdini process is live, and while the file was touched
  recently -- a live ``save()`` rewrites the whole file from memory and would
  silently discard this repair.
* Backs up before writing, verifies the backup by hash, verifies the repaired
  file by replaying the loader's own predicate, and refuses to install if
  verification fails.
* Original ciphertext lines are preserved byte-for-byte. Lines are only dropped,
  never rewritten or re-encrypted.
* **Never point this at a backup.** A backup's whole job is to hold the original
  bytes; deduping one destroys the thing it exists to preserve.

USAGE
    python harness/notes/store-incident-2026-09-17/mirror_repair.py <dir> [<dir> ...]
    python harness/notes/store-incident-2026-09-17/mirror_repair.py <dir> --apply
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "python"))

DEFAULT_QUIET_SECONDS = 120.0


def _crypto():
    from synapse.memory.store import _get_crypto
    return _get_crypto()


def _richness(d: dict) -> tuple:
    """Metadata carried, as a sortable tuple. Identical to primary_repair's."""
    tags = d.get("tags") or []
    try:
        n = len(tags)
    except TypeError:
        n = 0
    return (
        n,
        1 if (d.get("hip_file") or "") else 0,
        0 if (d.get("source") or "") == "auto" else 1,
        1 if d.get("frame") is not None else 0,
        1 if (d.get("hip_version") or 0) else 0,
    )


def _houdini_live() -> List[str]:
    """Process names that would rewrite a store out from under us.

    Windows uses tasklist; POSIX uses ps. A detector that silently answers
    "nothing running" is worse than none, so an unusable probe returns a
    sentinel rather than an empty list.
    """
    names = ("houdini", "hython", "husk", "mplay", "hindie")
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=20).stdout
        else:
            out = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:  # noqa: BLE001 -- an unusable probe must not read as "clear"
        return ["<could not probe processes: %s>" % exc]
    low = out.lower()
    return [n for n in names if n in low]


def scan(store_dir: Path) -> Tuple[List[str], Dict[str, List[int]], Dict[int, dict], int]:
    """Return (raw_lines, id -> line indices, index -> payload, unreadable)."""
    path = store_dir / "memory.jsonl"
    raw = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    c = _crypto()
    by_id: Dict[str, List[int]] = collections.defaultdict(list)
    payload: Dict[int, dict] = {}
    unreadable = 0
    for i, line in enumerate(raw):
        s = line.strip()
        if not s:
            continue
        try:
            d = json.loads(c.decrypt_line(s) if c else s)
            required = ("id", "created_at", "content", "memory_type")
            if (not isinstance(d, dict)
                    or any(not isinstance(d.get(k), str) for k in required)
                    or not d["id"] or not d["created_at"]):
                raise ValueError("incomplete record identity or content")
            by_id[d["id"]].append(i)
            payload[i] = d
        except Exception:
            unreadable += 1
    return raw, dict(by_id), payload, unreadable


def plan(by_id, payload) -> Tuple[Dict[str, Tuple[int, List[int]]], set]:
    """For each conflicting id: (kept index, dropped indices)."""
    decisions: Dict[str, Tuple[int, List[int]]] = {}
    drop: set = set()
    for mid, idxs in by_id.items():
        if len(idxs) < 2:
            continue
        canon = {i: json.dumps(payload[i], sort_keys=True) for i in idxs}
        if len(set(canon.values())) < 2:
            continue  # byte-identical repeats: the loader already tolerates these
        keep = max(idxs, key=lambda i: (_richness(payload[i]), -i))
        dropped = [i for i in idxs if i != keep]
        decisions[mid] = (keep, dropped)
        drop.update(dropped)
    return decisions, drop


def repair(store_dir: Path, apply: bool, quiet_seconds: float, allow_live: bool) -> int:
    path = store_dir / "memory.jsonl"
    if not path.is_file():
        print("  NOT FOUND: %s" % path)
        return 2

    raw, by_id, payload, unreadable = scan(store_dir)
    decisions, drop = plan(by_id, payload)

    print("  records readable : %d   distinct ids : %d   unreadable : %d"
          % (len(payload), len(by_id), unreadable))
    print("  conflicting ids  : %d   lines to drop : %d" % (len(decisions), len(drop)))
    for mid, (keep, dropped) in decisions.items():
        kd = payload[keep]
        print("     %s  KEEP line %-5d tags=%-2d source=%-5s  DROP %s"
              % (mid, keep + 1, len(kd.get("tags") or []), kd.get("source"),
                 [i + 1 for i in dropped]))

    if not decisions:
        print("  nothing to repair")
        return 0

    live = _houdini_live()
    age = time.time() - path.stat().st_mtime
    blocked = []
    if live and not allow_live:
        blocked.append("live process(es): %s" % ", ".join(live))
    if age < quiet_seconds and not allow_live:
        blocked.append("file touched %.0fs ago (< %.0fs)" % (age, quiet_seconds))
    if blocked:
        print("  REFUSED: %s" % "; ".join(blocked))
        return 3
    if not apply:
        print("  DRY RUN -- re-run with --apply to install")
        return 0

    stamp = int(time.time())
    backup = path.with_name(path.name + ".pre-mirror-repair-%d" % stamp)
    shutil.copy2(path, backup)
    if hashlib.sha256(backup.read_bytes()).hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest():
        print("  ABORT: backup hash mismatch; original untouched")
        return 4

    tmp = path.with_suffix(path.suffix + ".repaired")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        for i, line in enumerate(raw):
            if i not in drop:
                fh.write(line)

    # verify by replaying the loader's own predicate over the repaired file
    c = _crypto()
    seen: Dict[str, str] = {}
    bad = 0
    with open(tmp, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            try:
                d = json.loads(c.decrypt_line(s) if c else s)
                canon = json.dumps(d, sort_keys=True)
                prior = seen.get(d["id"])
                if prior is not None and prior != canon:
                    raise ValueError("conflicting duplicate memory identity")
                seen[d["id"]] = canon
            except Exception:
                bad += 1
    if bad:
        tmp.unlink(missing_ok=True)
        print("  ABORT: repaired file still has %d unreadable/conflicting record(s); original untouched" % bad)
        return 5

    os.replace(tmp, path)
    print("  APPLIED: %d -> %d lines, %d ids, 0 conflicts" % (len(raw), len(raw) - len(drop), len(seen)))
    print("  backup : %s" % backup.name)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Dedupe conflicting identities out of one or more JSONL memory stores. "
                    "Dry run unless --apply. Never point this at a backup.")
    ap.add_argument("store_dirs", nargs="+", help=".synapse directories holding memory.jsonl")
    ap.add_argument("--apply", action="store_true", help="actually install the repair")
    ap.add_argument("--allow-live", action="store_true",
                    help="skip the liveness and quiet-period refusals (you are certain nothing owns these files)")
    ap.add_argument("--quiet-seconds", type=float, default=DEFAULT_QUIET_SECONDS)
    args = ap.parse_args(argv)

    rc = 0
    for d in args.store_dirs:
        print("\n%s" % d)
        rc = repair(Path(d), args.apply, args.quiet_seconds, args.allow_live) or rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
