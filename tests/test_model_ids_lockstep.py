"""Model-ID drift alarm — the out-of-panel Claude model literals stay active.

Four first-party sites hardcode Anthropic model ids outside the panel registry
(the "un-reconciled fork"): the daemon agent loop, the standalone agent, the
routing tiers, and the spike-0 bootstrap. Until they import a shared
``core/model_ids.py`` (post-H22 backlog), this scan is the CI alarm: every
``claude-*`` literal in those files must be in the active-id allowlist derived
from the panel registry ∪ a small legacy-active set. A retired id (e.g. the
old ``claude-3-haiku-20240307``, which now 404s) fails here instead of at
runtime. Text-scan idiom per test_m3_egress_docs.py — headless, zero-hou,
zero-Qt, imports no handler/panel module beyond the registry data.
"""
import re
from pathlib import Path

from synapse.panel.providers.registry import ANTHROPIC_MODELS

_ROOT = Path(__file__).resolve().parent.parent

# The four out-of-panel sites holding Claude model literals today.
_SITES = (
    "python/synapse/cognitive/agent_loop.py",
    "agent/synapse_agent.py",
    "python/synapse/routing/router.py",
    "spikes/spike_0.py",
)

# Registry rows are the primary source of truth; the legacy-active set covers
# ids that are live at the API but deliberately not panel-selectable (the
# undated haiku alias used by spike_0 — the registry keeps the dated id).
_LEGACY_ACTIVE = {"claude-haiku-4-5"}

_MODEL_LITERAL = re.compile(r'"(claude-[a-z0-9][a-z0-9.-]*)"')


def test_out_of_panel_model_literals_are_active():
    allow = {mid for mid, _ in ANTHROPIC_MODELS} | _LEGACY_ACTIVE
    stale = {}
    for rel in _SITES:
        path = _ROOT / rel
        assert path.is_file(), f"{rel} moved — update this pin"
        found = set(_MODEL_LITERAL.findall(path.read_text(encoding="utf-8")))
        bad = found - allow
        if bad:
            stale[rel] = sorted(bad)
    assert not stale, (
        f"Stale/unknown Claude model id(s) {stale} — refresh the literal(s) or, "
        "if the id is genuinely live, extend the registry/_LEGACY_ACTIVE allowlist."
    )


def test_sites_still_carry_a_model_literal():
    """If a site drops its literal (e.g. moves to a shared module), this pin
    should be updated in the same change — the alarm must track reality."""
    for rel in _SITES:
        text = (_ROOT / rel).read_text(encoding="utf-8")
        assert _MODEL_LITERAL.search(text), (
            f"{rel} no longer holds a claude-* literal — update _SITES "
            "(the shared-module refactor should retire this pin)."
        )
