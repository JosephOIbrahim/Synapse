"""Scout APEX federation (D-H22-2, Mode A).

Pins the ratified wording: hits come from the federated ``apex_mcp`` provider
(explicit ``domain="apex"`` opt-in only — "both" NEVER includes it), every
federated hit carries ``exists_in_runtime``, and the introspected symbol
table stays the SOLE membership authority — the MCP is a retrieval source,
never a membership authority. Provider failure is fail-loud (``ScoutError``).
"""

import json

import pytest

import synapse.providers as providers
from synapse.cognitive.tools import scout


def _envelope(snippets):
    return {"observed": {"snippets": snippets}, "source": "apex_mcp",
            "tool": "search_snippets", "args_digest": "0" * 64, "ts": 0.0}


class _FakeApexProvider:
    id = "apex_mcp"

    def __init__(self, snippets=None, fail=False):
        self._snippets = snippets or []
        self._fail = fail
        self.calls = []

    def call_tool(self, name, args=None):
        if self._fail:
            raise RuntimeError("transport down")
        self.calls.append((name, dict(args or {})))
        return _envelope(self._snippets)


@pytest.fixture()
def fed(monkeypatch):
    """Hermetic federation harness: caches cleared, real committed symbol table
    (21.0.671) as authority, and a wire() helper that plants a fake provider."""
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS,
                  scout._TABLE_CACHE):
        cache.clear()
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", None)

    def wire(snippets=None, fail=False):
        fake = _FakeApexProvider(snippets, fail)
        monkeypatch.setitem(providers._INSTANCES, "apex_mcp", fake)
        return fake

    return wire


# ── hit tagging + per-hit exists_in_runtime ──────────────────────────────────

def test_hits_tagged_source_and_domain(fed):
    fed(snippets=[{"id": "a", "type": "apex_snippet", "text": "pose blend graph"}])
    out = scout.synapse_scout("blend the rig pose", domain="apex")
    assert out["domain"] == "apex" and out["mode"] == "federated"
    assert out["hits"]
    for h in out["hits"]:
        assert h["source"] == "apex_mcp"
        assert h["domain"] == "apex"
        assert "exists_in_runtime" in h          # ratified D-H22-2 wording


def test_real_dotted_symbol_resolves_true(fed):
    fed(snippets=[{"id": "a", "type": "apex_snippet",
                   "text": "drive it with hou.node('/obj/rig')"}])
    out = scout.synapse_scout("blend the rig pose", domain="apex")
    assert out["hits"][0]["exists_in_runtime"] is True
    assert "unverified_reason" not in out["hits"][0]


def test_phantom_dotted_symbol_resolves_false(fed):
    # Table authority beats the MCP's prose: hou.lopNetworks is a known phantom.
    fed(snippets=[{"id": "a", "type": "apex_snippet",
                   "text": "walk hou.lopNetworks() for the rig stage"}])
    out = scout.synapse_scout("blend the rig pose", domain="apex")
    assert out["hits"][0]["exists_in_runtime"] is False


def test_apex_only_snippet_is_honestly_unverified(fed):
    fed(snippets=[{"id": "a", "type": "apex_snippet",
                   "text": "wire skeleton::SetPoseLocal into a Blend node"}])
    out = scout.synapse_scout("blend the rig pose", domain="apex")
    hit = out["hits"][0]
    assert hit["exists_in_runtime"] is None
    assert "apex_probes" in hit["unverified_reason"]


def test_query_symbols_still_grounded_by_table(fed):
    fed(snippets=[{"id": "a", "type": "apex_snippet", "text": "pose"}])
    out = scout.synapse_scout("can hou.lopNetworks drive an apex pose", domain="apex")
    verdicts = {s["symbol"]: s["exists_in_runtime"] for s in out["symbols"]}
    assert verdicts.get("hou.lopNetworks") is False


# ── federation plumbing ──────────────────────────────────────────────────────

def test_search_tool_and_args_come_from_the_source_registry(fed):
    fake = fed(snippets=[{"id": "a", "type": "apex_snippet", "text": "pose"}])
    scout.synapse_scout("apex rig pose", domain="apex", k=4)
    assert fake.calls == [("search_snippets", {"query": "apex rig pose", "k": 4})]


def test_provider_failure_raises_scout_error(fed):
    fed(fail=True)
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("apex rig pose", domain="apex")


def test_missing_sources_registry_fails_loud(fed, tmp_path, monkeypatch):
    fed(snippets=[])
    monkeypatch.setattr(scout, "SCOUT_SOURCES_PATH", tmp_path / "nope.json")
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("apex rig pose", domain="apex")


def test_non_provider_kind_rejected(fed, tmp_path, monkeypatch):
    # The D-H22-2 non-goal: an apex source that isn't a federated provider
    # (e.g. a local corpus) must be refused, not silently served.
    fed(snippets=[])
    reg = tmp_path / "scout_sources.json"
    reg.write_text(json.dumps({"apex": {"kind": "corpus", "provider": "apex_mcp"}}),
                   encoding="utf-8")
    monkeypatch.setattr(scout, "SCOUT_SOURCES_PATH", reg)
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("apex rig pose", domain="apex")


# ── "both" excludes apex (no silent behavior change) ─────────────────────────

_ENTRIES = [
    {"id": "d1", "type": "node_reference", "source": "lop.md",
     "searchable_text": "hou.LopNode usd stage apex rig pose notes"},
]


def test_both_never_calls_the_provider(fed, tmp_path, monkeypatch):
    fake = fed(snippets=[{"id": "a", "type": "apex_snippet", "text": "pose"}])
    cdir = tmp_path / "corpus"
    cdir.mkdir()
    (cdir / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in _ENTRIES), encoding="utf-8")
    (tmp_path / "semantic_index").mkdir()
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    monkeypatch.setattr(scout, "DRIFT_POLICY", "warn")
    out = scout.synapse_scout("apex rig pose", domain="both", k=5)
    assert fake.calls == []                       # never federated implicitly
    assert all(h["source"] != "apex_mcp" for h in out["hits"])


def test_domain_enum_includes_apex_default_stays_both():
    prop = scout.SYNAPSE_SCOUT_SCHEMA["input_schema"]["properties"]["domain"]
    assert prop["enum"] == ["docs", "vex", "both", "apex"]
    assert prop["default"] == "both"


# ── end-to-end against the real mock (the Mode-A proof) ──────────────────────

def test_end_to_end_against_the_mock(fed, monkeypatch):
    # No fake planted: resolve the DEFAULT registry row → ApexMCPProvider →
    # MockApexMCP reading the recorded surface. This is scout domain="apex"
    # against the mock, end to end.
    monkeypatch.delenv("SYNAPSE_APEX_MCP_ENDPOINT", raising=False)
    monkeypatch.setattr(providers, "_INSTANCES", {})
    out = scout.synapse_scout("blend the rig pose", domain="apex", k=5)
    assert out["hits"], "mock should serve at least one snippet"
    for h in out["hits"]:
        assert h["source"] == "apex_mcp"
        assert "exists_in_runtime" in h
    # The mock's hou.node snippet grounds True against the committed table.
    by_id = {h["id"]: h for h in out["hits"]}
    assert by_id["apex:snippet:python_drive"]["exists_in_runtime"] is True
