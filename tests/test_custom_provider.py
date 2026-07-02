"""Floor guard for the Custom panel provider (user-configured OpenAI-compat
endpoint). CustomProvider subclasses NemotronProvider — the transport, SSE
parser, and <think> filter are inherited (pinned by the nemotron/ollama
tests), so this pins the delta: the injected base_url endpoint resolution,
the resolve_key matrix (incl. unconfigured → SURFACED, never a silent Claude
switch), and the settings-injected registry integration. Qt-free, hou-free,
network-free.
"""
from synapse.panel.providers.custom_provider import CustomProvider


def _prov(base_url="http://localhost:8000", model="qwen3-vl:30b", key_env=""):
    return CustomProvider(base_url=base_url, model=model, key_env=key_env,
                          max_tokens=4096)


# -- endpoint resolution (injected base_url) ----------------------------------

def test_endpoint_variants():
    cases = {
        "http://localhost:8000":      ("http", "localhost:8000", "/v1/chat/completions"),
        "https://api.example.com/v1": ("https", "api.example.com", "/v1/chat/completions"),
        "https://host.tld/":          ("https", "host.tld", "/v1/chat/completions"),
        "host.tld":                   ("https", "host.tld", "/v1/chat/completions"),  # bare → TLS
        "https://proxy.host/serve":   ("https", "proxy.host", "/serve/chat/completions"),
    }
    for base, exp in cases.items():
        assert _prov(base_url=base)._get_endpoint() == exp, "base %r" % base


def test_no_reasoning_directive():
    # "detailed thinking on/off" is Nemotron-specific — never sent to a
    # user-configured backend.
    assert _prov()._system_directive() is None


# -- resolve_key matrix --------------------------------------------------------

def test_unconfigured_resolves_none_with_configure_message():
    for prov in (_prov(base_url=""), _prov(model=""), _prov(base_url="", model="")):
        assert prov.resolve_key() is None
        assert "Configure" in prov.key_error_message()


def test_configured_keyless_is_not_needed(monkeypatch):
    monkeypatch.delenv("MY_CUSTOM_KEY", raising=False)
    assert _prov().resolve_key() == "not-needed"


def test_key_env_resolution(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_KEY", "  sk-custom-1  ")
    assert _prov(key_env="MY_CUSTOM_KEY").resolve_key() == "sk-custom-1"


def test_key_env_missing_is_none_with_env_named_message(monkeypatch):
    monkeypatch.delenv("MY_CUSTOM_KEY", raising=False)
    prov = _prov(key_env="MY_CUSTOM_KEY")
    assert prov.resolve_key() is None
    assert "MY_CUSTOM_KEY" in prov.key_error_message()


def test_key_env_ignores_other_provider_keys(monkeypatch):
    monkeypatch.delenv("MY_CUSTOM_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert _prov(key_env="MY_CUSTOM_KEY").resolve_key() is None


# -- registry integration (settings-injected; NEVER the Claude floor) ---------

def _patch_settings(monkeypatch, base_url="", model="", key_env=""):
    from synapse.panel import settings as pset
    monkeypatch.setattr(pset, "load_settings", lambda path=None: {
        "version": 1, "provider_id": "custom", "model_by_provider": {},
        "custom": {"base_url": base_url, "model": model, "key_env": key_env}})


def test_registry_builds_custom_never_the_floor(monkeypatch):
    from synapse.panel.providers import registry as reg
    _patch_settings(monkeypatch)                       # UNCONFIGURED
    prov = reg.build_provider("custom")
    assert prov.id == "custom"                         # never the Claude floor
    assert prov.resolve_key() is None

    _patch_settings(monkeypatch, base_url="http://localhost:11434", model="glm-5:cloud")
    prov = reg.build_provider("custom")
    assert prov.id == "custom"
    assert prov.model_identity == "glm-5:cloud"
    assert prov._get_endpoint() == ("http", "localhost:11434", "/v1/chat/completions")


def test_registry_rows_track_the_config(monkeypatch):
    from synapse.panel.providers import registry as reg
    assert "custom" in reg.PROVIDER_IDS
    assert reg.PROVIDER_LABELS["custom"] == "Custom"
    _patch_settings(monkeypatch)                       # unconfigured → empty
    assert reg.models_for("custom") == ()
    assert reg.default_model("custom") == ""
    _patch_settings(monkeypatch, model="qwen3-vl:30b")
    assert reg.models_for("custom") == (("qwen3-vl:30b", "qwen3-vl:30b"),)
    assert reg.default_model("custom") == "qwen3-vl:30b"


def test_model_override_beats_config(monkeypatch):
    from synapse.panel.providers import registry as reg
    _patch_settings(monkeypatch, base_url="http://localhost:8000", model="a")
    assert reg.build_provider("custom", model="b").model_identity == "b"
