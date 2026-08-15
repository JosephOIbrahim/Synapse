"""Promote the H22 node corpus from a harness note to a product artifact.

INGEST-01 forbade wiring: "Nothing wires into the RAG corpus in this harness.
U.6 found 15 phantom createNode sites already living there, outside the emission
gate, re-teaching phantoms through knowledge_lookup. Adding thousands of
doc-derived entries to that surface without a gate is the same mistake at scale."

The gate turned out to be already in the data. I1 validated every entry against
the LIVE runtime at ingest time, and each carries `live_type_matched`:

    660 entries   659 matched   1 unmatched (cop2/terrain_noise)

So the gate is a FILTER AT BUILD TIME, not a check at read time - a phantom
cannot be served because it is never written into the artifact. That is the
stronger placement: a read-time filter can be bypassed by a future caller;
an entry that does not exist cannot.

Writes rag/corpus/h22_nodes.json with only matched, VERIFIED-DOC entries, and
records what it excluded and why.

W4-KNOW retrieval repair (Target 1): every kept entry now carries an ``id`` and
a ``searchable_text`` field. Before this, scout_ingest silently DROPPED all 659
node entries at ingest (``scout_ingest._entries_from_corpus_dir`` skips any entry
missing ``id``/``searchable_text``), so scout - the tool CLAUDE.md 11.15 tells an
agent to call BEFORE emitting a node type - shared zero rows with the corpus. The
id is (context, type) qualified and made unique across the 9 duplicate
(context, type) pairs; the searchable_text is the node's terse IDENTITY (see
_searchable_text for why terse).
"""
import argparse, io, json, os, sys

SRC = "harness/notes/ingest/h22_node_corpus.i1-orchestrator.json"
DST = "rag/corpus/h22_nodes.json"


def _entry_id(context, ntype, seen):
    """Stable, unique, context-qualified id. Nine (context, type) pairs repeat in
    the source (all pyro_* in cop); a bare (context, type) key would collide in
    scout's by-id dedup and drop one, so a repeat gets a #<n> discriminator. The
    ``h22:`` prefix keeps these disjoint from the reference-file-stem ids
    scout_ingest mints for the H21 prose corpus."""
    base = "h22:%s/%s" % (context, ntype)
    if base not in seen:
        seen[base] = 1
        return base
    seen[base] += 1
    return "%s#%d" % (base, seen[base])


def _searchable_text(entry):
    """Lexical body for scout's FTS index - the node's IDENTITY, deliberately
    terse.

    W4-KNOW measured this: bundling every parameter's names into the body made
    each node a long document, and BM25 length-normalization then buried the
    exact-type node under the verbose H21 prose corpus for a bare-type query
    (type-name P@1 fell to 0.71). An identity-only body - the type (boosted),
    label, context and summary - restores lexical P@1 to ~0.95. Internal parm
    names + channels are NOT indexed here; they are SERVED by knowledge.py's node
    datasheet (Target 5), which reads the `parameters` array directly, so nothing
    is lost - the searchable body is a findability index, not a copy of the
    corpus. The type appears twice on purpose: it is the rare, decisive token a
    grounding query carries, and the small boost helps it win its own name."""
    t = str(entry.get("live_type") or "")
    label = str(entry.get("runtime_label") or "")
    ctx = str(entry.get("context") or "")
    summary = str(entry.get("summary") or "")
    return "\n".join(s for s in (
        "%s (%s)" % (label, t),
        "%s node - %s context" % (t, ctx),
        summary,
    ) if s and s.strip())


