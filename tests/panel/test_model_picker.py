"""Goalpost — the registry must carry MULTIPLE models per provider.

Contract: model-picker (order 2). Encodes the goal:

    "the panel must let the artist pick among MULTIPLE models per provider —
    Claude: sonnet / opus / haiku — via the '...' Engine menu rendered as a
    per-provider submenu, with the rail author token reflecting the chosen
    model."

Today `providers/registry.py` is one-model-per-provider: a single
``ANTHROPIC_MODEL = "claude-sonnet-4-6"`` constant and a ``build_provider``
that ignores any model choice. The substrate this feature stands on is a
multi-model TABLE — ``registry.MODELS`` (or an equivalent multi-model mapping)
listing >=2 Claude entries including an opus and a haiku, with
``build_provider`` accepting a model KEY from that table.

PURE PYTHON by design: the registry is stdlib-only DATA (no PySide), so these
run as REAL assertions under stock CPython *and* hython — no QApplication
required. That is deliberate: this is the dependable pass/fail under the
harness's stock ``pytest -q`` (the menu-shape goalpost, which needs a live
QWidget, lives in test_model_picker_menu.py and runs via the hython shim).

Both tests use getattr/find_spec guards so they FAIL CLEANLY with an assertion
(not an import/attribute ERROR) while the multi-model table is absent.
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

_REGISTRY = "synapse.panel.providers.registry"
_ANTHROPIC = "synapse.panel.providers.anthropic_provider"


def _models_table(reg):
    """The multi-model table the feature must expose, normalized to a dict of
    ``key -> entry``. Accepts the named ``MODELS`` attribute (the intended shape)
    or an equivalent multi-model mapping, so the worker isn't pinned to one name.
    Returns ``{}`` when no such table exists yet (the unbuilt state). Never
    raises — the absent-table case resolves to a clean assertion, not an error."""
    table = getattr(reg, "MODELS", None)
    if isinstance(table, dict) and table:
        return table
    return {}


def _entry_model_id(entry):
    """Pull the model-id string out of a table entry, tolerant of the entry
    being the raw model-id string, a dict ({'model': ...} / {'id': ...} /
    {'model_id': ...}), or an object carrying a ``model``/``model_id`` attribute.
    Returns ``""`` when nothing string-like is found (no raise)."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for k in ("model", "id", "model_id", "model_identity"):
            v = entry.get(k)
            if isinstance(v, str) and v:
                return v
        return ""
    for k in ("model", "model_id", "model_identity"):
        v = getattr(entry, k, None)
        if isinstance(v, str) and v:
            return v
    return ""


def _claude_entries(reg, table):
    """The table entries whose provider is Claude. An entry counts as Claude if
    its model id starts with ``claude-`` OR (when entries are dicts/objects) it
    carries a provider field of ``claude``. Returns ``{key: model_id}``."""
    claude = {}
    for key, entry in table.items():
        mid = _entry_model_id(entry)
        provider = ""
        if isinstance(entry, dict):
            provider = (entry.get("provider") or "")
        else:
            provider = (getattr(entry, "provider", "") or "")
        if mid.startswith("claude-") or str(provider).lower() == "claude":
            if mid:
                claude[key] = mid
    return claude


def _author_token_for(model):
    """Replicate synapse_panel._author_token's pure rendering convention so this
    pure-python test needs no QWidget: ``claude-opus-4-x`` -> ``opus-4.x``;
    family-only (``claude-haiku``) -> ``haiku``. Copied to keep the test
    self-contained — the panel method is PySide-bound and can't import here."""
    if not model:
        return ""
    m = model
    if m.startswith("claude-"):
        m = m[len("claude-"):]
        for fam in ("opus", "sonnet", "haiku"):
            if m.startswith(fam):
                rest = m[len(fam):].lstrip("-").replace("-", ".")
                return ("%s-%s" % (fam, rest)) if rest else fam
        return m
    return m


