"""W4-KNOW Target 1 (promote emits id + searchable_text) and Target 8 (a
conformance test pins the NEW served-corpus contract at a runtime checkpoint -
corpus-derived types are guarded DOWNSTREAM of promote, closing the phantom-lint
blindspot that finding 5 named: neither phantom lint ever scans a corpus entry).

Two halves:
  * unit - the promote functions build the id/searchable_text contract correctly,
    including unique ids across the 9 duplicate (context, type) pairs and the
    build-time gate that drops unmatched entries;
  * conformance - the SHIPPED rag/corpus/h22_nodes.json still satisfies the
    contract every downstream reader depends on. If a future regen drops id,
    searchable_text, the build stamp, or the internal-name-bearing parameters,
    THIS test fails - the guard the lints can't provide.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_PROMOTE = ROOT / "harness" / "notes" / "rag_promote_h22.py"
_CORPUS = ROOT / "rag" / "corpus" / "h22_nodes.json"


def _load_promote():
    spec = importlib.util.spec_from_file_location("rag_promote_h22", _PROMOTE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # main() is __name__-guarded: no I/O on import
    return mod


# --------------------------------------------------------------------------- #
#  Target 1 - unit                                                            #
# --------------------------------------------------------------------------- #
def test_entry_id_unique_across_duplicate_pairs():
    m = _load_promote()
    seen = {}
    a = m._entry_id("cop", "pyro", seen)
    b = m._entry_id("cop", "pyro", seen)          # same (context, type) again
    c = m._entry_id("cop2", "pyro", seen)
    assert a == "h22:cop/pyro"
    assert b == "h22:cop/pyro#2"                  # discriminated, not a collision
    assert c == "h22:cop2/pyro"
    assert len({a, b, c}) == 3


def test_searchable_text_carries_the_type():
    m = _load_promote()
    e = {"live_type": "chromakey", "runtime_label": "Chroma Key",
         "context": "cop", "summary": "key out a colour",
         "parameters": [{"label": "Key", "ids": ["keycolor"], "channels": []}]}
    st = m._searchable_text(e)
    assert "chromakey" in st                       # the decisive grounding token
    assert "Chroma Key" in st and "cop" in st


def test_promote_gate_drops_unmatched():
    m = _load_promote()
    src = {"build": "22.0.368", "entries": [
        {"live_type": "keep", "context": "cop", "tier": "VERIFIED-DOC",
         "live_type_matched": True, "runtime_label": "Keep", "parameters": []},
        {"stem": "ghost", "context": "cop2", "tier": "VERIFIED-DOC",
         "live_type_matched": False},               # gate: not live-matched -> excluded
        {"live_type": "lowtier", "context": "cop", "tier": "DOC-ONLY",
         "live_type_matched": True},                # gate: wrong tier -> excluded
    ]}
    out = m.promote(src)
    kept_types = [e["type"] for e in out["entries"]]
    assert kept_types == ["keep"]                   # only the gated-in entry survives
    assert out["counts"] == {"kept": 1, "excluded": 2}
    assert out["build"] == "22.0.368"
    kept = out["entries"][0]
    assert kept["id"] == "h22:cop/keep" and kept["searchable_text"]


# --------------------------------------------------------------------------- #
#  Target 8 - conformance on the SHIPPED artifact                             #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def corpus():
    if not _CORPUS.is_file():
        pytest.skip("shipped h22 node corpus not present")
    return json.loads(_CORPUS.read_text(encoding="utf-8"))


def test_corpus_carries_build_stamp_and_producer(corpus):
    assert corpus.get("build"), "served corpus must carry a build stamp (Target 7)"
    assert corpus.get("producer") == "harness/notes/rag_promote_h22.py"
    assert corpus.get("entries"), "served corpus is empty"


def test_every_served_entry_meets_the_contract(corpus):
    """The NEW contract, checked at a runtime checkpoint (Target 8): every served
    node entry is scout-visible (id + searchable_text) AND index-keyable
    (type + context). This is the guard the phantom lints structurally cannot
    give - they never scan a corpus entry (finding 5)."""
    ids = []
    for e in corpus["entries"]:
        assert isinstance(e, dict)
        for field in ("id", "type", "context", "label", "searchable_text", "parameters"):
            assert field in e, "served entry missing %r: %r" % (field, e.get("id"))
        assert str(e["id"]).startswith("h22:")
        assert str(e["searchable_text"]).strip(), "empty searchable_text -> scout-invisible"
        assert str(e["type"]).lower() in e["searchable_text"].lower()
        ids.append(e["id"])
    assert len(ids) == len(set(ids)), "duplicate ids collide in scout by-id dedup"


def test_served_params_carry_internal_names_and_channels(corpus):
    """Target 5 downstream: the parameter items promote writes must carry the
    internal ids + channels knowledge.py serves uncapped. Pins that a future
    regen cannot silently revert to labels-only."""
    checked = 0
    for e in corpus["entries"]:
        for p in (e.get("parameters") or []):
            assert isinstance(p, dict)
            assert "ids" in p and "channels" in p, \
                "param on %s lacks ids/channels: %r" % (e["id"], p)
            checked += 1
    assert checked > 0, "no parameters found to check"


def test_over_12_param_entries_exist_and_are_whole(corpus):
    """The corpus really does carry entries past the old 12-label ceiling - the
    condition Target 5 exists for - and they keep all their params."""
    over12 = [e for e in corpus["entries"] if len(e.get("parameters") or []) > 12]
    assert over12, "expected entries with >12 params (the 12-cap was the bug)"
    biggest = max(over12, key=lambda e: len(e["parameters"]))
    assert len(biggest["parameters"]) > 100          # the pyro nodes carry hundreds
