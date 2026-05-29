"""FORGE tests for the branch-aware upstream Karma-LOP walk in _handle_render.

Cluster: BRAINSTEM (render/recovery). Opportunity C3.

The upstream-picture discovery inside RenderHandlerMixin._handle_render used to
follow only inputs()[0], so a Karma LOP reachable solely via a branched input
(inputs()[1] of a merge/switch LOP) was never visited and its `picture` parm
never found. The fix is a bounded breadth-first walk over ALL node.inputs()
with a visited set + node budget.

These tests reproduce the missed-branch case, guard the direct-loppath happy
path against regression, and prove a cyclic graph still terminates.

Bootstrap mirrors tests/test_render.py verbatim (stub hou/hdefereval into
sys.modules, importlib-load synapse.server.handlers, grab
_handlers_hou = handlers_mod.hou, `handler` fixture -> SynapseHandler()).
The fake graph follows the conftest _MockNode contract (parm/inputs/path/type)
but is built with MagicMock nodes inline, matching the sibling test
test_upstream_karma_lop_picture_discovered that lives next to it.

Mock-based -- no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini (verbatim from tests/test_render.py)
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]
    if not hasattr(_hou, "undos"):
        _hou.undos = MagicMock()

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]

if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()

_handlers_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "server" / "handlers.py"
_proto_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "protocol.py"
_aliases_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "aliases.py"

for mod_name, mod_path in [
    ("synapse", Path(__file__).resolve().parent.parent / "python" / "synapse"),
    ("synapse.core", Path(__file__).resolve().parent.parent / "python" / "synapse" / "core"),
    ("synapse.server", Path(__file__).resolve().parent.parent / "python" / "synapse" / "server"),
    ("synapse.session", Path(__file__).resolve().parent.parent / "python" / "synapse" / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _proto_path),
    ("synapse.core.aliases", _aliases_path),
    ("synapse.server.handlers", _handlers_path),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]

_handlers_hou = handlers_mod.hou
if not hasattr(_handlers_hou, "undos"):
    _handlers_hou.undos = MagicMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


# ---------------------------------------------------------------------------
# Helpers: build conftest _MockNode-style LOP nodes with MagicMock
# ---------------------------------------------------------------------------

def _make_lop(path, *, picture=None, inputs=None):
    """Build a MagicMock LOP node honoring the _MockNode contract.

    picture: str path returned by parm("picture").eval(), or None for no parm.
    inputs:  list of upstream nodes returned by .inputs() (default []).
    """
    node = MagicMock()
    node.path.return_value = path

    if picture is not None:
        pic_parm = MagicMock()
        pic_parm.eval.return_value = picture
        node.parm.side_effect = lambda n: pic_parm if n == "picture" else None
    else:
        node.parm.side_effect = lambda n: None

    node.inputs.return_value = list(inputs or [])
    return node


# ---------------------------------------------------------------------------
# Tests: branch-aware upstream Karma-LOP discovery (Opportunity C3)
# ---------------------------------------------------------------------------

class TestForgeBranchWalk:

    def _patched_render(self, handler, node_map, rop_path):
        """Run _handle_render inline with hou.node resolving via node_map."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn, *a, **kw: fn(*a, **kw)

        def _hou_node(p):
            return node_map.get(p)

        with patch.object(_handlers_hou, "node", side_effect=_hou_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=1.0, create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("time.sleep", return_value=None), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)), \
             patch("pathlib.Path.mkdir", return_value=None):
            return handler._handle_render({"node": rop_path})

    def test_branch_input_karma_lop_discovered(self, handler):
        """Karma LOP reachable ONLY via inputs()[1] (a branch) is found.

        Graph:
            ROP /out/usdrender1 (empty outputimage/picture, loppath=/stage/merge1)
            /stage/merge1  picture=None  inputs=[null1, karma1]   <-- branch
            /stage/null1   picture=None  inputs=[]   (dead-end on input slot 0)
            /stage/karma1  picture=/renders/branch_beauty.$F4.exr inputs=[]

        Old linear inputs()[0] walk descends into null1 and terminates,
        never reaching karma1 on slot 1. The BFS over all inputs reaches it.
        """
        # ROP node: empty outputimage, loppath -> merge1
        rop = MagicMock()
        rop.path.return_value = "/out/usdrender1"
        rop.type.return_value.name.return_value = "usdrender"

        out_parm = MagicMock()
        out_parm.eval.return_value = ""

        loppath_parm = MagicMock()
        loppath_parm.eval.return_value = "/stage/merge1"

        def _rop_parm(n):
            if n in ("outputimage", "picture"):
                return out_parm
            if n == "loppath":
                return loppath_parm
            return None

        rop.parm.side_effect = _rop_parm

        karma_lop = _make_lop("/stage/karma1", picture="/renders/branch_beauty.$F4.exr", inputs=[])
        dead_end = _make_lop("/stage/null1", picture=None, inputs=[])
        # input slot 0 = dead_end (non-karma), input slot 1 = karma (the branch)
        merge_lop = _make_lop("/stage/merge1", picture=None, inputs=[dead_end, karma_lop])

        node_map = {
            "/out/usdrender1": rop,
            "/stage/merge1": merge_lop,
            "/stage/null1": dead_end,
            "/stage/karma1": karma_lop,
        }

        result = self._patched_render(handler, node_map, "/out/usdrender1")

        # BFS reached the branch -> picked up branch_beauty
        assert "output_file" in result
        assert "branch_beauty" in result["output_file"]

    def test_direct_loppath_karma_still_found(self, handler):
        """Regression guard: zero-branch happy path still discovers picture.

        loppath -> /stage/karma1 directly, karma1.inputs() -> []. The rewrite
        must not break the original single-node case.
        """
        rop = MagicMock()
        rop.path.return_value = "/out/usdrender1"
        rop.type.return_value.name.return_value = "usdrender"

        out_parm = MagicMock()
        out_parm.eval.return_value = ""

        loppath_parm = MagicMock()
        loppath_parm.eval.return_value = "/stage/karma1"

        def _rop_parm(n):
            if n in ("outputimage", "picture"):
                return out_parm
            if n == "loppath":
                return loppath_parm
            return None

        rop.parm.side_effect = _rop_parm

        karma_lop = _make_lop("/stage/karma1", picture="/renders/direct_beauty.$F4.exr", inputs=[])

        node_map = {
            "/out/usdrender1": rop,
            "/stage/karma1": karma_lop,
        }

        result = self._patched_render(handler, node_map, "/out/usdrender1")

        assert "output_file" in result
        assert "direct_beauty" in result["output_file"]

    def test_cyclic_graph_terminates(self, handler):
        """Safety: a cycle (A.inputs->[B], B.inputs->[A], no picture) must not hang.

        With no discoverable picture the handler falls through to the default
        EXR path. The visited set + node budget guarantee termination.
        """
        rop = MagicMock()
        rop.path.return_value = "/out/usdrender1"
        rop.type.return_value.name.return_value = "usdrender"

        out_parm = MagicMock()
        out_parm.eval.return_value = ""

        loppath_parm = MagicMock()
        loppath_parm.eval.return_value = "/stage/A"

        def _rop_parm(n):
            if n in ("outputimage", "picture"):
                return out_parm
            if n == "loppath":
                return loppath_parm
            return None

        rop.parm.side_effect = _rop_parm

        node_a = _make_lop("/stage/A", picture=None, inputs=[])
        node_b = _make_lop("/stage/B", picture=None, inputs=[])
        node_a.inputs.return_value = [node_b]
        node_b.inputs.return_value = [node_a]  # cycle

        node_map = {
            "/out/usdrender1": rop,
            "/stage/A": node_a,
            "/stage/B": node_b,
        }

        # Default $HIP expandString returns "$HIP" (unchanged) -> temp EXR path.
        result = self._patched_render(handler, node_map, "/out/usdrender1")

        # No picture discovered -> fell through to the default EXR render path,
        # and crucially the call returned (did not hang).
        assert "output_file" in result
        assert result["output_file"].endswith(".exr")
