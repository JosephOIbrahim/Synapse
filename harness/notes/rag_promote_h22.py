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
"""
import io, json, os

SRC = "harness/notes/ingest/h22_node_corpus.i1-orchestrator.json"
DST = "rag/corpus/h22_nodes.json"

src = json.load(open(SRC, encoding="utf-8"))
entries = src.get("entries") or []

kept, dropped = [], []
for e in entries:
    if e.get("live_type_matched") and e.get("tier") == "VERIFIED-DOC":
        kept.append({
            "type": e.get("live_type"),
            "context": e.get("context"),
            "label": e.get("runtime_label"),
            "summary": e.get("summary"),
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

out = {
    "schema": "h22_node_corpus/v1",
    "build": src.get("build"),
    "truth_tier": "VERIFIED-DOC",
    "gate": ("Entries are filtered AT BUILD TIME on live_type_matched, which I1 "
             "established by probing each documented type against the running "
             "catalogue. A phantom is not filtered at read time - it is never "
             "written here. INGEST-01 required a gate before wiring; this is it."),
    "source_archive": src.get("source_archive"),
    "producer": "harness/notes/rag_promote_h22.py",
    "counts": {"kept": len(kept), "excluded": len(dropped)},
    "excluded": dropped,
    "entries": kept,
}

os.makedirs(os.path.dirname(DST), exist_ok=True)
with io.open(DST, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, indent=1)

print("  kept     :", len(kept))
print("  excluded :", len(dropped))
for d in dropped:
    print("     %-10s %-24s %s" % (d["context"], d["stem"], d["why"]))
print("  written  : %s  (%d KB)" % (DST, os.path.getsize(DST) / 1024))
print()
k = kept[0]
print("  sample entry:")
for f_ in ("type", "context", "label", "help_key"):
    print("     %-10s %s" % (f_, str(k.get(f_))[:70]))
print("     summary    %s" % str(k.get("summary"))[:70])
print("     parameters %s" % (("%d" % len(k["parameters"])) if isinstance(k.get("parameters"), (list, dict)) else str(k.get("parameters"))[:40]))
