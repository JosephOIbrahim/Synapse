"""Floor guard for the Ollama panel provider.

OllamaProvider subclasses NemotronProvider — the OpenAI-compat SSE parser and
the <think> filter are inherited, so this pins the delta: the OLLAMA_HOST
endpoint resolution, the never-blocks key posture, the /api/tags row parser,
and the registry integration. Qt-free, hou-free, network-free (the one
failure-path test points at an unroutable localhost port).
"""
import json

from synapse.panel.providers.ollama_provider import (
    OllamaProvider,
    _ollama_endpoint,
    _parse_tags,
)


def _prov():
    return OllamaProvider(model="glm-5:cloud", max_tokens=4096)


# -- endpoint resolution (OLLAMA_HOST) ---------------------------------------

def test_default_endpoint_is_plaintext_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert _prov()._get_endpoint() == ("http", "localhost:11434", "/v1/chat/completions")


def test_endpoint_variants(monkeypatch):
    cases = {
        "localhost:11434":            ("http", "localhost:11434", "/v1/chat/completions"),
        "http://127.0.0.1:11434":     ("http", "127.0.0.1:11434", "/v1/chat/completions"),
        "http://127.0.0.1:11434/":    ("http", "127.0.0.1:11434", "/v1/chat/completions"),
        "https://ollama.example.com": ("https", "ollama.example.com", "/v1/chat/completions"),
        "https://proxy.host/ollama":  ("https", "proxy.host", "/ollama/v1/chat/completions"),
    }
    for base, exp in cases.items():
        monkeypatch.setenv("OLLAMA_HOST", base)
        assert _prov()._get_endpoint() == exp, "base %r" % base


def test_nemotron_base_url_does_not_leak_into_ollama(monkeypatch):
    # provider identities stay distinct — NVIDIA_BASE_URL must not steer Ollama
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    scheme, host, _path = _prov()._get_endpoint()
    assert (scheme, host) == ("http", "localhost:11434")


# -- system directive + inherited SSE parse ----------------------------------

def test_no_reasoning_directive():
    assert _prov()._system_directive() is None


def test_inherited_sse_parse_with_glm_think_spans():
    """Smoke: the inherited OpenAI SSE parser + <think> filter serve GLM —
    reasoning stripped from the stream AND the replayed block, tags split
    across chunk boundaries included."""

    class _FakeResponse:
        def __init__(self, data: bytes):
            self._buf = data

        def read(self, n: int = 4096) -> bytes:
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

    def _sse(chunks) -> bytes:
        out = []
        for ch in chunks:
            out.append("data: %s" % json.dumps({"choices": [ch]}))
            out.append("")
        out.append("data: [DONE]")
        out.append("")
        return ("\n".join(out) + "\n").encode("utf-8")

    tokens = []
    stream = _sse([
        {"delta": {"content": "<thi"}, "finish_reason": None},
        {"delta": {"content": "nk>chain of thought</th"}, "finish_reason": None},
        {"delta": {"content": "ink>visible "}, "finish_reason": None},
        {"delta": {"tool_calls": [
            {"index": 0, "id": "call_1",
             "function": {"name": "houdini_create_node", "arguments": '{"parent":"/obj"}'}}]},
         "finish_reason": "tool_calls"},
    ])
    stop, blocks = _prov()._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)
    assert "chain of thought" not in "".join(tokens)
    assert "".join(tokens) == "visible "
    assert stop == "tool_use"
    assert blocks[0] == {"type": "text", "text": "visible "}
    assert blocks[1]["name"] == "houdini_create_node"
    assert blocks[1]["input"] == {"parent": "/obj"}


# -- key posture (never blocks) ----------------------------------------------

def test_resolve_key_not_needed_by_default(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert _prov().resolve_key() == "not-needed"


def test_resolve_key_uses_ollama_api_key_when_set(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "  sk-oll-1  ")
    assert _prov().resolve_key() == "sk-oll-1"


def test_resolve_key_ignores_other_provider_keys(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert _prov().resolve_key() == "not-needed"


# -- /api/tags parsing + failure → None ---------------------------------------

def test_parse_tags_rows():
    data = {"models": [{"name": "glm-5:cloud"}, {"name": "gemma4:latest"}, {"name": ""}]}
    assert _parse_tags(data) == (("glm-5:cloud", "glm-5:cloud"),
                                 ("gemma4:latest", "gemma4:latest"))


def test_parse_tags_empty_or_unshaped_is_none():
    assert _parse_tags({"models": []}) is None
    assert _parse_tags({}) is None
    assert _parse_tags("garbage") is None


def test_available_models_none_on_dead_host(monkeypatch):
    # an unroutable localhost port fails fast — connection refused, no hang
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    assert OllamaProvider.available_models(timeout=0.5) is None


# -- registry integration -----------------------------------------------------

def test_registry_builds_ollama():
    from synapse.panel.providers.registry import build_provider, OLLAMA_MODEL
    prov = build_provider("ollama")
    assert prov.id == "ollama"
    assert prov.model_identity == OLLAMA_MODEL


def test_registry_rows_and_labels():
    from synapse.panel.providers import registry as reg
    assert "ollama" in reg.PROVIDER_IDS
    assert reg.PROVIDER_LABELS["ollama"] == "Ollama"
    ids = [m for m, _ in reg.models_for("ollama")]
    assert reg.OLLAMA_MODEL in ids
    # the fallback GLM label is short + chip-safe (no slash, no raw tag colon)
    lbl = reg.model_label("ollama", reg.OLLAMA_MODEL)
    assert "/" not in lbl and ":" not in lbl and 0 < len(lbl) < 30
