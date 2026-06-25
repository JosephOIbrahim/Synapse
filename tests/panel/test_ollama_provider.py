"""Goalpost -- the panel gains an OLLAMA engine, mirroring the Gemini pair.

Contract: ollama-provider (Leg 3 of the multi-provider relay). Encodes the goal:
add an ``OllamaProvider`` (``StreamProvider`` subclass, stdlib http to the local
daemon at ``http://localhost:11434/api/chat`` which proxies ``:cloud`` models) +
an ``ollama_translate`` layer (Anthropic tools <-> Ollama tools, tool_calls <->
tool_use), with the registry exposing selectable ollama ``:cloud`` models --
exactly the shape of ``gemini_provider.py`` + ``gemini_translate.py``.

PURE PYTHON by design: the provider/translate/registry layers are stdlib-only
(no PySide, no hou -- the StreamProvider contract forbids both), and these tests
exercise only module existence, registry DATA, and the pure translation
functions. So they run as REAL assertions under stock CPython -- never the
false-green a skipped PySide-bound test would give. No network, no live daemon:
every fixture is in-memory (a live-daemon smoke is a MANUAL check in the
contract, deliberately NOT a goalpost -- offline it would skip-or-error and lie).

Each test resolves to a clean ASSERTION pass/fail today (feature unbuilt), never
an import/collection ERROR: not-yet-existing modules go through
``importlib.util.find_spec`` and not-yet-existing attrs through ``getattr(...)``.
"""

import importlib
import importlib.util
import os
import sys

# Make the package importable from a source checkout (no install), matching the
# sys.path bootstrap the existing panel tests use.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_PROVIDER_MOD = "synapse.panel.providers.ollama_provider"
_TRANSLATE_MOD = "synapse.panel.providers.ollama_translate"
_REGISTRY_MOD = "synapse.panel.providers.registry"


def test_ollama_module_exists():
    # FAILS now CLEANLY: find_spec returns None for a module that does not exist
    # yet (no ImportError, no collection error). PASSES once
    # providers/ollama_provider.py lands with an OllamaProvider class.
    spec = importlib.util.find_spec(_PROVIDER_MOD)
    assert spec is not None, (
        "%s does not exist yet -- add providers/ollama_provider.py with an "
        "OllamaProvider(StreamProvider) mirroring gemini_provider.py" % _PROVIDER_MOD
    )

    mod = importlib.import_module(_PROVIDER_MOD)
    provider_cls = getattr(mod, "OllamaProvider", None)
    assert provider_cls is not None, (
        "%s must define an OllamaProvider class" % _PROVIDER_MOD
    )

    # It must be a StreamProvider subclass (the worker's provider abstraction)
    # and advertise id == 'ollama' so the worker never learns the engine.
    from synapse.panel.providers.base import StreamProvider

    assert issubclass(provider_cls, StreamProvider), (
        "OllamaProvider must subclass providers.base.StreamProvider"
    )
    assert getattr(provider_cls, "id", None) == "ollama", (
        "OllamaProvider.id must be 'ollama'; got %r" % getattr(provider_cls, "id", None)
    )


def test_registry_lists_ollama_models():
    # The registry exposes models as DATA; the worker's goal is a MODELS table
    # the picker reads. Today registry.py carries per-provider constants and no
    # MODELS list, so the getattr guard FAILS cleanly (no AttributeError).
    registry = importlib.import_module(_REGISTRY_MOD)

    models = getattr(registry, "MODELS", None)
    assert models is not None, (
        "registry.py must expose a MODELS table (the picker reads it as data); "
        "none found yet"
    )

    # Find the ollama entries. A model row may be a dict, a tuple, or an object;
    # accept any shape and read a provider id + a model id off it generically, so
    # this goalpost pins BEHAVIOUR (an ollama :cloud model is selectable), not a
    # premature row schema the worker is free to choose.
    def _provider_of(entry):
        if isinstance(entry, dict):
            return entry.get("provider") or entry.get("provider_id")
        return getattr(entry, "provider", None) or getattr(entry, "provider_id", None)

    def _model_id_of(entry):
        if isinstance(entry, dict):
            return entry.get("model") or entry.get("model_id") or entry.get("id")
        return (getattr(entry, "model", None) or getattr(entry, "model_id", None)
                or getattr(entry, "id", None))

    rows = list(models.values()) if isinstance(models, dict) else list(models)
    ollama_rows = [r for r in rows if (_provider_of(r) or "").lower() == "ollama"]
    assert ollama_rows, (
        "registry.MODELS must include >=1 ollama entry; found provider ids: %r"
        % sorted({(_provider_of(r) or "") for r in rows})
    )

    cloud_rows = [r for r in ollama_rows if ":cloud" in (_model_id_of(r) or "")]
    assert cloud_rows, (
        "at least one ollama model id must contain ':cloud' "
        "(e.g. glm-5:cloud, nemotron-3-ultra:cloud); got %r"
        % [_model_id_of(r) for r in ollama_rows]
    )

    # build_provider must construct an id=='ollama' provider for an ollama key.
    # build_provider exists today (Claude/Gemini), so resolve the selector from a
    # real ollama row rather than hardcoding one -- pins the contract, not a name.
    build_provider = getattr(registry, "build_provider", None)
    assert build_provider is not None, "registry.build_provider missing"

    chosen = cloud_rows[0]
    # The selector key build_provider takes: prefer an explicit row key, else the
    # provider id, else the model id -- whichever the worker wires.
    selector = None
    if isinstance(models, dict):
        for k, v in models.items():
            if v is chosen:
                selector = k
                break
    if selector is None:
        selector = _model_id_of(chosen) or _provider_of(chosen)

    provider = build_provider(selector)
    assert getattr(provider, "id", None) == "ollama", (
        "build_provider(%r) must return an id=='ollama' provider; got id=%r"
        % (selector, getattr(provider, "id", None))
    )


