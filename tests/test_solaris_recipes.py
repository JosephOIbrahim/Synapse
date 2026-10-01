"""Pieke pack (10/1): verified H22 Solaris recipes reachable from the artist's words.

The 10/1 baseline (.token-saver/pack/bench3.json) sent three Pieke requests to the
panel worker; none was built. These queries are the ones the model actually sent
and got nothing useful back from. Each must now reach its recipe.
"""
import json

import pytest

from synapse.routing import solaris_recipes as R
from synapse.routing.knowledge import KnowledgeIndex


@pytest.mark.parametrize("query,key", [
    ("lightfilter", "karma_blocker"),
    ("blocker light filter", "karma_blocker"),
    ("karma blocker", "karma_blocker"),
    ("filter blocker", "karma_blocker"),
    ("Karma light filter box shape", "karma_blocker"),
    ("scatter instances LOP", "scatter_instances"),
    ("scatter instances points instancing camera visibility", "scatter_instances"),
    ("render passes", "render_passes"),
    ("render_pass_split template render pass beauty product", "render_passes"),
])
def test_bench_queries_reach_the_recipe(query, key):
    result = KnowledgeIndex(rag_root=None).lookup(query, context="lop")
    assert result.found and result.topic == key
    assert "VERIFIED RECIPE" in result.answer
    assert "synapse_solaris_build_graph" in result.answer


@pytest.mark.parametrize("query", ["scatterinstances", "karmablockerlightfilter", "renderpass"])
def test_bare_type_keeps_its_datasheet(query):
    # The whole query is the type name: the datasheet path owns it, not the recipe.
    assert R.match({query}) is None


@pytest.mark.parametrize("query", ["scatter points on a grid", "camera", "beauty", "karma", "light"])
def test_unrelated_queries_do_not_match(query):
    assert R.match(set(query.lower().split())) is None


FILLS = {
    "scatter_instances": dict(UPSTREAM="cam", DOWNSTREAM="settings", COLLIDER_GLB="C:\\w\\x_collider.glb",
                              WORLD_PRIM="/World/w", CAMERA_PRIM="/cameras/c"),
    "karma_blocker": dict(UPSTREAM="a", DOWNSTREAM="b"),
    "render_passes": dict(UPSTREAM="a", DOWNSTREAM="settings", ISOLATE_PRIM="/World/w"),
}


@pytest.mark.parametrize("key", sorted(R.RECIPES))
def test_payload_fills_and_splices(key):
    pl = R.payload(key, **FILLS[key])
    text = json.dumps(pl)
    assert "<" not in text
    assert "\\\\" not in text  # Windows paths normalised to forward slashes
    nodes = {n["id"]: n for n in pl["nodes"]}
    assert nodes["up"]["existing"] and nodes["down"]["existing"]
    last = pl["connections"][-1]
    assert last["to"] == "down" and last["insert"] is True and last["input"] == 0
    for n in pl["nodes"]:
        if not n.get("existing"):
            assert n["type"] in R.RECIPES[key]["types"]


def test_unfilled_placeholder_raises():
    with pytest.raises(ValueError):
        R.payload("karma_blocker", UPSTREAM="a")


def test_prompt_names_the_recipes():
    from synapse.panel.system_prompt import build_system_prompt
    text = build_system_prompt({"network": "/stage"})
    for t in ("scatterinstances", "karmablockerlightfilter", "renderpass"):
        assert t in text
    assert "Never guess" in text
