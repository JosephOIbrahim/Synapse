"""Surface-probe contract (D-H22-4, Mode A).

The probe enumerates the configured provider's LIVE tool list and diffs it
against the recorded surface. Against the mock the diff must be empty — that
empty diff is what proves the probe machinery before the drop makes it real.
``renamed`` is honest: only an exact schema-digest match under a different
name; everything else stays absent+added (which fails the wiring gate).
"""

import json

import pytest

import synapse.providers as providers
from synapse.science import mcp_surface_probe as probe
from synapse.science.mcp_mock import MockApexMCP


@pytest.fixture()
def fresh_registry(monkeypatch):
    monkeypatch.delenv("SYNAPSE_APEX_MCP_ENDPOINT", raising=False)
    monkeypatch.setattr(providers, "_INSTANCES", {})
    monkeypatch.setattr(providers, "_FACTORIES", dict(providers._FACTORIES))


# ── the Mode-A gate: mock diff is empty ──────────────────────────────────────

def test_mock_diff_is_empty(fresh_registry):
    delta = probe.diff_surface(probe.live_surface(), probe.recorded_surface())
    assert delta["absent"] == []
    assert delta["added"] == []
    assert delta["renamed"] == []


def test_record_round_trips_to_empty_diff(fresh_registry, tmp_path):
    recorded = tmp_path / "recorded.json"
    probe.record(path=recorded)
    delta = probe.diff_surface(probe.live_surface(), probe.recorded_surface(recorded))
    assert delta["absent"] == [] and delta["added"] == [] and delta["renamed"] == []


# ── tamper detection ─────────────────────────────────────────────────────────

def test_tampered_surface_detects_absent(tmp_path):
    raw = json.loads(probe.SURFACE_PATH.read_text(encoding="utf-8"))
    raw["tools"].append({"name": "ghost_tool",
                         "input_schema": {"type": "object"},
                         "schema_digest": "f" * 64})
    tampered = tmp_path / "surface.json"
    tampered.write_text(json.dumps(raw), encoding="utf-8")
    delta = probe.diff_surface(probe.live_surface(MockApexMCP()),
                               probe.recorded_surface(tampered))
    assert delta["absent"] == ["ghost_tool"]
    assert delta["renamed"] == []


def test_renamed_requires_exact_digest_match():
    live = {"pingu": "abc", "validate": "vvv"}
    recorded = {"ping": "abc", "validate": "vvv"}
    delta = probe.diff_surface(live, recorded)
    assert delta["renamed"] == [{"from": "ping", "to": "pingu",
                                 "schema_digest": "abc"}]
    assert delta["absent"] == [] and delta["added"] == []


def test_digest_mismatch_stays_absent_plus_added():
    # A different schema under a different name is NOT a rename — it surfaces
    # as absent+added and fails the gate, forcing a human re-record.
    delta = probe.diff_surface({"pingu": "xyz"}, {"ping": "abc"})
    assert delta["absent"] == ["ping"]
    assert delta["added"] == ["pingu"]
    assert delta["renamed"] == []


def test_ambiguous_rename_candidates_not_guessed():
    # Two live tools share the digest of one absent recorded tool → ambiguous,
    # so nothing is claimed as a rename.
    delta = probe.diff_surface({"a2": "d", "b2": "d"}, {"a": "d"})
    assert delta["renamed"] == []
    assert delta["absent"] == ["a"] and delta["added"] == ["a2", "b2"]


# ── CLI shape (what harness check_mcp_surface_probe consumes) ────────────────

def test_cli_writes_delta_json(fresh_registry, tmp_path):
    out = tmp_path / "delta.json"
    rc = probe.main(["--diff", "--out", str(out)])
    assert rc == 0
    delta = json.loads(out.read_text(encoding="utf-8"))
    assert set(delta) == {"live", "recorded", "absent", "added", "renamed"}
    assert delta["absent"] == [] and delta["renamed"] == []


def test_cli_operational_failure_exits_nonzero(fresh_registry, tmp_path):
    rc = probe.main(["--diff", "--surface", str(tmp_path / "missing.json")])
    assert rc == 1


def test_schema_digest_is_canonical():
    a = probe.schema_digest({"type": "object", "properties": {"a": {}, "b": {}}})
    b = probe.schema_digest({"properties": {"b": {}, "a": {}}, "type": "object"})
    assert a == b
    assert probe.schema_digest(None) == probe.schema_digest({})
