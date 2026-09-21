"""BP10-GUIDES Target 2 / G0: the guide transform, tool map, and phantom gate on fixtures,
plus one deliberately-broken fixture that must land in quarantine.

No ``hou`` needed -- guides.py resolves against the committed symbol table, live catalogue and
node datasheet. The fixtures under ``tests/fixtures/guides/`` are a clean guide (real H22 nodes,
reaches corpus) and a broken guide (a planted fake node, must quarantine).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag" / "ingest"))
import guides  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "guides"


# a small deterministic resolver for the unit-level tests
def _resolver():
    return guides.Resolver(
        symbols={"hou.pwd", "hou.Node"},
        node_types={"pyrosolver", "oceansource", "particlefluidsurface"},
        parm_names={"voxelsize"},
    )


TOOLS = {
    "get_help_page": {"synapse": "synapse_knowledge_lookup", "doc": "H22 lookup", "kind": "tool"},
    "setup_pyro_sim": {"synapse": "build the network", "doc": "no recipe", "kind": "tool"},
    "capture_screenshot": {"synapse": None, "reason": "gui only", "kind": "tool", "drop": True},
}


# --------------------------------------------------------------------------- #
#  Step 1: strip framing                                                        #
# --------------------------------------------------------------------------- #
def test_strip_removes_goal_and_you_are():
    text = "You are setting up pyro. Real prose.\n\nGoal: {description}\n\n## S\n\nbody"
    out = guides.strip_framing(text)
    assert "Goal:" not in out
    assert not out.lstrip().startswith("You are")
    assert "Real prose." in out and "## S" in out


# --------------------------------------------------------------------------- #
#  Step 2: rewrite tool references                                              #
# --------------------------------------------------------------------------- #
def test_tool_rewrite_maps_and_drops():
    text = "Use get_help_page then setup_pyro_sim. Also `capture_screenshot` here."
    out, refs, drops = guides.rewrite_tools(text, "fix", TOOLS)
    assert "synapse_knowledge_lookup" in out            # mapped
    assert "build the network" in out                   # phrase rewrite
    assert "get_help_page" not in out and "setup_pyro_sim" not in out
    assert "capture_screenshot" not in out              # dropped
    assert {r["token"] for r in refs} == {"get_help_page", "setup_pyro_sim"}
    assert drops and drops[0]["token"] == "capture_screenshot" and drops[0]["line"]


def test_tool_map_value_is_load_bearing():
    # crucible criterion: a wrong tool_map value changes the emitted chunk text.
    text = "Read the docs with get_help_page now."
    good, _, _ = guides.rewrite_tools(text, "fix", TOOLS)
    wrong = dict(TOOLS)
    wrong["get_help_page"] = {"synapse": "houdini_delete_node", "doc": "x", "kind": "tool"}
    bad, _, _ = guides.rewrite_tools(text, "fix", wrong)
    assert good != bad
    assert "synapse_knowledge_lookup" in good and "houdini_delete_node" in bad


# --------------------------------------------------------------------------- #
#  Step 3: the phantom gate                                                     #
# --------------------------------------------------------------------------- #
def test_gate_passes_real_nodes():
    r = _resolver()
    for tok in ("pyrosolver", "oceansource", "voxelsize", "density"):  # density is canonical
        ok, _tier, _near = r.resolve(tok)
        assert ok, tok


def test_gate_quarantines_planted_fake_node():
    # crucible criterion: no guide text reaches the corpus without passing the symbol-table step.
    r = _resolver()
    ok, tier, nearest = r.resolve("notarealnode_zzz")
    assert ok is False and tier is None
    assert isinstance(nearest, list)   # nearest suggestions for triage, even on a miss


# --------------------------------------------------------------------------- #
#  Step 4: chunk record                                                         #
# --------------------------------------------------------------------------- #
def test_chunks_carry_name_title_origin_licence():
    text = "intro\n\n## First\n\nalpha body\n\n## Second\n\nbeta body"
    chunks = guides.chunk_sections(text, "pyro")
    assert [c["title"] for c in chunks] == ["First", "Second"]
    assert all(c["scope"] == "guide" and c["page"] == "pyro" for c in chunks)
    assert all(c["licence"] == "mit" for c in chunks)
    assert all(c["origin"] == "fxhoudinimcp@29b6695b:prompts/markdown/workflows/pyro.md" for c in chunks)
    assert all(c["build"] == "22.0.400" and len(c["content_sha"]) == 64 for c in chunks)
    assert [c["chunk_index"] for c in chunks] == [0, 1]


# --------------------------------------------------------------------------- #
#  Fixtures: clean -> corpus, broken -> quarantine                              #
# --------------------------------------------------------------------------- #
def test_fixtures_partition_clean_and_broken():
    rep = guides.build(vendor=FIX, write=False)
    assert "good_fixture" in rep["corpus"] and rep["corpus"]["good_fixture"] >= 1
    assert "broken_fixture" in rep["quarantine"]
    toks = {u["token"] for u in rep["quarantine"]["broken_fixture"]}
    assert "notarealnode_zzz" in toks                  # the planted fake is the reason
    assert "good_fixture" not in rep["quarantine"]      # exactly one bucket each


def test_broken_fixture_quarantine_file_lists_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(guides, "CORPUS_OUT", tmp_path / "corpus")
    monkeypatch.setattr(guides, "QUARANTINE_OUT", tmp_path / "quar")
    monkeypatch.setattr(guides, "REPORT_OUT", tmp_path / "report.json")
    guides.build(vendor=FIX, write=True)
    qfile = tmp_path / "quar" / "broken_fixture.md"
    assert qfile.exists()
    body = qfile.read_text(encoding="utf-8")
    assert "notarealnode_zzz" in body and "Failing tokens" in body
    assert not (tmp_path / "corpus" / "broken_fixture.jsonl").exists()
    # the clean fixture became real JSONL chunks
    good = (tmp_path / "corpus" / "good_fixture.jsonl").read_text(encoding="utf-8").splitlines()
    assert good and all("origin" in json.loads(line) for line in good)


# --------------------------------------------------------------------------- #
#  Integration: the real 31-guide vendor tree partitions cleanly (G2)           #
# --------------------------------------------------------------------------- #
def test_real_vendor_partitions_all_31():
    rep = guides.build(write=False)
    corpus, quar = set(rep["corpus"]), set(rep["quarantine"])
    assert len(corpus) + len(quar) == rep["counts"]["total"] == 31
    assert corpus.isdisjoint(quar)                      # exactly one bucket per guide
    for name, residuals in rep["quarantine"].items():
        assert residuals, f"{name} quarantined with no failing token"
