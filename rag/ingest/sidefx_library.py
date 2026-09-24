"""Build immutable, searchable SideFX help generations outside Houdini.

Two independently stamped sources: the installed help archives and the official
Markdown cache produced by sidefx_download. Raw source bytes are retained locally.
No network, model, hou, or install-time dependency; SQLite FTS5 is built here, never
in the query path. APEX callback pages are archived but stay out of docs retrieval.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
import time
from urllib.parse import quote
import zipfile

from rag.ingest.help_archive import wiki_to_markdown
from rag.ingest.sidefx_markdown import _chunks
from rag.ingest import help_archive, sidefx_markdown

SCHEMA = "sidefx_library/v1"
BASE = "https://www.sidefx.com/docs/houdini/"
MAX_PAGE = 16 * 1024 * 1024
MAX_CHUNK = 6000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            name = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name is not None and name.exists():
            name.unlink()


def confined(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("invalid relative source path")
    parts = PurePosixPath(relative)
    path = (root / relative).resolve()
    if parts.is_absolute() or any(p in (".", "..") for p in parts.parts) or not path.is_relative_to(root.resolve()):
        raise ValueError("source path escapes corpus root")
    return path


@contextmanager
def writer_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".ingest.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "started": time.time()}, sort_keys=True).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _installed_build(hfs: Path) -> str:
    header = hfs / "toolkit/include/SYS/SYS_Version.h"
    match = re.search(r'#define\s+SYS_VERSION_FULL\s+"(\d+\.\d+\.\d+)"', header.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("cannot determine installed help build from SYS_Version.h")
    return match.group(1)


def _raw_cache(root: Path, data: bytes, suffix: str) -> tuple[str, str]:
    digest = sha(data)
    rel = f"cache/installed/{digest[:2]}/{digest}{suffix}"
    path = confined(root, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or sha(path.read_bytes()) != digest:
        # Content-addressed and single-writer; incomplete cache files never publish.
        path.write_bytes(data)
    return rel, digest


def snapshot_installed(root: Path, hfs: Path) -> dict:
    """Enumerate *all* help .txt pages, including root/loose files and licenses.

    The older archive importer skipped licenses, root files and most loose trees.
    Inventory includes them here; loose help overrides archive pages, as installed.
    Zip members are read, never extracted to paths from the archive.
    """
    build = _installed_build(hfs)
    help_dir = hfs / "houdini/help"
    if not help_dir.is_dir():
        raise ValueError("installed help directory is unavailable")
    captured = datetime.now(timezone.utc).isoformat()
    pages, overrides = {}, []
    try:
        prior = json.loads((root / "installed_manifest.json").read_text(encoding="utf-8"))
        prior_pages = prior.get("pages", {}) if prior.get("schema") == "sidefx_installed_manifest/v1" else {}
    except (OSError, ValueError):
        prior_pages = {}

    def record(page, data, origin):
        if len(data) > MAX_PAGE:
            raise ValueError(f"installed page exceeds limit: {page}")
        if ".." in PurePosixPath(page).parts or page.startswith("/"):
            raise ValueError("invalid installed page name")
        if page in pages:
            overrides.append({"page": page, "prior": pages[page]["origin"], "current": origin})
        rel, digest = _raw_cache(root, data, ".txt")
        old = prior_pages.get(page, {})
        fetched = (old.get("fetched_at", captured)
                   if (old.get("sha256"), old.get("docs_build"), old.get("origin")) == (digest, build, origin)
                   else captured)
        pages[page] = {"path": rel, "sha256": digest, "origin": origin,
                       "source_url": BASE + quote(page[:-4] + ".md", safe="/"),
                       "docs_build": build, "docs_build_basis": "installed_SYS_Version.h",
                       "fetched_at": fetched, "format": "sidefx_wiki"}

    archives = []
    for archive in sorted(help_dir.glob("*.zip")):
        with zipfile.ZipFile(archive) as stream:
            infos = [i for i in stream.infolist() if not i.is_dir() and i.filename.lower().endswith(".txt")]
            for info in infos:
                if info.file_size > MAX_PAGE:
                    raise ValueError("installed page exceeds limit")
                record(f"{archive.stem}/{info.filename}", stream.read(info), f"{archive.name}:{info.filename}")
        archives.append({"path": str(archive), "pages": len(infos), "size": archive.stat().st_size})
    for path in sorted(help_dir.rglob("*.txt")):
        if path.is_symlink() or not path.resolve().is_relative_to(help_dir.resolve()):
            raise ValueError("installed help symlink leaves the source directory")
        record(path.relative_to(help_dir).as_posix(), path.read_bytes(), str(path))
    if not pages:
        raise ValueError("installed help contains no text pages")
    manifest = {"schema": "sidefx_installed_manifest/v1", "docs_build": build,
                "hfs": str(hfs), "captured_at": captured, "pages": pages,
                "archives": archives, "overrides": overrides, "complete": True}
    atomic_json(root / "installed_manifest.json", manifest)
    return manifest


def chunks(text: str):
    """Headings plus bounded paragraph windows; raw text remains in the cache."""
    for heading, anchor, section in _chunks(text):
        start = 0
        while start < len(section):
            end = min(start + MAX_CHUNK, len(section))
            if end < len(section):
                cut = section.rfind("\n", start + MAX_CHUNK // 2, end)
                if cut > start:
                    end = cut + 1
            body = section[start:end].strip()
            if body:
                yield heading, anchor, body
            start = end


def read_checked(root: Path, record: dict) -> bytes:
    path = confined(root, record["path"])
    with path.open("rb") as stream:
        data = stream.read(MAX_PAGE + 1)
    if len(data) > MAX_PAGE or sha(data) != record.get("sha256"):
        raise ValueError(f"cached source verification failed: {record['path']}")
    return data


def build_library(root: Path, *, include_web: bool = False,
                  allow_incomplete_web: bool = False, runtime_build: str | None = None) -> dict:
    """Validate every input before atomically publishing a new immutable database."""
    root = root.resolve()
    installed = json.loads((root / "installed_manifest.json").read_text(encoding="utf-8"))
    if installed.get("schema") != "sidefx_installed_manifest/v1" or not installed.get("complete"):
        raise ValueError("installed snapshot is incomplete or invalid")
    sources = [("installed", installed)]
    if include_web:
        web = json.loads((root / "web_manifest.json").read_text(encoding="utf-8"))
        if web.get("schema") != "sidefx_web_manifest/v1":
            raise ValueError("invalid web snapshot schema")
        complete = (web.get("closure_complete") and not web.get("pending")
                    and all(row.get("status") == "ok" for row in web["pages"].values()))
        if not complete and not allow_incomplete_web:
            raise ValueError("web crawl is incomplete; prior index preserved")
        sources.append(("web", web))
    provenance = []
    for kind, manifest in sources:
        for page, row in sorted(manifest["pages"].items()):
            if kind == "web" and row.get("status") != "ok":
                continue
            # HTTP revalidation timestamps/validators do not change the emitted
            # citation or searchable content; avoid rebuilding 100k chunks on
            # a 304-only refresh. All response-affecting provenance is retained.
            emitted = {k: v for k, v in row.items()
                       if k not in {"validated_at", "etag", "last_modified", "bytes", "status", "error"}}
            provenance.append((kind, page, emitted))
    state = [{"source": kind, "closure_complete": m.get("closure_complete"),
              "fetch_complete": m.get("fetch_complete"),
              "pages": [(p, r.get("status", "ok"), r.get("error")) for p, r in sorted(m["pages"].items())]}
             for kind, m in sources]
    generation = sha(json.dumps({"inputs": provenance, "state": state, "schema": SCHEMA,
                                "producer": sha(Path(__file__).read_bytes()),
                                "converter": sha(Path(help_archive.__file__).read_bytes()),
                                "chunker": sha(Path(sidefx_markdown.__file__).read_bytes()),
                                "runtime": runtime_build}, sort_keys=True).encode())[:24]
    relative = f"indexes/{generation}.sqlite3"
    final = root / relative
    final.parent.mkdir(parents=True, exist_ok=True)
    # Always verify input hashes even when an identical generation already exists.
    if final.exists():
        for kind, manifest in sources:
            for row in manifest["pages"].values():
                if kind == "installed" or row.get("status") == "ok":
                    read_checked(root, row)
        # Some shipped SQLite versions implement the FTS5 integrity probe with
        # an internal write transaction. This is the offline publisher (under
        # its writer lock); quick_check does not change published content.
        with sqlite3.connect(final) as existing:
            meta = {k: json.loads(v) for k, v in existing.execute("SELECT key,value FROM meta")}
            count = existing.execute("SELECT count(*) FROM chunks").fetchone()[0]
            if (meta.get("schema") != SCHEMA or meta.get("generation") != generation
                    or count != meta.get("coverage", {}).get("chunks")
                    or existing.execute("PRAGMA quick_check").fetchone()[0] != "ok"):
                raise ValueError("existing generation failed validation; prior pointer preserved")
        pointer = {"schema": "sidefx_library_pointer/v1", "database": relative,
                   "generation": generation, "coverage": meta["coverage"],
                   "published_at": datetime.now(timezone.utc).isoformat()}
        atomic_json(root / "current.json", pointer)
        atomic_json(root / "coverage.json", meta["coverage"])
        return pointer
    coverage = {"sources": {}, "apex_archived_not_indexed": 0, "empty_pages": 0,
                "indexed_pages": 0, "chunks": 0, "generation": generation}
    fd, temp = tempfile.mkstemp(prefix=".sidefx-", suffix=".sqlite3", dir=final.parent)
    os.close(fd)
    temp = Path(temp)
    con = sqlite3.connect(temp)
    try:
        con.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE chunks(id TEXT PRIMARY KEY,source_url TEXT,title TEXT,body TEXT,metadata TEXT,domain TEXT);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(id UNINDEXED,body,tokenize='porter unicode61');
        """)
        for kind, manifest in sources:
            stats = {"pages": len(manifest["pages"]), "cached": 0, "indexed": 0,
                     "apex_federated": 0, "failed": 0}
            for page, row in sorted(manifest["pages"].items()):
                if kind == "web" and row.get("status") != "ok":
                    stats["failed"] += 1
                    continue
                data = read_checked(root, row)
                stats["cached"] += 1
                if page.startswith("nodes/apex/"):
                    stats["apex_federated"] += 1
                    coverage["apex_archived_not_indexed"] += 1
                    continue
                raw = data.decode("utf-8", errors="replace")
                if kind == "installed":
                    title, body = wiki_to_markdown(raw)
                    # The conversion is intentionally not a wiki renderer. Keep
                    # expansion/anchor directives visible as source evidence so
                    # missing includes are not silently presented as full prose.
                    directives = "\n".join(line for line in raw.splitlines()
                                           if re.match(r"\s*(#(?:contentfrom|id):|:include\s|:list:)", line))
                    if directives:
                        body += "\n\n## Source directives (unexpanded)\n" + directives
                else:
                    body = raw
                    title_match = re.search(r"^#\s+(.+)", body, re.M)
                    title = title_match.group(1) if title_match else page
                title = title or page
                count = 0
                for count, (heading, anchor, text) in enumerate(chunks(body), 1):
                    identity = f"sidefx_library:{kind}:{page}#{count}"
                    url = row["source_url"]
                    if anchor:
                        url += "#" + quote(anchor, safe="")
                    meta = {"id": identity, "source": url, "source_url": row["source_url"],
                            "source_anchor": anchor, "docs_build": row.get("docs_build"),
                            "docs_build_basis": row.get("docs_build_basis", row.get("build_source", "unknown")),
                            "evidence_level": "document_only", "source_sha256": row["sha256"],
                            "content_sha256": sha(text.encode()), "heading": heading,
                            "fetched_at": row.get("fetched_at"), "raw_source_path": row["path"],
                            "source_origin": row.get("origin", row["source_url"]),
                            "source_format": "sidefx_wiki_unexpanded" if kind == "installed" else "markdown",
                            "source_url_basis": "derived_from_installed_path" if kind == "installed" else "fetched_official_url",
                            "snapshot_id": generation, "scope": "sidefx_docs",
                            "licence": "sidefx-documentation-local-use",
                            "type": "sidefx_installed_help" if kind == "installed" else "sidefx_markdown",
                            "runtime_build_at_import": runtime_build}
                    searchable = "\n".join((title, heading, text))
                    domain = "vex" if page.startswith("vex/") else "docs"
                    con.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                                (identity, row["source_url"], title, searchable, json.dumps(meta, sort_keys=True), domain))
                    con.execute("INSERT INTO chunks_fts(id,body) VALUES (?,?)", (identity, searchable))
                if count:
                    stats["indexed"] += 1
                    coverage["indexed_pages"] += 1
                    coverage["chunks"] += count
                else:
                    coverage["empty_pages"] += 1
            if kind == "web":
                stats["closure_complete"] = bool(manifest.get("closure_complete"))
                stats["fetch_complete"] = bool(manifest.get("fetch_complete", stats["failed"] == 0))
            coverage["sources"][kind] = stats
        if not coverage["chunks"]:
            raise ValueError("library has no searchable content")
        for key, value in {"schema": SCHEMA, "generation": generation, "coverage": coverage}.items():
            con.execute("INSERT INTO meta VALUES (?,?)", (key, json.dumps(value, sort_keys=True)))
        con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
        con.commit()
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        con.close()
        if not final.exists():
            os.replace(temp, final)
        else:
            # Same generation is immutable; do not replace beneath active readers.
            temp.unlink()
        pointer = {"schema": "sidefx_library_pointer/v1", "database": relative,
                   "generation": generation, "coverage": coverage,
                   "published_at": datetime.now(timezone.utc).isoformat()}
        atomic_json(root / "current.json", pointer)
        atomic_json(root / "coverage.json", coverage)
        return pointer
    finally:
        con.close()
        temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--hfs", type=Path, help="Snapshot installed help before indexing")
    parser.add_argument("--include-web", action="store_true")
    parser.add_argument("--allow-incomplete-web", action="store_true")
    parser.add_argument("--runtime-build")
    args = parser.parse_args(argv)
    with writer_lock(args.root):
        if args.hfs:
            snapshot_installed(args.root, args.hfs)
        result = build_library(args.root, include_web=args.include_web,
                               allow_incomplete_web=args.allow_incomplete_web,
                               runtime_build=args.runtime_build)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
