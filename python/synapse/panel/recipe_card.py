"""Pure plain-text and Qt rich-text card rendering; no Qt or host imports.

``render_html(card, tokens=...)`` receives the panel's already-loaded
``designsystem.tokens`` object. Loading that token module can seed the live
host theme, so the renderer deliberately does NOT import it, even lazily.
The panel owns theme initialization on its main thread. This follows the
health strip's STATUS grammar and escaped rich-text convention.
"""
from __future__ import annotations

from html import escape
import json
from typing import Any

from synapse.recipes.card import RecipeCard
from synapse.recipes.contracts import (
    Availability, CheckId, EvidenceFreshness, OperationState,
    RecoveryVerdict, TerminalVerdict,
)
from synapse.recipes.receipt import _encode


_CHECK_LABELS = {
    CheckId.P1_GRAPH: "Graph", CheckId.P2_USD: "USD",
    CheckId.P3_RENDER_READY: "Render readiness", CheckId.P4_COMPOSITION: "Composition",
    CheckId.P5_IMAGE_SMOKE: "Render image", CheckId.P6_LOCALITY: "Locality / recovery",
}


def _rows(card: RecipeCard) -> list[tuple[str, str]]:
    rows = [
        ("Recipe / action", f"{card.recipe_id} @ {card.recipe_version} / {card.action_id.value}"),
        ("Scope", card.scope), ("Availability", card.availability.value),
        ("Operation", card.operation_state.value),
        ("Recorded verdict", card.verdict.value if card.verdict else "No completed attempt"),
        ("Freshness", card.freshness.value),
    ]
    for check in card.checks:
        detail = check.status.value
        if check.reason:
            detail += f" — {check.reason}"
        if check.evidence:
            detail += " | " + json.dumps(_encode(check.evidence), sort_keys=True, ensure_ascii=False)
        rows.append((f"{_CHECK_LABELS[check.check]} ({check.check.value})", detail))
    approval = "Required for current scope" if card.approval_required else "Not required"
    if card.approval is not None:
        binding = card.approval
        approval += (f"; recorded: {binding.approved_by} at {binding.approved_at}; "
                     f"{binding.instance_id} revision {binding.graph_revision}, {binding.engine}, "
                     f"{binding.resolution[0]}x{binding.resolution[1]}, {binding.samples} samples, "
                     f"{binding.output_path}")
    rows.extend([("Approval", approval), ("Recovery", card.recovery.value),
                 ("Reason", card.reason), ("Next action", card.next_action)])
    if card.run_id:
        rows.append(("Run", card.run_id))
    return rows


def render_text(card: RecipeCard) -> str:
    return "\n".join(f"{label}: {value}" for label, value in _rows(card))


def _status_kind(card: RecipeCard) -> str:
    if card.availability == Availability.BLOCKED or card.approval_required:
        return "warning"
    if card.verdict == TerminalVerdict.BROKEN or card.recovery == RecoveryVerdict.RESIDUE:
        return "error"
    if card.operation_state == OperationState.RUNNING:
        return "working"
    if card.freshness != EvidenceFreshness.CURRENT or card.recovery == RecoveryVerdict.UNKNOWN:
        return "disconnected"
    if card.verdict == TerminalVerdict.VERIFIED and card.operation_state == OperationState.TERMINAL:
        return "connected"
    return "idle"


def render_html(card: RecipeCard, *, tokens: Any) -> str:
    """Render escaped Qt-compatible table/span markup using vendored tokens.

    No external links, image fetches, browser dialogs or clickable execution
    controls. Stale VERIFIED history is explicitly labelled and never green.
    """
    family, size, weight, _ = tokens.TYPE_ROLES["body"]
    style = (f"background-color:{tokens.SURFACE};color:{tokens.TEXT_PRIMARY};"
             f"font-family:{family};font-size:{size}px;font-weight:{weight};")
    color = escape(tokens.STATUS[_status_kind(card)][0], quote=True)
    rows = "".join(
        f'<tr><td><b>{escape(label)}</b></td><td>{escape(value)}</td></tr>'
        for label, value in _rows(card)
    )
    return (f'<table style="{escape(style, quote=True)}" cellspacing="{tokens.SPACE_SM}">'
            f'<tr><td colspan="2"><span style="color:{color}">'
            f'{escape(card.action_id.value)} — {card.freshness.value}</span></td></tr>'
            f'{rows}</table>')
