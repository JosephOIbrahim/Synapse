"""PANEL-COMMENT: the send-path comment matches what the code does.

d5d2b415 (F04) dropped "a bridge /mcp consent-gated call" from the worker's
gate-denial text because the process bridge is built auto-approve, so that
call gates nothing. The comment above the ClaudeWorker construction in
synapse_panel.py still pointed the reader at the same non-gate. This test
reads the source text only; it never imports or constructs SynapsePanel.
"""
from __future__ import annotations

from pathlib import Path

_PANEL = (
    Path(__file__).resolve().parents[1]
    / "python" / "synapse" / "panel" / "synapse_panel.py"
)


def _send_comment_block() -> str:
    """The comment lines directly above the enforce_worker_policy worker."""
    lines = _PANEL.read_text(encoding="utf-8").splitlines()
    anchor = next(
        i for i, ln in enumerate(lines)
        if "Joe DECIDE 2026-08-18 (ENG-INJ-GATE-OFF)" in ln
    )
    end = next(
        i for i in range(anchor, len(lines))
        if "enforce_worker_policy=True" in lines[i]
    )
    return "\n".join(
        ln.strip() for ln in lines[anchor:end] if ln.strip().startswith("#")
    )


def test_panel_source_names_no_consent_gated_path():
    assert "consent-gated" not in _PANEL.read_text(encoding="utf-8")


def test_send_comment_points_at_the_native_ui_and_names_the_auto_approve_bridge():
    block = _send_comment_block()
    assert "native Houdini UI" in block
    assert "auto-approve" in block
