"""R-007 (HANDS-3): undo + idempotency contract for the Solaris builder tools.

The finding: four of the five registered Solaris builder tools opened
``hou.undos.group`` and re-raised without ``performUndo`` — a group only
GROUPS undo entries. Their name-based idempotency guards then answered
``already_exists`` on every retry, so a half-built component could never be
completed by the same tool.

These tests pin the control flow the repair owns:

  * a mid-build failure performs EXACTLY ONE guarded ``performUndo``
    (never zero, never two), and the retry rebuilds instead of answering
    ``already_exists``;
  * an existing container whose child chain is not whole reports
    ``incomplete`` with the missing nodes instead of ``already_exists``;
  * the guard itself never fires without undo-label evidence.

Mock-``hou`` is acceptable for THIS node: the assertion is the tool's own
control flow, not a claim about host behaviour. The LIVE half — that a real
``hou.undos`` group is rolled back by ``performUndo`` under Houdini
22.0.400 — needs the live tier and is deferred (`live_deferred` on the
wave receipt; run ``hython tests/solaris/run_live.py``).
"""

import pytest

from synapse.mcp.tool_impls.solaris import (
    component_builder,
    create_variants,
    import_megascans,
    scene_template,
)
from synapse.mcp.tool_impls.solaris.builder_guards import (
    rollback_if_group_left_entry,
    undo_labels_snapshot,
)


# ---------------------------------------------------------------------------
# A minimal, transactional fake host.
#
# Undo semantics modelled: a group leaves ONE label on the stack; the actions
# the body performed are kept only if the group exits with an exception, and
# performUndo replays them in reverse. That is what lets a retry prove it saw
# the scene the failed run actually left behind.
# ---------------------------------------------------------------------------

class _FakeUndoGroup:
    def __init__(self, stack, label):
        self._stack = stack
        self._label = label

    def __enter__(self):
        self._stack.labels.append(self._label)
        self._stack.open_groups.append([])
        return self

    def __exit__(self, exc_type, exc, tb):
        actions = self._stack.open_groups.pop()
        if exc_type is not None:
            self._stack.failed_actions.append(actions)
        return False


class FakeUndoStack:
    def __init__(self):
        self.labels = []
        self.open_groups = []
        self.failed_actions = []
        self.perform_undo_calls = 0

    def group(self, label):
        return _FakeUndoGroup(self, label)

    def undoLabels(self):
        return tuple(reversed(self.labels))

    def areEnabled(self):
        return True

    def performUndo(self):
        self.perform_undo_calls += 1
        if self.labels:
            self.labels.pop()
        actions = self.failed_actions.pop() if self.failed_actions else []
        for action in reversed(actions):
            action()


class _FakeParm:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class _FakeType:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class FakeNode:
    def __init__(self, host, name, type_name, parent=None):
        self.host = host
        self._name = name
        self._type_name = type_name
        self._parent = parent
        self._children = []
        self._inputs = {}
        self._display = False

    # -- identity ---------------------------------------------------------
    def name(self):
        return self._name

    def setName(self, name, unique_name=False):
        self._name = name

    def path(self):
        if self._parent is None:
            return "/"
        return self._parent.path().rstrip("/") + "/" + self._name

    def type(self):
        return _FakeType(self._type_name)

    def childTypeCategory(self):
        return _FakeType("Lop")

    def parent(self):
        return self._parent

    # -- children ---------------------------------------------------------
    def children(self):
        return list(self._children)

    def node(self, path):
        node = self
        for part in path.strip("/").split("/"):
            if not part:
                continue
            node = next((c for c in node._children if c.name() == part), None)
            if node is None:
                return None
        return node

    def createNode(self, type_name, name=None):
        name = name or type_name
        self.host.raise_if_injected(type_name, name)
        child = FakeNode(self.host, name, type_name, self)
        self._children.append(child)
        if type_name == "componentgeometry":
            # Mirror the real HDA's writable SOP subnet (F9).
            sopnet = FakeNode(self.host, "sopnet", "subnet", child)
            child._children.append(sopnet)
            sopnet._children.append(FakeNode(self.host, "geo", "subnet", sopnet))
        self.host.undo_record(lambda: self._children.remove(child))
        return child

    # -- parms / wiring ---------------------------------------------------
    def parm(self, name):
        return _FakeParm()

    def setInput(self, index, node):
        self._inputs[index] = node

    def inputs(self):
        if not self._inputs:
            return []
        return [self._inputs.get(i) for i in range(max(self._inputs) + 1)]

    def outputs(self):
        return [n for n in self.host.walk() if self in n.inputs()]

    def layoutChildren(self, *args, **kwargs):
        pass

    def position(self):
        return (0.0, 0.0)

    def setPosition(self, pos):
        pass

    def setDisplayFlag(self, flag):
        self._display = flag

    def isDisplayFlagSet(self):
        return self._display

    def setUserData(self, key, value):
        pass


