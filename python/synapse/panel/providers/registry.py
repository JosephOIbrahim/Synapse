"""Provider registry — model IDs and per-provider config as DATA.

Adding or retiring a model must never touch worker/dispatch code; it changes a
row here. ``build_provider`` is the only constructor the panel/worker call.
``claude_worker`` re-exports ``ANTHROPIC_MODEL``/``ANTHROPIC_MAX_TOKENS`` as
``_MODEL``/``_MAX_TOKENS`` so the panel author-token import keeps a single source.

Each provider exposes a list of selectable ``(model_id, label)`` rows; the panel
model picker reads ``PROVIDER_MODELS`` so switching models is a data lookup, and
``build_provider(provider_id, model=...)`` constructs with the chosen model.
"""
from __future__ import annotations

# -- model ids + token caps as data (the single source of truth) -----------

# Anthropic — the full set selectable in the panel (mirrors Claude desktop).
ANTHROPIC_MODELS = (
    ("claude-opus-4-8",            "Opus 4.8"),
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
# integrate.api.nvidia.com (2026-06-24, per Comfy-Cozy agent/config.py).
NVIDIA_MODELS = (
    ("nvidia/nemotron-3-super-120b-a12b", "Nemotron Super 120B"),
    ("nvidia/nemotron-3-nano-30b-a3b",    "Nemotron Nano 30B"),
)
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"   # default pick
NVIDIA_MAX_TOKENS = 4096

DEFAULT_PROVIDER = "claude"

# Provider ids selectable in the panel (the engine selector iterates this).
PROVIDER_IDS = ("claude", "gemini", "nemotron")

# Display labels for the engine selector pills.
PROVIDER_LABELS = {
    "claude": "Claude",
    "gemini": "Gemini",
    "nemotron": "Nemotron",
}

# Per-provider selectable model rows + the provider's default model id.
PROVIDER_MODELS = {
    "claude": ANTHROPIC_MODELS,
    "gemini": GEMINI_MODELS,
    "nemotron": NVIDIA_MODELS,
}
PROVIDER_DEFAULT_MODEL = {
    "claude": ANTHROPIC_MODEL,
    "gemini": GEMINI_MODEL,
    "nemotron": NVIDIA_MODEL,
}


def models_for(provider_id: str):
    """The selectable ``(model_id, label)`` rows for a provider (empty tuple if
    unknown)."""
    return PROVIDER_MODELS.get((provider_id or "").lower(), ())


def default_model(provider_id: str) -> str:
    """The default model id for a provider (Anthropic's if unknown)."""
    return PROVIDER_DEFAULT_MODEL.get((provider_id or "").lower(), ANTHROPIC_MODEL)


def model_label(provider_id: str, model_id: str) -> str:
    """Display label for a model id under a provider (falls back to the id)."""
    for mid, lbl in models_for(provider_id):
        if mid == model_id:
            return lbl
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
    from .anthropic_provider import AnthropicProvider
    return AnthropicProvider(model=model or ANTHROPIC_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS)
