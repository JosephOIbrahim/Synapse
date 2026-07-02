"""Contract tests for the D-H22-1 provider seam (Mode A — mock endpoint).

Pins the truth-contract envelope shape, the registry semantics, and the
fail-loud transport discipline of ``synapse.providers.apex_mcp`` before the
H22 drop makes the endpoint real. Pure Python — no hou, no network.
"""

import hashlib
import json

import pytest

import synapse.providers as providers
from synapse.providers import ProviderError
from synapse.providers.apex_mcp import (
    ApexMCPProvider,
    args_digest,
    assert_no_overclaim,
)


@pytest.fixture()
def registry(monkeypatch):
    """A hermetic registry: fresh instance cache, copied factory table, and the
    default (mock) endpoint regardless of ambient env."""
    monkeypatch.delenv("SYNAPSE_APEX_MCP_ENDPOINT", raising=False)
    monkeypatch.setattr(providers, "_INSTANCES", {})
    monkeypatch.setattr(providers, "_FACTORIES", dict(providers._FACTORIES))
    return providers


# ── registry semantics ───────────────────────────────────────────────────────

def test_registry_resolves_apex_mcp(registry):
    prov = registry.get("apex_mcp")
    assert isinstance(prov, ApexMCPProvider)


def test_registry_lazy_constructs_once(registry):
    prov = registry.get("apex_mcp")
    assert registry.get("apex_mcp") is prov          # cached, not rebuilt


def test_unknown_provider_fails_loud(registry):
    with pytest.raises(ProviderError):
        registry.get("no_such_provider")


def test_broken_factory_surfaces_as_provider_error(registry):
    registry.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("nope")))
    with pytest.raises(ProviderError):
        registry.get("broken")


# ── truth-contract envelope shape ────────────────────────────────────────────

def test_envelope_shape_for_ping(registry):
    env = registry.get("apex_mcp").call_tool("ping", {})
    assert isinstance(env["observed"], dict)          # raw result, never synthesized
    assert env["observed"].get("pong") is True
    assert env["source"] == "apex_mcp"
    assert env["tool"] == "ping"
    assert "ts" in env
    expected = hashlib.sha256(
        json.dumps({}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert env["args_digest"] == expected


def test_provider_never_sets_claimed(registry):
    env = registry.get("apex_mcp").call_tool("ping", {})
    assert "claimed" not in env


def test_validator_verdict_present_iff_result_carries_one(registry):
    prov = registry.get("apex_mcp")
    ping = prov.call_tool("ping", {})
    assert "validator_verdict" not in ping            # ping carries no verdict
    validate = prov.call_tool("validate", {"src": "noop"})
    assert "validator_verdict" in validate
    # Carried, not restated: the envelope field IS the observed one.
    assert validate["validator_verdict"] == validate["observed"]["validator_verdict"]


def test_args_digest_is_order_insensitive():
    assert args_digest({"b": 1, "a": 2}) == args_digest({"a": 2, "b": 1})
    assert args_digest(None) == args_digest({})


# ── overclaim guard (check_mcp_truth_contract's rule) ────────────────────────

def test_assert_no_overclaim_passes_without_claimed():
    assert_no_overclaim({"observed": {"x": 1}})


def test_assert_no_overclaim_passes_when_claimed_equals_observed():
    assert_no_overclaim({"observed": {"x": 1}, "claimed": {"x": 1}})


def test_assert_no_overclaim_rejects_divergent_claim():
    with pytest.raises(ProviderError):
        assert_no_overclaim({"observed": {"x": 1}, "claimed": {"x": 2}})


# ── fail-loud transport discipline ───────────────────────────────────────────

class _BrokenTransport:
    def list_tools(self):
        raise ConnectionError("boom")

    def call_tool(self, name, args):
        raise TimeoutError("mcp timed out")


def test_transport_failure_raises_provider_error():
    prov = ApexMCPProvider(transport=_BrokenTransport())
    with pytest.raises(ProviderError):
        prov.call_tool("ping", {})
    with pytest.raises(ProviderError):
        prov.list_tools()


def test_unsupported_endpoint_fails_loud_no_silent_mock_fallback(monkeypatch):
    monkeypatch.setenv("SYNAPSE_APEX_MCP_ENDPOINT", "http://localhost:9998")
    with pytest.raises(ProviderError):
        ApexMCPProvider()


# ── mock surface (shared source of truth with the probe) ────────────────────

def test_mock_serves_the_recorded_surface(registry):
    names = {t["name"] for t in registry.get("apex_mcp").list_tools()}
    assert names == {"ping", "validate", "search_snippets", "get_rules"}


def test_mock_unknown_tool_fails_loud(registry):
    with pytest.raises(ProviderError):
        registry.get("apex_mcp").call_tool("mutate_scene", {})