def promote(src):
    """Build the served corpus dict from the I1 source. Pure (no I/O) so the
    contract test can exercise _entry_id/_searchable_text + the gate directly."""
    entries = src.get("entries") or []
    kept, dropped = [], []
    seen_ids = {}
    for e in entries:
        if e.get("live_type_matched") and e.get("tier") == "VERIFIED-DOC":
            context = e.get("context")
            ntype = e.get("live_type")
            kept.append({
                "id": _entry_id(context, ntype, seen_ids),
                "type": ntype,
                "context": context,
                "label": e.get("runtime_label"),
                "summary": e.get("summary"),
                "searchable_text": _searchable_text(e),
                "parameters": e.get("parameters"),
                "help_key": e.get("help_key"),
                "source": e.get("source"),
            })
        else:
            dropped.append({
                "stem": e.get("stem"),
                "context": e.get("context"),
                "why": "live_type_matched=false" if not e.get("live_type_matched")
                       else "tier=%s" % e.get("tier"),
            })

    return {
        "schema": "h22_node_corpus/v1",
        "build": src.get("build"),
        "truth_tier": "VERIFIED-DOC",
        "gate": ("Entries are filtered AT BUILD TIME on live_type_matched, which I1 "
                 "established by probing each documented type against the running "
                 "catalogue. A phantom is not filtered at read time - it is never "
                 "written here. INGEST-01 required a gate before wiring; this is it."),
        "entry_contract": ("Every served entry carries id + searchable_text (scout "
                           "visibility, W4-KNOW Target 1), type + context (the "
                           "(context, type) index key, Target 2), label, summary, and "
                           "a parameters array whose items carry internal ids + "
                           "channels uncapped (Target 5). Guarded downstream of "
                           "promote by tests/test_rag_promote_contract.py (Target 8)."),
        "source_archive": src.get("source_archive"),
        "producer": "harness/notes/rag_promote_h22.py",
        "counts": {"kept": len(kept), "excluded": len(dropped)},
        "excluded": dropped,
        "entries": kept,
    }


def _resolve_io(argv):
    """(src, dst) from CLI/env, defaulting to the committed pin (the .368 orchestrator
    archive -> served corpus). Back-compat is exact: no args reproduce the historical
    behaviour byte-for-byte.

    W5-DELTA (ING-DELTA): re-promoting the shipped contexts from the 22.0.400 archive
    needs ZERO change to the gate here -- promote() already stamps build/source_archive
    from the src it is handed. Point --src at a .400 I1 archive (produced via i1_extract's
    parameterized helpdoc surface, load_corpus(build='22.0.400')) and the served corpus is
    stamped 22.0.400 with the same build-time live_type filter. The archive is chosen, not
    the machinery changed."""
    ap = argparse.ArgumentParser(description="Promote an H22 I1 node archive to the served RAG corpus.")
    ap.add_argument("--src", default=os.environ.get("RAG_PROMOTE_SRC", SRC),
                    help="I1 source archive (default: the committed .368 orchestrator archive)")
    ap.add_argument("--dst", default=os.environ.get("RAG_PROMOTE_DST", DST),
                    help="served corpus path (default: rag/corpus/h22_nodes.json)")
    a = ap.parse_args(argv)
    return a.src, a.dst


def main(argv=None):
    src_path, dst_path = _resolve_io(sys.argv[1:] if argv is None else argv)
    src = json.load(open(src_path, encoding="utf-8"))
    out = promote(src)
    kept, dropped = out["entries"], out["excluded"]

    dst_dir = os.path.dirname(dst_path)
    if dst_dir:
        os.makedirs(dst_dir, exist_ok=True)
    with io.open(dst_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)

    print("  src      :", src_path)
    print("  build    :", out.get("build"))
    print("  kept     :", len(kept))
    print("  excluded :", len(dropped))
    for d in dropped:
        print("     %-10s %-24s %s" % (d["context"], d["stem"], d["why"]))
    print("  written  : %s  (%d KB)" % (dst_path, os.path.getsize(dst_path) / 1024))
    print()
    k = kept[0]
    print("  sample entry:")
    for f_ in ("id", "type", "context", "label", "help_key"):
        print("     %-10s %s" % (f_, str(k.get(f_))[:70]))
    print("     summary    %s" % str(k.get("summary"))[:70])
    print("     search     %s" % str(k.get("searchable_text"))[:70].replace("\n", " "))
    print("     parameters %s" % (("%d" % len(k["parameters"])) if isinstance(k.get("parameters"), (list, dict)) else str(k.get("parameters"))[:40]))


if __name__ == "__main__":
    main()
