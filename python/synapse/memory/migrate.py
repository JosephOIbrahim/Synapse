"""W3-MIGRATE — JSONL → Moneta go-live: copy-and-verify, ids preserved, reversible.

The actual go-live for the memory substrate (Blueprint P6: *never destroy a
memory*). This module is the **data-safe** migration layer that sits ABOVE the
stores and touches no store internals:

  * ``backup_memory_stores`` — the HARD BACKUP GATE. Every real store is copied
    whole and byte-verified BEFORE any migration step runs. Sources are only
    ever READ; a sha256 taken before the run is re-checked after, so
    ``originals are byte-untouched`` is *proven*, not asserted (acceptance #1).

  * ``export_jsonl_to_moneta`` — the one-shot exporter. Reads memories through
    the tested (decrypting) ``MemoryStore`` loader and deposits each into a
    Moneta target via the public ``MonetaBackedStore`` facade, so the whole
    ``Memory`` payload — **including its ``mem_...`` id** — round-trips
    (moneta_store.py:430/491). Preserves ids so links survive (target #2).

  * ``verify_export`` — recomputes count parity **directly from disk**
    (``.moneta/snapshot.json`` rows vs the source JSONL), confirms no id was
    dropped, and spot-checks ≥5 memories field-by-field (acceptance #2/#3).

Two hazards this layer handles that the STORE deliberately does not
(moneta_store.py is append-only, no id-dedup, dim-strict on reopen):

  1. **Re-export double-counts.** Moneta ``deposit()`` always appends a new row
     and ``count()`` counts rows, not distinct ids — a naive second run doubles
     the store. The exporter is **idempotent + keep-both**: an id already
     present with the *identical* payload is skipped (idempotent); an id present
     with a *different* payload is a collision → **KEEP BOTH**, a second
     receipted row, never an overwrite (target #5). This is the W1
     ``merge_moneta`` policy (scripts/w1_consolidate_stores.py:246-267) applied
     on the JSONL→Moneta axis.

  2. **Embedder-dim mismatch crashes reopen.** ``from_storage_dir`` defaults to
     the 384-dim ``SemanticEmbedder``; reopening a 256-dim on-disk snapshot
     under it raises inside Moneta's hydrate (vector_index dim guard) and
     escapes construction. The exporter **detects the on-disk vector dim and
     pins a matching embedder** before it opens a target that already has rows,
     so a live store is never corrupted by a dim change.

Reversibility (the cut-over is copy-and-verify, never cut-over-and-pray):
  * Sources (JSONL + .md ledgers) are NEVER written. The Moneta target is a
    SEPARATE artifact under ``.moneta/``. To fall back to JSONL-primary, set
    ``SYNAPSE_MEMORY_BACKEND=jsonl`` (store.py:956) — the JSONL store is
    untouched and authoritative. The exact steps live in the receipt.
  * Default everywhere is ``dry_run=True``; nothing is written until the caller
    passes ``dry_run=False`` / ``--execute``.

Pure-Python, zero ``hou``. Moneta is imported lazily inside the two functions
that need it, so backup + census reading work with Moneta absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# small, self-contained primitives (mirrors of the proven W1 helpers so this
# module has no import dependency on the scripts/ tree)
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_path(store_dir) -> Path:
    return Path(store_dir) / ".moneta" / "snapshot.json"


def read_snapshot_rows(store_dir) -> List[dict]:
    """The independent, store-free view of a Moneta target: the raw rows list in
    ``.moneta/snapshot.json``. Absent/empty snapshot → ``[]``. This is the
    adversarial count-from-disk source (never MonetaBackedStore.count())."""
    snap = _snapshot_path(store_dir)
    if not snap.is_file():
        return []
    try:
        data = json.loads(snap.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"unreadable Moneta snapshot {snap}: {exc}") from exc
    rows = data.get("rows", [])
    return rows if isinstance(rows, list) else []


def _payload_id(row: dict) -> Optional[str]:
    """SYNAPSE ``mem_...`` id carried inside a Moneta row's JSON payload."""
    try:
        return json.loads(row["payload"]).get("id")
    except Exception:
        return None


