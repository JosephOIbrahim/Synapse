"""W4-KNOW predicate 6 - the type-name scorecard instrument (scout_eval extension).

Tests the INSTRUMENT'S ARITHMETIC on a controlled fixture (mirroring how
test_scout_eval.py guards run_eval), with an injected fake scout so the numbers
are deterministic and hermetic - no embedder, no shipped corpus. The LIVE numbers
on the shipped corpus are a receipt "check", re-run adversarially by W4-CRUX; this
test guards that the scorer can't lie about them.
"""

import json
from pathlib import Path

import pytest

from synapse.cognitive.tools import scout_eval as ev
from synapse.routing.knowledge import KnowledgeIndex


# A fixture node set: 'foo' collides across cop+sop; 'bar' is cop-only.
_NODES = [
    {"id": "h22:cop/foo", "type": "foo", "context": "cop", "label": "Foo COP",
     "summary": "foo cop", "searchable_text": "Foo COP (foo) foo node cop",
     "parameters": [{"label": "A", "ids": ["a"], "channels": []}]},
    {"id": "h22:sop/foo", "type": "foo", "context": "sop", "label": "Foo SOP",
     "summary": "foo sop", "searchable_text": "Foo SOP (foo) foo node sop",
     "parameters": [{"label": "A", "ids": ["a"], "channels": []}]},
    {"id": "h22:cop/bar", "type": "bar", "context": "cop", "label": "Bar",
     "summary": "bar cop", "searchable_text": "Bar (bar) bar node cop",
     "parameters": [{"label": "B", "ids": ["b"], "channels": []}]},
]
_LIVE = {"cop": {"foo", "bar"}, "sop": {"foo"}}


def _fake_scout(nodes):
    """A perfect retriever: a bare-type query returns every entry OF that type,
    exact matches first. Lets us assert the SCORER, not scout's ranking."""
    def scout(query, k=6, **kw):
        q = query.lower().strip()
        hits = [{"id": e["id"], "type": e["type"], "source": "", "score": 1.0,
                 "snippet": ""} for e in nodes if e["type"].lower() == q]
        return {"query": query, "mode": "lexical_only", "hits": hits[:k],
                "symbols": [], "warnings": []}
    return scout


@pytest.fixture
def ki(tmp_path):
    (tmp_path / "corpus").mkdir(parents=True)
    (tmp_path / "corpus" / "h22_nodes.json").write_text(json.dumps({
        "schema": "h22_node_corpus/v1", "build": "22.0.368", "entries": _NODES,
    }), encoding="utf-8")
    return KnowledgeIndex(rag_root=str(tmp_path))


def test_perfect_corpus_scores_perfect(ki):
    card = ev.run_type_name_eval(
        scout_fn=_fake_scout(_NODES), knowledge_index=ki,
        corpus_entries=_NODES, live_types=_LIVE)
    d = card.to_dict()
    assert d["p_at_1"] == 1.0                        # every top-1 is the right type
    assert d["disambiguation_rate"] == 1.0           # foo (cop+sop) resolves both ways
    assert d["served_phantom_rate"] == 0.0           # all served types are live
    assert d["cop_lop_floor_clearing"] == 1.0        # cop entries clear top-k
    assert d["disambiguation_detail"]["total"] == 1  # exactly one collision type (foo)


def test_p_at_1_penalises_wrong_top1(ki):
    # A retriever that returns the WRONG type first must drop P@1.
    def wrong(query, k=6, **kw):
        return {"hits": [{"id": "h22:cop/bar", "type": "bar"}], "mode": "lexical_only"}
    card = ev.run_type_name_eval(scout_fn=wrong, knowledge_index=ki,
                                 corpus_entries=_NODES, live_types=_LIVE)
    assert card.p_at_1 < 1.0                          # 'foo' queries land 'bar' -> miss


def test_served_phantom_detected():
    """A served type absent from the live catalogue is a phantom the scorer must
    catch - the second, independent check on promote's build-time gate."""
    nodes = _NODES + [{"id": "h22:cop/ghost", "type": "ghost", "context": "cop",
                       "label": "Ghost", "summary": "", "searchable_text": "ghost",
                       "parameters": []}]
    card = ev.run_type_name_eval(scout_fn=_fake_scout(nodes), knowledge_index=None,
                                 corpus_entries=nodes, live_types=_LIVE)
    assert card.served_phantom_rate > 0.0
    assert "cop/ghost" in card.served_phantom_leaked


def test_no_catalogue_reports_none_not_zero():
    """House rule: unobtainable renders UNKNOWN (None), never a fabricated 0.00.
    With no live catalogue there is nothing to check phantoms against."""
    card = ev.run_type_name_eval(scout_fn=_fake_scout(_NODES), knowledge_index=None,
                                 corpus_entries=_NODES, live_types={})
    assert card.served_phantom_rate is None
    assert card.disambiguation_rate is None          # no knowledge_index injected


def test_scorecard_to_dict_schema(ki):
    d = ev.run_type_name_eval(scout_fn=_fake_scout(_NODES), knowledge_index=ki,
                              corpus_entries=_NODES, live_types=_LIVE).to_dict()
    assert set(d) >= {"p_at_1", "disambiguation_rate", "served_phantom_rate",
                      "cop_lop_floor_clearing", "p_at_1_detail",
                      "served_phantom_detail", "floor_detail"}


def test_parse_h22_id():
    assert ev._parse_h22_id("h22:cop/blur") == ("cop", "blur")
    assert ev._parse_h22_id("h22:cop/pyro#2") == ("cop", "pyro")   # discriminator stripped
    assert ev._parse_h22_id("rag_prose_doc") is None
