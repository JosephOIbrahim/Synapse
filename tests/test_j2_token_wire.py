"""J2 - TOKEN counts tokens (RULING_JOE_FIVE.md J2, 2026-09-05).

Joe: "the whole point of TOKEN is it supposed to count token use. If that
isnt possible this shouldnt exist. Currently it does nothing."

The trace behind the ruling: the worker already folds ``provider.last_usage``
into ``usage_sink`` after every ``stream()`` (claude_worker.py), but only the
Anthropic adapter ever set ``last_usage``. Ollama / Custom / Nemotron share
one OpenAI-style parser that never read the ``usage`` chunk (and never asked
for one - no ``stream_options``), Gemini's parser skipped ``usageMetadata``,
the sink knew one task at a time with no session, no provider id and no
context window, and the face had no prompt / completion / total row at all.

Six pins, stock Python, network-free (``-k token`` selects this file):

  (a) the OpenAI-style parser lands the usage chunk on ``last_usage``
  (b) the request body asks for it (``stream_options.include_usage``)
  (c) the Gemini parser lands ``usageMetadata``
  (d) the sink accumulates a SESSION across tasks, task fields stay per-task
  (e) context window + last prompt -> the share arithmetic
  (f) ``model_facts.cost``: local ollama -> $0, unknown -> None, never a bool

Every number here is one the provider reported; nothing is estimated (R162).
"""
import http.client
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402


class _FakeResponse:
    """Minimal http.client.HTTPResponse stand-in: ``.read(n)`` drains a buffer."""

    status = 200

    def __init__(self, data: bytes):
        self._buf = data

    def read(self, n: int = 4096) -> bytes:
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk


def _openai_sse(chunks, usage=None) -> bytes:
    """OpenAI chat-completions SSE: delta chunks, then - exactly as Ollama
    0.33.2 emits it with ``stream_options.include_usage`` (recorded live
    2026-09-05) - a final chunk with ``choices: []`` carrying ``usage``."""
    out = []
    for ch in chunks:
        out.append("data: %s" % json.dumps({"choices": [ch]}))
        out.append("")
    if usage is not None:
        out.append("data: %s" % json.dumps({"choices": [], "usage": usage}))
        out.append("")
    out.append("data: [DONE]")
    out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")


def _gemini_sse(chunks) -> bytes:
    out = []
    for ch in chunks:
        out.append("data: %s" % json.dumps(ch))
        out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")


_NOOP = dict(emit_token=lambda s: None, should_abort=lambda: False)


# --------------------------------------------------------------------- (a) --