def snapshot_dim(store_dir) -> Optional[int]:
    """On-disk embedding dim of a Moneta target (len of the first row's vector),
    or ``None`` when there is no row to read. The number the exporter must match
    so a reopen does not hit Moneta's dim guard."""
    rows = read_snapshot_rows(store_dir)
    for r in rows:
        vec = r.get("semantic_vector")
        if isinstance(vec, list):
            return len(vec)
    return None


def count_jsonl_lines(store_dir) -> int:
    """Raw non-empty line count of ``memory.jsonl`` — the source-side disk count,
    independent of the (decrypting) loader. JSONL entries may be Fernet-encrypted
    so ids are not extractable from raw bytes, but the LINE count is honest."""
    jsonl = Path(store_dir) / "memory.jsonl"
    if not jsonl.is_file():
        return 0
    return sum(
        1 for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()
    )


# ---------------------------------------------------------------------------
# store map (backup-gate scope) — the memory-bearing REAL stores from a census
# ---------------------------------------------------------------------------

def real_stores_from_census(census_path) -> List[dict]:
    """All ``classification == 'real'`` stores in a W1 store census."""
    data = json.loads(Path(census_path).read_text(encoding="utf-8"))
    stores = data["entries"][0]["value"]["stores"]
    return [s for s in stores if s.get("classification") == "real"]


def memory_bearing_stores(census_path) -> List[dict]:
    """The REAL stores that actually hold memories (jsonl lines OR moneta rows).

    NOTE: census counts are a point-in-time snapshot; the store may have DRIFTED
    since (R2 grew 4→583 jsonl lines between the 2026-08-09 census and
    2026-08-13). The backup gate re-reads the live disk; the census only tells us
    WHICH dirs to look at, never the live count.
    """
    out = []
    for s in real_stores_from_census(census_path):
        ec = s.get("entry_counts", {})
        if ec.get("memory_jsonl_lines", 0) > 0 or ec.get("moneta_rows", 0) > 0:
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# 1) HARD BACKUP GATE
# ---------------------------------------------------------------------------

@dataclass
class StoreBackup:
    source: str
    backup: Optional[str] = None
    files: int = 0
    bytes: int = 0
    # rel-path -> sha256 taken from the SOURCE at backup time (the byte-untouched
    # baseline re-checked at end-of-run).
    source_sha: Dict[str, str] = field(default_factory=dict)
    verified: Optional[bool] = None   # backup bytes == source bytes (per file)
    error: Optional[str] = None


