"""
Tests for agent_state.py v2.0.0 schema.

Covers:
  - Pure helper functions (_safe_prim_name, _counter_suffix)
  - USDA stub fallback (no pxr)
  - Graceful no-op when PXR_AVAILABLE=False
  - Full round-trip with mocked pxr (create -> write -> read -> verify)

Run: python -m pytest tests/test_agent_state.py -v
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.memory import agent_state


# ═════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="synapse_agent_state_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def agent_usd_path(tmp_dir):
    return os.path.join(tmp_dir, "agent.usd")


# ═════════════════════════════════════════════════════════════════
# Helper Tests (pure logic, no pxr needed)
# ═════════════════════════════════════════════════════════════════

class TestSafePrimName:
    def test_alphanumeric_passthrough(self):
        assert agent_state._safe_prim_name("task_001") == "task_001"

    def test_special_chars_replaced(self):
        assert agent_state._safe_prim_name("my-task.v2") == "my_task_v2"

    def test_leading_digit_prefixed(self):
        assert agent_state._safe_prim_name("123abc") == "p_123abc"

    def test_empty_string(self):
        assert agent_state._safe_prim_name("") == "unnamed"

    def test_all_special_chars(self):
        result = agent_state._safe_prim_name("@#$%")
        assert result == "____"

    def test_spaces_replaced(self):
        assert agent_state._safe_prim_name("my task") == "my_task"


class TestCounterSuffix:
    def test_first_entry(self):
        parent = MagicMock()
        parent.IsValid.return_value = True
        parent.GetChildren.return_value = []
        assert agent_state._counter_suffix(parent, "decision_") == "decision_0000"

    def test_sequential_numbering(self):
        parent = MagicMock()
        parent.IsValid.return_value = True
        child0 = MagicMock()
        child0.GetName.return_value = "decision_0000"
        child1 = MagicMock()
        child1.GetName.return_value = "decision_0001"
        parent.GetChildren.return_value = [child0, child1]
        assert agent_state._counter_suffix(parent, "decision_") == "decision_0002"

    def test_invalid_parent(self):
        parent = MagicMock()
        parent.IsValid.return_value = False
        assert agent_state._counter_suffix(parent, "handoff_") == "handoff_0000"

    def test_mixed_prefixes_only_count_matching(self):
        parent = MagicMock()
        parent.IsValid.return_value = True
        c1 = MagicMock(); c1.GetName.return_value = "decision_0000"
        c2 = MagicMock(); c2.GetName.return_value = "handoff_0000"
        c3 = MagicMock(); c3.GetName.return_value = "decision_0001"
        parent.GetChildren.return_value = [c1, c2, c3]
        assert agent_state._counter_suffix(parent, "decision_") == "decision_0002"
        assert agent_state._counter_suffix(parent, "handoff_") == "handoff_0001"


# ═════════════════════════════════════════════════════════════════
# USDA Stub Tests (no pxr needed)
# ═════════════════════════════════════════════════════════════════

class TestUsdaStub:
    def test_stub_writes_valid_usda(self, agent_usd_path):
        agent_state._write_usda_stub(agent_usd_path)
        assert os.path.exists(agent_usd_path)

        with open(agent_usd_path, encoding="utf-8") as f:
            content = f.read()

        assert '#usda 1.0' in content
        assert f'"synapse:version" = "{agent_state.SCHEMA_VERSION}"' in content
        assert '"synapse:type" = "agent_state"' in content

    def test_stub_has_v2_prims(self, agent_usd_path):
        agent_state._write_usda_stub(agent_usd_path)

        with open(agent_usd_path, encoding="utf-8") as f:
            content = f.read()

        assert 'def Xform "agent"' in content
        assert 'synapse:status = "idle"' in content
        assert 'synapse:dispatched_agents' in content
        assert 'def Xform "integrity"' in content
        assert 'synapse:session_fidelity' in content
        assert 'synapse:operations_total' in content
        assert 'synapse:operations_verified' in content
        assert 'synapse:anchor_violations' in content
        assert 'def Xform "routing_log"' in content
        assert 'def Xform "handoff_chain"' in content
        assert 'def Xform "session_history"' in content
        assert 'def Xform "verification_log"' in content

    def test_stub_has_memory_hierarchy(self, agent_usd_path):
        agent_state._write_usda_stub(agent_usd_path)

        with open(agent_usd_path, encoding="utf-8") as f:
            content = f.read()

        assert 'def Xform "memory"' in content
        for sub in ("sessions", "decisions", "assets", "parameters", "wedges"):
            assert f'def Xform "{sub}"' in content

    def test_initialize_falls_back_to_stub(self, agent_usd_path):
        """Without pxr, initialize_agent_usd writes the stub."""
        assert not agent_state.PXR_AVAILABLE
        agent_state.initialize_agent_usd(agent_usd_path)
        assert os.path.exists(agent_usd_path)

        with open(agent_usd_path, encoding="utf-8") as f:
            content = f.read()
        assert '#usda 1.0' in content


# ═════════════════════════════════════════════════════════════════
# Graceful No-Op Tests (PXR_AVAILABLE=False)
# ═════════════════════════════════════════════════════════════════

class TestNoOpWithoutPxr:
    """All pxr-dependent functions should return gracefully when pxr is unavailable."""

    def test_create_task_noop(self, agent_usd_path):
        agent_state.create_task(agent_usd_path, "t1", "Test task")
        # Should not raise, should not create file

    def test_update_task_status_noop(self, agent_usd_path):
        agent_state.update_task_status(agent_usd_path, "t1", "completed")

    def test_suspend_all_tasks_noop(self, agent_usd_path):
        agent_state.suspend_all_tasks(agent_usd_path)

    def test_resume_task_noop(self, agent_usd_path):
        agent_state.resume_task(agent_usd_path, "t1")

    def test_abandon_task_noop(self, agent_usd_path):
        agent_state.abandon_task(agent_usd_path, "t1")

    def test_log_integrity_noop(self, agent_usd_path):
        agent_state.log_integrity(agent_usd_path, "create_node", "HANDS", 1.0, True)

    def test_get_integrity_defaults(self, agent_usd_path):
        result = agent_state.get_integrity(agent_usd_path)
        assert result["session_fidelity"] == 1.0
        assert result["operations_total"] == 0

    def test_log_routing_decision_noop(self, agent_usd_path):
        name = agent_state.log_routing_decision(agent_usd_path, "fp", "HANDS", "OBSERVER", "dense")
        assert name == ""

    def test_get_routing_log_empty(self, agent_usd_path):
        assert agent_state.get_routing_log(agent_usd_path) == []

    def test_log_handoff_noop(self, agent_usd_path):
        name = agent_state.log_handoff(agent_usd_path, "OBSERVER", "HANDS", "t1", 1.0)
        assert name == ""

    def test_get_handoff_chain_empty(self, agent_usd_path):
        assert agent_state.get_handoff_chain(agent_usd_path) == []

    def test_set_dispatched_agents_noop(self, agent_usd_path):
        agent_state.set_dispatched_agents(agent_usd_path, ["HANDS", "OBSERVER"])

    def test_get_dispatched_agents_empty(self, agent_usd_path):
        assert agent_state.get_dispatched_agents(agent_usd_path) == []

    def test_log_session_noop(self, agent_usd_path):
        agent_state.log_session(agent_usd_path, {"tasks_completed": 5})

    def test_write_verification_noop(self, agent_usd_path):
        agent_state.write_verification(agent_usd_path, "t1", "h1", "h2", ["check"], "pass")

    def test_migrate_to_v2_noop(self, agent_usd_path):
        assert agent_state.migrate_to_v2(agent_usd_path) is False

    def test_load_agent_state_defaults(self, tmp_dir):
        state = agent_state.load_agent_state(tmp_dir)
        assert state["status"] == "idle"
        assert state["version"] == agent_state.SCHEMA_VERSION
        assert state["dispatched_agents"] == []
        assert state["integrity"]["session_fidelity"] == 1.0
        assert state["routing_decisions"] == 0
        assert state["handoffs"] == 0


# ═════════════════════════════════════════════════════════════════
# Schema Version
# ═════════════════════════════════════════════════════════════════

class TestSchemaVersion:
    def test_version_is_2_0_0(self):
        assert agent_state.SCHEMA_VERSION == "2.0.0"

    def test_prev_version_is_0_1_0(self):
        assert agent_state._PREV_VERSION == "0.1.0"


# ═════════════════════════════════════════════════════════════════
# Mocked pxr Round-Trip Tests
# ═════════════════════════════════════════════════════════════════

class FakeAttribute:
    """Minimal USD attribute mock that stores a value."""
    def __init__(self, value=None):
        self._value = value

    def Set(self, value):
        self._value = value

    def Get(self):
        return self._value

    def __bool__(self):
        return True


class FakePrim:
    """Minimal USD prim mock with attribute storage."""
    def __init__(self, name=""):
        self._name = name
        self._attrs: dict[str, FakeAttribute] = {}
        self._children: dict[str, "FakePrim"] = {}
        self._valid = True

    def GetName(self):
        return self._name

    def IsValid(self):
        return self._valid

    def CreateAttribute(self, name, type_name):
        if name not in self._attrs:
            self._attrs[name] = FakeAttribute()
        return self._attrs[name]

    def GetAttribute(self, name):
        return self._attrs.get(name)

    def GetChildren(self):
        return list(self._children.values())

    def _add_child(self, name):
        child = FakePrim(name)
        self._children[name] = child
        return child


class FakeLayer:
    def __init__(self):
        self.customLayerData = {}

    def Save(self):
        pass

    def ExportToString(self):
        return "#usda 1.0\n"


class FakeStage:
    """Minimal USD stage mock that stores prims in a dict."""
    def __init__(self):
        self._prims: dict[str, FakePrim] = {}
        self._layer = FakeLayer()

    def DefinePrim(self, path, type_name="Xform"):
        if path not in self._prims:
            name = path.rsplit("/", 1)[-1]
            prim = FakePrim(name)
            self._prims[path] = prim
            # Register with parent
            parent_path = path.rsplit("/", 1)[0]
            if parent_path and parent_path in self._prims:
                self._prims[parent_path]._children[name] = prim
        return self._prims[path]

    def GetPrimAtPath(self, path):
        if path in self._prims:
            return self._prims[path]
        invalid = FakePrim()
        invalid._valid = False
        return invalid

    def GetRootLayer(self):
        return self._layer

    def SetDefaultPrim(self, prim):
        pass


# Shared stage registry so CreateNew/Open return the same stage for a path
_fake_stages: dict[str, FakeStage] = {}


def _fake_create_new(path):
    stage = FakeStage()
    _fake_stages[os.path.normpath(path)] = stage
    # Touch the file so os.path.exists works
    with open(path, "w", encoding="utf-8") as f:
        f.write("")
    return stage


def _fake_open(path):
    return _fake_stages.get(os.path.normpath(path), FakeStage())


class FakeSdf:
    class ValueTypeNames:
        String = "string"
        StringArray = "string[]"
        Int = "int"
        Float = "float"


class FakeVt:
    @staticmethod
    def StringArray(items=None):
        return list(items) if items else []


@pytest.fixture
def mock_pxr(tmp_dir):
    """Patch agent_state to use fake pxr objects."""
    _fake_stages.clear()

    fake_usd = MagicMock()
    fake_usd.Stage.CreateNew = _fake_create_new
    fake_usd.Stage.Open = _fake_open

    with patch.object(agent_state, "PXR_AVAILABLE", True), \
         patch.object(agent_state, "Usd", fake_usd), \
         patch.object(agent_state, "Sdf", FakeSdf), \
         patch.object(agent_state, "Vt", FakeVt):
        yield

    _fake_stages.clear()


class TestInitializeWithMockPxr:
    def test_creates_agent_prim(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]

        agent = stage.GetPrimAtPath("/SYNAPSE/agent")
        assert agent.IsValid()
        assert agent.GetAttribute("synapse:status").Get() == "idle"
        assert agent.GetAttribute("synapse:version").Get() == "2.0.0"

    def test_creates_integrity_prim(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]

        integrity = stage.GetPrimAtPath("/SYNAPSE/agent/integrity")
        assert integrity.IsValid()
        assert integrity.GetAttribute("synapse:session_fidelity").Get() == 1.0
        assert integrity.GetAttribute("synapse:operations_total").Get() == 0
        assert integrity.GetAttribute("synapse:operations_verified").Get() == 0
        assert integrity.GetAttribute("synapse:anchor_violations").Get() == 0

    def test_creates_routing_log(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        assert stage.GetPrimAtPath("/SYNAPSE/agent/routing_log").IsValid()

    def test_creates_handoff_chain(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        assert stage.GetPrimAtPath("/SYNAPSE/agent/handoff_chain").IsValid()

    def test_creates_memory_hierarchy(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]

        assert stage.GetPrimAtPath("/SYNAPSE/memory").IsValid()
        for sub in ("sessions", "decisions", "assets", "parameters", "wedges"):
            assert stage.GetPrimAtPath(f"/SYNAPSE/memory/{sub}").IsValid()

    def test_dispatched_agents_initially_empty(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]

        attr = stage.GetPrimAtPath("/SYNAPSE/agent").GetAttribute("synapse:dispatched_agents")
        assert attr.Get() == []


class TestTasksWithMockPxr:
    def test_create_and_read_task(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.create_task(agent_usd_path, "build_rig", "Build character rig")

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        task = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/build_rig")
        assert task.IsValid()
        assert task.GetAttribute("synapse:task_id").Get() == "build_rig"
        assert task.GetAttribute("synapse:description").Get() == "Build character rig"
        assert task.GetAttribute("synapse:status").Get() == "pending"

    def test_update_task_status(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.create_task(agent_usd_path, "t1", "Test")
        agent_state.update_task_status(agent_usd_path, "t1", "completed",
                                       verification={"result": "pass"})

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        task = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/t1")
        assert task.GetAttribute("synapse:status").Get() == "completed"
        assert task.GetAttribute("synapse:verificationResult").Get() == "pass"

    def test_suspend_all_tasks(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.create_task(agent_usd_path, "t1", "Task 1")
        agent_state.create_task(agent_usd_path, "t2", "Task 2")
        agent_state.update_task_status(agent_usd_path, "t1", "executing")

        agent_state.suspend_all_tasks(agent_usd_path)

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        t1 = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/t1")
        t2 = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/t2")
        assert t1.GetAttribute("synapse:status").Get() == "suspended"
        assert t2.GetAttribute("synapse:status").Get() == "suspended"

    def test_resume_task(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.create_task(agent_usd_path, "t1", "Task 1")
        agent_state.suspend_all_tasks(agent_usd_path)
        agent_state.resume_task(agent_usd_path, "t1")

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        assert stage.GetPrimAtPath("/SYNAPSE/agent/tasks/t1").GetAttribute("synapse:status").Get() == "pending"

    def test_abandon_task(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.create_task(agent_usd_path, "t1", "Task 1")
        agent_state.abandon_task(agent_usd_path, "t1")

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        assert stage.GetPrimAtPath("/SYNAPSE/agent/tasks/t1").GetAttribute("synapse:status").Get() == "abandoned"

    def test_update_nonexistent_task(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        # Should not raise
        agent_state.update_task_status(agent_usd_path, "nonexistent", "completed")

    def test_task_id_with_special_chars(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.create_task(agent_usd_path, "my-task.v2", "Special chars")

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        task = stage.GetPrimAtPath("/SYNAPSE/agent/tasks/my_task_v2")
        assert task.IsValid()
        assert task.GetAttribute("synapse:task_id").Get() == "my-task.v2"


class TestIntegrityWithMockPxr:
    def test_log_perfect_integrity(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_integrity(
            agent_usd_path, "create_node", "HANDS",
            fidelity=1.0, anchors_hold=True,
            scene_hash_before="aabb", scene_hash_after="ccdd", delta_hash="eeff"
        )

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        integrity = stage.GetPrimAtPath("/SYNAPSE/agent/integrity")
        assert integrity.GetAttribute("synapse:operations_total").Get() == 1
        assert integrity.GetAttribute("synapse:operations_verified").Get() == 1
        assert integrity.GetAttribute("synapse:anchor_violations").Get() == 0
        assert integrity.GetAttribute("synapse:session_fidelity").Get() == 1.0

    def test_log_degraded_fidelity(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_integrity(agent_usd_path, "op1", "HANDS", 1.0, True)
        agent_state.log_integrity(agent_usd_path, "op2", "HANDS", 0.5, False)

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        integrity = stage.GetPrimAtPath("/SYNAPSE/agent/integrity")
        assert integrity.GetAttribute("synapse:operations_total").Get() == 2
        assert integrity.GetAttribute("synapse:operations_verified").Get() == 1
        assert integrity.GetAttribute("synapse:anchor_violations").Get() == 1
        assert integrity.GetAttribute("synapse:session_fidelity").Get() == 0.5

    def test_session_fidelity_tracks_minimum(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_integrity(agent_usd_path, "op1", "HANDS", 0.8, True)
        agent_state.log_integrity(agent_usd_path, "op2", "HANDS", 0.3, True)
        agent_state.log_integrity(agent_usd_path, "op3", "HANDS", 0.9, True)

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        fid = stage.GetPrimAtPath("/SYNAPSE/agent/integrity").GetAttribute("synapse:session_fidelity").Get()
        assert fid == 0.3  # Minimum, not latest

    def test_get_integrity_roundtrip(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_integrity(agent_usd_path, "op1", "HANDS", 0.9, True)
        agent_state.log_integrity(agent_usd_path, "op2", "BRAINSTEM", 1.0, True)

        result = agent_state.get_integrity(agent_usd_path)
        assert result["operations_total"] == 2
        assert result["operations_verified"] == 1  # Only op2 had fidelity 1.0
        assert result["session_fidelity"] == 0.9
        assert result["anchor_violations"] == 0


class TestRoutingLogWithMockPxr:
    def test_log_single_decision(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        name = agent_state.log_routing_decision(
            agent_usd_path,
            fingerprint="generation|moderate|materialx+usd|normal",
            primary_agent="HANDS",
            advisory_agent="OBSERVER",
            method="dense"
        )
        assert name == "decision_0000"

    def test_log_multiple_decisions_sequential(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        n1 = agent_state.log_routing_decision(agent_usd_path, "fp1", "HANDS", "OBSERVER", "dense")
        n2 = agent_state.log_routing_decision(agent_usd_path, "fp2", "SUBSTRATE", None, "fast_path")
        assert n1 == "decision_0000"
        assert n2 == "decision_0001"

    def test_get_routing_log_roundtrip(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_routing_decision(agent_usd_path, "fp1", "HANDS", "OBSERVER", "dense")
        agent_state.log_routing_decision(agent_usd_path, "fp2", "SUBSTRATE", None, "fast_path")

        log = agent_state.get_routing_log(agent_usd_path)
        assert len(log) == 2
        assert log[0]["fingerprint"] == "fp1"
        assert log[0]["primary_agent"] == "HANDS"
        assert log[0]["advisory_agent"] == "OBSERVER"
        assert log[0]["method"] == "dense"
        assert log[1]["fingerprint"] == "fp2"
        assert log[1]["advisory_agent"] == ""  # None -> ""

    def test_no_advisory_stored_as_empty(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_routing_decision(agent_usd_path, "fp", "INTEGRATOR", None, "fast_path")

        log = agent_state.get_routing_log(agent_usd_path)
        assert log[0]["advisory_agent"] == ""


class TestHandoffChainWithMockPxr:
    def test_log_single_handoff(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        name = agent_state.log_handoff(agent_usd_path, "OBSERVER", "HANDS", "create_mtlx", 1.0)
        assert name == "handoff_0000"

    def test_log_multiple_handoffs(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        n1 = agent_state.log_handoff(agent_usd_path, "OBSERVER", "HANDS", "t1", 1.0)
        n2 = agent_state.log_handoff(agent_usd_path, "HANDS", "CONDUCTOR", "t2", 1.0)
        assert n1 == "handoff_0000"
        assert n2 == "handoff_0001"

    def test_get_handoff_chain_roundtrip(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_handoff(agent_usd_path, "OBSERVER", "HANDS", "create_shader", 1.0)
        agent_state.log_handoff(agent_usd_path, "HANDS", "CONDUCTOR", "submit_render", 0.95)

        chain = agent_state.get_handoff_chain(agent_usd_path)
        assert len(chain) == 2
        assert chain[0]["from_agent"] == "OBSERVER"
        assert chain[0]["to_agent"] == "HANDS"
        assert chain[0]["task_id"] == "create_shader"
        assert chain[0]["fidelity_at_handoff"] == 1.0
        assert chain[1]["from_agent"] == "HANDS"
        assert chain[1]["fidelity_at_handoff"] == 0.95


class TestDispatchedAgentsWithMockPxr:
    def test_set_and_get_agents(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.set_dispatched_agents(agent_usd_path, ["HANDS", "OBSERVER"])

        agents = agent_state.get_dispatched_agents(agent_usd_path)
        assert agents == ["HANDS", "OBSERVER"]

    def test_set_empty_clears_agents(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.set_dispatched_agents(agent_usd_path, ["HANDS"])
        agent_state.set_dispatched_agents(agent_usd_path, [])

        agents = agent_state.get_dispatched_agents(agent_usd_path)
        assert agents == []

    def test_get_agents_from_fresh_stage(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agents = agent_state.get_dispatched_agents(agent_usd_path)
        assert agents == []


class TestLoadAgentStateWithMockPxr:
    def test_load_fresh_state(self, tmp_dir, mock_pxr):
        agent_usd_path = os.path.join(tmp_dir, "agent.usd")
        agent_state.initialize_agent_usd(agent_usd_path)

        state = agent_state.load_agent_state(tmp_dir)
        assert state["status"] == "idle"
        assert state["version"] == "2.0.0"
        assert state["dispatched_agents"] == []
        assert state["integrity"]["session_fidelity"] == 1.0
        assert state["integrity"]["operations_total"] == 0
        assert state["routing_decisions"] == 0
        assert state["handoffs"] == 0
        assert not state["has_suspended_tasks"]

    def test_load_state_with_data(self, tmp_dir, mock_pxr):
        path = os.path.join(tmp_dir, "agent.usd")
        agent_state.initialize_agent_usd(path)

        # Add some data
        agent_state.create_task(path, "t1", "Task 1")
        agent_state.suspend_all_tasks(path)
        agent_state.log_integrity(path, "op1", "HANDS", 0.8, True)
        agent_state.log_routing_decision(path, "fp1", "HANDS", "OBSERVER", "dense")
        agent_state.log_handoff(path, "OBSERVER", "HANDS", "t1", 1.0)
        agent_state.set_dispatched_agents(path, ["HANDS", "BRAINSTEM"])

        state = agent_state.load_agent_state(tmp_dir)
        assert state["has_suspended_tasks"] is True
        assert state["suspended_count"] == 1
        assert state["suspended_tasks"][0]["id"] == "t1"
        assert state["dispatched_agents"] == ["HANDS", "BRAINSTEM"]
        assert state["integrity"]["operations_total"] == 1
        assert state["integrity"]["session_fidelity"] == 0.8
        assert state["routing_decisions"] == 1
        assert state["handoffs"] == 1

    def test_load_nonexistent_returns_defaults(self, tmp_dir, mock_pxr):
        state = agent_state.load_agent_state(os.path.join(tmp_dir, "no_such_dir"))
        assert state["status"] == "idle"
        assert state["version"] == "2.0.0"


class TestMigrationWithMockPxr:
    def _make_v1_stage(self, path, mock_pxr):
        """Create a v0.1.0 stage (old schema)."""
        agent_state.initialize_agent_usd(path)
        stage = _fake_stages[os.path.normpath(path)]
        # Downgrade version to simulate v0.1.0
        stage.GetPrimAtPath("/SYNAPSE/agent").GetAttribute("synapse:version").Set("0.1.0")
        # Remove v2 prims to simulate old schema
        # (In our fake, we just need the version check to trigger migration)
        return stage

    def test_migrate_bumps_version(self, agent_usd_path, mock_pxr):
        self._make_v1_stage(agent_usd_path, mock_pxr)
        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        stage.GetPrimAtPath("/SYNAPSE/agent").GetAttribute("synapse:version").Set("0.1.0")

        result = agent_state.migrate_to_v2(agent_usd_path)
        assert result is True

        version = stage.GetPrimAtPath("/SYNAPSE/agent").GetAttribute("synapse:version").Get()
        assert version == "2.0.0"

    def test_migrate_already_v2_is_noop(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        result = agent_state.migrate_to_v2(agent_usd_path)
        assert result is False

    def test_migrate_nonexistent_file(self, tmp_dir, mock_pxr):
        result = agent_state.migrate_to_v2(os.path.join(tmp_dir, "nonexistent.usd"))
        assert result is False


class TestSessionHistoryWithMockPxr:
    def test_log_session_creates_prim(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.log_session(agent_usd_path, {
            "start_time": "2026-03-06T10:00:00Z",
            "end_time": "2026-03-06T11:00:00Z",
            "tasks_completed": 5,
            "tasks_failed": 1,
            "tasks_suspended": 0,
            "summary_text": "Completed lighting setup",
        })

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        history = stage.GetPrimAtPath("/SYNAPSE/agent/session_history")
        children = history.GetChildren()
        assert len(children) == 1
        child = children[0]
        assert child.GetAttribute("synapse:tasksCompleted").Get() == 5
        assert child.GetAttribute("synapse:summary").Get() == "Completed lighting setup"


class TestVerificationLogWithMockPxr:
    def test_write_verification_creates_prim(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        agent_state.write_verification(
            agent_usd_path, "t1", "hash_before", "hash_after",
            ["composition_valid", "fidelity_check"], "pass"
        )

        stage = _fake_stages[os.path.normpath(agent_usd_path)]
        log = stage.GetPrimAtPath("/SYNAPSE/agent/verification_log")
        children = log.GetChildren()
        assert len(children) == 1
        child = children[0]
        assert child.GetAttribute("synapse:taskId").Get() == "t1"
        assert child.GetAttribute("synapse:result").Get() == "pass"
