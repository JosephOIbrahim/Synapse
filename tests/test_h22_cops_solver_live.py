"""W.4-H22-solverblocks (SB-3) live pin: explicit block binding COOKS on H22.

Runs ONLY under real Houdini (hython on H22.0.368+). Under the stock suite the
conftest canonical fake ``hou`` is resident, so every test here skips — the
stock-python side of this cycle (emitted parm writes on the live surface) is
pinned by tests/test_cops.py (TestW4SolverBlockBinding /
TestW4StylizeQuantizeSurface).

Ground truth being pinned (W.4/N-4 live-bridge probe,
docs/reviews/h22-live-reconfirm-2026-07-16.md §2.1, re-observed by the SB-3
hython parm probe on 22.0.368, 2026-07-16):

  * ``block_end`` (Cop) LOST ``method``/``blocktype``/``blockpath``; its
    surviving surface is the sim/iteration driver (``simulate``,
    ``iterations``, ``startframe``, ``cacheenabled``, ...).
  * ``blockpath`` MOVED to ``block_begin``; binding is NOT implicit — an
    unbound pair raises ``hou.OperationFailed`` on cook ("Cannot do simulate
    if the block doesn't have a begin node at the same level").
  * Binding ``block_begin.blockpath`` to the paired end (relative
    ``../<name>``) cooks clean. The handlers author exactly that.
  * ``limit`` resolves to ``clamp`` (creation-time alias); the clamp surface
    is ``upperlimit``/``doupperlimit`` (max/high ABSENT).
  * Cop ``quantize`` counts levels via ``method='segments'`` + ``segments``.

Run:  hython -m pytest tests/test_h22_cops_solver_live.py -v
"""

from __future__ import annotations

import pytest

import hou

# Real-hou gate: the canonical fake carries __synapse_canonical__ and does not
# define lopNodeTypeCategory; real hou has both properties inverted.
_LIVE = (
    not getattr(hou, "__synapse_canonical__", False)
    and hasattr(hou, "lopNodeTypeCategory")
)

pytestmark = pytest.mark.skipif(
    not _LIVE, reason="requires real Houdini (hython) — H22 live create+cook pin"
)


def _handler():
    from synapse.server.handlers_cops import CopsHandlerMixin

    return CopsHandlerMixin()


@pytest.fixture()
def copnet():
    net = hou.node("/obj").createNode("copnet", "w4live")
    try:
        yield net
    finally:
        try:
            net.destroy()
        except Exception:  # noqa: BLE001 — teardown best-effort
            pass


def test_block_end_parm_surface_is_sim_driver(copnet):
    """Live pin of the removal itself — the fix's reason to exist."""
    end = copnet.createNode("block_end", "w4_surface_end")
    assert end.parm("method") is None
    assert end.parm("blocktype") is None
    assert end.parm("blockpath") is None
    assert end.parm("simulate") is not None
    assert end.parm("iterations") is not None
    begin = copnet.createNode("block_begin", "w4_surface_begin")
    assert begin.parm("blockpath") is not None


def test_create_solver_via_handler_cooks(copnet):
    result = _handler()._handle_cops_create_solver(
        {"parent": copnet.path(), "name": "w4solver", "iterations": 4}
    )
    assert result["bound"] is True
    begin = hou.node(result["block_begin"])
    end = hou.node(result["block_end"])
    assert begin.parm("blockpath").eval() == "../w4solver_end"
    assert end.parm("iterations").eval() == 4
    end.cook(force=True)
    assert not end.errors(), f"create_solver block cook errors: {end.errors()}"


def test_growth_propagation_via_handler_cooks(copnet):
    result = _handler()._handle_cops_growth_propagation(
        {"parent": copnet.path(), "iterations": 3, "threshold": 0.6}
    )
    assert result["bound"] is True
    end = hou.node(result["block_end"])
    thresh = hou.node(result["threshold"])
    # canonical clamp emitted, authored on the live surface
    assert thresh.type().name() == "clamp"
    assert thresh.parm("upperlimit").eval() == pytest.approx(0.6)
    assert thresh.parm("doupperlimit").eval() == 1
    end.cook(force=True)
    assert not end.errors(), f"growth block cook errors: {end.errors()}"


def test_wetmap_via_handler_cooks_in_simulate_mode(copnet):
    """Tool #17: the frame-by-frame decay driver is the simulate toggle."""
    result = _handler()._handle_cops_wetmap({"parent": copnet.path()})
    assert result["bound"] is True
    end = hou.node(result["block_end"])
    assert end.parm("simulate").eval() == 1
    end.cook(force=True)
    assert not end.errors(), f"wetmap block cook errors: {end.errors()}"


def test_stylize_toon_authors_segments_live(copnet):
    result = _handler()._handle_cops_stylize(
        {"parent": copnet.path(), "style_type": "toon", "levels": 4}
    )
    assert result["levels_applied"] is True
    node = hou.node(result["path"])
    assert node.type().name() == "quantize"
    assert node.parm("segments").eval() == 4
