"""Provider registry — model IDs and per-provider config as DATA.

Adding or retiring a model must never touch worker/dispatch code; it changes a
row here. ``build_provider`` is the only constructor the panel/worker call.
``claude_worker`` re-exports ``ANTHROPIC_MODEL``/``ANTHROPIC_MAX_TOKENS`` as
``_MODEL``/``_MAX_TOKENS`` so the panel author-token import keeps a single source.

Each provider exposes a list of selectable ``(model_id, label)`` rows; the panel
model picker reads ``PROVIDER_MODELS`` so switching models is a data lookup, and
``build_provider(provider_id, model=...)`` constructs with the chosen model.

These tables are a SELECTION list, never an availability claim
---------------------------------------------------------------
A model row here says "the panel offers this"; it does not say "the provider
serves this". Availability, quota, latency and probe age come from
``providers/probe.py``, which asks the provider. Routing is probe-derived; a
row in this file is documentation, and documentation ages (see the R74 note on
``OLLAMA_MODELS`` below for the worked example).

MEASURED 2026-07-28 by ``harness/notes/econ/v3_probe_live.py``
(``harness/notes/econ/V3_probe_live.install.json``), zero completion spend:

    provider    declared here   served live   declared-but-absent
    claude          6               11              0
    nemotron        2              102              0
    ollama          1               13              0

Every declared row was live on that date — the drift is entirely in the other
direction, models the provider serves that this file does not offer. A
declared row the provider stops serving comes back from the probe as
``available=False, reason="declared_but_absent"`` and reads RED, so the
``hou.ActiveRender`` failure (documented, absent at runtime) surfaces here as a
colour rather than as a support ticket.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# -- model ids + token caps as data (the single source of truth) -----------

# Anthropic — the full set selectable in the panel (mirrors Claude desktop).
ANTHROPIC_MODELS = (
    # Opus 5 added 2026-07-27 from the assistant's own runtime context, with the
    # standing instruction "verify against /v1/models before any release cites
    # it". VERIFIED 2026-07-28: live GET /v1/models returns claude-opus-5
    # ("Claude Opus 5", created_at 2026-07-24). All six rows below were served
    # on that date. Producer: harness/notes/econ/v3_probe_live.py ->
    # V3_probe_live.install.json. The provenance gap is closed; the DATE is the
    # load-bearing part, because this note becomes a claim about the past the
    # moment it is written (R74) and probe.py is what keeps it honest.
    ("claude-opus-5",              "Opus 5"),
    ("claude-opus-4-8",            "Opus 4.8"),
    ("claude-sonnet-5",            "Sonnet 5"),      # verified live (GET /v1/models, 2026-07-01)
    ("claude-sonnet-4-6",          "Sonnet 4.6"),
    ("claude-haiku-4-5-20251001",  "Haiku 4.5"),
    ("claude-fable-5",             "Fable 5"),
)
ANTHROPIC_MODEL = "claude-sonnet-4-6"   # default pick
ANTHROPIC_MAX_TOKENS = 4096

GEMINI_MODELS = (
    ("gemini-3.5-flash", "Gemini 3.5 Flash"),
)
GEMINI_MODEL = "gemini-3.5-flash"          # GA, agentic-tuned (confirmed live)
GEMINI_MAX_TOKENS = 4096

# NVIDIA / Nemotron — OpenAI-compatible reasoning LLM (NVIDIA NIM cloud by
# default). Model ids verified live via GET /v1/models on
# integrate.api.nvidia.com (2026-07-01; both rows still served).
NVIDIA_MODELS = (
    ("nvidia/nemotron-3-super-120b-a12b", "Nemotron Super 120B"),
    ("nvidia/nemotron-3-nano-30b-a3b",    "Nemotron Nano 30B"),
)
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"   # default pick
NVIDIA_MAX_TOKENS = 4096

# Ollama — local-first OpenAI-compatible endpoint (http://localhost:11434 by
# default; override via OLLAMA_HOST). Static FALLBACK rows only: the panel's
# model menu fetches the live tag list from GET /api/tags and falls back here.
# Tag verified live on Ollama 0.30.11 (2026-07-01): the GLM slot resolved to
# "glm-5:cloud" on this install. RE-CHECKED 2026-07-27: `GET /api/tags` now also
# returns "glm-5.2:cloud", and the panel shows it because it reads the LIVE tag
# list rather than this table. The 2026-07-01 note said "no glm-5.2 tag exists";
# that was true when written and is a claim about the future that aged into a
# claim about the present (R74). The static rows below are a FALLBACK only.
# RE-MEASURED 2026-07-28 (harness/notes/econ/v3_probe_live.py): GET /api/tags
# returns THIRTEEN tags against the one row below. Seven run locally; six carry
# a ``remote_host`` of ollama.com and are metered by it — including the default
# picked here. "Ollama is local and free" is therefore not true of this row, and
# probe.py reports its cost as unknown rather than as zero.
OLLAMA_MODELS = (
    ("glm-5:cloud", "GLM 5"),
)
OLLAMA_MODEL = "glm-5:cloud"   # default pick
OLLAMA_MAX_TOKENS = 4096

# Custom — a user-configured OpenAI-compatible endpoint. Base URL / model id /
# key env-var name live in <repo>/.synapse/panel_settings.json (panel/settings.py);
# no static rows here — models_for()/default_model() read the LIVE config, and
# the empty-model default "" marks the unconfigured state (surfaced by the
# provider's resolve_key, never a silent Claude switch).
CUSTOM_MAX_TOKENS = 4096

DEFAULT_PROVIDER = "claude"

# Provider ids selectable in the panel (the engine selector iterates this).
PROVIDER_IDS = ("claude", "gemini", "nemotron", "ollama", "custom")

# Display labels for the engine selector pills.
PROVIDER_LABELS = {
    "claude": "Claude",
    "gemini": "Gemini",
    "nemotron": "Nemotron",
    "ollama": "Ollama",
    "custom": "Custom",
}

# Per-provider selectable model rows + the provider's default model id.
# ("custom" holds static placeholders — models_for()/default_model() special-
# case it against the live settings config.)
PROVIDER_MODELS = {
    "claude": ANTHROPIC_MODELS,
    "gemini": GEMINI_MODELS,
    "nemotron": NVIDIA_MODELS,
    "ollama": OLLAMA_MODELS,
    "custom": (),
}
PROVIDER_DEFAULT_MODEL = {
    "claude": ANTHROPIC_MODEL,
    "gemini": GEMINI_MODEL,
    "nemotron": NVIDIA_MODEL,
    "ollama": OLLAMA_MODEL,
    "custom": "",
}


def _custom_config() -> dict:
    """The persisted Custom-engine config (``base_url``/``model``/``key_env``).
    Never raises — empty dict on any failure (the load_settings posture)."""
    try:
        from synapse.panel import settings as _pset
        return _pset.load_settings().get("custom") or {}
    except Exception:
        return {}


def models_for(provider_id: str):
    """The selectable ``(model_id, label)`` rows for a provider (empty tuple if
    unknown). ``custom`` reads the live config — one row when configured."""
    pid = (provider_id or "").lower()
    if pid == "custom":
        model = _custom_config().get("model") or ""
        return ((model, model),) if model else ()
    return PROVIDER_MODELS.get(pid, ())


def default_model(provider_id: str) -> str:
    """The default model id for a provider (Anthropic's if unknown). ``custom``
    reads the live config — ``""`` marks the unconfigured state."""
    pid = (provider_id or "").lower()
    if pid == "custom":
        return _custom_config().get("model") or ""
    return PROVIDER_DEFAULT_MODEL.get(pid, ANTHROPIC_MODEL)


def _pretty_ollama(model_id: str) -> str:
    """A clean family label for a live Ollama tag the static registry doesn't
    carry: drop the ``:tag`` and any ``ns/`` prefix, spell out separators, and
    upper the short family word ('glm-5.2:cloud' -> 'GLM 5.2'). Never the raw id —
    the header author token must stay short + colon-free (G3)."""
    base = (model_id.split(":", 1)[0].split("/")[-1]
            .replace("-", " ").replace("_", " ").strip())
    words = [(w.upper() if w.isalpha() and len(w) <= 3 else (w[:1].upper() + w[1:]))
             for w in base.split()]
    return " ".join(words) or model_id


def model_label(provider_id: str, model_id: str) -> str:
    """Display label for a model id under a provider. A registry row wins; an
    unknown *Ollama* tag is prettified (never the raw ':tag' id — Ollama tags
    advance faster than the static fallback rows); any other unknown id falls
    back to itself."""
    for mid, lbl in models_for(provider_id):
        if mid == model_id:
            return lbl
    if (provider_id or "").lower() == "ollama" and model_id:
        return _pretty_ollama(model_id)
    return model_id or ""


def build_provider(provider_id: str = DEFAULT_PROVIDER, model: str = None):
    """Construct the StreamProvider for ``provider_id`` (data-driven).

    ``model`` overrides the provider default (the panel passes the picked model);
    ``None`` ⇒ the provider's default. Unknown ids fall back to the Claude floor —
    the panel never crashes on a stale selection.
    """
    pid = (provider_id or DEFAULT_PROVIDER).lower()
    if pid == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(model=model or GEMINI_MODEL, max_tokens=GEMINI_MAX_TOKENS)
    if pid == "nemotron":
        from .nemotron_provider import NemotronProvider
        return NemotronProvider(model=model or NVIDIA_MODEL, max_tokens=NVIDIA_MAX_TOKENS)
    if pid == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(model=model or OLLAMA_MODEL, max_tokens=OLLAMA_MAX_TOKENS)
    if pid == "custom":
        # NEVER the Claude floor — an unconfigured Custom engine is surfaced
        # through the provider's resolve_key → key_error_message worker path.
        from .custom_provider import CustomProvider
        cfg = _custom_config()
        return CustomProvider(
            base_url=cfg.get("base_url", ""),
            model=model or cfg.get("model", ""),
            key_env=cfg.get("key_env", ""),
            max_tokens=CUSTOM_MAX_TOKENS,
        )
    if pid != "claude":
        # Stale persisted / unknown id: fall back to the Claude floor, but
        # LOUDLY — the panel surfaces the swap in chat (never a silent switch).
        logger.warning("Unknown provider id %r — falling back to the Claude floor", pid)
    from .anthropic_provider import AnthropicProvider
    return AnthropicProvider(model=model or ANTHROPIC_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS)
