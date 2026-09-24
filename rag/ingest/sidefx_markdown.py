"""Import an explicit, bounded SideFX Markdown snapshot into Scout's row schema.

Offline only: this module never fetches, follows links, runs Houdini or calls a
model. The caller supplies local files and SHA256 values in a JSON manifest:

    {"schema": "sidefx_markdown_inputs/v1", "docs_build": "22.0.452",
     "runtime_build": "22.0.400", "fetched_at": "2026-09-24T17:00:00+00:00",
     "index": {"path": "llms.txt", "sha256": "..."},
     "pages": [{"path": "sopimport.md", "sha256": "...",
                "source_url": "https://www.sidefx.com/docs/houdini/nodes/lop/sopimport.md"}]}

The captured llms.txt must contain the declared build. That is an index stamp,
not proof that each page or the running Houdini implements every documented
feature. Every row remains document-only. APEX callback pages stay federated.
Only explicit anchors become URL fragments; heading slugs are never invented.

Use --manifest <file> --out <local-rag>/corpus/sidefx_docs.json. The existing
scout_ingest reader consumes that flat file on its next materialization. Keep
downloaded/generated SideFX text local and uncommitted; redistribution terms
have not been established by this importer. Publishing is one atomic replace,
after all inputs validate, so a failed refresh preserves the previous snapshot.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit, urlunsplit


INPUT_SCHEMA = "sidefx_markdown_inputs/v1"
OUTPUT_SCHEMA = "sidefx_markdown_snapshot/v1"
MAX_PAGES = 16
MAX_PAGE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
INDEX_URL = "https://www.sidefx.com/docs/houdini/llms.txt"
_BUILD = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_ANCHOR = re.compile(r'<a\s+id=[\"\']([^\"\']+)[\"\']\s*>\s*</a>', re.I)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def _build(value: object) -> tuple[int, ...]:
    if not isinstance(value, str) or not _BUILD.fullmatch(value):
        raise ValueError("build must be an explicit major.minor.build string")
    return tuple(int(n) for n in value.split("."))


def _read_checked(record: dict, base: Path) -> tuple[bytes, Path]:
    if not isinstance(record, dict):
        raise ValueError("each input must be a file record")
    raw_path = record.get("path")
    digest = record.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("each input requires a local path")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("each input requires a lowercase SHA256")
    path = (base / raw_path).resolve()
    # Inputs are confined to the manifest's own snapshot directory, including
    # symlink resolution. No absolute paths, traversal or arbitrary local reads.
    if Path(raw_path).is_absolute() or not path.is_relative_to(base):
        raise ValueError("input path must stay inside the snapshot directory")
    with path.open("rb") as stream:
        content = stream.read(MAX_PAGE_BYTES + 1)
    if len(content) > MAX_PAGE_BYTES:
        raise ValueError("page exceeds snapshot byte limit")
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError(f"SHA256 mismatch for {raw_path}")
    return content, path


def _page_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("page requires an official SideFX Markdown URL")
    parts = urlsplit(value)
    path = unquote(parts.path)
    if (parts.scheme != "https" or parts.netloc not in ("www.sidefx.com", "sidefx.com")
            or parts.query or parts.fragment or "\\" in path
            or any(segment in (".", "..") for segment in path.split("/"))
            or not path.startswith("/docs/houdini/") or not path.endswith(".md")):
        raise ValueError("page requires an official SideFX Markdown URL")
    if path.startswith("/docs/houdini/nodes/apex/"):
        raise ValueError("APEX callback knowledge remains federated; do not import it")
    return urlunsplit(("https", "www.sidefx.com", parts.path, "", ""))


def _chunks(text: str):
    """Yield (heading, explicit anchor or None, text), respecting code fences."""
    heading, anchor, lines = "", None, []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        match = _HEADING.match(line) if fence is None and not marker else None
        if match:
            if "\n".join(lines).strip():
                yield heading, anchor, "\n".join(lines).strip()
            raw_heading = match.group(1)
            found = _ANCHOR.search(raw_heading)
            anchor = found.group(1) if found else None
            heading = _ANCHOR.sub("", raw_heading).strip()
            lines = []
        lines.append(line)
    if "\n".join(lines).strip():
        yield heading, anchor, "\n".join(lines).strip()


def import_snapshot(manifest_path, out_path) -> dict:
    """Validate all local inputs, then atomically replace one complete corpus file."""
    manifest_path = Path(manifest_path).resolve()
    base = manifest_path.parent
    with manifest_path.open("rb") as stream:
        manifest_bytes = stream.read(MAX_PAGE_BYTES + 1)
    if len(manifest_bytes) > MAX_PAGE_BYTES:
        raise ValueError("manifest exceeds byte limit")
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema") != INPUT_SCHEMA:
        raise ValueError("unsupported input manifest schema")
    docs_build, runtime_build = manifest.get("docs_build"), manifest.get("runtime_build")
    docs_version, runtime_version = _build(docs_build), _build(runtime_build)
    captured = manifest.get("fetched_at")
    if not isinstance(captured, str) or datetime.fromisoformat(captured).tzinfo is None:
        raise ValueError("fetched_at requires an ISO timestamp with a timezone")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
        raise ValueError(f"snapshot requires 1..{MAX_PAGES} explicit pages")
    index, index_path = _read_checked(manifest.get("index"), base)
    stamps = set(_BUILD.findall(index.decode("utf-8")))
    if stamps != {docs_build}:
        raise ValueError("captured llms.txt build does not match docs_build")
    relation = ("same_build" if docs_version == runtime_version else
                "different_version" if docs_version[:2] != runtime_version[:2] else
                "ahead_of_runtime" if docs_version > runtime_version else "behind_runtime")
    entries, page_records, seen = [], [], set()
    input_paths = {manifest_path, index_path}
    total_bytes = len(index)
    for record in pages:
        if not isinstance(record, dict):
            raise ValueError("each page must be a file record")
        url = _page_url(record.get("source_url"))
        if url in seen:
            raise ValueError("duplicate page URL")
        seen.add(url)
        raw, path = _read_checked(record, base)
        input_paths.add(path)
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("snapshot exceeds total byte limit")
        text = raw.decode("utf-8-sig")
        if not text.strip() or not _HEADING.match(text.splitlines()[0]):
            raise ValueError("page must be non-empty Markdown with a title")
        page_records.append({"source_url": url, "sha256": record["sha256"], "bytes": len(raw)})
        for n, (heading, anchor, body) in enumerate(_chunks(text)):
            source = url + ("#" + anchor if anchor else "")
            entries.append({
                "id": f"sidefx-docs:{docs_build}:{urlsplit(url).path}#{n}",
                "type": "sidefx_markdown", "scope": "sidefx_docs",
                "source": source, "source_url": url, "source_anchor": anchor,
                "source_sha256": record["sha256"],
                "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "heading": heading, "searchable_text": body,
                "docs_build": docs_build, "docs_build_basis": "captured_root_index",
                "runtime_build_at_import": runtime_build,
                "build_relation_at_import": relation, "evidence_level": "document_only",
                "fetched_at": captured, "licence": "sidefx_terms_unverified",
            })
    snapshot_id = hashlib.sha256(manifest_bytes).hexdigest()
    for entry in entries:
        entry["snapshot_id"] = snapshot_id
    snapshot = {
        "schema": OUTPUT_SCHEMA, "snapshot_id": snapshot_id,
        "docs_build": docs_build, "runtime_build_at_import": runtime_build,
        "index": {"source_url": INDEX_URL, "sha256": manifest["index"]["sha256"]},
        "fetched_at": captured, "imported_at": datetime.now(timezone.utc).isoformat(),
        "pages": page_records, "entries": entries,
    }
    output = Path(out_path).resolve()
    if output.suffix != ".json" or output in input_paths:
        raise ValueError("output must be a separate .json corpus file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output.parent, prefix=".sidefx-", suffix=".tmp",
                                         delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(snapshot, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, output)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return {"path": str(output), "pages": len(page_records), "entries": len(entries),
            "docs_build": docs_build, "snapshot_id": snapshot_id}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(import_snapshot(args.manifest, args.out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
