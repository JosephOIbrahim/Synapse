"""Floor guard for the provider capability probe (V3, blueprint Mile 4).

Pins the four properties the layer exists for:

1. **Colour is computed, never stored.** There is no colour field and no
   serialized colour key. Adding one fails ``test_colour_is_not_a_field``.
2. **Staleness degrades to GREY, never to green.** Age is checked before
   availability, so an aged-out ``available=True`` row reads UNKNOWN.
3. **Zero completion spend is structural.** Every method a probe can emit is
   in ``FREE_ENDPOINTS``, and no non-docstring string literal in the module
   names a completions endpoint.
4. **A declared-but-absent model reads RED.** The ``hou.ActiveRender`` pattern
   — documented and missing at runtime — caught by construction.

Network-free by construction: every probe test monkeypatches
``probe._request``. Qt-free, hou-free.
"""
import ast
import inspect
import json
import pathlib

import pytest

from synapse.panel.providers import probe as P


NOW = 1_800_000_000.0     # a fixed clock; every test passes now= explicitly


def _result(**over):
    """A fresh, available, green-by-default row. Overrides shift one axis."""
    base = dict(
        model="m", tier_candidates=(P.TIER_BALANCED,), available=True,
        quota_remaining=None, quota_total=None,
        cost_per_1k_in=None, cost_per_1k_out=None,
        latency_ms=12.0, probed_at=NOW, provider="test",
        method="local:config", evidence_tier="VERIFIED-RUNTIME",
    )
    base.update(over)
    return P.ProbeResult(**base)


# ---------------------------------------------------------------------------
# 1 · Colour is computed, never stored
# ---------------------------------------------------------------------------

def test_colour_is_not_a_field():
    """Fails if anyone adds a colour/status/state field to ProbeResult.

    A stored colour is a colour that can be stale without saying so — which is
    the entire failure mode this layer is built against.
    """
    names = set(P.result_field_names())
    for banned in ("colour", "color", "status", "state", "health"):
        assert banned not in names, "%r must be computed, not stored" % banned


def test_serialized_result_carries_no_colour():
    payload = json.loads(json.dumps(_result().to_dict()))
    for banned in ("colour", "color", "status", "state", "health"):
        assert banned not in payload


def test_colour_for_is_a_pure_function_of_time():
    """The same row reads GREEN now and GREY later. Nothing on the row changed."""
    r = _result()
    assert P.colour_for(r, now=NOW) == P.COLOUR_GREEN
    assert P.colour_for(r, now=NOW + P.PROBE_TTL_S + 1) == P.COLOUR_GREY


# ---------------------------------------------------------------------------
# 2 · Staleness degrades to GREY, never to green
# ---------------------------------------------------------------------------

def test_stale_available_row_is_grey_not_green():
    """The load-bearing case: available=True, but the probe is old."""
    r = _result(available=True)
    assert P.colour_for(r, now=NOW + P.PROBE_TTL_S + 0.001) == P.COLOUR_GREY


def test_never_probed_is_grey():
    assert P.colour_for(_result(probed_at=None), now=NOW) == P.COLOUR_GREY


def test_future_timestamp_is_grey_not_green():
    """Clock skew is not freshness. A future stamp must not pin a rail green."""
    r = _result(probed_at=NOW + 3600)
    assert P.colour_for(r, now=NOW) == P.COLOUR_GREY


def test_boundary_exactly_at_ttl_is_still_fresh():
    r = _result()
    assert P.colour_for(r, now=NOW + P.PROBE_TTL_S) == P.COLOUR_GREEN
    assert P.colour_for(r, now=NOW + P.PROBE_TTL_S + 1e-6) == P.COLOUR_GREY


def test_staleness_outranks_availability_in_both_directions():
    """Stale wins whatever the availability says — GREY, never GREEN, never RED."""
    for available in (True, False):
        r = _result(available=available)
        assert P.colour_for(r, now=NOW + 10_000) == P.COLOUR_GREY


def test_is_stale_and_age_agree_with_colour():
    r = _result()
    assert P.is_stale(r, now=NOW) is False
    assert P.is_stale(r, now=NOW + P.PROBE_TTL_S + 1) is True
    assert P.age_s(r, now=NOW + 5) == pytest.approx(5.0)
    assert P.age_s(_result(probed_at=None)) is None


# ---------------------------------------------------------------------------
# 3 · RED, and what does NOT make RED
# ---------------------------------------------------------------------------

