"""rag/retrieval/scope_weights.py -- the one ranking table.

Pins the documented order (h22_prose > guide > h21), the how-to vs reference rule, the
guide slot being ACTIVE as of BP10-GUIDES (it was landed inert by BP10-CORPUS and armed here
once ``rag/corpus/guides/`` shipped), h22_prose-first-with-h21-fallback ordering, and that
every ordered hit carries its scope.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag" / "retrieval"))
import scope_weights as sw  # noqa: E402


def test_base_order_h22_over_guide_over_h21():
    # reference phrasing: h22_prose > guide > h21
    q = "scatter"
    assert sw.scope_weight("h22_prose", q) > sw.scope_weight("guide", q)
    assert sw.scope_weight("guide", q) > sw.scope_weight("h21", q)


def test_h22_prose_always_outranks_h21():
    for q in ("scatter", "how do I set up pyro", "why does the sim explode"):
        assert sw.scope_weight("h22_prose", q) > sw.scope_weight("h21", q)


def test_howto_lifts_guide_above_prose_reference_does_not():
    # how-to phrasing: the guide scope outranks prose
    assert sw.scope_weight("guide", "how do I set up pyro") > sw.scope_weight("h22_prose", "how do I set up pyro")
    # reference phrasing (a bare node name): prose outranks guides
    assert sw.scope_weight("h22_prose", "pyrosolver") > sw.scope_weight("guide", "pyrosolver")


def test_phrasing_classifier():
    assert sw.phrasing("how do I blur an image") == sw.HOWTO
    assert sw.phrasing("set up a karma render") == sw.HOWTO
    assert sw.phrasing("chromakey") == sw.REFERENCE
    assert sw.phrasing("light intensity parameter name") == sw.REFERENCE


def test_guide_slot_active_after_bp10_guides():
    # BP10-GUIDES armed the slot: it is present AND active now that rag/corpus/guides/ shipped.
    assert "guide" in sw.SCOPES
    assert sw.is_active("guide") is True
    assert sw.is_active("h22_prose") and sw.is_active("h21")
    # an active guide ranks on how-to phrasing (above prose, per the how-to bonus)
    assert sw.ranked_scopes("how do I set up pyro")[0] == "guide"
    assert "guide" in sw.ranked_scopes("how do I set up pyro", available={"guide", "h21"})


def test_ranked_scopes_default_is_h22_then_guide_then_h21():
    # reference phrasing, all three active: prose > guide > h21
    assert sw.ranked_scopes("chromakey") == ["h22_prose", "guide", "h21"]


def test_fallback_on_miss():
    # h22_prose returned nothing -> h21 is served (fallback on miss)
    assert sw.ranked_scopes("chromakey", available={"h21"}) == ["h21"]
    # h22_prose present -> it leads
    assert sw.ranked_scopes("chromakey", available={"h22_prose", "h21"})[0] == "h22_prose"


def test_order_hits_carries_scope_and_prioritises_h22():
    hits = {
        "h22_prose": [{"title": "Scatter", "text": "..."}],
        "h21": [{"title": "scatter (H21)", "text": "..."}],
    }
    ordered = sw.order_hits(hits, "what is scatter")
    assert [h["scope"] for h in ordered] == ["h22_prose", "h21"]   # h22 first, each tagged
    assert all("scope" in h for h in ordered)                       # every answer carries scope


def test_order_hits_guide_leads_on_howto():
    # the activation's whole point: a guide hit leads a how-to query
    hits = {"h22_prose": [{"title": "Pyro"}], "guide": [{"title": "pyro guide"}]}
    ordered = sw.order_hits(hits, "how do I set up pyro")
    assert ordered[0]["scope"] == "guide"


def test_order_hits_h21_only_when_h22_absent():
    ordered = sw.order_hits({"h21": [{"title": "x"}]}, "chromakey")
    assert len(ordered) == 1 and ordered[0]["scope"] == "h21"


def test_carry_scope_tags_non_dict_hit():
    assert sw.carry_scope("raw-hit", "h21") == {"hit": "raw-hit", "scope": "h21"}


def test_table_is_data():
    t = sw.table()
    assert t["h22_prose"]["base"] > t["h21"]["base"]
    assert t["guide"]["active"] is True
