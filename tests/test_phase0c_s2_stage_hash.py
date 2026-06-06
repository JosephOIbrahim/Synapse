"""Phase 0c / S2: scene hash must incorporate the COMPOSED LOP stage.

Before S2, _compute_scene_hash digested SOP intrinsics + cookCount; for a LOP
target node.geometry() is None, so the hash collapsed to "did the node recook"
and could NOT detect that the composed stage content changed -- blind on the
Solaris path (the integrity eval-signal the Floor depends on).

LIVE V1 evidence (H21.0.631 hython, .scout/s2_lop_recon2.py): flatten-export is
stable (same stage -> same hash) AND attribute-sensitive (radius 1.0->3.5 changes
the hash; a path+type-only digest does NOT). This test pins the INTEGRATION in
stock CI via a fake stage: the hash includes the composed stage and changes with it.
"""
import shared.bridge as b


class _FakeStage:
    def __init__(self, export):
        self._export = export

    def Flatten(self):
        return self

    def ExportToString(self):
        return self._export


class _FakeLop:
    """A LOP-like node: no SOP geometry, but a composed stage."""
    def __init__(self, export):
        self._stage = _FakeStage(export)

    def children(self):
        return []

    def cookCount(self):
        return 1

    def geometry(self):
        return None  # LOPs have no SOP geometry — the geo block is skipped

    def stage(self):
        return self._stage


class _FakeHou:
    def __init__(self, node):
        self._node = node

    def node(self, path):
        return self._node


def test_scene_hash_includes_and_tracks_composed_stage(monkeypatch):
    bridge = b.LosslessExecutionBridge()
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)

    monkeypatch.setattr(b, "hou", _FakeHou(_FakeLop("COMPOSED_STAGE_A")))
    h1 = bridge._compute_scene_hash("/stage")
    h1b = bridge._compute_scene_hash("/stage")
    assert h1 == h1b, "same composed stage must hash identically (no false-positive)"

    monkeypatch.setattr(b, "hou", _FakeHou(_FakeLop("COMPOSED_STAGE_B")))
    h2 = bridge._compute_scene_hash("/stage")
    assert h2 != h1, "scene hash must change when the composed stage content changes (S2)"
