"""F04 (SC-3): the worker's gate denial does not point at a consent gate.

The denial reason reaches the panel activity and the LLM. It used to send
the artist to "a bridge /mcp consent-gated call", but the process bridge is
built auto-approve, so nothing on /mcp gates. The reason now sends the
artist to the native Houdini UI only.
"""

from synapse.panel import worker_policy as policy


def _standard_denial(monkeypatch, tool_name="houdini_execute_python"):
    monkeypatch.delenv(policy._ENV_VAR, raising=False)
    monkeypatch.delenv(policy._PROFILE_ENV_VAR, raising=False)
    allowed, reason = policy.is_tool_allowed_for_worker(tool_name, profile="standard")
    assert not allowed
    assert reason.startswith("gate '"), reason
    return reason


def test_gate_denial_does_not_claim_a_consent_gated_path(monkeypatch):
    reason = _standard_denial(monkeypatch)
    assert "consent-gated" not in reason
    assert "/mcp" not in reason


def test_gate_denial_sends_the_artist_to_the_native_ui(monkeypatch):
    assert "native Houdini UI" in _standard_denial(monkeypatch)
