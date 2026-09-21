"""BP10-CORPUS Target 1 + Target 2: H22 prose corpus from the shipped help archives.

Clean-room reader. Written after reading fxhoudinimcp's ``help_handlers.py`` for its
three path rules ONLY (MIT, healkeiser @ 29b6695b): read both ``$HFS/houdini/help/*.zip``
and the loose help directories; key every page by its forward-slash path relative to the
scope root with the ``.txt`` extension dropped; decode UTF-8 with replacement. Everything
after the read step (wiki->markdown, chunking, the phantom gate, the ingest ledger and the
stamp) is SYNAPSE's own and shares nothing with theirs.

Licensing: SideFX help text ships under the Houdini EULA, not MIT. The generated corpus is
derived from the user's own install at ingest time and is NEVER committed
(``rag/corpus/h22_prose/*.jsonl`` is gitignored). What is committed is this builder, the
STAMP file, and the probe results.

Phantom gate authority (reconciliation, flagged for ruling in the receipt):
    The mission brief and HARVEST_SPEC say "node names vs h22_symbol_table.json". But
    h22_symbol_table.json is 36,472 DOTTED ``hou.*`` API symbols (verified 22.0.400); node
    TYPE names (scatter, pyrosolver) are not in it, so gating node names against it would
    quarantine every real node and empty the corpus. The live node-type authority is the
    catalogue ``rag/catalog/<build>/`` (CLAUDE.md rulebook discipline: "node-type authority
    is the live catalogue"). This gate therefore resolves node references against the
    catalogue. Node references are read from the corpus's own canonical markup
    (``[Node:context/type]`` cross-references), OP contexts only; the ``apex`` context is a
    separate graph-node surface (not the OP catalogue) and is exempt. Matching is on the
    unqualified type name (namespace/version stripped), which measured ~1.4% quarantine on
    the live archive -- all reviewable, never dropped -- while still catching a planted fake.

Usage (headless, under hython on the target build):
    hython rag/ingest/help_archive.py --build        # ingest -> corpus + STAMP.json
    hython rag/ingest/help_archive.py --status        # phantom_gate_status: CURRENT/STALE
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]                      # rag/ingest/ -> repo root
LICENCE = "sidefx-eula"
# Help subtrees that are not prose (licence texts alone are 250 pages of ordinary English
# that outrank real pages): skip any path whose directory segments name one of these.
SKIP_SEGMENTS = frozenset({"files", "images", "videos", "licenses", "licensing"})
# APEX is a separate graph-node surface, not the OP node catalogue; its refs are out of
# scope for the node-type gate, never phantoms.
APEX_EXEMPT = frozenset({"apex"})

NODE_XREF = re.compile(r"\[Node:([a-z0-9_]+)/([A-Za-z0-9_:./\-]+)\]")


# --------------------------------------------------------------------------- #
#  Path rules (clean-room)                                                     #
# --------------------------------------------------------------------------- #
def _keep_txt(name: str) -> bool:
    """A .txt page whose directory segments name no skipped subtree."""
    parts = name.replace("\\", "/").split("/")
    if not parts[-1].lower().endswith(".txt"):
        return False
    return not any(seg.lower() in SKIP_SEGMENTS for seg in parts[:-1])


def _noext(path: str) -> str:
    p = path.replace("\\", "/")
    return p[:-4] if p.lower().endswith(".txt") else p


def iter_pages(hfs):
    """Yield ``(scope, page, raw_text, source_suffix)`` for every help page.

    scope  = zip basename (no .zip) or loose-dir name.
    page   = ``<scope>/<zip-or-dir-relative path, extension dropped>`` (forward slashes).
    source_suffix = ``<scope>.zip`` or ``<scope>/`` -- the archive, not the page.
    """
    help_dir = Path(hfs) / "houdini" / "help"
    for zpath in sorted(help_dir.glob("*.zip")):
        scope = zpath.stem
        suffix = f"{scope}.zip"
        with zipfile.ZipFile(zpath) as zf:
            for name in zf.namelist():
                if not _keep_txt(name):
                    continue
                raw = zf.read(name).decode("utf-8", "replace")
                yield scope, f"{scope}/{_noext(name)}", raw, suffix
    for d in sorted(p for p in help_dir.iterdir() if p.is_dir() and p.name not in SKIP_SEGMENTS):
        scope = d.name
        suffix = f"{scope}/"
        for txt in sorted(d.rglob("*.txt")):
            rel = txt.relative_to(help_dir).as_posix()
            if any(seg.lower() in SKIP_SEGMENTS for seg in rel.split("/")[:-1]):
                continue
            raw = txt.read_text(encoding="utf-8", errors="replace")
            yield scope, _noext(rel), raw, suffix


# --------------------------------------------------------------------------- #
#  Wiki markup -> markdown                                                     #
# --------------------------------------------------------------------------- #
def _directives(raw: str) -> dict:
    """The node identity directives a node page declares at the top."""
    return dict(re.findall(r"^#(type|context|internal|icon|since):\s*(.*)$", raw, re.M))


def wiki_to_markdown(raw: str):
    """Convert one SideFX help page to (title, markdown_body).

    Not a full wiki engine -- it handles the markup the 22.0 archive actually uses (measured
    on 11,460 pages): ``= Title =`` / ``== Section ==`` headings, ``\"\"\"summary\"\"\"``
    taglines, ``#directive:`` metadata lines, ``[label|target]`` internal links (the label
    is kept, the target dropped), ``[Node:ctx/type]`` cross-references (kept verbatim so the
    phantom gate can read them), ``__bold__``, ``* bullets``, and NOTE/TIP/WARNING callouts.
    """
    body = raw.replace("\r\n", "\n")
    # title: first single-'=' heading
    title = ""
    m = re.search(r"^=\s*(.+?)\s*=\s*$", body, re.M)
    if m:
        title = m.group(1).strip()
        body = body[:m.start()] + body[m.end():]
    # strip every #directive: line (node identity captured separately by _directives)
    body = re.sub(r"^[ \t]*#\w+:.*$", "", body, flags=re.M)
    # triple-quote taglines -> plain text
    body = re.sub(r'"""(.*?)"""', lambda mm: mm.group(1).strip(), body, flags=re.S)
    # == Section == -> ## Section  (2..6 '='; single '=' was the title, already removed)
    body = re.sub(r"^(={2,6})\s*(.+?)\s*\1\s*$",
                  lambda mm: "#" * len(mm.group(1)) + " " + mm.group(2).strip(),
                  body, flags=re.M)
    # @parameters / @related section markers -> headings
    body = re.sub(r"^@(\w+)[ \t]*$", lambda mm: "## " + mm.group(1).capitalize(), body, flags=re.M)
    # [label|target] internal links -> label  (leaves [Node:ctx/type], which has no '|')
    body = re.sub(r"\[([^\]|]+)\|[^\]]*\]", r"\1", body)
    # __bold__ -> **bold**
    body = re.sub(r"__([^_\n]+)__", r"**\1**", body)
    # * bullet -> - bullet (line-initial only; inline *italic* is left alone)
    body = re.sub(r"^([ \t]*)\*[ \t]+", r"\1- ", body, flags=re.M)
    # NOTE:/TIP:/WARNING: callouts
    body = re.sub(r"^(NOTE|TIP|WARNING|IMPORTANT|WARN|CAUTION):", r"**\1:**", body, flags=re.M)
    # collapse 3+ blank lines, trim trailing spaces
    body = re.sub(r"[ \t]+$", "", body, flags=re.M)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return title, body


def chunk_markdown(md: str):
    """Split into chunks on ``## `` (H2) boundaries; the pre-first-heading intro is chunk 0.
    Empty chunks are dropped. Returns a list of non-empty chunk texts."""
    parts = re.split(r"(?m)^(?=## )", md)
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------- #
#  Phantom gate (node types vs the live catalogue)                             #
# --------------------------------------------------------------------------- #
def _unqual(name: str) -> str:
    """The unqualified, version-stripped node-type name (kinefx::motionclip::2.0 -> motionclip).

    Version is stripped BEFORE the namespace split, because a ``::N.N`` version is itself a
    ``::``-delimited segment; splitting first would leave the version, not the name."""
    s = name.strip().lower().split("/")[-1]
    s = re.sub(r"::\d+(\.\d+)*$", "", s)     # namespaced version  ::2  ::2.0
    s = re.sub(r"-\d+\.\d+$", "", s)          # dashed dotted version  -2.0
    return re.split(r"::|--", s)[-1]          # unqualified last component


def _catalogue_dir(rag_root, build: str):
    """The live-catalogue directory for a build. It is named ``h<build>`` (e.g. h22.0.400);
    fall back to a bare ``<build>`` or any dir under catalog/ containing the build string."""
    base = Path(rag_root) / "catalog"
    for cand in (base / f"h{build}", base / build):
        if cand.is_dir():
            return cand
    hits = sorted(base.glob(f"*{build}*"))
    return hits[0] if hits else base / f"h{build}"


def load_catalogue_authority(rag_root, build: str) -> set:
    """Unqualified node-type names from the live catalogue ``rag/catalog/h<build>/*.json``."""
    auth = set()
    cat = _catalogue_dir(rag_root, build)
    for f in sorted(glob.glob(str(cat / "*.json"))):
        if Path(f).name.startswith("_"):
            continue
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        types = data.get("types")
        if isinstance(types, dict):
            for k in types:
                auth.add(_unqual(k))
    return auth


def node_refs(text: str) -> set:
    """OP-context node references from ``[Node:ctx/type]`` markup (apex is exempt)."""
    return {(ctx, typ) for ctx, typ in NODE_XREF.findall(text) if ctx not in APEX_EXEMPT}


def phantom_hits(refs, authority) -> list:
    """The node references whose unqualified type is absent from the authority (sorted)."""
    return sorted({f"{ctx}/{typ}" for ctx, typ in refs if _unqual(typ) not in authority})


# --------------------------------------------------------------------------- #
#  Records + stamp                                                             #
# --------------------------------------------------------------------------- #
def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _open_scope(writers, out_dir, scope):
    if scope not in writers:
        writers[scope] = (out_dir / f"{scope}.jsonl").open("w", encoding="utf-8")
    return writers[scope]


def build(hfs, rag_root, build_str, *, out_dir=None, quar_dir=None):
    """Ingest every help page into ``rag/corpus/h22_prose/<scope>.jsonl`` + quarantine.

    Returns the stat dict the stamp records. Quarantine rows are metadata-only (id, page,
    failing refs, reason, sha) so the reviewable list carries no EULA prose body.
    """
    rag_root = Path(rag_root)
    out_dir = Path(out_dir) if out_dir else rag_root / "corpus" / "h22_prose"
    quar_dir = Path(quar_dir) if quar_dir else rag_root / "quarantine" / "prose"
    out_dir.mkdir(parents=True, exist_ok=True)
    quar_dir.mkdir(parents=True, exist_ok=True)
    authority = load_catalogue_authority(rag_root, build_str)

    writers, qwriters = {}, {}
    scopes, pages, chunks, quar = set(), 0, 0, 0
    try:
        for scope, page, raw, suffix in iter_pages(hfs):
            scopes.add(scope)
            pages += 1
            title, md = wiki_to_markdown(raw)
            source = f"hfs:{build_str}:$HFS/houdini/help/{suffix}"
            for idx, text in enumerate(chunk_markdown(md)):
                hits = phantom_hits(node_refs(text), authority)
                rec_id = f"h22:{page}#{idx}"
                if hits:
                    _open_scope(qwriters, quar_dir, scope).write(json.dumps({
                        "id": rec_id, "scope": scope, "page": page, "title": title,
                        "chunk_index": idx, "failing_refs": hits,
                        "reason": ("phantom node reference(s) absent from live catalogue "
                                   f"rag/catalog/{build_str}: " + ", ".join(hits)),
                        "content_sha": _sha(text), "build": build_str, "licence": LICENCE,
                    }, ensure_ascii=False) + "\n")
                    quar += 1
                    continue
                _open_scope(writers, out_dir, scope).write(json.dumps({
                    "id": rec_id, "scope": scope, "page": page, "title": title,
                    "chunk_index": idx, "text": text, "source": source,
                    "build": build_str, "content_sha": _sha(text), "licence": LICENCE,
                }, ensure_ascii=False) + "\n")
                chunks += 1
    finally:
        for h in list(writers.values()) + list(qwriters.values()):
            h.close()

    stats = {"scope_count": len(scopes), "page_count": pages,
             "chunk_count": chunks, "quarantine_count": quar}
    write_stamp(out_dir, stats, build_str)
    return stats


def write_stamp(out_dir, stats, build_str):
    stamp = {
        "build": build_str,
        "scope_count": stats["scope_count"],
        "page_count": stats["page_count"],
        "chunk_count": stats["chunk_count"],
        "quarantine_count": stats["quarantine_count"],
        "ingest_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "help_archive_sha": _file_sha(__file__),
        "producer": "hython rag/ingest/help_archive.py --build",
        "licence_note": "corpus chunks are SideFX-EULA and gitignored; this stamp is committed",
    }
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "STAMP.json").write_text(
        json.dumps(stamp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return stamp


# --------------------------------------------------------------------------- #
#  Target 2: phantom_gate_status                                               #
# --------------------------------------------------------------------------- #
def _status(stamp_build, live_build) -> str:
    """CURRENT when the stamp equals the running build, STALE when it differs, UNKNOWN when
    either is unavailable. UNKNOWN is never a pass -- an unmeasurable build stays UNKNOWN."""
    if not stamp_build or not live_build:
        return "UNKNOWN"
    return "CURRENT" if str(stamp_build) == str(live_build) else "STALE"


def phantom_gate_status(stamp_path, live_build) -> dict:
    """Read the corpus stamp and compare its build to the running build."""
    stamp_path = Path(stamp_path)
    stamp_build = None
    if stamp_path.is_file():
        try:
            stamp_build = json.loads(stamp_path.read_text(encoding="utf-8")).get("build")
        except ValueError:
            stamp_build = None
    return {"status": _status(stamp_build, live_build),
            "stamp_build": stamp_build, "live_build": live_build,
            "stamp": str(stamp_path)}


def resolve_live_build():
    """The running Houdini build: hou if inside hython, else $SYNAPSE_LIVE_BUILD, else None."""
    try:
        import hou  # type: ignore
        return hou.applicationVersionString()
    except Exception:
        return os.environ.get("SYNAPSE_LIVE_BUILD") or None


def resolve_hfs():
    hfs = os.environ.get("HFS")
    if hfs:
        return hfs
    try:
        import hou  # type: ignore
        h = hou.getenv("HFS")
        if h:
            return h
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
#  CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="H22 prose corpus builder + phantom_gate_status")
    ap.add_argument("--build", action="store_true", help="ingest $HFS help -> corpus + STAMP")
    ap.add_argument("--status", action="store_true", help="phantom_gate_status: CURRENT/STALE")
    ap.add_argument("--rag-root", default=str(REPO / "rag"))
    a = ap.parse_args(argv)
    out_dir = Path(a.rag_root) / "corpus" / "h22_prose"

    if a.status:
        st = phantom_gate_status(out_dir / "STAMP.json", resolve_live_build())
        print(json.dumps(st, indent=2))
        return {"CURRENT": 0, "STALE": 1, "UNKNOWN": 2}[st["status"]]

    if a.build:
        build_str = resolve_live_build()
        hfs = resolve_hfs()
        if not build_str:
            print("BLOCKED: no running Houdini build (run under hython, or set SYNAPSE_LIVE_BUILD)",
                  file=sys.stderr)
            return 2
        if not hfs:
            print("BLOCKED: $HFS not resolvable (run under hython, or set HFS)", file=sys.stderr)
            return 2
        stats = build(hfs, a.rag_root, build_str)
        print(json.dumps({"build": build_str, **stats,
                          "stamp": str(out_dir / "STAMP.json")}, indent=2))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
