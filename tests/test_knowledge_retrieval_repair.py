"""W4-KNOW retrieval repair — knowledge.py Targets 2,4,5,6,7.

Pins the NEW contract on both a CONTROLLED fixture corpus (deterministic - the
shipped corpus is cop/lop/cop2 only, so a noise-spans-cop/sop/vop/chop case must
be synthesised) and the REAL rag/ corpus (the 5 pre-flight natural-language node
questions, and the topic-query regression guard).

  Target 2 - index keyed (context, type); ambiguous bare type -> disambiguation
             list, never a silent _CONTEXT_RANK pick.
  Target 4 - type-name intent replaces the 2-token bail; sentence-shaped node
             questions route to the node path or honest not-found, never to prose.
  Target 5 - node answers carry internal parm names + channels, UNCAPPED; the
             measured serve size is reported per response.
  Target 6 - similarity floor: a weak fuzzy match returns found=False, not
             confident-wrong.
  Target 7 - corpus build stamp checked against the live build; loud on mismatch.
"""

import json
import warnings
from pathlib import Path

import pytest

from synapse.routing import knowledge as K

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
#  Fixture corpus builder                                                     #
# --------------------------------------------------------------------------- #
def _param(label, ids, channels=None, desc=""):
    return {"label": label, "ids": list(ids), "channels": list(channels or []),
            "description": desc}


def _write_rag(tmp_path, nodes, build="22.0.368", topics=None, refs=None):
    """A minimal rag/ tree KnowledgeIndex reads: corpus/h22_nodes.json (+ optional
    semantic_index topics and skills reference .md files)."""
    (tmp_path / "corpus").mkdir(parents=True, exist_ok=True)
    (tmp_path / "corpus" / "h22_nodes.json").write_text(json.dumps({
        "schema": "h22_node_corpus/v1", "build": build,
        "producer": "test", "entries": nodes,
    }), encoding="utf-8")
    meta = tmp_path / "documentation" / "_metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "semantic_index.json").write_text(json.dumps(topics or {}), encoding="utf-8")
    if refs:
        rd = tmp_path / "skills" / "houdini21-reference"
        rd.mkdir(parents=True, exist_ok=True)
        for name, content in refs.items():
            (rd / name).write_text(content, encoding="utf-8")
    return tmp_path


# A collision type ("noise") spanning four contexts + a >12-param node ("blur").
_BLUR_PARAMS = [_param("Strength", ["strength"], ["strength"], "blur strength"),
                _param("Radius", ["radius", "radiusx", "radiusy"], ["radiusx", "radiusy"]),
                _param("Quality", ["quality"], [])]
_BLUR_PARAMS += [_param("Extra %d" % i, ["extra%d" % i], ["extra%d" % i])
                 for i in range(14)]   # -> 17 params total (> the old 12 cap)

_FIXTURE_NODES = [
    {"type": "noise", "context": "cop", "label": "Noise (COP)",
     "summary": "copernicus noise", "parameters": [_param("Amp", ["amp"], ["amp"])]},
    {"type": "noise", "context": "sop", "label": "Noise (SOP)",
     "summary": "sop noise", "parameters": [_param("Amp", ["amp"], [])]},
    {"type": "noise", "context": "vop", "label": "Noise (VOP)",
     "summary": "vop noise", "parameters": [_param("Freq", ["freq"], [])]},
    {"type": "noise", "context": "chop", "label": "Noise (CHOP)",
     "summary": "chop noise", "parameters": [_param("Rate", ["rate"], [])]},
    {"type": "blur", "context": "cop", "label": "Blur",
     "summary": "blur an image", "parameters": _BLUR_PARAMS},
    {"type": "chromakey", "context": "cop", "label": "Chroma Key",
     "summary": "key out a colour", "parameters": [_param("Key", ["keycolor"], [])]},
]


@pytest.fixture
def ki(tmp_path):
    return K.KnowledgeIndex(rag_root=str(_write_rag(tmp_path, _FIXTURE_NODES)))


# --------------------------------------------------------------------------- #
#  Target 2 - (context, type) keying + disambiguation (predicate 3)           #
# --------------------------------------------------------------------------- #
def test_keyed_by_context_type(ki):
    st = ki.stats()
    assert st["h22_nodes"] == 6          # 6 (context, type) keys
    assert st["h22_types"] == 3          # noise, blur, chromakey
    assert st["corpus_build"] == "22.0.368"


