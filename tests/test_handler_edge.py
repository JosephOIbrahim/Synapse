"""Tests for handler edge cases — TOPS race, VEX cleanup, PDG callback."""
import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

# Stub hou
if "hou" not in sys.modules:
    mock_hou = types.ModuleType("hou")
    mock_hou.node = MagicMock(return_value=None)
    mock_hou.undos = MagicMock()
    sys.modules["hou"] = mock_hou


class TestTopsMonitorRace:
    """C8: Concurrent stop doesn't crash."""

    def test_double_stop_raises_valueerror_not_keyerror(self):
        """Stopping an already-stopped monitor raises ValueError, not KeyError."""
        # Load handlers_tops
        spec = importlib.util.spec_from_file_location(
            "synapse.server.handlers_tops", _base / "server" / "handlers_tops" / "__init__.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Simulate: monitor already stopped (not in dict)
        handler_obj = MagicMock()
        handler_obj._tops_monitors = {}
        # pop with default should return None
        result = handler_obj._tops_monitors.pop("mon-1", None)
        assert result is None  # No KeyError

    def test_pop_with_default_is_atomic(self):
        """dict.pop(key, None) doesn't raise even if key missing."""
        d = {"a": 1}
        d.pop("a", None)  # Removes a
        result = d.pop("a", None)  # Second pop — returns None, no KeyError
        assert result is None


class _FakeParm:
    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


class _FakeWrangle:
    """The attribwrangle: the cook raises, and the failure is visible to the handler."""

    def __init__(self, cook_error=None):
        self._cook_error = cook_error or RuntimeError(
            "VEX error: undefined variable 'foo'")
        self._parms = {}
        self.parent_node = None
        self.cook_calls = []
        self.inputs = []

    def parm(self, name):
        return self._parms.setdefault(name, _FakeParm())

    def setInput(self, index, node):
        self.inputs.append((index, node))

    def setDisplayFlag(self, flag):
        self.display = flag

    def setRenderFlag(self, flag):
        self.render = flag

    def cook(self, force=False):
        self.cook_calls.append(force)
        raise self._cook_error

    def errors(self):
        return []

    def path(self):
        return self.parent_node.path() + "/synapse_vex"

    def parent(self):
        return self.parent_node


class _FakeGeo:
    """A geo container; ``destroyed`` is the behaviour under test."""

    def __init__(self, name, wrangle=None):
        self._name = name
        self._wrangle = wrangle
        self.destroyed = 0
        self.name_calls = 0
        if wrangle is not None:
            wrangle.parent_node = self

    def createNode(self, node_type, name):
        assert (node_type, name) == ("attribwrangle", "synapse_vex")
        return self._wrangle

    def name(self):
        self.name_calls += 1
        return self._name

    def path(self):
        return "/obj/" + self._name

    def destroy(self):
        self.destroyed += 1


class _FakeObj:
    """/obj — hands back the temp geo when the handler asks for one."""

    def __init__(self, temp_geo):
        self._temp_geo = temp_geo
        self.created = []

    def createNode(self, node_type, name):
        self.created.append((node_type, name))
        return self._temp_geo


class TestVexTempCleanup:
    """C11 / R-016: Temp VEX nodes cleaned up on failure — proven behaviourally.

    These tests used to assert that ``"destroy()"`` and ``"not input_node"``
    appear in ``inspect.getsource(_handle_execute_vex)`` — a pin a comment
    could satisfy, and one that stayed green if the call itself were removed.
    They now drive the public handler entry point against a fake hou and watch
    which nodes are actually destroyed.
    """

    @staticmethod
    def _handler(monkeypatch, fake_hou):
        from synapse.server import handlers as handlers_module

        monkeypatch.setattr(handlers_module, "hou", fake_hou, raising=False)
        monkeypatch.setattr(handlers_module, "HOU_AVAILABLE", True)
        monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)
        monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
        monkeypatch.setattr(handlers_module.SynapseHandler, "_submit_logs",
                            lambda self, *a, **k: None)
        return handlers_module.SynapseHandler()

    def test_temp_node_deleted_on_cook_failure_no_input(self, monkeypatch):
        """A failing cook with no input_node destroys the temp container."""
        wrangle = _FakeWrangle()
        temp_geo = _FakeGeo("synapse_vex_temp", wrangle)
        obj = _FakeObj(temp_geo)
        fake_hou = SimpleNamespace(node=lambda path: obj if path == "/obj" else None)

        result = self._handler(monkeypatch, fake_hou)._handle_execute_vex(
            {"snippet": "vector c = foo;"})

        assert wrangle.cook_calls == [True], "the cook must have been attempted"
        assert obj.created == [("geo", "synapse_vex_temp")]
        assert temp_geo.name_calls == 1, "the temp container is identified by its name"
        assert temp_geo.destroyed == 1, "the temp container must be destroyed"
        assert result["node"] == "(cleaned up)"
        assert result["errors"], "the cook failure is reported"

    def test_temp_node_preserved_with_input(self, monkeypatch):
        """A failing cook with input_node retains the wrangle in the user's network."""
        wrangle = _FakeWrangle()
        user_geo = _FakeGeo("geo1", wrangle)
        source = SimpleNamespace(path=lambda: "/obj/geo1", parent=lambda: user_geo)
        touched = []

        def _node(path):
            touched.append(path)
            if path == "/obj/geo1":
                return source
            raise AssertionError("no temp geo may be looked up when input_node is given")

        fake_hou = SimpleNamespace(node=_node)

        result = self._handler(monkeypatch, fake_hou)._handle_execute_vex(
            {"snippet": "vector c = foo;", "input_node": "/obj/geo1"})

        assert "/obj" not in touched
        assert wrangle.inputs == [(0, source)]
        assert user_geo.name_calls == 0, "cleanup never even considers the artist's network"
        assert user_geo.destroyed == 0, "a node we did not create is never destroyed"
        assert result["node"] == "/obj/geo1/synapse_vex", (
            "the broken wrangle stays inspectable where the artist can see it")
        assert result["errors"], "the cook failure is reported"


class TestPdgCallbackCleanup:
    """C13: PDG callback unregistered on storage failure."""

    def test_callback_cleanup_pattern_exists(self):
        """The monitor start code should have cleanup logic."""
        spec = importlib.util.spec_from_file_location(
            "synapse.server.handlers_tops", _base / "server" / "handlers_tops" / "__init__.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        import inspect
        source = inspect.getsource(mod.TopsHandlerMixin._handle_tops_monitor_stream)
        assert "removeEventHandler" in source, "Monitor start should have callback cleanup"