@dataclass
class BackupManifest:
    backup_root: str
    dry_run: bool
    generated: str
    stores: List[StoreBackup] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Every store backed up and byte-verified (or dry-run)."""
        if self.dry_run:
            return all(b.error is None for b in self.stores)
        return all(b.error is None and b.verified for b in self.stores)

    def to_dict(self) -> dict:
        return {
            "backup_root": self.backup_root,
            "dry_run": self.dry_run,
            "generated": self.generated,
            "ok": self.ok,
            "stores": [
                {
                    "source": b.source, "backup": b.backup, "files": b.files,
                    "bytes": b.bytes, "verified": b.verified, "error": b.error,
                    "source_sha": b.source_sha,
                }
                for b in self.stores
            ],
        }


def _slug(path: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(Path(path))).strip("_")
    return s[-100:]


def backup_memory_stores(
    store_dirs, backup_root, *, dry_run: bool = True
) -> BackupManifest:
    """Copy every store dir WHOLE into ``backup_root`` and byte-verify each file.

    Data-safety contract:
      * Sources are only READ. sha256 of every source file is recorded so the
        caller can prove (via :func:`verify_sources_untouched`) that the full run
        left them byte-identical (acceptance #1).
      * A per-file backup that does not byte-match its source sets ``error`` and
        makes ``manifest.ok`` False — the caller MUST treat that as a BLOCK and
        not proceed with migration.
      * Additive only: never deletes, never writes into a source.
    """
    root = Path(backup_root)
    manifest = BackupManifest(
        backup_root=str(root),
        dry_run=dry_run,
        generated=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
    for sd in store_dirs:
        src = Path(sd)
        sb = StoreBackup(source=str(src))
        manifest.stores.append(sb)
        if not src.is_dir():
            sb.error = "source dir not present on disk"
            continue
        dest = root / _slug(str(src))
        sb.backup = str(dest)
        try:
            files = [p for p in src.rglob("*") if p.is_file()]
            for p in files:
                rel = p.relative_to(src).as_posix()
                sha = _sha256_file(p)
                sb.source_sha[rel] = sha
                sb.files += 1
                sb.bytes += p.stat().st_size
                if not dry_run:
                    d = dest / rel
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, d)
                    if _sha256_file(d) != sha:
                        raise IOError(f"backup byte-mismatch for {rel}")
            sb.verified = None if dry_run else True
        except Exception as exc:  # a failed backup is a BLOCK, surfaced not swallowed
            sb.error = f"{type(exc).__name__}: {exc}"
            sb.verified = False if not dry_run else None
            logger.error("backup FAILED for %s: %s", src, exc)
    return manifest


def verify_sources_untouched(manifest: BackupManifest) -> Tuple[bool, List[str]]:
    """Re-hash every source file recorded at backup time; report any drift.

    Proves acceptance #1's "originals are byte-untouched after the full run".
    A source file that changed OR vanished since the backup is reported. (A file
    legitimately appended by a live Houdini during the run would show here too —
    that is honest signal, not a migration write, since this module never writes
    a source.)
    """
    changed: List[str] = []
    for sb in manifest.stores:
        src = Path(sb.source)
        for rel, sha in sb.source_sha.items():
            p = src / rel
            if not p.is_file():
                changed.append(f"{sb.source}:{rel} (missing)")
            elif _sha256_file(p) != sha:
                changed.append(f"{sb.source}:{rel} (bytes changed)")
    return (not changed), changed


# ---------------------------------------------------------------------------
# 2) ONE-SHOT EXPORTER — JSONL → Moneta, ids preserved, keep-both, dim-gated
# ---------------------------------------------------------------------------

@dataclass
class ExportReport:
    source_dir: str
    target_dir: str
    dry_run: bool
    embedder_id: Optional[str] = None
    embedding_dim: Optional[int] = None
    source_count: int = 0            # memories the (decrypting) loader returned
    source_jsonl_lines: int = 0      # raw disk line count (independent)
    added: int = 0                   # new ids deposited
    kept_both: List[str] = field(default_factory=list)   # collision ids (2nd row)
    skipped_identical: int = 0       # idempotent: exact payload already present
    target_count_before: int = 0     # rows on disk before
    target_count_after: int = 0      # rows on disk after
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source_dir": self.source_dir, "target_dir": self.target_dir,
            "dry_run": self.dry_run, "embedder_id": self.embedder_id,
            "embedding_dim": self.embedding_dim,
            "source_count": self.source_count,
            "source_jsonl_lines": self.source_jsonl_lines,
            "added": self.added, "kept_both": self.kept_both,
            "skipped_identical": self.skipped_identical,
            "target_count_before": self.target_count_before,
            "target_count_after": self.target_count_after,
            "error": self.error,
        }


def _pick_embedder(dim: Optional[int]):
    """An embedder whose dim matches an existing target (so reopen never hits the
    Moneta dim guard). 256→HashEmbedder, 384→SemanticEmbedder(→hash-384 fallback
    is fine, dim stays 384). Unknown/fresh → the store's own default resolution.
    """
    from .embedding import HashEmbedder, SemanticEmbedder
    if dim == 256:
        return HashEmbedder()
    if dim == 384:
        try:
            return SemanticEmbedder()
        except Exception:
            return HashEmbedder(dim=384)
    # fresh target: mirror from_storage_dir's default (Semantic, else Hash)
    try:
        return SemanticEmbedder()
    except Exception:
        return HashEmbedder()


def _load_source_memories(source_dir):
    """Read all memories through the tested, decrypting JSONL loader."""
    from .store import MemoryStore
    src = MemoryStore(Path(source_dir), background_load=False)
    src._wait_loaded()
    return src.all()


def export_jsonl_to_moneta(
    source_dir,
    target_dir,
    *,
    embedder=None,
    dry_run: bool = True,
    keep_both: bool = True,
) -> ExportReport:
    """Export the JSONL memories at ``source_dir`` into a Moneta target.

    ``target_dir`` is a SEPARATE artifact (its ``.moneta/`` sublayer). The source
    JSONL is never modified. Idempotent + keep-both: an exact-payload dup is
    skipped; a same-id/different-payload collision keeps both. Preserves ids.

    Pass ``target_dir == source_dir`` for an in-place go-live (the JSONL stays as
    the write-through net); pass a fresh dir for copy-and-verify.
    """
    report = ExportReport(
        source_dir=str(source_dir), target_dir=str(target_dir), dry_run=dry_run
    )
    try:
        memories = _load_source_memories(source_dir)
        report.source_count = len(memories)
        report.source_jsonl_lines = count_jsonl_lines(source_dir)

        existing_rows = read_snapshot_rows(target_dir)
        report.target_count_before = len(existing_rows)
        # id -> set of payload strings already present in the target
        have: Dict[str, set] = {}
        for r in existing_rows:
            pid = _payload_id(r)
            if pid is not None:
                have.setdefault(pid, set()).add(r.get("payload"))

        # classify every source memory against the target (pure, no writes yet)
        plan: List[Tuple[str, "object"]] = []   # (action, memory)
        for mem in memories:
            payload = mem.to_json()
            prior = have.get(mem.id)
            if prior and payload in prior:
                report.skipped_identical += 1
                continue
            if prior:  # same id, different payload -> collision
                if keep_both:
                    report.kept_both.append(mem.id)
                    plan.append(("add", mem))
                else:
                    report.skipped_identical += 1  # would-overwrite: refuse, skip
                    continue
            else:
                plan.append(("add", mem))
            have.setdefault(mem.id, set()).add(payload)

        if dry_run:
            report.added = sum(1 for a, _ in plan if a == "add")
            report.embedding_dim = snapshot_dim(target_dir)
            report.target_count_after = report.target_count_before + report.added
            return report

        # write path — pin the embedder to the on-disk dim so an existing target
        # is never corrupted; a fresh target takes the chosen/default embedder.
        from .moneta_store import MonetaBackedStore
        emb = embedder or _pick_embedder(snapshot_dim(target_dir))
        target = MonetaBackedStore.from_storage_dir(target_dir, embedder=emb)
        report.embedder_id = target.embedder_id
        report.embedding_dim = getattr(emb, "dim", None)
        try:
            for action, mem in plan:
                target.add(mem)        # append-only deposit; add() saves() each
                report.added += 1
            target.save()
        finally:
            target.close()

        report.target_count_after = len(read_snapshot_rows(target_dir))
    except Exception as exc:
        report.error = f"{type(exc).__name__}: {exc}"
        logger.error("export FAILED %s -> %s: %s", source_dir, target_dir, exc)
    return report


# ---------------------------------------------------------------------------
# 3) VERIFY — count parity from disk + no id dropped + field-by-field spot-check
# ---------------------------------------------------------------------------

# The Memory fields compared in the spot-check (identity + content-bearing).
_SPOT_FIELDS = (
    "id", "content", "summary", "memory_type", "tier", "tags", "keywords",
    "created_at", "source", "hip_file", "frame",
)


@dataclass
class SpotCheck:
    id: str
    matched: bool
    mismatched_fields: List[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    source_dir: str
    target_dir: str
    source_count: int = 0            # memories via decrypting loader
    source_jsonl_lines: int = 0      # raw disk lines
    target_rows: int = 0             # rows in snapshot.json (from disk)
    target_distinct_ids: int = 0     # distinct payload ids in snapshot.json
    ids_missing_from_target: List[str] = field(default_factory=list)
    spot_checks: List[SpotCheck] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def count_parity(self) -> bool:
        """Every source memory id is present as a target row (no prim dropped).
        Uses DISTINCT ids so keep-both duplicate rows do not mask a drop."""
        return not self.ids_missing_from_target and self.source_count > 0 \
            and self.target_distinct_ids >= self.source_count

    @property
    def spot_ok(self) -> bool:
        return bool(self.spot_checks) and all(s.matched for s in self.spot_checks)

    def to_dict(self) -> dict:
        return {
            "source_dir": self.source_dir, "target_dir": self.target_dir,
            "source_count": self.source_count,
            "source_jsonl_lines": self.source_jsonl_lines,
            "target_rows": self.target_rows,
            "target_distinct_ids": self.target_distinct_ids,
            "count_parity": self.count_parity, "spot_ok": self.spot_ok,
            "ids_missing_from_target": self.ids_missing_from_target,
            "spot_checks": [
                {"id": s.id, "matched": s.matched,
                 "mismatched_fields": s.mismatched_fields}
                for s in self.spot_checks
            ],
            "error": self.error,
        }


def verify_export(source_dir, target_dir, *, spot_check: int = 5) -> VerifyReport:
    """Independently verify a JSONL→Moneta export straight from disk.

    Recomputes the target row/id sets from ``.moneta/snapshot.json`` (NOT from
    MonetaBackedStore.count()), confirms every source id is present, and
    compares ``spot_check`` memories field-by-field between the JSONL source and
    the Moneta payload. This is the crucible's "recompute parity from disk".
    """
    from .models import Memory
    report = VerifyReport(source_dir=str(source_dir), target_dir=str(target_dir))
    try:
        memories = _load_source_memories(source_dir)
        report.source_count = len(memories)
        report.source_jsonl_lines = count_jsonl_lines(source_dir)

        rows = read_snapshot_rows(target_dir)
        report.target_rows = len(rows)
        # id -> Memory rebuilt from the target payload (last write wins for the map;
        # keep-both rows share an id but the spot-check compares whole payloads).
        target_by_id: Dict[str, Memory] = {}
        for r in rows:
            try:
                m = Memory.from_json(r["payload"])
                target_by_id[m.id] = m
            except Exception:
                continue
        report.target_distinct_ids = len(target_by_id)

        report.ids_missing_from_target = sorted(
            {m.id for m in memories} - set(target_by_id)
        )

        # field-by-field spot-check on the first `spot_check` source memories
        for mem in memories[: max(spot_check, 0)]:
            tgt = target_by_id.get(mem.id)
            sc = SpotCheck(id=mem.id, matched=(tgt is not None))
            if tgt is None:
                sc.matched = False
                sc.mismatched_fields = ["<absent from target>"]
            else:
                src_d, tgt_d = mem.to_dict(), tgt.to_dict()
                for fld in _SPOT_FIELDS:
                    if src_d.get(fld) != tgt_d.get(fld):
                        sc.mismatched_fields.append(fld)
                sc.matched = not sc.mismatched_fields
            report.spot_checks.append(sc)
    except Exception as exc:
        report.error = f"{type(exc).__name__}: {exc}"
        logger.error("verify FAILED %s vs %s: %s", source_dir, target_dir, exc)
    return report


# ---------------------------------------------------------------------------
# CLI — dry-run by default (mirrors backfill.py's safety posture)
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="W3-MIGRATE JSONL->Moneta copy-and-verify.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backup", help="hard backup gate for the census real stores")
    b.add_argument("--census", required=True)
    b.add_argument("--backup-root", required=True)
    b.add_argument("--execute", action="store_true")

    e = sub.add_parser("export", help="one-shot JSONL->Moneta exporter")
    e.add_argument("source_dir")
    e.add_argument("target_dir")
    e.add_argument("--execute", action="store_true")

    v = sub.add_parser("verify", help="verify an export from disk")
    v.add_argument("source_dir")
    v.add_argument("target_dir")
    v.add_argument("--spot-check", type=int, default=5)

    args = ap.parse_args(argv)

    if args.cmd == "backup":
        stores = [s["path"] for s in memory_bearing_stores(args.census)]
        manifest = backup_memory_stores(
            stores, args.backup_root, dry_run=not args.execute
        )
        print(json.dumps(manifest.to_dict(), indent=2))
        return 0 if manifest.ok else 1

    if args.cmd == "export":
        report = export_jsonl_to_moneta(
            args.source_dir, args.target_dir, dry_run=not args.execute
        )
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.error is None else 1

    if args.cmd == "verify":
        report = verify_export(args.source_dir, args.target_dir, spot_check=args.spot_check)
        print(json.dumps(report.to_dict(), indent=2))
        ok = report.error is None and report.count_parity and report.spot_ok
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
