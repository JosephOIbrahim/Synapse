"""Phase 0b / D1 (2026-06-05, harness target ratified H21.0.631): consent posture, pinned.

DECISION D1: single-user-localhost auto-approve. The live ``/synapse`` handler path
does NOT enforce consent on ``execute_python`` / ``execute_vex``, and the docs no
longer claim it does (CLAUDE.md 1.2 live-path note + safety rule 5).

This test BINDS that doc claim to code reality (v4 4a.4 DocConformance): the live
handlers must contain no consent-gate construct. If you later add a real
handler-layer gate (D1-a, going multi-user/studio), you MUST update the consent docs
(CLAUDE.md 1.2 / rule 5) AND this test together — that coupling is the entire point.
A green test here means "docs and code agree: ungated on localhost".

Floor note: this asserts against live source via ``inspect.getsource`` (the running
package), not a mock — so it cannot go green against an assumed API.
"""
import inspect

from synapse.server.handlers import SynapseHandler

# The constructs a real consent gate would introduce on the handler path.
_GATE_MARKERS = ("HumanGate", "_check_consent", ".propose(", "GateProposal")


def _src(method_name):
    return inspect.getsource(getattr(SynapseHandler, method_name))


def test_live_execute_python_is_ungated():
    src = _src("_handle_execute_python")
    for marker in _GATE_MARKERS:
        assert marker not in src, (
            f"execute_python handler now references {marker!r} -- a consent gate "
            "appeared on the live path. Update CLAUDE.md 1.2 / safety rule 5 and "
            "this test together (D1)."
        )
    # Documents the actual posture for the next reader: full exec, no import filter.
    assert "__builtins__" in src


def test_live_execute_vex_is_ungated():
    src = _src("_handle_execute_vex")
    for marker in _GATE_MARKERS:
        assert marker not in src, (
            f"execute_vex handler now references {marker!r} -- update the consent "
            "docs and this test together (D1)."
        )
