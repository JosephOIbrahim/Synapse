"""model_facts — documented context windows and public list prices, as DATA.

J2 (RULING_JOE_FIVE.md, 2026-09-05): the TOKEN face shows the share of the
model's context window a prompt used, and what the session cost. Neither the
Anthropic nor the NVIDIA API reports either figure on the wire (V3-F5: no
provider exposes per-token price over its API), so both come from here: a
table of facts, each verified on the provider's PUBLIC price / model page on
the date in the row. Nothing unverified is in the table — a model that is not
here is simply absent, and the face says "price unknown for <model>" /
"context window not reported by <provider>" rather than guessing (R162).

Rows are keyed by (provider id, registry model id) — the exact ids
``providers/registry.py`` offers — and every row carries its source and date,
because a price typed into code is documentation, and documentation ages (R74).
Re-verify the rows when the registry changes or a provider re-prices; the
tests/test_j2_token_wire.py pin refuses a row that is not a registry model or
has no dated source.

Ollama and Gemini report their own windows live (``/api/show`` and
``models.get``, see the providers); the Gemini row here is the fallback when
that call fails. An Ollama tag alone cannot prove local execution. Historical
usage records lack endpoint-bound locality evidence, so their per-token cost
is unknown; a cloud relay also has no public per-token rate here. NVIDIA NIM
(``integrate.api.nvidia.com``) publishes no per-token
list price for its developer API either (checked 2026-09-05), so Nemotron rows
are absent on purpose and the face says so.

Pure Python: no Qt, no hou, no network.
"""
from __future__ import annotations

from typing import Optional, Tuple

_ANTHROPIC_PRICING = "https://platform.claude.com/docs/en/about-claude/pricing · 2026-09-05"
_ANTHROPIC_MODELS = "https://platform.claude.com/docs/en/models/overview · 2026-09-05"
_GEMINI_PRICING = "https://ai.google.dev/gemini-api/docs/pricing · 2026-09-05"
_GEMINI_MODELS_GET = "generativelanguage.googleapis.com models.get inputTokenLimit · 2026-09-05"

#: (provider id, model id) -> (context window in tokens, "source · YYYY-MM-DD")
CONTEXT_WINDOW = {
    # Models overview compare table: Opus 5 / Sonnet 5 "1M tokens", Haiku 4.5
    # "200K tokens" (API id claude-haiku-4-5-20251001). The pricing page's
    # "Long context pricing": "Claude 4.6 and later models ... include the
    # full 1M token context window" covers Opus 4.8, Sonnet 4.6 and Fable 5.
    ("claude", "claude-opus-5"):             (1_000_000, _ANTHROPIC_MODELS),
    ("claude", "claude-opus-4-8"):           (1_000_000, _ANTHROPIC_PRICING),
    ("claude", "claude-sonnet-5"):           (1_000_000, _ANTHROPIC_MODELS),
    ("claude", "claude-sonnet-4-6"):         (1_000_000, _ANTHROPIC_PRICING),
    ("claude", "claude-haiku-4-5-20251001"): (200_000, _ANTHROPIC_MODELS),
    ("claude", "claude-fable-5"):            (1_000_000, _ANTHROPIC_PRICING),
    # Live GET /v1beta/models/gemini-3.5-flash on 2026-09-05:
    # inputTokenLimit 1048576 (version 3.5-flash-05-2026). Fallback only —
    # GeminiProvider asks models.get itself.
    ("gemini", "gemini-3.5-flash"):          (1_048_576, _GEMINI_MODELS_GET),
}

#: (provider id, model id) -> (input, output, cache read, cache write) in USD
#: per MILLION tokens, then "source · YYYY-MM-DD". None = that field has no
#: public per-token price; it then contributes nothing (never a guess).
PRICE_USD_PER_MTOK = {
    # Anthropic "Model pricing" table: base input / output, 5-minute cache
    # writes (the panel's _with_prompt_cache uses the default ephemeral TTL),
    # cache hits at 0.1x base input.
    ("claude", "claude-opus-5"):             (5.0, 25.0, 0.50, 6.25, _ANTHROPIC_PRICING),
    ("claude", "claude-opus-4-8"):           (5.0, 25.0, 0.50, 6.25, _ANTHROPIC_PRICING),
    ("claude", "claude-sonnet-5"):           (2.0, 10.0, 0.20, 2.50, _ANTHROPIC_PRICING),
    ("claude", "claude-sonnet-4-6"):         (3.0, 15.0, 0.30, 3.75, _ANTHROPIC_PRICING),
    ("claude", "claude-haiku-4-5-20251001"): (1.0, 5.0, 0.10, 1.25, _ANTHROPIC_PRICING),
    ("claude", "claude-fable-5"):            (10.0, 50.0, 1.0, 12.50, _ANTHROPIC_PRICING),
    # Gemini paid tier: "Output price (including thinking tokens)" — thoughts
    # are billed as output, which is why gemini_provider folds
    # thoughtsTokenCount into output_tokens. Context caching is priced per
    # token READ plus per hour of storage; storage is not a per-token write
    # rate, so cache write stays None.
    ("gemini", "gemini-3.5-flash"):          (1.50, 9.00, 0.15, None, _GEMINI_PRICING),
}