def test_fresh_unavailable_is_red():
    r = _result(available=False, reason="unreachable")
    assert P.colour_for(r, now=NOW) == P.COLOUR_RED


def test_exhausted_quota_is_red():
    r = _result(quota_remaining=0, quota_total=1000)
    assert P.colour_for(r, now=NOW) == P.COLOUR_RED


def test_unknown_quota_does_not_manufacture_red():
    """``None`` means no quota signal was obtainable — it is not zero."""
    r = _result(quota_remaining=None, quota_source="unavailable_at_zero_cost")
    assert P.colour_for(r, now=NOW) == P.COLOUR_GREEN


def test_positive_quota_is_green():
    assert P.colour_for(_result(quota_remaining=7, quota_total=1000),
                        now=NOW) == P.COLOUR_GREEN


def test_cost_never_affects_colour():
    """A price cannot make anything green, or red."""
    cheap = _result(cost_per_1k_in=0.0, cost_per_1k_out=0.0)
    dear = _result(cost_per_1k_in=999.0, cost_per_1k_out=999.0)
    unknown = _result(cost_per_1k_in=None, cost_per_1k_out=None)
    colours = {P.colour_for(r, now=NOW) for r in (cheap, dear, unknown)}
    assert colours == {P.COLOUR_GREEN}


def test_only_three_colours_exist():
    assert set(P.COLOURS) == {"green", "red", "grey"}
    seen = set()
    for available in (True, False):
        for quota in (None, 0, 5):
            for stamp in (None, NOW, NOW - 10_000, NOW + 10_000):
                seen.add(P.colour_for(
                    _result(available=available, quota_remaining=quota,
                            probed_at=stamp), now=NOW))
    assert seen <= set(P.COLOURS)


# ---------------------------------------------------------------------------
# 4 · Polling — the probe must not be the thing that trips a rate limit
# ---------------------------------------------------------------------------

def test_should_refresh_is_demand_driven():
    assert P.should_refresh(None) is True
    assert P.should_refresh(_result(probed_at=None)) is True
    assert P.should_refresh(_result(), now=NOW) is False
    assert P.should_refresh(_result(), now=NOW + P.REFRESH_INTERVAL_S) is True
    assert P.should_refresh(_result(), now=NOW + P.REFRESH_INTERVAL_S - 0.001) is False


def test_future_stamp_forces_a_refresh():
    assert P.should_refresh(_result(probed_at=NOW + 3600), now=NOW) is True


def test_ttl_exceeds_refresh_interval():
    """TTL must be strictly longer than the refresh interval, or a row greys
    before the layer is even allowed to re-probe it."""
    assert P.PROBE_TTL_S > P.REFRESH_INTERVAL_S
    assert P.PROBE_TTL_S / P.REFRESH_INTERVAL_S >= 2.0


def test_refresh_interval_is_at_least_one_per_minute():
    """A liveness check that consumes the quota it reports on is self-defeating.
    60s/provider is ~1 rpm, far under any published request-rate tier."""
    assert P.REFRESH_INTERVAL_S >= 60.0


# ---------------------------------------------------------------------------
# 5 · Zero completion spend, structurally
# ---------------------------------------------------------------------------