class FakeHou:
    """The `hou` surface the four tools actually touch."""

    def __init__(self):
        self.undos = FakeUndoStack()
        self.fail_on = set()
        self.root = FakeNode(self, "", "root")
        self.Vector2 = lambda x, y: (x, y)  # noqa: E731 — instance attribute

    # -- scene ------------------------------------------------------------
    def make_stage(self):
        stage = FakeNode(self, "stage", "lopnet", self.root)
        self.root._children.append(stage)
        return stage

    def add_child(self, parent, name, type_name):
        child = FakeNode(self, name, type_name, parent)
        parent._children.append(child)
        return child

    def node(self, path):
        if path in (None, "", "/"):
            return self.root
        node = self.root
        for part in path.strip("/").split("/"):
            node = next((c for c in node._children if c.name() == part), None)
            if node is None:
                return None
        return node

    def walk(self):
        stack = list(self.root._children)
        while stack:
            node = stack.pop()
            yield node
            stack.extend(node._children)

    # -- failure injection -------------------------------------------------
    def raise_if_injected(self, type_name, name):
        if (type_name, name) in self.fail_on:
            raise RuntimeError(
                "induced mid-build failure creating %s %r" % (type_name, name))

    def undo_record(self, action):
        if self.undos.open_groups:
            self.undos.open_groups[-1].append(action)

    def copyNodesTo(self, nodes, parent):
        copies = []
        for src in nodes:
            copy = FakeNode(self, src.name(), src.type().name(), parent)
            parent._children.append(copy)
            self.undo_record(lambda p=parent, c=copy: p._children.remove(c))
            copies.append(copy)
        return copies

    # -- remaining hou surface --------------------------------------------
    def lopNodeTypeCategory(self):
        return _FakeType("Lop")

    def nodeType(self, category, name):
        return None

    def applicationVersionString(self):
        return "22.0.400"


def _bind(monkeypatch, module, host):
    """Point the tool module at the fake host (never touches sys.modules)."""
    monkeypatch.setattr(module, "hou", host)
    monkeypatch.setattr(module, "HOU_AVAILABLE", True)


def _fresh_lopnet():
    host = FakeHou()
    net = host.add_child(host.make_stage(), "build_net", "lopnet")
    return host, net


# ---------------------------------------------------------------------------
# The guard itself.
# ---------------------------------------------------------------------------

class TestGuardedUndo:
    def test_empty_group_is_not_undone(self):
        host = FakeHou()
        labels = undo_labels_snapshot(host)
        assert labels == ()
        assert rollback_if_group_left_entry(host, labels) is False
        assert host.undos.perform_undo_calls == 0

    def test_unreadable_evidence_skips_undo(self):
        class _NoUndos:
            pass

        assert undo_labels_snapshot(_NoUndos()) is None
        assert rollback_if_group_left_entry(_NoUndos(), None) is False

    def test_changed_stack_is_undone_exactly_once(self):
        host = FakeHou()
        labels = undo_labels_snapshot(host)
        with host.undos.group("SYNAPSE: test group"):
            pass
        assert rollback_if_group_left_entry(host, labels) is True
        assert host.undos.perform_undo_calls == 1


# ---------------------------------------------------------------------------
# component_builder
# ---------------------------------------------------------------------------

class TestComponentBuilderFailurePath:
    def test_mid_build_failure_undoes_once_and_retry_rebuilds(self, monkeypatch):
        host, net = _fresh_lopnet()
        _bind(monkeypatch, component_builder, host)
        host.fail_on.add(("componentoutput", "output_undo_cb"))

        with pytest.raises(RuntimeError, match="induced"):
            component_builder.execute(
                {"asset_name": "undo_cb", "parent_path": net.path()})

        assert host.undos.perform_undo_calls == 1
        assert net.node("component_undo_cb") is None, (
            "the guarded performUndo did not roll the half-built subnet back")

        host.fail_on.clear()
        result = component_builder.execute(
            {"asset_name": "undo_cb", "parent_path": net.path()})
        assert result["status"] == "created"
        assert host.undos.perform_undo_calls == 1  # success performs none

    def test_half_built_component_reports_incomplete(self, monkeypatch):
        host, net = _fresh_lopnet()
        _bind(monkeypatch, component_builder, host)
        comp = host.add_child(net, "component_half", "subnet")
        host.add_child(comp, "geo_half", "componentgeometry")

        result = component_builder.execute(
            {"asset_name": "half", "parent_path": net.path()})

        assert result["status"] == "incomplete"
        assert set(result["missing_nodes"]) == {"mat_half", "output_half"}
        assert host.undos.perform_undo_calls == 0


# ---------------------------------------------------------------------------
# import_megascans
# ---------------------------------------------------------------------------