# The usage_sink vocabulary, in the PRICE row's field order.
_COST_FIELDS = ("input_tokens", "output_tokens", "cache_read", "cache_creation")


def _is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _date_of(source: str) -> str:
    """The trailing YYYY-MM-DD of a 'source · date' string."""
    return source[-10:]


def _key(provider_id, model_id):
    return ((provider_id or "").lower(), model_id or "")


def context_window(provider_id, model_id) -> Optional[Tuple[int, str]]:
    """``(window, source)`` for a documented (provider, model), else ``None``."""
    return CONTEXT_WINDOW.get(_key(provider_id, model_id))


def price(provider_id, model_id):
    """The ``PRICE_USD_PER_MTOK`` row for a (provider, model), else ``None``."""
    return PRICE_USD_PER_MTOK.get(_key(provider_id, model_id))


def is_local(provider_id, model_id, remote_host=None, *, local_evidence=False) -> bool:
    """A model tag alone cannot establish local inference or a zero price.

    The caller must hold affirmative endpoint-bound evidence. Historical usage
    records lack it, so their unknown cost stays unknown.
    """
    if remote_host:
        return False
    pid, model = _key(provider_id, model_id)
    return local_evidence is True and pid == "ollama" and bool(model) and ":cloud" not in model


def cost(snapshot, remote_host=None):
    """Cost of one usage record — a usage_sink snapshot, or one of its
    ``session['by_model']`` parts: a dict with ``provider`` / ``model`` and any of
    ``input_tokens`` / ``output_tokens`` / ``cache_read`` / ``cache_creation``.

    Returns ``(usd, note)`` or ``None``:
      (0.0, 'local')                        local weights (Ollama, no remote host)
      (usd, 'list price · YYYY-MM-DD')      list price × the fields it reported
      (None, 'tokens not reported')         a priced model that reported nothing
      None                                  no public price for this model

    ``usd`` is a float, never a bool; only int-and-not-bool counts are priced
    (the usage_sink guard); a field whose rate is None contributes nothing.
    """
    if not isinstance(snapshot, dict):
        return None
    pid, model = _key(snapshot.get("provider"), snapshot.get("model"))
    if is_local(pid, model, remote_host):
        return (0.0, "local")
    row = PRICE_USD_PER_MTOK.get((pid, model))
    if row is None:
        return None
    usd, priced_any = 0.0, False
    for field, rate in zip(_COST_FIELDS, row[:4]):
        count = snapshot.get(field)
        if rate is None or not _is_count(count):
            continue
        usd += count * rate / 1_000_000.0
        priced_any = True
    if not priced_any:
        return (None, "tokens not reported")
    return (float(usd), "list price · %s" % _date_of(row[4]))


def _parts(snapshot):
    session = snapshot.get("session") if isinstance(snapshot, dict) else None
    parts = session.get("by_model") if isinstance(session, dict) else None
    return [p for p in (parts or []) if isinstance(p, dict)]


def session_cost(snapshot):
    """Cost of the whole session: the sum over its ``by_model`` parts.

    ``(usd, note)`` when every part is priceable — local parts add $0, and the
    note is ``'local'`` only when ALL of them are; ``(None, 'tokens not
    reported')`` when the priced parts reported nothing; ``None`` when any part
    has no public price (see ``unpriced_models``) or the session is empty.
    """
    parts = _parts(snapshot)
    if not parts:
        return None
    total, any_usd, notes = 0.0, False, []
    for part in parts:
        priced = cost(part)
        if priced is None:
            return None
        usd, note = priced
        if usd is None:
            continue
        total += usd
        any_usd = True
        if note not in notes:
            notes.append(note)
    if not any_usd:
        return (None, "tokens not reported")
    dated = [n for n in notes if n != "local"]
    return (float(total), " · ".join(dated) if dated else "local")


def unpriced_models(snapshot):
    """Model ids in the session with no public price and no local posture —
    the names the face puts after 'price unknown for'."""
    names = []
    for part in _parts(snapshot):
        if cost(part) is None:
            name = part.get("model") or "?"
            if name not in names:
                names.append(name)
    return names
