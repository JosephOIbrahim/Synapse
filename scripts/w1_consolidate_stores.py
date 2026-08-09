#!/usr/bin/env python
"""W1 store consolidation -- fold the bug-scattered UNSAVED-scene fragments into
one canonical store, losslessly.

WHY
    The literal-env-var resolver bug (store.py:_resolve_project_path, fixed in
    fix/memory-store-recovery) scattered the UNSAVED-scene memory store across
    several addresses that SHOULD have resolved to ONE place
    ($HOUDINI_TEMP_DIR/untitled). This script consolidates those fragments into
    the canonical store the FIXED resolver produces.

CANONICAL is DERIVED, never hardcoded (mirrors the fixed resolver):
    root = --canonical-root
         | $HOUDINI_TEMP_DIR/untitled          (env, honoured by the resolver)
         | <platform-temp>/houdini_temp/untitled  (Houdini's built-in default)
    canonical .synapse = <root>/.synapse   canonical claude = <root>/claude
    A residual literal $VAR/%VAR% segment is refused before use.

DATA-SAFETY CONTRACT (non-negotiable -- this is USER MEMORY):
    * NEVER delete anything. NEVER overwrite a canonical file.
    * On any key/file collision: KEEP BOTH -- the loser is quarantined under a
      suffixed path in canonical, and every collision is reported.
    * Fragment (source) stores are opened READ-ONLY; they are never modified.
    * Re-runnable / idempotent: running twice == running once (dedup by raw
      jsonl line and by moneta payload id; copy-if-absent-or-identical).
    * Default is DRY-RUN. Pass --apply to write. Even --apply is additive-only
      into the canonical store; it keeps a .w1-pre-<ts> pre-image of any
      canonical file it extends before touching it.

Run with Houdini CLOSED (a live Moneta handle holds an in-memory URI lock and
could race a snapshot write; this script writes snapshot.json directly).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_LITERAL_ENV_SEG = re.compile(r"^(?:\$\w+|\$\{[^}]+\}|%[^%]+%)$")
_TEMP_MARKERS = ("temp", "tmp", "houdini_temp")


# ---------------------------------------------------------------------------
# canonical derivation (no hardcoded user path)
# ---------------------------------------------------------------------------

def _has_literal_env_segment(path: str) -> bool:
    return any(_LITERAL_ENV_SEG.match(seg) for seg in Path(str(path)).parts)


def canonical_unsaved_root(override: Optional[str] = None) -> Path:
    """The unsaved-scene canonical root, matching the FIXED in-Houdini resolver.

    The resolver inside Houdini yields ``$HOUDINI_TEMP_DIR/untitled``; Houdini's
    default ``$HOUDINI_TEMP_DIR`` is ``<platform-temp>/houdini_temp``. Headless we
    honour the env var, else fall back to that documented default (which is where
    the bulk of the real unsaved memory already sits per the census).
    """
    if override:
        root = os.path.expanduser(os.path.expandvars(override))
    else:
        env = os.environ.get("HOUDINI_TEMP_DIR")
        if env and not _has_literal_env_segment(env):
            root = os.path.join(env, "untitled")
        else:
            root = os.path.join(tempfile.gettempdir(), "houdini_temp", "untitled")
    root = os.path.normpath(root)
    if _has_literal_env_segment(root):
        raise SystemExit(
            f"refusing: derived canonical root still holds a literal env token: {root}"
        )
    return Path(root)


def canonical_store(root: Path, store_type: str) -> Path:
    """Canonical .synapse / claude store dir under *root*."""
    return root / store_type


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def store_type_of(path: str) -> Optional[str]:
    base = os.path.basename(os.path.normpath(path))
    return base if base in (".synapse", "claude") else None


def is_unsaved_scene_store(path: str) -> bool:
    """True for a store scattered by the unsaved-scene resolver bug.

    Signatures (any one): a literal ``$VAR`` path segment; a store dir directly
    under a dir named ``untitled.hip`` (the <cwd>/untitled.hip pattern); or under
    a dir named ``untitled`` that lives in a temp dir (the $HOUDINI_TEMP_DIR /
    platform-temp untitled dirs). Deliberately does NOT match ``~/.synapse`` (home
    top-level), a repo/worktree ``.synapse``, or a saved-project ``claude``.
    """
    norm = os.path.normpath(path)
    if _has_literal_env_segment(norm):
        return True
    parent = os.path.basename(os.path.dirname(norm))
    if parent == "untitled.hip":
        return True
    if parent == "untitled":
        low = norm.replace("\\", "/").lower()
        return any(m in low for m in _TEMP_MARKERS)
    return False


def classify(real_paths: List[str], root: Path) -> Dict[str, List[str]]:
    """Split census real stores into canonical / fragment / leave."""
    can_syn = os.path.normpath(str(canonical_store(root, ".synapse")))
    can_cla = os.path.normpath(str(canonical_store(root, "claude")))
    out = {"canonical": [], "fragment": [], "leave": []}
    for p in real_paths:
        npath = os.path.normpath(p)
        if npath.lower() in (can_syn.lower(), can_cla.lower()):
            out["canonical"].append(npath)
        elif is_unsaved_scene_store(npath):
            out["fragment"].append(npath)
        else:
            out["leave"].append(npath)
    return out


# ---------------------------------------------------------------------------
# merge primitives (all keep-both, never-overwrite, never-delete)
# ---------------------------------------------------------------------------

def _slug(path: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", os.path.normpath(path)).strip("_")
    return s[-80:]


def _sha(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fp:
            fp.write(text)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def merge_jsonl(frag: Path, canon: Path, apply: bool, rep: dict) -> None:
    """Append fragment jsonl lines absent from canonical (raw-line dedup)."""
    if not frag.is_file():
        return
    frag_lines = frag.read_text(encoding="utf-8").splitlines()
    canon_lines = (
        canon.read_text(encoding="utf-8").splitlines() if canon.is_file() else []
    )
    have = set(canon_lines)
    new = [ln for ln in frag_lines if ln.strip() and ln not in have]
    rep["jsonl"] = {"fragment_lines": len(frag_lines),
                    "already_present": len(frag_lines) - len(new),
                    "appended": len(new)}
    if new and apply:
        if canon.is_file():
            pre = canon.with_name(f"{canon.name}.w1-pre-{int(time.time())}")
            if not pre.exists():
                shutil.copy2(canon, pre)
                rep["jsonl"]["pre_image"] = pre.name
        merged = "\n".join(canon_lines + new) + "\n"
        _atomic_write_text(canon, merged)


def _payload_ids(rows: List[dict]) -> set:
    ids = set()
    for r in rows:
        try:
            ids.add(json.loads(r["payload"]).get("id"))
        except Exception:
            pass
    return ids


def merge_moneta(frag_store: Path, canon_store: Path, frag_slug: str,
                 apply: bool, rep: dict) -> None:
    """Merge fragment .moneta rows into canonical, dim-gated + keep-both.

    Dim-MATCH -> append fragment rows whose payload id is absent from canonical
    (id-collision-with-different-payload is quarantined, not overwritten).
    Dim-MISMATCH -> preserve the whole fragment .moneta under
    <canonical>/.w1_incoming_moneta/<slug>/ (a 384-dim vector merged into a
    256-dim index would corrupt recall).
    """
    frag_snap = frag_store / ".moneta" / "snapshot.json"
    if not frag_snap.is_file():
        return
    try:
        fdata = json.loads(frag_snap.read_text(encoding="utf-8"))
        frows = fdata.get("rows", [])
    except Exception as exc:
        rep["moneta"] = {"error": f"unreadable fragment snapshot: {exc}"}
        return
    if not frows:
        rep["moneta"] = {"fragment_rows": 0, "appended": 0}
        return
    frag_dim = len(frows[0].get("semantic_vector", []))

    canon_snap = canon_store / ".moneta" / "snapshot.json"
    cdata = {"snapshot_version": 1, "snapshot_created_at": time.time(), "rows": []}
    crows: List[dict] = []
    if canon_snap.is_file():
        try:
            cdata = json.loads(canon_snap.read_text(encoding="utf-8"))
            crows = cdata.get("rows", [])
        except Exception as exc:
            rep["moneta"] = {"error": f"unreadable canonical snapshot: {exc}"}
            return
    canon_dim = len(crows[0].get("semantic_vector", [])) if crows else frag_dim

    if frag_dim != canon_dim:
        dest = canon_store / ".w1_incoming_moneta" / frag_slug
        rep["moneta"] = {"fragment_rows": len(frows), "appended": 0,
                         "preserved_not_merged": True,
                         "reason": f"embedder dim mismatch (frag={frag_dim}, "
                                   f"canonical={canon_dim})",
                         "preserved_to": str(dest)}
        if apply:
            _keep_both_tree(frag_store / ".moneta", dest, rep)
        return

    have = _payload_ids(crows)
    canon_entity_ids = {r.get("entity_id") for r in crows}
    appended, collisions = [], []
    for r in frows:
        pid = None
        try:
            pid = json.loads(r["payload"]).get("id")
        except Exception:
            pass
        if pid is not None and pid in have:
            # id already present -> keep both only if payload actually differs
            existing = next((c for c in crows if _row_pid(c) == pid), None)
            if existing is not None and existing.get("payload") != r.get("payload"):
                collisions.append(pid)
                _quarantine_row(canon_store, frag_slug, r, apply)
            continue
        if r.get("entity_id") in canon_entity_ids:
            # extremely unlikely UUID collision -> quarantine, never overwrite
            collisions.append(f"entity:{r.get('entity_id')}")
            _quarantine_row(canon_store, frag_slug, r, apply)
            continue
        appended.append(r)

    rep["moneta"] = {"fragment_rows": len(frows), "appended": len(appended),
                     "collisions_kept_both": collisions,
                     "canonical_dim": canon_dim}
    if appended and apply:
        if canon_snap.is_file():
            pre = canon_snap.with_name(f"snapshot.json.w1-pre-{int(time.time())}")
            if not pre.exists():
                shutil.copy2(canon_snap, pre)
                rep["moneta"]["pre_image"] = pre.name
        merged = dict(cdata)
        merged["rows"] = crows + appended
        _atomic_write_text(canon_snap, json.dumps(merged))
        # validate: re-parse and confirm the row count grew by exactly len(appended)
        check = json.loads(canon_snap.read_text(encoding="utf-8"))
        if len(check.get("rows", [])) != len(crows) + len(appended):
            raise SystemExit(
                "ABORT: merged snapshot row count mismatch -- restore from "
                f"{pre if canon_snap.is_file() else 'backup'}")


def _row_pid(row: dict) -> Optional[str]:
    try:
        return json.loads(row["payload"]).get("id")
    except Exception:
        return None


def _quarantine_row(canon_store: Path, slug: str, row: dict, apply: bool) -> None:
    if not apply:
        return
    qdir = canon_store / ".w1_quarantine" / slug / "moneta_rows"
    qdir.mkdir(parents=True, exist_ok=True)
    name = f"{row.get('entity_id', 'row')}.json"
    (qdir / name).write_text(json.dumps(row), encoding="utf-8")


def _keep_both_tree(src: Path, dest: Path, rep: dict) -> None:
    """Copy *src* tree to *dest*, keep-both on any differing file. Never overwrite."""
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        for f in files:
            s = Path(root) / f
            d = dest / rel / f if rel != "." else dest / f
            _keep_both_file(s, d, rep)


def _keep_both_file(src: Path, dest: Path, rep: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(src, dest)
        rep.setdefault("copied", []).append(str(dest))
        return
    if _sha(src) == _sha(dest):
        rep.setdefault("identical_skipped", []).append(str(dest))
        return
    # differ -> keep both under a .collision- sibling, never overwrite
    alt = dest.with_name(f"{dest.name}.w1-collision-{_sha(src)[:8]}")
    if not alt.exists():
        shutil.copy2(src, alt)
    rep.setdefault("collisions_kept_both", []).append(str(alt))


def merge_files(frag_store: Path, canon_store: Path, frag_slug: str,
                apply: bool, rep: dict) -> None:
    """File-level keep-both for everything except jsonl + .moneta (handled apart)."""
    for root, _dirs, files in os.walk(frag_store):
        rel = os.path.relpath(root, frag_store)
        top = rel.split(os.sep)[0]
        if top == ".moneta":
            continue  # handled by merge_moneta
        for f in files:
            if rel == "." and f == "memory.jsonl":
                continue  # handled by merge_jsonl
            s = Path(root) / f
            d = (canon_store / rel / f) if rel != "." else canon_store / f
            if not apply:
                # dry-run accounting only
                if not d.exists():
                    rep.setdefault("copied", []).append(str(d))
                elif _sha(s) == _sha(d):
                    rep.setdefault("identical_skipped", []).append(str(d))
                else:
                    rep.setdefault("collisions_kept_both", []).append(str(d))
                continue
            if rel != "." and f == "memory.jsonl":
                continue
            _keep_both_file(s, d, rep)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def consolidate(census: Optional[str], root: Path, apply: bool) -> dict:
    if census and os.path.isfile(census):
        data = json.load(open(census, encoding="utf-8"))
        stores = data["entries"][0]["value"]["stores"]
        real = [s["path"] for s in stores if s.get("classification") == "real"]
    else:
        real = []
    cls = classify(real, root)

    report: dict = {
        "mode": "apply" if apply else "dry-run",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "canonical_root": str(root),
        "canonical_synapse": str(canonical_store(root, ".synapse")),
        "canonical_claude": str(canonical_store(root, "claude")),
        "classification": cls,
        "fragments": [],
    }

    for frag in cls["fragment"]:
        stype = store_type_of(frag)
        if stype is None:
            continue
        canon = canonical_store(root, stype)
        frep: dict = {"source": frag, "store_type": stype,
                      "canonical": str(canon), "exists": os.path.isdir(frag)}
        report["fragments"].append(frep)
        if not os.path.isdir(frag):
            frep["skipped"] = "fragment path not present on disk"
            continue
        if apply:
            canon.mkdir(parents=True, exist_ok=True)
        fp, cp = Path(frag), Path(canon)
        slug = _slug(frag)
        if stype == ".synapse":
            merge_jsonl(fp / "memory.jsonl", cp / "memory.jsonl", apply, frep)
            merge_moneta(fp, cp, slug, apply, frep)
        merge_files(fp, cp, slug, apply, frep)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parents[1]
    ap.add_argument("--census",
                    default=str(here / "harness" / "notes" /
                               "W1_STORE_CENSUS_2026-08-09.json"))
    ap.add_argument("--canonical-root", default=None,
                    help="override the derived unsaved-scene canonical root")
    ap.add_argument("--apply", action="store_true",
                    help="write (default is dry-run: report only, no changes)")
    ap.add_argument("--report", default=None, help="write the JSON report here")
    args = ap.parse_args(argv)

    root = canonical_unsaved_root(args.canonical_root)
    report = consolidate(args.census, root, args.apply)

    text = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)

    n_frag = len(report["classification"]["fragment"])
    n_appended = sum(f.get("jsonl", {}).get("appended", 0)
                     + f.get("moneta", {}).get("appended", 0)
                     for f in report["fragments"])
    print(f"\n[{report['mode']}] canonical={root} fragments={n_frag} "
          f"entries_merged={n_appended}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
