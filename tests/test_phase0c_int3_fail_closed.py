"""Phase 0c / INT-3 (v4 4a fail-closed): _verify_composition must fail CLOSED.

If composition validation raises (a pxr quirk, an unexpected stage), the Scene
Integrity anchor must report the composition INVALID -- not silently return True
(which would yield composition_valid=True / fidelity=1.0 having validated nothing).

CI-safe: forces the production path via monkeypatch and makes hou.node raise, then
asserts the except path returns False. No real Houdini needed.
"""
import shared.bridge as b


def test_verify_composition_fails_closed_on_exception(monkeypatch):
    bridge = b.LosslessExecutionBridge()

    class _BoomHou:
        def node(self, *a, **k):
            raise RuntimeError("validation boom")

    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", _BoomHou())

    # hou.node() raises -> except -> INT-3 fail-closed -> False (was True pre-fix).
    assert bridge._verify_composition("/stage") is False


def test_verify_composition_true_when_nothing_to_validate(monkeypatch):
    # The legitimate early-returns stay True: no Houdini -> nothing to validate.
    monkeypatch.setattr(b, "_HOU_AVAILABLE", False)
    bridge = b.LosslessExecutionBridge()
    assert bridge._verify_composition("/stage") is True