def test_translate_tool_roundtrip():
    # Clean fail if the translate module is absent (find_spec -> None, no import
    # error). Only import it once present.
    spec = importlib.util.find_spec(_TRANSLATE_MOD)
    assert spec is not None, (
        "%s does not exist yet -- add providers/ollama_translate.py mirroring "
        "gemini_translate.py" % _TRANSLATE_MOD
    )
    ot = importlib.import_module(_TRANSLATE_MOD)

    translate_tools = getattr(ot, "translate_tools", None)
    assert translate_tools is not None, (
        "ollama_translate must expose translate_tools(anthropic_tools) -> ollama tools"
    )

    # ---- forward: an Anthropic tool spec -> an Ollama tool spec -------------
    # Ollama's /api/chat tool schema is OpenAI-shaped:
    #   {"type": "function", "function": {"name", "description", "parameters"}}
    anthropic_tools = [{
        "name": "set_parm",
        "description": "Set a parameter on a node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_path": {"type": "string", "description": "the node"},
                "value": {"type": "number"},
            },
            "required": ["node_path"],
        },
    }]

    ollama_tools = translate_tools(anthropic_tools)
    assert isinstance(ollama_tools, list) and ollama_tools, (
        "translate_tools must return a non-empty list for one tool"
    )

    # Locate the function descriptor regardless of exact nesting, then assert the
    # load-bearing facts survived: name, the parameters object, and a property.
    def _func_of(entry):
        if isinstance(entry, dict):
            if isinstance(entry.get("function"), dict):
                return entry["function"]
            if "name" in entry and "parameters" in entry:
                return entry
        return None

    fn = _func_of(ollama_tools[0])
    assert fn is not None, (
        "expected an OpenAI-shaped {'type':'function','function':{...}} tool; got %r"
        % (ollama_tools[0],)
    )
    assert fn.get("name") == "set_parm", (
        "tool name must survive translation; got %r" % fn.get("name")
    )
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    assert "node_path" in props, (
        "the input_schema properties must carry into ollama parameters; got %r" % props
    )
    assert params.get("type") == "object", (
        "ollama tool parameters must be an object schema; got %r" % params.get("type")
    )

    # ---- return: an Ollama tool_call -> an Anthropic tool_use block ---------
    to_tool_use = (getattr(ot, "tool_calls_to_blocks", None)
                   or getattr(ot, "to_tool_use", None)
                   or getattr(ot, "translate_tool_calls", None))
    assert to_tool_use is not None, (
        "ollama_translate must expose a tool_call->tool_use mapper "
        "(tool_calls_to_blocks / to_tool_use / translate_tool_calls)"
    )

    # An Ollama tool_call as it arrives on a message (OpenAI-shaped):
    ollama_tool_calls = [{
        "function": {
            "name": "set_parm",
            "arguments": {"node_path": "/obj/geo1", "value": 0.5},
        }
    }]
    blocks = to_tool_use(ollama_tool_calls)
    assert isinstance(blocks, list) and blocks, (
        "tool_call mapper must return a non-empty list of Anthropic content blocks"
    )

    tu = next((b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"),
              None)
    assert tu is not None, (
        "expected a {'type':'tool_use', ...} Anthropic block; got %r" % (blocks,)
    )
    assert tu.get("name") == "set_parm", (
        "tool_use.name must echo the call; got %r" % tu.get("name")
    )
    assert tu.get("input") == {"node_path": "/obj/geo1", "value": 0.5}, (
        "tool_use.input must faithfully carry the ollama arguments; got %r"
        % (tu.get("input"),)
    )
    # Anthropic tool_use blocks require an id (the tool_result round-trips on it).
    assert tu.get("id"), "tool_use block must carry a non-empty id"