def test_bare_ambiguous_type_disambiguates(ki):
    """predicate 3: bare noise query returns a disambiguation list spanning
    cop/sop/vop/chop - never a silent _CONTEXT_RANK pick."""
    r = ki.lookup("noise")
    assert r.found
    assert r.parameters == []                       # a list, not a datasheet
    assert {d["context"] for d in r.disambiguation} == {"cop", "sop", "vop", "chop"}
    assert "DISAMBIGUATION" in r.agent_hint


def test_context_qualified_type_resolves_exactly(ki):
    """predicate 3: (context=cop, noise) returns exactly the COP entry."""
    r = ki.lookup("noise", context="cop")
    assert r.found and r.context == "cop"
    assert not r.disambiguation
    assert "copernicus noise" in r.answer


def test_context_absent_for_type_is_honest_not_found(ki):
    """noise exists in cop/sop/vop/chop but NOT lop -> honest not-found, never a
    fall-through to prose."""
    r = ki.lookup("noise", context="lop")
    assert not r.found


def test_k_bounds_disambiguation(ki):
    r = ki.lookup("noise", k=2)
    assert len(r.disambiguation) == 2               # capped to k


def test_disambiguation_orders_current_context_first(ki):
    # cop outranks the others (_CONTEXT_RANK); it must lead the list.
    r = ki.lookup("noise")
    assert r.disambiguation[0]["context"] == "cop"


# --------------------------------------------------------------------------- #
#  Target 5 - uncapped internal names + channels + measured serve size        #
# --------------------------------------------------------------------------- #
def test_uncapped_internal_names_and_channels(ki):
    """predicate 4: an entry with >12 parameters returns ALL of them with internal
    names and channels; measured serve size is reported per response."""
    r = ki.lookup("blur", context="cop")
    assert r.found
    assert len(r.parameters) == 17                  # NOT capped at 12
    # every parameter carries the fields needed to actually set it
    assert all("ids" in p and "channels" in p for p in r.parameters)
    # internal ids + channels are present in the answer text, not just labels
    assert "strength" in r.answer                   # an internal id
    assert "radiusx" in r.answer                    # an internal id AND a channel
    # at least one parameter carries channels
    assert any(p["channels"] for p in r.parameters)
    # serve size is MEASURED (matches the payload byte length), reported, > 0
    assert r.serve_bytes > 0
    assert r.serve_bytes == len(json.dumps(
        {"answer": r.answer, "parameters": r.parameters,
         "disambiguation": r.disambiguation}, ensure_ascii=False).encode("utf-8"))


def test_agent_hint_reports_corpus_build_not_hardcoded(ki):
    """Target 7: the agent hint reports the corpus's OWN build stamp - the old
    hardcoded 'Houdini 22.0.368' literal is gone."""
    r = ki.lookup("chromakey", context="cop")
    assert "22.0.368" in r.agent_hint               # from the fixture stamp...
    # ...and proven dynamic: a differently-stamped corpus reports its own build.
    other = K.KnowledgeIndex(rag_root=str(_write_rag(
        Path(str(ki._rag_root)) / "other", _FIXTURE_NODES, build="22.5.123")))
    assert "22.5.123" in other.lookup("chromakey", context="cop").agent_hint


# --------------------------------------------------------------------------- #
#  Target 6 - similarity floor: weak fuzzy match -> found=False (predicate 5)  #
# --------------------------------------------------------------------------- #
def test_similarity_floor_drops_weak_match(tmp_path):
    """predicate 5: an out-of-corpus query whose only match is a weak section-header
    hit (confidence 0.45 < the 0.5 floor) returns found=False, not confident-wrong.
    Lowering the floor per-call recovers the same weak answer - proving the floor,
    not a missing corpus, is what suppressed it."""
    rag = _write_rag(tmp_path, _FIXTURE_NODES,
                     refs={"widget.md": "# Frobnicator\nnotes about the frobnicator.\n"})
    ki = K.KnowledgeIndex(rag_root=str(rag))
    assert K.DENSE_MATCH_FLOOR == 0.5
    assert not ki.lookup("frobnicator").found                 # below floor -> not found
    assert ki.lookup("frobnicator", min_similarity=0.0).found  # floor lowered -> found


def test_floor_does_not_suppress_strong_match(tmp_path):
    rag = _write_rag(tmp_path, _FIXTURE_NODES, topics={
        "pyro_simulation": {"summary": "pyro fire smoke sim",
                            "keywords": ["pyro", "fire", "smoke", "simulation"]}})
    ki = K.KnowledgeIndex(rag_root=str(rag))
    r = ki.lookup("pyro fire smoke simulation")
    assert r.found and r.confidence >= K.DENSE_MATCH_FLOOR


