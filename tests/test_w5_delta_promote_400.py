"""W5-DELTA / ING-DELTA -- pins the .400 re-promote invariants downstream of the promote.

The served rag/corpus/h22_nodes.json was re-promoted from the 22.0.400 help archive
(harness/notes/h22/w5_delta_build_400.py -> parameterized rag_promote_h22.py). These
tests pin, at a runtime checkpoint, the four guarantees the mission's acceptance and
crucible criteria stand on, so a future regen cannot silently break them:

  * FRESHNESS  the corpus build stamp == the resolved ratified build (the K.7
               corpus_stamp_fresh invariant, pinned here at test level too).
  * ZERO-LOSS  every (context,type) key AND every id served at .368 survives at
               >= its multiplicity (deletions forbidden; collisions keep both).
  * ANATOMY    no .400 corpus entry contradicts the live-verified compound-node
               anatomy (no karmamaterial* type; no 'instancer' type; the real
               copytopoints + componentgeometry ARE served).
  * BACK-COMPAT promote()'s build-time live_type gate is unchanged.

The .368 zero-loss baseline is the SLIM, committed manifest
harness/notes/h22/w5_delta_368_baseline.json (per-context counts + the (context,type)
multiset + the id set), so the guarantee survives the 8 MB backup's deletion.
"""
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "rag" / "corpus" / "h22_nodes.json"
BASELINE = ROOT / "harness" / "notes" / "h22" / "w5_delta_368_baseline.json"
LEDGER = ROOT / "harness" / "ingest_ledger.py"
PROMOTE = ROOT / "harness" / "notes" / "rag_promote_h22.py"


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _import(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def corpus():
    if not CORPUS.is_file():
        pytest.skip("served corpus not present")
    return _load(CORPUS)


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE.is_file():
        pytest.skip("W5-DELTA .368 baseline not present")
    return _load(BASELINE)


# --------------------------------------------------------------------------- #
#  FRESHNESS -- the K.7 corpus_stamp_fresh invariant, pinned at test level     #
# --------------------------------------------------------------------------- #
def test_corpus_build_equals_ratified(corpus):
    mod = _import(LEDGER, "w5delta_ingest_ledger")
    r = mod.resolve_ratified_build(str(ROOT))
    assert not r.get("error") and r.get("build"), "no ratified-build authority: %r" % r
    assert corpus.get("build") == r["build"], (
        "STALE corpus: build %r != ratified %r (via %s) -- K.7 would go red"
        % (corpus.get("build"), r["build"], r.get("source")))


def test_source_archive_names_the_400_build(corpus):
    assert "22.0.400" in str(corpus.get("source_archive") or ""), (
        "source_archive must name the .400 help archive: %r" % corpus.get("source_archive"))


# --------------------------------------------------------------------------- #
#  ZERO-LOSS -- deletions forbidden; collisions keep both                      #
# --------------------------------------------------------------------------- #
def test_zero_loss_context_type_multiset(corpus, baseline):
    served = Counter((e["context"], e["type"]) for e in corpus["entries"])
    lost = []
    for spec in baseline["context_type_multiset"]:
        key, mult = spec.rsplit("|", 1)
        ctx, typ = key.split("/", 1)
        if served[(ctx, typ)] < int(mult):
            lost.append("%s (was %s, now %d)" % (spec, mult, served[(ctx, typ)]))
    assert not lost, "LOST served (context,type) keys vs .368: %r" % lost[:20]


def test_zero_loss_ids(corpus, baseline):
    served_ids = set(e["id"] for e in corpus["entries"])
    missing = [i for i in baseline["ids"] if i not in served_ids]
    assert not missing, "lost served ids vs .368: %r" % missing[:20]


def test_per_context_counts_ge_baseline(corpus, baseline):
    served = Counter(e["context"] for e in corpus["entries"])
    for ctx, n in baseline["per_context_counts"].items():
        assert served[ctx] >= n, "%s dropped: %d < baseline %d" % (ctx, served[ctx], n)


# --------------------------------------------------------------------------- #
#  ANATOMY -- no entry contradicts the live-verified compound-node anatomy     #
# --------------------------------------------------------------------------- #
def test_no_karmamaterial_phantom_served(corpus):
    km = [(e["context"], e["type"]) for e in corpus["entries"]
          if "karmamaterial" in (e["type"] or "").lower()]
    assert not km, ("karmamaterial* served as a type (phantom) -- the anatomy doc says "
                    "the tab entry is a configured subnet, no such VOP type exists: %r" % km)


def test_no_instancer_type_served(corpus):
    ins = [(e["context"], e["type"]) for e in corpus["entries"] if e["type"] == "instancer"]
    assert not ins, ("'instancer' served as a type -- the anatomy doc says the instancer "
                     "tab resolves to type copytopoints: %r" % ins)


def test_real_solaris_types_served(corpus):
    served = set((e["context"], e["type"]) for e in corpus["entries"])
    assert ("lop", "copytopoints") in served, "copytopoints (the real instancer type) not served"
    assert ("lop", "componentgeometry") in served, "componentgeometry not served"


# --------------------------------------------------------------------------- #
#  BACK-COMPAT -- promote()'s build-time live_type gate is unchanged           #
# --------------------------------------------------------------------------- #
def test_promote_gate_still_drops_unmatched():
    m = _import(PROMOTE, "rag_promote_h22")
    src = {"build": "22.0.400", "source_archive": "x", "entries": [
        {"live_type": "keep", "context": "lop", "tier": "VERIFIED-DOC",
         "live_type_matched": True, "runtime_label": "Keep", "parameters": []},
        {"stem": "ghost", "context": "lop", "tier": "VERIFIED-DOC",
         "live_type_matched": False},
    ]}
    out = m.promote(src)
    assert [e["type"] for e in out["entries"]] == ["keep"]
    assert out["counts"] == {"kept": 1, "excluded": 1}
    assert out["build"] == "22.0.400"           # promote stamps the src build (the .400 flip)
