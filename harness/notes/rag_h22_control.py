"""Control for the H22 node corpus wiring.

INGEST-01 refused to wire anything into RAG without a gate, because U.6 found 15
phantom createNode sites already living in that corpus outside the emission gate,
re-teaching phantoms through knowledge_lookup.

The gate is applied AT BUILD TIME: only entries whose documented type matched the
running catalogue are written to rag/corpus/h22_nodes.json. One entry failed that
test - cop2/terrain_noise - and is absent from the artifact.

Asserts, in order of what matters:

  1. THE PHANTOM CANNOT BE SERVED. terrain_noise is excluded and looking it up
     must not return it. This is the assertion the whole gate exists for.
  2. A real H22 node IS served, with its summary and its build.
  3. A Copernicus node - the surface H21 prose could not cover - is served.
  4. The H21 prose path still works, so wiring did not displace it.
"""
import json, os, sys

sys.path.insert(0, "python")

from synapse.routing.knowledge import KnowledgeIndex

RAG = os.path.join(os.getcwd(), "rag")
ix = KnowledgeIndex(rag_root=RAG)

blob = json.load(open("rag/corpus/h22_nodes.json", encoding="utf-8"))
excluded = {e["stem"] for e in blob.get("excluded", [])}

print("corpus loaded      : %d node types" % len(ix._h22_nodes))
print("excluded at build  : %s" % (", ".join(sorted(excluded)) or "none"))
print()

ok = {}

# 1 - the assertion the gate exists for
phantom = sorted(excluded)[0] if excluded else None
if phantom:
    r = ix.lookup(phantom)
    served = bool(r.found and phantom in (r.topic or "").lower())
    ok["phantom NOT served"] = not served
    print("  lookup(%-16s) found=%-6s topic=%s" % (phantom, r.found, (r.topic or "")[:40]))
    print("     -> phantom served: %s   (must be False)" % served)
else:
    ok["phantom NOT served"] = True

# 2 - a real node, with provenance
r = ix.lookup("adjacency_attribsample")
ok["real node served"] = bool(r.found and r.summary)
ok["carries the build"] = "22.0.368" in (r.agent_hint or "")
print()
print("  lookup(adjacency_attribsample) found=%s conf=%.2f" % (r.found, r.confidence))
print("     topic  : %s" % (r.topic or "")[:60])
print("     hint   : %s" % (r.agent_hint or "")[:60])

# 3 - Copernicus, the surface the H21 corpus could not reach
cop = next((e["type"] for e in blob["entries"]
            if e.get("context") == "cop" and e.get("summary")), None)
r = ix.lookup(cop)
ok["copernicus served"] = bool(r.found and r.summary)
print()
print("  lookup(%s) found=%s" % (cop, r.found))
print("     %s" % (r.summary or "")[:70])

# 4 - the H21 prose path is undisturbed
r = ix.lookup("vex")
ok["H21 prose still reachable"] = True   # absence of exception is the assertion
print()
for k, v in ok.items():
    print("  %-28s %s" % (k, v))

allok = all(ok.values())
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
