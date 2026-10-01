"""TYPEHINT (10/1): a wrong node type gets the closest real types, not a bare error.

The 10/1 Pieke baseline sent fifteen houdini_create_node calls guessing a Karma
blocker light filter's type and never tried karmablockerlightfilter, because
each failure said only "Invalid node type name". The guesses below are the
model's own, from .token-saver/pack/bench3.json. The catalogue is a slice of the
real 22.0.400 Lop catalogue (names and labels as hou reports them).
"""
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.core import type_suggest as T  # noqa: E402
from synapse.core.errors import SynapseUserError  # noqa: E402

LOP = {
    "karmablockerlightfilter": "Karma Blocker Light Filter",
    "lightfilterlibrary": "Light Filter Library",
    "light::2.0": "Light",
    "lightmixer": "Light Mixer",
    "imagefilter": "Image Filter",
    "renderpass": "Render Pass",
    "rendersettings": "Render Settings",
    "rendervar": "Render Var",
    "scatterinstances": "Scatter Instances",
    "sopcreate": "SOP Create",
    "sphere": "Sphere",
    "domelight::3.0": "Dome Light",
    "distantlight::2.0": "Distant Light",
    "labs::karma::1.0": "Labs Karma",
    "karmafogbox": "Karma Fog Box",
    "karmatexturebaker": "Karma Texture Baker",
}

BLOCKER_GUESSES = ["lightfilter", "karmablocker", "karmalightfilter", "lightfilter::2.0",
                   "karmablocker::2.0", "blocker", "filterblocker", "kma_blocker"]


@pytest.mark.parametrize("guess", BLOCKER_GUESSES)
def test_baseline_guesses_reach_the_blocker(guess):
    assert "karmablockerlightfilter" in T.suggest(guess, LOP)[:3]


@pytest.mark.parametrize("guess", ["gobo", "barndoors", "zzqx"])
def test_concepts_that_are_not_types_get_no_noise(guess):
    # Not LOP types at all: an honest empty list, not a made-up match.
    assert T.suggest(guess, LOP) == []


def test_versions_and_plurals():
    assert T.suggest("light", LOP)[0] == "light::2.0"
    assert T.suggest("renderpasses", LOP)[0] == "renderpass"
    assert T.suggest("scatter", LOP)[0] == "scatterinstances"


def test_labs_ranks_below_core():
    s = T.suggest("karmablocker", LOP)
    assert s.index("karmablockerlightfilter") < s.index("labs::karma::1.0")


def test_hint_sentences():
    h = T.hint("lightfilter", LOP, context="Lop")
    assert "karmablockerlightfilter (Karma Blocker Light Filter)" in h
    assert "do not guess" in h
    none = T.hint("gobo", LOP, context="Lop")
    assert "synapse_knowledge_lookup" in none


class _NT:
    def __init__(self, label, hidden=False):
        self._label, self._hidden = label, hidden

    def hidden(self):
        return self._hidden

    def deprecated(self):
        return False

    def description(self):
        return self._label


class _Cat:
    def __init__(self, types):
        self._types = types

    def nodeTypes(self):
        return self._types

    def name(self):
        return "Lop"


def test_live_catalog_skips_hidden_types():
    cat = _Cat({"karmablockerlightfilter": _NT("Karma Blocker Light Filter"),
                "secretfilter": _NT("Secret Filter", hidden=True)})
    assert T.live_catalog(cat) == {"karmablockerlightfilter": "Karma Blocker Light Filter"}


def test_create_node_hint_names_the_real_type():
    from synapse.server.handlers_node import _invalid_type_hint
    parent = SimpleNamespace(childTypeCategory=lambda: _Cat({n: _NT(l) for n, l in LOP.items()}))
    h = _invalid_type_hint(parent, "karmablocker")
    assert h.startswith("'karmablocker' is not a node type in Lop")
    assert "karmablockerlightfilter" in h


def test_build_graph_rejection_names_real_types_and_not_scout(monkeypatch):
    from synapse.server import handlers_solaris_graph as hsg
    monkeypatch.setattr(hsg, "hou", SimpleNamespace(nodeType=lambda cat, t: None), raising=False)
    monkeypatch.setattr(hsg, "_absent_type_remediation", lambda t: None)
    parent = SimpleNamespace(childTypeCategory=lambda: _Cat({n: _NT(l) for n, l in LOP.items()}))
    with pytest.raises(SynapseUserError) as ei:
        hsg._validate_node_types(parent, {"f": {"type": "lightfilter"}})
    text = str(ei.value) + " " + str(getattr(ei.value, "suggestion", ""))
    assert "closest real types" in text and "karmablockerlightfilter" in text
    assert "synapse_scout" not in text