# --------------------------------------------------------------------------- #
#  Target 7 - build-stamp mismatch is loud at load (predicate 5)              #
# --------------------------------------------------------------------------- #
def test_build_stamp_mismatch_warns_loud(tmp_path, monkeypatch):
    """predicate 5: a corpus stamped for a DIFFERENT build than the live one fails
    loud (a RuntimeWarning) at load and records the mismatch for the release gate."""
    monkeypatch.setattr(K, "EXPECTED_HOUDINI_VERSION", "22.0.400")
    rag = _write_rag(tmp_path, _FIXTURE_NODES, build="22.0.368")
    with pytest.warns(RuntimeWarning, match="build mismatch"):
        ki = K.KnowledgeIndex(rag_root=str(rag))
    assert ki.stats()["corpus_build_mismatch"] == ("22.0.368", "22.0.400")


def test_build_stamp_match_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "EXPECTED_HOUDINI_VERSION", "22.0.368")
    rag = _write_rag(tmp_path, _FIXTURE_NODES, build="22.0.368")
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        ki = K.KnowledgeIndex(rag_root=str(rag))       # no RuntimeWarning raised
    assert ki.stats()["corpus_build_mismatch"] is None


def test_no_live_build_no_false_alarm(tmp_path, monkeypatch):
    """Outside Houdini (no injected version, no HOUDINI_VERSION env) there is
    nothing to compare against - the stamp check must stay silent, never alarm."""
    monkeypatch.setattr(K, "EXPECTED_HOUDINI_VERSION", None)
    monkeypatch.delenv("HOUDINI_VERSION", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        ki = K.KnowledgeIndex(rag_root=str(_write_rag(tmp_path, _FIXTURE_NODES)))
    assert ki.stats()["corpus_build_mismatch"] is None


# --------------------------------------------------------------------------- #
#  Target 4 - the intent test, on the REAL corpus (predicate 2)               #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def real_ki():
    rag = ROOT / "rag"
    if not (rag / "corpus" / "h22_nodes.json").is_file():
        pytest.skip("real h22 node corpus not present")
    return K.KnowledgeIndex(rag_root=str(rag))


def _is_node_or_notfound(r):
    """A result is on the NODE PATH (datasheet or disambiguation) or is honest
    not-found - i.e. NOT an H21-prose found=True answer."""
    if not r.found:
        return True
    return (r.agent_hint or "").startswith(("VERIFIED-DOC", "DISAMBIGUATION"))


# The 5 pre-flight natural-language node questions (recon 2026-08-15), incl. the
# Copernicus blur question that used to be served legacy cop2net prose, and the
# noise-in-copernicus question that used to serve legacy cop2 guidance and now
# honestly returns not-found (there is no noise node in current Copernicus).
PREFLIGHT = [
    "how do I blur an image in copernicus",
    "what parameters does the copernicus chromakey node have",
    "how do I set up a karma render node in solaris",
    "how do I use the copernicus flip node",
    "how do I set the noise node in copernicus",
]


@pytest.mark.parametrize("q", PREFLIGHT)
def test_preflight_questions_never_serve_prose(real_ki, q):
    """predicate 2: each pre-flight NL question routes to the node path or honest
    not-found - ZERO H21-prose found=True answers."""
    assert _is_node_or_notfound(real_ki.lookup(q)), \
        "%r was answered from H21 prose (found=True), the confident-wrong class" % q


def test_copernicus_blur_resolves_to_current_cop(real_ki):
    r = real_ki.lookup("how do I blur an image in copernicus")
    assert r.found and r.context == "cop"            # current context, not legacy cop2


def test_noise_in_copernicus_is_honest_not_found(real_ki):
    """The exact confident-wrong case the recon caught: 'noise' lives only in the
    legacy cop2 context, so a Copernicus (cop) noise question must be honest
    not-found, NOT served legacy cop2 guidance as found=True."""
    r = real_ki.lookup("how do I set the noise node in copernicus")
    assert not r.found


# Topic queries that CONTAIN a live node-type token but are NOT node questions -
# they must keep resolving to their H21 topics (the 8-test regression the old
# 2-token bail protected). 'wrangle', 'wedge', 'merge', 'light' are all types.
REGRESSION_TOPICS = [
    ("vex attribute wrangle", "vex"),
    ("tops wedge parameter sweep", "tops"),
    ("scene assembly merge reference", "scene_assembly"),
    ("what is the light intensity parameter name", "solaris_parameter"),
]


@pytest.mark.parametrize("q,expected", REGRESSION_TOPICS)
def test_topic_queries_not_hijacked_by_node_path(real_ki, q, expected):
    r = real_ki.lookup(q)
    assert r.found and expected in r.topic.lower(), \
        "%r was hijacked to %r (context=%r)" % (q, r.topic, r.context)
