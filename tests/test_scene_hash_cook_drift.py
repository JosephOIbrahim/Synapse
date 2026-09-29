"""BP12 item 16, found live on 2026-09-29 in Houdini 22.0.400.

Two back-to-back same-value writes on a Karma Render Settings LOP, with only
reads between them, saw different scene hashes, so the second write reported
external_change_detected. The R1 hash read cook counts (the node's and its HDA
internals') before node.stage() cooked the pending change, so every write moved
the next read of an unchanged scene. A hython probe on Houdini 22.0.400 showed
the stage signature steady while the counts moved, and a stage restored to its
original content still hashed differently, which is how a clean rollback reads
"rollback_incomplete". With a complete stage signature the hash is now
topology plus content. The reduced mode keeps its inputs.
"""
import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.types import AgentID

TARGET = "/stage/lookdev_xpu/preview_settings"


class _Stage:
    def __init__(self, text):
        self._text = text

    def Flatten(self):
        return self

    def ExportToString(self):
        return self._text


class _Kid:
    def __init__(self, sid):
        self._sid = sid
        self.cooks = 1

    def sessionId(self):
        return self._sid

    def cookCount(self):
        return self.cooks


class _LazyLop:
    """Cooks like Houdini: a write marks it dirty, and the next stage() call
    cooks it, which bumps its own and its HDA internals' cook counts."""

    def __init__(self, text="STAGE_A"):
        self.text = text
        self.cooks = 1
        self.dirty = False
        self.kids = [_Kid(101), _Kid(102)]

    def children(self):
        return list(self.kids)

    def cookCount(self):
        return self.cooks

    def geometry(self):
        return None

    def stage(self):
        if self.dirty:
            self.dirty = False
            self.cooks += 1
            for kid in self.kids:
                kid.cooks += 1
        return _Stage(self.text)

    def write(self, text=None):
        if text is not None:
            self.text = text
        self.dirty = True


class _Undos:
    def group(self, label):
        class _Ctx:
            def __enter__(ctx):
                return ctx

            def __exit__(ctx, *args):
                return False
        return _Ctx()


class _Hou:
    def __init__(self, node):
        self._node = node
        self.undos = _Undos()
        self.LopNode = type("LopNode", (), {})

    def node(self, path):
        return self._node


def _bridge(monkeypatch, lop):
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", _Hou(lop))
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)
    return LosslessExecutionBridge()


def test_a_write_does_not_move_the_next_hash(monkeypatch):
    lop = _LazyLop()
    bridge = _bridge(monkeypatch, lop)
    lop.write()  # same content, a cook pending
    after = bridge._compute_scene_hash(TARGET)
    again = bridge._compute_scene_hash(TARGET)
    assert lop.cooks == 2  # the first hash's stage() call cooked it
    assert after == again


def test_restored_content_hashes_like_the_original(monkeypatch):
    lop = _LazyLop()
    bridge = _bridge(monkeypatch, lop)
    original = bridge._compute_scene_hash(TARGET)
    lop.write("STAGE_B")
    changed = bridge._compute_scene_hash(TARGET)
    lop.write("STAGE_A")
    restored = bridge._compute_scene_hash(TARGET)
    assert changed != original
    assert restored == original


def test_topology_still_changes_the_hash(monkeypatch):
    lop = _LazyLop()
    bridge = _bridge(monkeypatch, lop)
    before = bridge._compute_scene_hash(TARGET)
    lop.kids.append(_Kid(103))
    assert bridge._compute_scene_hash(TARGET) != before


def test_reduced_mode_keeps_cook_counts(monkeypatch):
    lop = _LazyLop()
    bridge = _bridge(monkeypatch, lop)
    monkeypatch.setattr(LosslessExecutionBridge, "_reduced_stage_signature",
                        staticmethod(lambda stage: "REDUCED"))
    bridge._stage_hash_begin_op()
    bridge._stage_hash_pin_mode("reduced")
    try:
        first = bridge._compute_scene_hash(TARGET)
        lop.write()
        bridge._compute_scene_hash(TARGET)  # cooks the pending write
        second = bridge._compute_scene_hash(TARGET)
    finally:
        bridge._stage_hash_end_op()
    assert first != second  # reduced mode still follows the cook counts


def _write_op(lop):
    # create_node is INFORM-gated, so consent passes without a prompt.
    return Operation(agent_id=AgentID.HANDS, operation_type="create_node",
                     summary="same-value write", fn=lop.write)


def test_second_write_reports_no_external_change(monkeypatch):
    lop = _LazyLop()
    bridge = _bridge(monkeypatch, lop)
    first = bridge.execute(_write_op(lop))
    second = bridge.execute(_write_op(lop))
    assert first.success and second.success
    assert second.integrity.external_change_detected is False