def _code_string_literals():
    """Every string literal in probe.py that is NOT a docstring.

    Docstrings are excluded on purpose: the module documentation *names* the
    completions endpoints in order to say it never calls them, and a naive
    grep would flag its own disclaimer.
    """
    src = pathlib.Path(inspect.getfile(P)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
        # PEP 258 attribute docstrings: a bare string statement anywhere
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            docstrings.add(id(node.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def test_no_completions_endpoint_in_executable_code():
    """Fails the moment a completions path is introduced as real code."""
    for lit in _code_string_literals():
        low = lit.lower()
        assert "chat/completions" not in low, "completions endpoint literal: %r" % lit
        assert "/completions" not in low or "count_tokens" in low, \
            "completions endpoint literal: %r" % lit
        # /v1/messages is the billed endpoint; only its count_tokens child is free
        assert not (low.startswith("/v1/messages") and "count_tokens" not in low), \
            "billed messages endpoint literal: %r" % lit


def test_probe_module_never_streams():
    """The probe must not reach a provider's completion path at all."""
    src = pathlib.Path(inspect.getfile(P)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "stream" not in called


def test_every_emitted_method_is_in_the_free_allowlist(monkeypatch):
    """Whatever a probe reports as its method must be a free endpoint."""
    monkeypatch.setattr(P, "_request", _boom)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    rows = P.probe_all(now=NOW)
    assert rows, "probe_all returned nothing to check"
    for r in rows:
        assert r.method in P.FREE_ENDPOINTS, "%r is not a free endpoint" % r.method


def test_free_endpoint_allowlist_holds_no_completions():
    for endpoint in P.FREE_ENDPOINTS:
        low = endpoint.lower()
        assert "chat/completions" not in low
        assert not (low.endswith("/v1/messages"))


def test_egress_doc_documents_the_probe_lane():
    """The frozen-egress pin was extended to admit probe.py; this is the other
    half of that bargain.

    ``test_m3_egress_docs.py`` allowlists the file, which on its own would let
    the documentation rot away while the pin stayed green. This fails if the
    EGRESS.md paragraph that justified the allowlist entry is removed.
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    doc = (root / "docs" / "studio" / "EGRESS.md").read_text(encoding="utf-8")
    assert "panel/providers/probe.py" in doc
    assert "capability-probe lane" in doc
    assert "GET /v1/models" in doc
    # the load-bearing security claim: this lane carries no payload
    assert "metadata only" in doc.lower()


# ---------------------------------------------------------------------------
# 6 · Tiering is derived from what the probe returned
# ---------------------------------------------------------------------------

def test_parse_parameter_size():
    assert P.parse_parameter_size("123.6B") == pytest.approx(123.6)
    assert P.parse_parameter_size("2.81T") == pytest.approx(2810.0)
    assert P.parse_parameter_size("756b") == pytest.approx(756.0)
    assert P.parse_parameter_size("8.0B") == pytest.approx(8.0)
    assert P.parse_parameter_size("500M") == pytest.approx(0.5)
    assert P.parse_parameter_size(None) is None
    assert P.parse_parameter_size("") is None
    assert P.parse_parameter_size("large") is None


def test_parameter_size_outranks_name_token():
    """A numeric size is the stronger evidence and must win.

    ``nemotron-mini`` carries a FAST token, but if the provider says it is
    600B the size decides — the point of probe-derived tiering.
    """
    tiers, basis = P.tier_candidates_for("nemotron-mini:latest",
                                         parameter_size="600B")
    assert tiers == (P.TIER_FRONTIER,)
    assert basis == "parameter_size"


def test_live_id_token_classifies_when_no_size_is_published():
    assert P.tier_candidates_for("claude-opus-5") == ((P.TIER_FRONTIER,), "live_id_token")
    assert P.tier_candidates_for("claude-sonnet-5") == ((P.TIER_BALANCED,), "live_id_token")
    assert P.tier_candidates_for("claude-haiku-4-5-20251001") == (
        (P.TIER_FAST,), "live_id_token")


def test_unclassified_gets_no_tier_never_a_default():
    """A model nothing established a tier for must not be routable.

    A default tier would be a guess wearing a tier constant.
    """
    tiers, basis = P.tier_candidates_for("zzz-unknown-model-9000")
    assert tiers == ()
    assert basis == "unclassified"


def test_no_tool_capability_is_a_hard_gate():
    tiers, basis = P.tier_candidates_for("big-model", parameter_size="900B",
                                         capabilities=["completion", "vision"])
    assert tiers == ()
    assert basis == "no_tool_capability"


def test_unknown_capabilities_apply_no_gate():
    """Absence of evidence is not evidence of absence."""
    tiers, basis = P.tier_candidates_for("claude-opus-5", capabilities=None)
    assert tiers == (P.TIER_FRONTIER,)
    assert basis == "live_id_token"


def test_tier_thresholds_are_ordered():
    assert P.FRONTIER_MIN_B > P.BALANCED_MIN_B > 0
    assert P.tier_candidates_for("x", parameter_size="%.1fB" % P.FRONTIER_MIN_B)[0] \
        == (P.TIER_FRONTIER,)
    assert P.tier_candidates_for("x", parameter_size="%.1fB" % P.BALANCED_MIN_B)[0] \
        == (P.TIER_BALANCED,)
    assert P.tier_candidates_for("x", parameter_size="1.0B")[0] == (P.TIER_FAST,)


# ---------------------------------------------------------------------------
# 7 · A declared-but-absent model reads RED (the ActiveRender pattern)
# ---------------------------------------------------------------------------

def test_declared_but_absent_model_is_red():
    rows = P._rows(
        "test",
        live={"really-there": {"display_name": "", "capabilities": None,
                               "cost": (None, None, "unprobeable")}},
        declared=["really-there", "typed-into-a-config-file"],
        probed_at=NOW, latency_ms=5.0,
        quota=(None, None, "unavailable_at_zero_cost"),
        method="local:config",
    )
    by_model = {r.model: r for r in rows}
    assert by_model["really-there"].available is True
    assert by_model["really-there"].live is True
    ghost = by_model["typed-into-a-config-file"]
    assert ghost.available is False
    assert ghost.reason == "declared_but_absent"
    assert ghost.declared is True and ghost.live is False
    assert P.colour_for(ghost, now=NOW) == P.COLOUR_RED


def test_live_model_absent_from_registry_is_still_returned():
    """Probe-derived means the live list wins — a model the registry never
    heard of is reported, not dropped."""
    rows = P._rows("test",
                   live={"brand-new:cloud": {"display_name": "", "capabilities": None,
                                             "cost": (None, None, "unprobeable")}},
                   declared=[], probed_at=NOW, latency_ms=1.0,
                   quota=(None, None, "x"), method="local:config")
    assert [r.model for r in rows] == ["brand-new:cloud"]
    assert rows[0].live is True and rows[0].declared is False


# ---------------------------------------------------------------------------
# 8 · Quota header parsing
# ---------------------------------------------------------------------------

def test_quota_absent_is_reported_as_unobtainable_not_zero():
    rem, total, src = P._quota_from_headers({"date": "now", "server": "cloudflare"})
    assert rem is None and total is None
    assert src == "unavailable_at_zero_cost"


def test_quota_headers_are_parsed_when_present():
    rem, total, src = P._quota_from_headers({
        "anthropic-ratelimit-requests-remaining": "3",
        "anthropic-ratelimit-requests-limit": "50",
    })
    assert (rem, total) == (3, 50)
    assert src.startswith("header:")


def test_malformed_quota_header_does_not_fabricate_a_number():
    rem, total, src = P._quota_from_headers(
        {"x-ratelimit-remaining": "lots", "x-ratelimit-limit": "50"})
    assert rem is None


# ---------------------------------------------------------------------------
# 9 · Transport failure is RED with a reason, never a lost provider
# ---------------------------------------------------------------------------

def _boom(*a, **kw):
    raise OSError("probe test: network is closed")


def test_unreachable_provider_is_red_with_a_reason(monkeypatch):
    monkeypatch.setattr(P, "_request", _boom)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    rows = P.probe_ollama(now=NOW)
    assert rows, "an unreachable provider must still emit its declared rows"
    for r in rows:
        assert r.available is False
        assert r.reason == "unreachable"
        assert P.colour_for(r, now=NOW) == P.COLOUR_RED


def test_http_error_status_is_carried_in_the_reason(monkeypatch):
    monkeypatch.setattr(P, "_request", lambda *a, **k: (503, {}, "", 4.0))
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    rows = P.probe_ollama(now=NOW)
    assert all(r.reason == "http_503" for r in rows)


def test_rate_limited_status_is_red_with_rate_limited_reason(monkeypatch):
    monkeypatch.setattr(P, "_request", lambda *a, **k: (
        429, {"anthropic-ratelimit-requests-remaining": "0",
              "anthropic-ratelimit-requests-limit": "50"}, "", 4.0))
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    rows = P.probe_ollama(now=NOW)
    assert rows
    for r in rows:
        assert r.reason == "rate_limited"
        assert r.quota_remaining == 0
        assert P.colour_for(r, now=NOW) == P.COLOUR_RED


def test_unparseable_response_does_not_read_available(monkeypatch):
    monkeypatch.setattr(P, "_request", lambda *a, **k: (200, {}, "<html>nope", 4.0))
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    rows = P.probe_ollama(now=NOW)
    assert all(r.available is False for r in rows)
    assert all(r.reason == "unparseable_response" for r in rows)


def test_unconfigured_provider_makes_no_network_call(monkeypatch):
    """No key ⇒ a local observation, not a request. Fails if a probe fires."""
    monkeypatch.setattr(P, "_request", _boom)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    rows = P.probe_gemini(now=NOW)
    for r in rows:
        assert r.method == "local:config"
        assert r.reason == "unconfigured"
        assert P.colour_for(r, now=NOW) == P.COLOUR_RED


# ---------------------------------------------------------------------------
# 10 · Ollama payload shape — cost is probed where it can be
# ---------------------------------------------------------------------------

_OLLAMA_PAYLOAD = json.dumps({"models": [
    {"name": "gemma4:latest", "details": {"parameter_size": "8.0B"},
     "capabilities": ["completion", "tools", "thinking"]},
    {"name": "glm-5.2:cloud", "remote_host": "https://ollama.com:443",
     "details": {"parameter_size": "756b"},
     "capabilities": ["completion", "tools", "thinking"]},
]})


def test_local_tag_costs_zero_and_cloud_tag_costs_unknown(monkeypatch):
    """A local tag's zero cost is PROBED (no remote_host). A ``:cloud`` tag is
    metered by that host, so its cost is unknown — not zero."""
    monkeypatch.setattr(P, "_request", lambda *a, **k: (200, {}, _OLLAMA_PAYLOAD, 3.0))
    rows = {r.model: r for r in P.probe_ollama(now=NOW)}
    local = rows["gemma4:latest"]
    assert (local.cost_per_1k_in, local.cost_per_1k_out) == (0.0, 0.0)
    assert local.cost_source == "probed:local_weights_no_remote_host"
    cloud = rows["glm-5.2:cloud"]
    assert cloud.cost_per_1k_in is None and cloud.cost_per_1k_out is None
    assert cloud.cost_source.startswith("metered:")


def test_ollama_tiers_come_from_the_probed_parameter_size(monkeypatch):
    monkeypatch.setattr(P, "_request", lambda *a, **k: (200, {}, _OLLAMA_PAYLOAD, 3.0))
    rows = {r.model: r for r in P.probe_ollama(now=NOW)}
    assert rows["glm-5.2:cloud"].tier_candidates == (P.TIER_FRONTIER,)
    assert rows["gemma4:latest"].tier_candidates == (P.TIER_FAST,)
    assert all(r.tier_basis == "parameter_size" for r in rows.values() if r.live)


def test_probe_rows_are_stamped_and_measured(monkeypatch):
    monkeypatch.setattr(P, "_request", lambda *a, **k: (200, {}, _OLLAMA_PAYLOAD, 3.0))
    for r in P.probe_ollama(now=NOW):
        assert r.probed_at == NOW
        assert r.latency_ms == 3.0
        assert r.method in P.FREE_ENDPOINTS
        assert r.evidence_tier == "VERIFIED-RUNTIME"


# ---------------------------------------------------------------------------
# 11 · Aggregation
# ---------------------------------------------------------------------------

def test_summarize_counts_by_computed_colour():
    rows = [_result(model="a"),
            _result(model="b", available=False),
            _result(model="c", probed_at=NOW - 10_000),
            _result(model="d", tier_candidates=())]
    s = P.summarize(rows, now=NOW)
    assert s["rows"] == 4
    assert s["by_colour"] == {"green": 2, "red": 1, "grey": 1}
    assert s["unclassified"] == 1
    assert s["ttl_s"] == P.PROBE_TTL_S


def test_summarize_moves_to_grey_as_the_clock_advances():
    rows = [_result(model="a"), _result(model="b")]
    assert P.summarize(rows, now=NOW)["by_colour"]["green"] == 2
    later = P.summarize(rows, now=NOW + P.PROBE_TTL_S + 1)["by_colour"]
    assert later["grey"] == 2 and later["green"] == 0


def test_probe_all_is_deterministically_ordered(monkeypatch):
    monkeypatch.setattr(P, "_request", _boom)
    rows = P.probe_all(now=NOW)
    keys = [(r.provider, r.model) for r in rows]
    assert keys == sorted(keys)


def test_probe_all_rejects_unknown_provider_ids(monkeypatch):
    monkeypatch.setattr(P, "_request", _boom)
    assert P.probe_all(["not-a-provider"], now=NOW) == []


# ---------------------------------------------------------------------------
# 12 · No Qt, no hou (the StreamProvider contract)
# ---------------------------------------------------------------------------

def test_module_imports_no_qt_and_no_hou():
    src = pathlib.Path(inspect.getfile(P)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "hou" not in imported
    assert not {"PySide2", "PySide6", "PyQt5", "PyQt6", "Qt"} & imported
