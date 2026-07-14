"""
tests/test_h22_resweep_spec.py — HONEST pure-python lint of the U.1-H22 re-sweep spec
=====================================================================================

Pins ``harness/notes/SYNAPSE_U1_H22_RESWEEP.md`` against the G-2 truth contract:
the discovery-breadth re-sweep may NAME net-new H22 node families as candidates for
adjudication, but it must never ASSERT any H22 spelling is real/confirmed API.

Zero-``synapse``-import, zero-``hou``: reads the committed markdown and lints text.
The vicinity checker (``_unqualified_h22_tokens``) is deliberately fail-capable — a
sibling test feeds it a bad and a good snippet to prove it discriminates, so a future
edit that drops a phantom qualifier next to an H22 node-type token fails loud.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "harness" / "notes" / "SYNAPSE_U1_H22_RESWEEP.md"

# A node-type-looking token: a Houdini namespaced spelling ``word::word[::...]``.
# The mandatory ``::`` part is what separates a candidate node-type spelling from
# ordinary prose and from real Python API (which is ``.``-dotted, e.g.
# hou.nodeTypeCategories) — so only genuine node-type tokens are inspected.
_H22_TOKEN = re.compile(r"[a-z][a-z0-9_]*(?:::[a-z0-9_]+)+")

# Phantom-discipline qualifier that must sit near any H22 node-type token.
_QUALIFIER = re.compile(
    r"candidate|phantom|unverified|pending|not[\s-]?verified|quarantin|proposal|"
    r"probe-pending|to-be-probed",
    re.IGNORECASE,
)

# An AFFIRMATIVE runtime-existence assertion (JSON or kwarg form). Requires a real
# separator so prose that merely *names* the field (to forbid it) does not trip.
_AFFIRMATIVE_EXISTS = re.compile(r'exists_in_runtime["\s]*[:=]["\s]*true', re.IGNORECASE)

_VICINITY = 220  # chars on each side of a token within which a qualifier must appear


def _spec_text() -> str:
    assert SPEC.exists(), f"spec not found: {SPEC}"
    return SPEC.read_text(encoding="utf-8")


def _unqualified_h22_tokens(text: str, window: int = _VICINITY) -> list:
    """Every H22 node-type-looking token whose vicinity lacks a phantom/candidate/
    unverified qualifier. Non-empty ⇒ the spec asserted a bare H22 spelling."""
    violations = []
    for m in _H22_TOKEN.finditer(text):
        lo = max(0, m.start() - window)
        hi = min(len(text), m.end() + window)
        if not _QUALIFIER.search(text[lo:hi]):
            violations.append((m.group(0), m.start()))
    return violations


# ---------------------------------------------------------------------------
# (a) phantom-discipline disclaimer + ratified:false present; no real-API assertion
# ---------------------------------------------------------------------------

def test_phantom_discipline_disclaimer_present():
    text = _spec_text()
    assert re.search(r"phantom[\s-]?discipline", text, re.IGNORECASE), \
        "spec must carry an explicit phantom-discipline disclaimer"


def test_ratified_false_appears():
    text = _spec_text()
    assert re.search(r'ratified"?\s*:\s*false', text, re.IGNORECASE), \
        "spec must show candidate entries as ratified: false"


def test_no_affirmative_runtime_existence_for_h22_symbol():
    text = _spec_text()
    hit = _AFFIRMATIVE_EXISTS.search(text)
    assert hit is None, \
        f"spec must never assert exists_in_runtime true (found: {hit.group(0)!r})"


def test_no_is_a_real_claim():
    text = _spec_text()
    hit = re.search(r"\bis a real\b", text, re.IGNORECASE)
    assert hit is None, \
        "spec must not claim any H22 symbol 'is a real' API"


# ---------------------------------------------------------------------------
# (b) references both the queue file and the NEW baseline inventory artifact
# ---------------------------------------------------------------------------

def test_references_flywheel_queue_and_inventory_baseline():
    text = _spec_text()
    assert "flywheel_queue.json" in text, \
        "spec must name the queue it deposits candidates into"
    assert "verified_node_inventory_21.0.671.json" in text, \
        "spec must name the NEW H21 full-category inventory baseline artifact"


def test_cites_the_binding_flow_it_defers_to():
    """The spec is thin BECAUSE probe->candidate->ratify is already binding; it must
    cite those bindings rather than re-specify them."""
    text = _spec_text()
    assert "h22-drop-week.js" in text, "must cite the drop-week runbook it plugs into"
    assert "spec-U1-wiring-flywheel.md" in text, "must cite the U.1 queue-append binding"


# ---------------------------------------------------------------------------
# (c) every H22 node-type-looking token co-occurs with a phantom qualifier
# ---------------------------------------------------------------------------

def test_every_h22_node_type_token_is_qualified():
    text = _spec_text()
    violations = _unqualified_h22_tokens(text)
    assert violations == [], (
        "unqualified H22 node-type token(s) — every ``word::word`` spelling must sit "
        f"near a candidate/phantom/unverified qualifier: {violations}"
    )
    # The spec is expected to actually USE at least one such example token (otherwise
    # the discipline check is vacuous). Guard against a spec that dodges the contract
    # by never naming a candidate spelling at all.
    assert _H22_TOKEN.search(text) is not None, \
        "spec should name at least one candidate node-type spelling (kept qualified)"


def test_lint_is_fail_capable():
    """Prove the vicinity checker discriminates: a bare spelling FAILS, a qualified
    one PASSES. This is what makes the (c) assertion meaningful rather than vacuous."""
    bad = "In H22 we will emit top::gaussian_splat_train and copernicus::mlinfer as new tools."
    flagged = _unqualified_h22_tokens(bad)
    assert flagged, "checker must flag unqualified H22 node-type tokens"
    assert {t for t, _ in flagged} == {"top::gaussian_splat_train", "copernicus::mlinfer"}

    good = ("The spelling top::gaussian_splat_train is a phantom-pending candidate, "
            "unverified until a live H22 probe confirms it.")
    assert _unqualified_h22_tokens(good) == [], \
        "checker must accept a token qualified as phantom-pending/candidate/unverified"


def test_affirmative_exists_regex_is_fail_capable():
    """The runtime-existence guard must catch a real assertion but ignore a mention
    that forbids it (the spec's own disclaimer names the field to ban it)."""
    assert _AFFIRMATIVE_EXISTS.search('"exists_in_runtime": true')
    assert _AFFIRMATIVE_EXISTS.search("exists_in_runtime=true")
    assert _AFFIRMATIVE_EXISTS.search("the `exists_in_runtime` field stays `false`") is None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