def test_registry_exposes_multiple_claude_models():
    # The substrate: a multi-model TABLE with >=2 Claude entries including an
    # opus AND a haiku, and a build_provider that accepts a model KEY and yields
    # an AnthropicProvider whose model_identity is that model's id.
    #
    # FAILS now: registry has only the single ANTHROPIC_MODEL constant and no
    # MODELS table -> _models_table() is {} -> the first assertion trips with a
    # clear message (NOT an AttributeError/ImportError).
    assert importlib.util.find_spec(_REGISTRY) is not None, (
        "registry module %s must exist" % _REGISTRY)
    reg = importlib.import_module(_REGISTRY)

    table = _models_table(reg)
    assert table, (
        "registry must expose a multi-model table (registry.MODELS or an "
        "equivalent multi-model mapping); none found — still one-model-per-"
        "provider (only ANTHROPIC_MODEL). The Engine submenu has nothing to "
        "list."
    )

    claude = _claude_entries(reg, table)
    assert len(claude) >= 2, (
        "the model table must list >=2 Claude models; found %d (%r)"
        % (len(claude), sorted(claude.values()))
    )

    has_opus = any("opus" in mid for mid in claude.values())
    has_haiku = any("haiku" in mid for mid in claude.values())
    assert has_opus and has_haiku, (
        "the Claude models must include both an opus and a haiku; got %r "
        "(opus=%s haiku=%s)" % (sorted(claude.values()), has_opus, has_haiku)
    )

    # build_provider(<the opus key>) must return an AnthropicProvider whose
    # model_identity is the opus id — i.e. the picker actually routes a chosen
    # model into the constructed provider, not just the default.
    opus_key = next(k for k, mid in claude.items() if "opus" in mid)
    opus_id = claude[opus_key]

    build = getattr(reg, "build_provider", None)
    assert callable(build), "registry.build_provider must be callable"

    prov = build(opus_key)
    assert prov is not None, (
        "build_provider(%r) returned None — the opus model key did not "
        "construct a provider" % (opus_key,)
    )

    AnthropicProvider = None
    if importlib.util.find_spec(_ANTHROPIC) is not None:
        AnthropicProvider = getattr(
            importlib.import_module(_ANTHROPIC), "AnthropicProvider", None)
    assert AnthropicProvider is not None, (
        "anthropic_provider.AnthropicProvider must be importable")
    assert isinstance(prov, AnthropicProvider), (
        "build_provider(%r) must return an AnthropicProvider, got %r"
        % (opus_key, type(prov).__name__)
    )
    assert getattr(prov, "model_identity", None) == opus_id, (
        "the constructed provider's model_identity must be the opus id %r, "
        "got %r — build_provider is ignoring the chosen model key"
        % (opus_id, getattr(prov, "model_identity", None))
    )


def test_author_token_reflects_chosen_model():
    # The rail author token must reflect the CHOSEN model, not just the provider.
    # The token is derived (via synapse_panel._author_token) from the active
    # model id; with a real picker, choosing the opus model must produce an
    # opus-flavoured token. Pure check: the opus entry's id renders to a token
    # that names 'opus' AND is distinct from the default sonnet token.
    #
    # FAILS now: no MODELS table -> no opus entry to choose -> assertion trips
    # cleanly (the default token stays 'sonnet-...').
    reg = importlib.import_module(_REGISTRY)
    table = _models_table(reg)
    assert table, (
        "registry must expose a multi-model table so a chosen model can drive "
        "the author token; none found (still one-model-per-provider)."
    )
    claude = _claude_entries(reg, table)
    opus_ids = [mid for mid in claude.values() if "opus" in mid]
    assert opus_ids, (
        "the model table must include an opus Claude model for the token to "
        "reflect; got %r" % (sorted(claude.values()),)
    )

    opus_token = _author_token_for(opus_ids[0])
    assert "opus" in opus_token, (
        "choosing the opus model must yield an opus-flavoured author token; "
        "rendered %r from %r" % (opus_token, opus_ids[0])
    )

    default_model = getattr(reg, "ANTHROPIC_MODEL", "")
    default_token = _author_token_for(default_model)
    assert opus_token != default_token, (
        "the opus author token (%r) must differ from the default token (%r) — "
        "otherwise the rail does not reflect the chosen model"
        % (opus_token, default_token)
    )