def test_openai_usage_chunk_lands_on_last_usage():
    from synapse.panel.providers.nemotron_provider import NemotronProvider
    prov = NemotronProvider(model="nemotron-mini:latest", max_tokens=4)

    stream = _openai_sse(
        [{"delta": {"content": "Hi"}, "finish_reason": None},
         {"delta": {}, "finish_reason": "length"}],
        usage={"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15})
    stop, blocks = prov._parse_sse_stream(_FakeResponse(stream), **_NOOP)
    assert stop == "length"
    assert blocks == [{"type": "text", "text": "Hi"}]
    assert prov.last_usage == {"input_tokens": 11, "output_tokens": 4}

    # No usage chunk -> None (not measured), never the previous call's numbers.
    prov._parse_sse_stream(_FakeResponse(_openai_sse(
        [{"delta": {"content": "x"}, "finish_reason": "stop"}])), **_NOOP)
    assert prov.last_usage is None

    # bool is an int subclass and must never be read as a count; a partial
    # receipt keeps only the genuine field.
    prov._parse_sse_stream(_FakeResponse(_openai_sse(
        [{"delta": {"content": "x"}, "finish_reason": "stop"}],
        usage={"prompt_tokens": True, "completion_tokens": 4})), **_NOOP)
    assert prov.last_usage == {"output_tokens": 4}


# --------------------------------------------------------------------- (b) --

class _CapturingConn:
    """Stands in for http.client.HTTPConnection: records the request, answers
    with a canned usage-bearing stream."""

    captured = []

    def __init__(self, host, timeout=None, context=None):
        self.host = host

    def request(self, method, path, body=None, headers=None):
        _CapturingConn.captured.append((method, path, body, headers))

    def getresponse(self):
        return _FakeResponse(_openai_sse(
            [{"delta": {"content": "Hi"}, "finish_reason": "stop"}],
            usage={"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15}))

    def close(self):
        pass


def test_ollama_request_asks_for_usage(monkeypatch):
    from synapse.panel.providers.nemotron_provider import NemotronProvider
    from synapse.panel.providers.ollama_provider import OllamaProvider
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(http.client, "HTTPConnection", _CapturingConn)
    _CapturingConn.captured.clear()

    prov = OllamaProvider(model="nemotron-mini:latest", max_tokens=4)
    prov.stream(messages=[{"role": "user", "content": "Say hi."}], tools=[],
                system="", api_key="not-needed", **_NOOP)
    method, path, body, _headers = _CapturingConn.captured[-1]
    assert (method, path) == ("POST", "/v1/chat/completions")
    sent = json.loads(body.decode("utf-8"))
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}
    # ...and the answer is forwarded on the additive channel the worker reads.
    assert prov.last_usage == {"input_tokens": 11, "output_tokens": 4}

    # The switch exists for an endpoint that 400s on stream_options (the NIM
    # probe decides Nemotron's default); off means the key is simply absent.
    monkeypatch.setattr(NemotronProvider, "_SEND_STREAM_OPTIONS", False)
    prov = OllamaProvider(model="nemotron-mini:latest", max_tokens=4)
    prov.stream(messages=[{"role": "user", "content": "Say hi."}], tools=[],
                system="", api_key="not-needed", **_NOOP)
    sent = json.loads(_CapturingConn.captured[-1][2].decode("utf-8"))
    assert "stream_options" not in sent


# --------------------------------------------------------------------- (c) --

def test_gemini_usage_metadata_lands_on_last_usage():
    from synapse.panel.providers.gemini_provider import GeminiProvider
    prov = GeminiProvider(model="gemini-3.5-flash", max_tokens=4)

    # usageMetadata rides every chunk and is CUMULATIVE: the last one wins.
    # promptTokenCount INCLUDES the cached part (Gemini's definition), so the
    # Anthropic-shaped input_tokens is the uncached remainder and the cached
    # part lands on cache_read_input_tokens - never counted twice.
    stream = _gemini_sse([
        {"candidates": [{"content": {"parts": [{"text": "Hi"}]}}],
         "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 1,
                           "totalTokenCount": 21}},
        {"candidates": [{"content": {"parts": [{"text": "!"}]},
                         "finishReason": "STOP"}],
         "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 4,
                           "thoughtsTokenCount": 6, "cachedContentTokenCount": 5,
                           "totalTokenCount": 30}},
    ])
    stop, blocks = prov._parse_sse_stream(_FakeResponse(stream), schema_by_name={}, **_NOOP)
    assert stop == "end_turn"
    assert blocks == [{"type": "text", "text": "Hi!"}]
    assert prov.last_usage == {"input_tokens": 15,          # 20 prompt - 5 cached
                               "output_tokens": 10,         # 4 candidates + 6 thoughts
                               "cache_read_input_tokens": 5}

    # No usageMetadata at all -> None, never a stale carry.
    prov._parse_sse_stream(_FakeResponse(_gemini_sse([
        {"candidates": [{"content": {"parts": [{"text": "x"}]}, "finishReason": "STOP"}]},
    ])), schema_by_name={}, **_NOOP)
    assert prov.last_usage is None


# --------------------------------------------------------------------- (d) --

def test_sink_accumulates_a_session_across_tasks():
    from synapse.panel import token_readout
    from synapse.panel.usage_sink import UsageSink
    s = UsageSink()
    s.begin_task("claude-sonnet-4-6", provider="claude")
    s.add({"input_tokens": 100, "output_tokens": 20,
           "cache_read_input_tokens": 30, "cache_creation_input_tokens": 5})
    s.add({"input_tokens": 80, "output_tokens": 40})
    s.begin_task("nemotron-mini:latest", provider="ollama")
    s.add({"input_tokens": 11, "output_tokens": 4})
    snap = s.snapshot()

    # The task-level keys the Token tab and the pill already read are the LAST
    # task's, unchanged in name and meaning (tests/test_token_tab_usage.py).
    assert snap["model"] == "nemotron-mini:latest"
    assert snap["runs"] == 1
    assert snap["input_tokens"] == 11 and snap["output_tokens"] == 4
    assert snap["cache_read"] is None and snap["cache_creation"] is None
    assert snap["provider"] == "ollama"
    assert token_readout.task_total(snap) == 15

    # The session is the sum across every task since clear(); begin_task never
    # resets it. A field no task reported stays None (UNKNOWN), never 0.
    sess = snap["session"]
    assert sess["input_tokens"] == 191 and sess["output_tokens"] == 64
    assert sess["cache_read"] == 30 and sess["cache_creation"] == 5
    assert sess["runs"] == 3 and sess["tasks"] == 2
    assert token_readout.session_total(snap) == 290
    assert [(p["provider"], p["model"]) for p in sess["by_model"]] == [
        ("claude", "claude-sonnet-4-6"), ("ollama", "nemotron-mini:latest")]

    s.clear()
    assert s.snapshot() is None


# --------------------------------------------------------------------- (e) --

def test_context_window_and_share_arithmetic():
    from synapse.panel import token_readout
    from synapse.panel.providers.ollama_provider import _parse_show_context
    from synapse.panel.usage_sink import UsageSink

    s = UsageSink()
    s.begin_task("nemotron-mini:latest", provider="ollama")
    s.add({"input_tokens": 11, "output_tokens": 4})
    s.set_context_window(4096, "ollama /api/show")
    snap = s.snapshot()
    assert snap["last_prompt"] == 11
    assert (snap["context_window"], snap["context_source"]) == (4096, "ollama /api/show")
    assert token_readout.context_text(snap["last_prompt"], snap["context_window"]) == "11 / 4096 · 0.3%"

    # The last prompt is the context the model actually held on its LAST call:
    # uncached input + cache read + cache write - of that call, not summed.
    s.begin_task("claude-sonnet-4-6", provider="claude")
    assert s.snapshot()["context_window"] is None          # a new task starts unknown
    s.add({"input_tokens": 1000, "cache_read_input_tokens": 2000,
           "cache_creation_input_tokens": 200, "output_tokens": 50})
    s.add({"input_tokens": 1100, "cache_read_input_tokens": 2100, "output_tokens": 5})
    assert s.snapshot()["last_prompt"] == 3200
    s.set_context_window(200_000, "model_facts")
    assert token_readout.context_text(3200, 200_000) == "3200 / 200k · 1.6%"
    assert token_readout.context_text(150_300, 1_048_576) == "150.3k / 1.0M · 14.3%"

    # Unknown on either side -> None (UNKNOWN), never a share of nothing.
    assert token_readout.context_text(None, 4096) is None
    assert token_readout.context_text(11, None) is None
    assert token_readout.context_text(11, 0) is None
    assert token_readout.context_text(True, 4096) is None
    s.set_context_window(None, None)
    assert s.snapshot()["context_window"] is None

    # Ollama /api/show: the first model_info key ending in .context_length is
    # the model's window (live: nemotron.context_length 4096); a modelfile
    # num_ctx, when present, is the window the daemon actually runs.
    assert _parse_show_context({"model_info": {"general.architecture": "nemotron",
                                               "nemotron.context_length": 4096}}) == 4096
    assert _parse_show_context({"model_info": {"qwen35.context_length": 262144},
                                "parameters": "temperature 1\nnum_ctx 8192\n"}) == 8192
    assert _parse_show_context({"model_info": {"x.context_length": True}}) is None
    assert _parse_show_context({}) is None
    assert _parse_show_context("garbage") is None


# --------------------------------------------------------------------- (f) --

def test_model_facts_cost_is_local_zero_unknown_none_never_bool():
    from synapse.panel.providers import model_facts as mf

    local = mf.cost({"provider": "ollama", "model": "nemotron-mini:latest",
                     "input_tokens": 11, "output_tokens": 4})
    # A tag alone does not prove localhost execution; old receipts lack
    # endpoint evidence, so their cost must remain unknown.
    assert local is None
    assert not mf.is_local("ollama", "nemotron-mini:latest")

    # An Ollama :cloud tag is metered by ollama.com with no per-token list
    # price on file -> unknown, never zero (R162: a zero is a claim).
    assert mf.cost({"provider": "ollama", "model": "glm-5:cloud",
                    "input_tokens": 11, "output_tokens": 4}) is None
    # A tag without :cloud that the probe saw with a remote_host is metered too.
    assert mf.cost({"provider": "ollama", "model": "nemotron-mini:latest",
                    "input_tokens": 11}, remote_host="https://ollama.com") is None
    assert mf.cost({"provider": "nemotron", "model": "nvidia/nemotron-3-super-120b-a12b",
                    "input_tokens": 11, "output_tokens": 4}) is None
    assert mf.cost({"provider": "custom", "model": "whatever", "input_tokens": 1}) is None
    assert mf.cost(None) is None
    assert mf.cost({}) is None

    # A verified list price: 1M input tokens of Sonnet 4.6 at $3 / MTok.
    priced = mf.cost({"provider": "claude", "model": "claude-sonnet-4-6",
                      "input_tokens": 1_000_000, "output_tokens": 0})
    assert priced is not None
    usd, note = priced
    assert abs(usd - 3.0) < 1e-9 and note.startswith("list price · 20")
    # The four billed fields each carry their own rate; a bool never counts.
    usd, _ = mf.cost({"provider": "claude", "model": "claude-sonnet-4-6",
                      "input_tokens": 1_000_000, "output_tokens": 1_000_000,
                      "cache_read": 1_000_000, "cache_creation": True})
    assert abs(usd - (3.0 + 15.0 + 0.30)) < 1e-9
    # Price on file but nothing reported -> nothing to price (not "unknown price").
    assert mf.cost({"provider": "claude", "model": "claude-sonnet-4-6"}) == (None, "tokens not reported")

    # Every row in the tables is a registry row with a dated public source.
    from synapse.panel.providers.registry import PROVIDER_MODELS
    for (pid, model), row in list(mf.PRICE_USD_PER_MTOK.items()) + list(mf.CONTEXT_WINDOW.items()):
        assert any(model == mid for mid, _lbl in PROVIDER_MODELS.get(pid, ())), (pid, model)
        assert row[-1][-10:].count("-") == 2, row
    for row in mf.PRICE_USD_PER_MTOK.values():
        assert all(v is None or (type(v) is float) for v in row[:4]), row

    # Session cost folds per-model parts; one unpriced part makes the whole
    # session unknown and names it; local parts add $0.
    snap = {"provider": "ollama", "model": "nemotron-mini:latest", "session": {"by_model": [
        {"provider": "claude", "model": "claude-sonnet-4-6", "input_tokens": 1_000_000},
        {"provider": "ollama", "model": "nemotron-mini:latest", "input_tokens": 11, "output_tokens": 4},
    ]}}
    assert mf.session_cost(snap) is None
    assert mf.unpriced_models(snap) == ["nemotron-mini:latest"]
    priced_only = {"session": {"by_model": snap["session"]["by_model"][:1]}}
    usd, note = mf.session_cost(priced_only)
    assert abs(usd - 3.0) < 1e-9 and note.startswith("list price · 20")
    snap["session"]["by_model"].append(
        {"provider": "ollama", "model": "glm-5:cloud", "input_tokens": 2})
    assert mf.session_cost(snap) is None
    assert mf.unpriced_models(snap) == ["nemotron-mini:latest", "glm-5:cloud"]
    assert mf.session_cost({"session": {"by_model": [
        {"provider": "ollama", "model": "nemotron-mini:latest"}]}}) is None
    assert mf.session_cost({"session": {"by_model": []}}) is None