class TestImportMegascansFailurePath:
    def test_mid_build_failure_undoes_once_and_retry_rebuilds(self, monkeypatch):
        host, net = _fresh_lopnet()
        _bind(monkeypatch, import_megascans, host)
        host.fail_on.add(("componentmaterial", "mat_undo_ms"))

        params = {
            "usdc_path": "/tmp/rock.usdc",
            "asset_name": "undo_ms",
            "parent_path": net.path(),
        }
        with pytest.raises(RuntimeError, match="induced"):
            import_megascans.execute(params)

        assert host.undos.perform_undo_calls == 1
        assert net.node("component_undo_ms") is None, (
            "the guarded performUndo did not roll the half-built component back")

        host.fail_on.clear()
        result = import_megascans.execute(params)
        assert result["status"] == "created"
        assert host.undos.perform_undo_calls == 1

    def test_half_built_component_reports_incomplete(self, monkeypatch):
        host, net = _fresh_lopnet()
        _bind(monkeypatch, import_megascans, host)
        comp = host.add_child(net, "component_half_ms", "subnet")
        host.add_child(comp, "geo_half_ms", "componentgeometry")
        host.add_child(comp, "mat_half_ms", "componentmaterial")

        result = import_megascans.execute({
            "usdc_path": "/tmp/rock.usdc",
            "asset_name": "half_ms",
            "parent_path": net.path(),
        })

        assert result["status"] == "incomplete"
        assert set(result["missing_nodes"]) == {
            "output_half_ms", "mtl_ref_half_ms"}
        assert host.undos.perform_undo_calls == 0


# ---------------------------------------------------------------------------
# scene_template
# ---------------------------------------------------------------------------

class TestSceneTemplateFailurePath:
    def test_mid_build_failure_undoes_once_and_retry_rebuilds(self, monkeypatch):
        host, net = _fresh_lopnet()
        _bind(monkeypatch, scene_template, host)
        host.fail_on.add(("camera", "camera1"))

        params = {"scene_name": "undo_st", "parent_path": net.path()}
        with pytest.raises(RuntimeError, match="induced"):
            scene_template.execute(params)

        assert host.undos.perform_undo_calls == 1
        assert net.node("primitive_undo_st") is None, (
            "the guarded performUndo did not roll the half-built chain back")

        host.fail_on.clear()
        result = scene_template.execute(params)
        assert result["status"] == "created"
        assert host.undos.perform_undo_calls == 1

    def test_half_built_chain_reports_incomplete(self, monkeypatch):
        host, net = _fresh_lopnet()
        _bind(monkeypatch, scene_template, host)
        host.add_child(net, "primitive_half_st", "primitive")

        result = scene_template.execute(
            {"scene_name": "half_st", "parent_path": net.path()})

        assert result["status"] == "incomplete"
        assert set(result["missing_nodes"]) == {
            "camera1", "materials", "physical_sky",
            "render_settings", "render"}
        assert host.undos.perform_undo_calls == 0


# ---------------------------------------------------------------------------
# create_variants
# ---------------------------------------------------------------------------

class TestCreateVariantsFailurePath:
    def test_mid_build_failure_undoes_once_and_retry_rebuilds(self, monkeypatch):
        host = FakeHou()
        stage = host.make_stage()
        comp = host.add_child(stage, "comp", "subnet")
        host.add_child(comp, "mat_base", "componentmaterial")
        _bind(monkeypatch, create_variants, host)
        host.fail_on.add(("explorevariants", "explore_comp"))

        params = {
            "component_path": comp.path(),
            "variant_type": "material",
            "variants": [{"name": "red"}, {"name": "blue"}],
        }
        with pytest.raises(RuntimeError, match="induced"):
            create_variants.execute(params)

        assert host.undos.perform_undo_calls == 1
        assert comp.node("mat_red") is None and comp.node("mat_blue") is None, (
            "the guarded performUndo did not roll the half-built variants back")

        host.fail_on.clear()
        result = create_variants.execute(params)
        assert result["status"] == "created"
        assert host.undos.perform_undo_calls == 1

    def test_half_built_variant_set_reports_incomplete(self, monkeypatch):
        host = FakeHou()
        stage = host.make_stage()
        comp = host.add_child(stage, "comp", "subnet")
        host.add_child(comp, "mat_base", "componentmaterial")
        host.add_child(comp, "mat_red", "componentmaterial")
        _bind(monkeypatch, create_variants, host)

        result = create_variants.execute({
            "component_path": comp.path(),
            "variant_type": "material",
            "variants": [{"name": "red"}, {"name": "blue"}],
            "add_explore_node": False,
        })

        assert result["status"] == "incomplete"
        assert result["missing_nodes"] == ["mat_blue"]
        assert host.undos.perform_undo_calls == 0
