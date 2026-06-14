"""Provider registry — model IDs and per-provider config as DATA.

Adding or retiring a model must never touch worker/dispatch code; it changes a
row here. ``build_provider`` is the only constructor the panel/worker call.
``claude_worker`` re-exports ``ANTHROPIC_MODEL``/``ANTHROPIC_MAX_TOKENS`` as
``_MODEL``/``_MAX_TOKENS`` so the panel author-token import keeps a single source.
"""
from __future__ import annotations

# -- model ids + token caps as data (the single source of truth) -----------
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 4096

DEFAULT_PROVIDER = "claude"

# Provider ids selectable in the panel. (Gemini lands in the next commit.)
PROVIDER_IDS = ("claude",)

# Display labels for the rail provider toggle.
PROVIDER_LABELS = {
    "claude": "Claude",
}


def build_provider(provider_id: str = DEFAULT_PROVIDER):
    """Construct the StreamProvider for ``provider_id`` (data-driven).

    Unknown ids fall back to the Claude floor — the panel never crashes on a
    stale selection.
    """
    pid = (provider_id or DEFAULT_PROVIDER).lower()
    # (Gemini branch added in the next commit; only Claude exists today.)
    from .anthropic_provider import AnthropicProvider
    return AnthropicProvider(model=ANTHROPIC_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS)
