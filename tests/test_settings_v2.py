"""Settings schema v2 (rope L5-3) — profile + model_choice + v1 migration.

Pins: a v1 file loads as expert; corrupt/unshaped loads as defaults; both new
keys round-trip through save/load; semantic values persist as tokens and are
resolved against the L4-2a catalog only at compose time. Qt-free, hou-free,
network-free (tmp_path only).
"""
import json

from synapse.panel import settings as pset
from synapse.panel.providers import catalog


V1_FILE = {
    "version": 1,
    "provider_id": "claude",
    "model_by_provider": {"claude": "claude-sonnet-4-6"},
    "custom": {"base_url": "", "model": "", "key_env": ""},
}


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _entry(mid, local, latency):
    return catalog.CatalogEntry(
        id=mid, provider="ollama", endpoint="http://127.0.0.1:11434",
        local=local, first_seen=1.0, last_seen=2.0,
        latency_ms=latency, auth_ok=True)


# --- migration ---------------------------------------------------------------

def test_v1_file_loads_as_expert(tmp_path):
    st = pset.load_settings(_write(tmp_path / "panel_settings.json", V1_FILE))
    assert st["version"] == pset.SETTINGS_VERSION == 2
    assert st["profile"] == "expert"
    assert st["fresh_install"] is False       # a v1 file is a configured install
    # v1 model_by_provider migrates as an exact pick for the active provider
    assert st["model_choice"] == {"mode": "exact", "value": "claude-sonnet-4-6"}
    assert st["model_by_provider"] == {"claude": "claude-sonnet-4-6"}


def test_missing_file_is_fresh_install_defaulting_expert(tmp_path):
    st = pset.load_settings(tmp_path / "nope.json")
    assert st == pset.default_settings()
    assert st["fresh_install"] is True        # skippable picker; skip = expert
    assert st["profile"] == "expert"


# --- defaults-on-corrupt (v1 behavior kept) ----------------------------------

def test_corrupt_file_returns_defaults(tmp_path):
    p = tmp_path / "panel_settings.json"
    p.write_text("{not json", encoding="utf-8")
    assert pset.load_settings(p) == pset.default_settings()


def test_unshaped_file_returns_defaults(tmp_path):
    p = _write(tmp_path / "panel_settings.json", ["not", "a", "dict"])
    assert pset.load_settings(p) == pset.default_settings()


def test_invalid_profile_and_choice_sanitize(tmp_path):
    bad = dict(V1_FILE, version=2, profile="wizard",
               model_choice={"mode": "semantic", "value": "cheapest"})
    st = pset.load_settings(_write(tmp_path / "panel_settings.json", bad))
    assert st["profile"] == "expert"          # unknown profile → expert
    # invalid choice falls back to the v1-style migration (exact)
    assert st["model_choice"] == {"mode": "exact", "value": "claude-sonnet-4-6"}


def test_exactly_three_profiles():
    assert pset.PROFILES == ("curious", "expert", "ml")
    assert pset.SEMANTIC_VALUES == ("free_local", "balanced", "best")


# --- round-trip --------------------------------------------------------------

def test_new_keys_round_trip_semantic(tmp_path):
    p = tmp_path / "panel_settings.json"
    st = pset.default_settings()
    st["profile"] = "curious"
    st["model_choice"] = {"mode": "semantic", "value": "balanced"}
    assert pset.save_settings(st, p)
    back = pset.load_settings(p)
    assert back["profile"] == "curious"
    assert back["model_choice"] == {"mode": "semantic", "value": "balanced"}


def test_new_keys_round_trip_exact(tmp_path):
    p = tmp_path / "panel_settings.json"
    st = pset.default_settings()
    st["profile"] = "ml"
    st["model_choice"] = {"mode": "exact", "value": "qwen3:32b"}
    assert pset.save_settings(st, p)
    back = pset.load_settings(p)
    assert back["profile"] == "ml"
    assert back["model_choice"] == {"mode": "exact", "value": "qwen3:32b"}


def test_semantic_token_persists_unresolved(tmp_path):
    # write time stores the token; resolution is compose-time only
    p = tmp_path / "panel_settings.json"
    st = pset.default_settings()
    st["profile"] = "curious"
    st["model_choice"] = {"mode": "semantic", "value": "best"}
    assert pset.save_settings(st, p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["model_choice"] == {"mode": "semantic", "value": "best"}


# --- compose-time resolution against the L4-2a catalog -----------------------

def test_resolve_exact_ignores_catalog(tmp_path):
    st = pset.default_settings()
    st["model_choice"] = {"mode": "exact", "value": "claude-sonnet-4-6"}
    assert pset.resolve_model_choice(st, tmp_path / "absent.json") == \
        "claude-sonnet-4-6"


def test_resolve_semantic_reads_catalog(tmp_path):
    cat = tmp_path / "model_catalog.json"
    assert catalog.save_catalog([
        _entry("tiny:3b", local=True, latency=12.0),
        _entry("mid:32b", local=False, latency=80.0),
        _entry("big:70b", local=False, latency=200.0),
    ], cat)

    def pick(value):
        st = pset.default_settings()
        st["model_choice"] = {"mode": "semantic", "value": value}
        return pset.resolve_model_choice(st, cat)

    assert pick("free_local") == "tiny:3b"    # the fastest local entry
    assert pick("best") == "big:70b"          # largest size hint
    assert pick("balanced") == "mid:32b"      # median size hint


def test_resolve_semantic_empty_catalog_is_empty_string(tmp_path):
    st = pset.default_settings()
    st["model_choice"] = {"mode": "semantic", "value": "best"}
    assert pset.resolve_model_choice(st, tmp_path / "absent.json") == ""
