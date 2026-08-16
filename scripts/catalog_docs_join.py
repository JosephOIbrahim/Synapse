"""Join help-cache docs onto the build-keyed node catalog -- honestly.

Second phase of the schema-catalog substrate (target 4). Reads the already-dumped
``rag/catalog/h<build>/<Category>.json`` files and, for every node row, attaches a
``doc`` field pulled from Houdini's local help-cache ASTs at

    C:/Users/User/OneDrive/Documents/houdini22.0/config/Help/cache/nodes/<ctx>/<name>.json

THE CACHE IS VISITED-PAGES-ONLY. It contains only help pages the artist actually
opened, so most rows will NOT get a doc -- and that is correct. **Absent docs stay
absent. Nothing is ever synthesized from a node name or from model memory.** A
``doc`` field appears on a row only when a real cache page for that exact
(context, internal[, namespace, version]) was found on disk; its text is copied
verbatim from the cache. This is the docs mirror of FP1: the doc is what the
binary's help system recorded, or it is nothing.

The cache page carries ``attrs`` (context/internal/namespace/version -- the
authoritative join key), ``title``, ``summary``, and ``included`` (parm-include
fragment refs, e.g. ``/nodes/cop/_input_descriptions``). We index by the attrs
key (not by guessing filenames), copy title+summary+since, and RESOLVE each
parm-include ref to whether its fragment file is present in the cache (resolved,
not synthesized).

This phase is pure Python (no ``hou``) so it runs in CI. It does NOT recompute a
category's ``blake2b`` -- that stamp is the binary-truth hash over the parm
surface and must stay stable regardless of which help pages happened to be
visited. Doc coverage is recorded in a ``docs_join`` block per file and in
``_docs_report.json``.

RUN (after scripts/build_node_catalog.py):

    python scripts/catalog_docs_join.py
    python scripts/catalog_docs_join.py --dir rag/catalog/h22.0.400 --cache "<help cache>"

DETERMINISM: sorted iteration, verbatim copy, no wall-clock stamp.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = _REPO / "rag" / "catalog" / "h22.0.400"
DEFAULT_CACHE = Path(
    "C:/Users/User/OneDrive/Documents/houdini22.0/config/Help/cache"
)

# hou nodeTypeCategory name -> help-cache context dir. Only the mappings whose
# context dir exists in the cache matter; unmapped categories simply get no docs
# (honest: those node families have no help pages under this cache layout).
CATEGORY_TO_CONTEXT = {
    "Sop": "sop", "Cop": "cop", "Cop2": "cop2", "Chop": "chop", "Dop": "dop",
    "Lop": "lop", "Vop": "vop", "Object": "obj", "Driver": "out", "Top": "top",
    "Shop": "shop", "Manager": "manager",
}


def _text(v) -> str | None:
    """Cache title/summary are lists of strings; join verbatim, or None."""
    if isinstance(v, list):
        s = " ".join(str(x) for x in v).strip()
        return s or None
    if isinstance(v, str):
        return v.strip() or None
    return None


def index_cache(cache_root: Path) -> tuple[dict, list]:
    """Walk the node-help cache, index by (context, internal, namespace, version).

    Returns (index, errors). index[key] = {title, summary, since, cache_rel,
    includes:[...]}. ``key`` is (context, internal, namespace_or_'', version_or_'')."""
    index: dict = {}
    errors: list = []
    nodes_root = cache_root / "nodes"
    if not nodes_root.is_dir():
        errors.append(f"cache nodes dir absent: {nodes_root}")
        return index, errors
    present_files = set()
    # First pass: record every cache file's relative path (for include resolution).
    for fp in nodes_root.rglob("*.json"):
        present_files.add(("/" + fp.relative_to(cache_root).as_posix()).replace(".json", ""))
    for fp in sorted(nodes_root.rglob("*.json")):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 -- a torn/odd cache file is skipped
            errors.append(f"unreadable cache file {fp.name}: {type(e).__name__}")
            continue
        if not isinstance(d, dict):
            continue
        attrs = d.get("attrs") or {}
        if attrs.get("type") != "node":
            continue  # only node help pages carry a joinable row identity
        ctx = attrs.get("context")
        internal = attrs.get("internal")
        if not ctx or not internal:
            continue
        ns = attrs.get("namespace") or ""
        ver = attrs.get("version") or ""
        includes = []
        for inc in (d.get("included") or []):
            if isinstance(inc, str):
                includes.append({"ref": inc, "resolved": inc in present_files})
        index[(ctx, internal, ns, ver)] = {
            "title": _text(d.get("title")),
            "summary": _text(d.get("summary")),
            "since": attrs.get("since"),
            "cache_rel": fp.relative_to(cache_root).as_posix(),
            "includes": includes,
        }
    return index, errors


def _split_type(type_name: str) -> tuple[str, str, str]:
    """`kinefx::twoboneik::2.0` -> (namespace='kinefx', base='twoboneik', version='2.0').
    `box` -> ('', 'box', ''). Version = trailing purely-numeric-dotted segment."""
    parts = type_name.split("::")
    version = ""
    if len(parts) > 1 and parts[-1] and all(c in "0123456789." for c in parts[-1]):
        version = parts[-1]
        parts = parts[:-1]
    if len(parts) == 1:
        return "", parts[0], version
    return parts[0], "::".join(parts[1:]), version


def _lookup(index: dict, ctx: str, type_name: str, bare_bases: set):
    """Resolve a node's help page -> (hit, tier) or (None, None).

    ``exact`` and ``version_relaxed`` stay on the node's OWN namespace, so they
    can only ever match the same node. ``namespace_relaxed`` (a namespaced node
    borrowing a page whose cache attrs omit the namespace) is REFUSED whenever a
    bare same-base sibling exists in this catalog: that sibling exactly owns the
    page, so borrowing it would cross-attribute one node's doc to another. This
    is the karma/filecache/wedge Labs mis-join class -- absent stays absent
    rather than wrong."""
    ns, base, ver = _split_type(type_name)
    for key, tier in (((ctx, base, ns, ver), "exact"),
                      ((ctx, base, ns, ""), "version_relaxed")):
        if key in index:
            return index[key], tier
    if ns and base not in bare_bases:
        for key in ((ctx, base, "", ver), (ctx, base, "", "")):
            if key in index:
                return index[key], "namespace_relaxed"
    return None, None


def join_file(fp: Path, index: dict, cache_root: Path) -> dict:
    payload = json.loads(fp.read_text(encoding="utf-8"))
    cat = payload.get("category")
    ctx = CATEGORY_TO_CONTEXT.get(cat)
    types = payload.get("types") or {}
    # Bare (un-namespaced) base names present in THIS catalog -- a namespaced
    # node may not borrow the page one of these exactly owns (mis-join guard).
    bare_bases = {_split_type(tn)[1] for tn in types if _split_type(tn)[0] == ""}
    joined = 0
    tiers = {"exact": 0, "version_relaxed": 0, "namespace_relaxed": 0}
    for type_name in sorted(types):
        # Clear any prior doc first so a re-run is idempotent AND self-correcting
        # (a row that no longer resolves loses its stale doc instead of keeping it).
        types[type_name].pop("doc", None)
        if not ctx:
            continue
        hit, tier = _lookup(index, ctx, type_name, bare_bases)
        if hit is None:
            continue  # absent stays absent -- never synthesized
        doc = {"context": ctx, "cache": hit["cache_rel"], "match": tier}
        if hit["title"]:
            doc["title"] = hit["title"]
        if hit["summary"]:
            doc["summary"] = hit["summary"]
        if hit["since"]:
            doc["since"] = hit["since"]
        if hit["includes"]:
            doc["includes"] = hit["includes"]
        types[type_name]["doc"] = doc
        joined += 1
        tiers[tier] += 1
    payload["docs_join"] = {
        "context": ctx,
        "cache_root": str(cache_root).replace("\\", "/"),
        "joined": joined,
        "tiers": tiers,
        "total": len(types),
        "note": ("visited-pages-only; absent docs stay absent, never "
                 "synthesized; each doc records its join tier ('match'); a "
                 "namespaced node never borrows a bare sibling's page. Binary "
                 "blake2b above is unchanged by this join."),
    }
    fp.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    return {"category": cat, "context": ctx, "joined": joined, "total": len(types)}


def main() -> int:
    argv = sys.argv[1:]
    catalog_dir = DEFAULT_CATALOG
    cache_root = DEFAULT_CACHE
    i = 0
    while i < len(argv):
        if argv[i] == "--dir" and i + 1 < len(argv):
            catalog_dir = Path(argv[i + 1]); i += 1
        elif argv[i] == "--cache" and i + 1 < len(argv):
            cache_root = Path(argv[i + 1]); i += 1
        i += 1

    if not catalog_dir.is_dir():
        sys.stdout.write(f"catalog dir absent: {catalog_dir}\n")
        return 2

    index, cache_errors = index_cache(cache_root)
    sys.stdout.write(f"DOCS JOIN: cache index={len(index)} node-help pages "
                     f"({len(cache_errors)} cache errors) from {cache_root}\n")

    report_rows = []
    total_joined = 0
    for fp in sorted(catalog_dir.glob("*.json")):
        if fp.name.startswith("_") or fp.name == "apex_callbacks.json":
            continue
        row = join_file(fp, index, cache_root)
        report_rows.append(row)
        total_joined += row["joined"]
        if row["joined"] or row["context"]:
            sys.stdout.write(f"  {row['category']}: joined {row['joined']}/{row['total']} "
                             f"(ctx={row['context']})\n")

    # Build key comes from the dump's own manifest (robust + deterministic
    # regardless of the output dir's name), falling back to the h<build> path.
    build = None
    try:
        build = json.loads((catalog_dir / "_manifest.json").read_text(encoding="utf-8")).get("build")
    except Exception:  # noqa: BLE001
        pass
    if not build and catalog_dir.name.startswith("h"):
        build = catalog_dir.name[1:]
    report = {
        "schema": "node_catalog_docs_report/v1",
        "build": build,
        "cache_root": str(cache_root).replace("\\", "/"),
        "cache_index_size": len(index),
        "total_docs_joined": total_joined,
        "cache_errors": sorted(cache_errors),
        "by_category": sorted(report_rows, key=lambda r: r["category"] or ""),
        "generated": {"by": "scripts/catalog_docs_join.py",
                      "note": "visited-pages-only; deterministic; never synthesized"},
    }
    (catalog_dir / "_docs_report.json").write_text(
        json.dumps(report, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    sys.stdout.write(f"DONE: total docs joined={total_joined} -> {catalog_dir}/_docs_report.json\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
