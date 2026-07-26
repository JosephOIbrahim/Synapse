"""Tests for render_diagnostics.py — issue-to-remedy mapping and memory integration.

Mock-based — no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: ensure synapse package structure is importable
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parent.parent / "python"

for mod_name, mod_path in [
    ("synapse", _root / "synapse"),
    ("synapse.core", _root / "synapse" / "core"),
    ("synapse.server", _root / "synapse" / "server"),
    ("synapse.memory", _root / "synapse" / "memory"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.determinism", _root / "synapse" / "core" / "determinism.py"),
    ("synapse.memory.models", _root / "synapse" / "memory" / "models.py"),
    ("synapse.server.render_diagnostics", _root / "synapse" / "server" / "render_diagnostics.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

diag_mod = sys.modules["synapse.server.render_diagnostics"]

Remedy = diag_mod.Remedy
ISSUE_REMEDIES = diag_mod.ISSUE_REMEDIES
classify_scene = diag_mod.classify_scene
diagnose_issues = diag_mod.diagnose_issues
query_known_fixes = diag_mod.query_known_fixes
record_fix_outcome = diag_mod.record_fix_outcome


# ---------------------------------------------------------------------------
# Tests: Remedy.compute_new_value
# ---------------------------------------------------------------------------

class TestRemedy:
    def test_multiply(self):
        r = Remedy("test", "desc", "samples", "multiply", 2.0, max_value=256)
        assert r.compute_new_value(32) == 64

    def test_multiply_capped(self):
        r = Remedy("test", "desc", "samples", "multiply", 2.0, max_value=256)
        assert r.compute_new_value(200) == 256

    def test_add(self):
        r = Remedy("test", "desc", "exposure", "add", 2.0, max_value=15.0)
        assert r.compute_new_value(3.0) == 5.0

    def test_add_negative(self):
        r = Remedy("test", "desc", "exposure", "add", -1.0)
        assert r.compute_new_value(5.0) == 4.0

    def test_set(self):
        r = Remedy("test", "desc", "depth", "set", 4)
        assert r.compute_new_value(10) == 4

    def test_unknown_fn(self):
        r = Remedy("test", "desc", "x", "unknown", 99)
        assert r.compute_new_value(5.0) == 5.0


# ---------------------------------------------------------------------------
# Tests: ISSUE_REMEDIES table
# ---------------------------------------------------------------------------

class TestIssueRemedies:
    def test_saturation_has_remedies(self):
        assert "saturation" in ISSUE_REMEDIES
        assert len(ISSUE_REMEDIES["saturation"]) >= 2

    def test_black_frame_has_remedy(self):
        assert "black_frame" in ISSUE_REMEDIES
        assert len(ISSUE_REMEDIES["black_frame"]) >= 1

    def test_nan_check_has_remedy(self):
        assert "nan_check" in ISSUE_REMEDIES

    def test_clipping_has_remedy(self):
        assert "clipping" in ISSUE_REMEDIES

    def test_underexposure_has_remedy(self):
        assert "underexposure" in ISSUE_REMEDIES

    def test_all_remedies_have_required_fields(self):
        for issue_type, remedies in sorted(ISSUE_REMEDIES.items()):
            for r in remedies:
                assert r.issue_type == issue_type
                assert r.parm_name
                assert r.adjust_fn in ("multiply", "add", "set")
                assert 0 <= r.confidence <= 1


# ---------------------------------------------------------------------------
# Tests: classify_scene
# ---------------------------------------------------------------------------

class TestClassifyScene:
    def test_empty_stage(self):
        tags = classify_scene({"prims": []})
        assert tags == []

    def test_interior_keywords(self):
        prims = [
            {"path": "/World/room/walls", "type": "Mesh"},
            {"path": "/World/interior_light", "type": "RectLight"},
        ]
        tags = classify_scene({"prims": prims})
        assert "interior" in tags

    def test_has_environment(self):
        prims = [
            {"path": "/lights/dome_light", "type": "DomeLight"},
        ]
        tags = classify_scene({"prims": prims})
        assert "has_environment" in tags

    def test_has_volumes(self):
        prims = [
            {"path": "/fx/smoke_volume", "type": "Volume"},
        ]
        tags = classify_scene({"prims": prims})
        assert "has_volumes" in tags

    def test_many_lights(self):
        prims = [
            {"path": f"/lights/light_{i}", "type": "RectLight"}
            for i in range(6)
        ]
        tags = classify_scene({"prims": prims})
        assert "many_lights" in tags

    def test_high_poly(self):
        tags = classify_scene({"prims": [], "prim_count": 100000})
        assert "high_poly" in tags

    def test_outdoor_keywords(self):
        prims = [
            {"path": "/World/exterior/terrain", "type": "Mesh"},
        ]
        tags = classify_scene({"prims": prims})
        assert "outdoor" in tags

    def test_tags_sorted(self):
        """He2025: output is deterministic and sorted."""
        prims = [
            {"path": "/interior/room", "type": "Mesh"},
            {"path": "/lights/dome_light", "type": "DomeLight"},
        ]
        tags = classify_scene({"prims": prims})
        assert tags == sorted(tags)


# ---------------------------------------------------------------------------
# Tests: diagnose_issues
# ---------------------------------------------------------------------------

class TestDiagnoseIssues:
    def test_all_passed(self):
        val = {"valid": True, "checks": {"black_frame": {"passed": True}}}
        result = diagnose_issues(val)
        assert result == []

    def test_single_failure(self):
        val = {
            "valid": False,
            "checks": {
                "saturation": {"passed": False, "saturation_pct": 5.2},
                "black_frame": {"passed": True},
            },
        }
        result = diagnose_issues(val)
        assert len(result) == 1
        issue_type, remedy, mem = result[0]
        assert issue_type == "saturation"
        assert remedy.parm_name == "pathtracedsamples"
        assert mem is None

    def test_multiple_failures(self):
        val = {
            "valid": False,
            "checks": {
                "saturation": {"passed": False},
                "clipping": {"passed": False},
            },
        }
        result = diagnose_issues(val)
        assert len(result) == 2

    def test_sorted_by_priority(self):
        val = {
            "valid": False,
            "checks": {
                "clipping": {"passed": False},
                "saturation": {"passed": False},
            },
        }
        result = diagnose_issues(val)
        # Both have priority 10 for top remedy; sorted deterministically
        assert len(result) == 2

    def test_unknown_issue_type(self):
        val = {
            "valid": False,
            "checks": {
                "unknown_check": {"passed": False},
            },
        }
        result = diagnose_issues(val)
        assert result == []

    def test_with_memory_match(self):
        mock_memory = MagicMock()
        mock_result = MagicMock()
        mock_result.memory.content = "**Parameter:** pathtracedsamples = 128"
        mock_result.memory.tags = ["render_fix", "success", "saturation"]
        mock_result.memory.id = "mem-123"
        mock_result.score = 0.9
        mock_memory.store.search.return_value = [mock_result]

        val = {
            "valid": False,
            "checks": {"saturation": {"passed": False}},
        }
        result = diagnose_issues(val, memory=mock_memory, scene_tags=["interior"])
        assert len(result) == 1
        issue_type, remedy, mem_match = result[0]
        assert mem_match is not None
        assert mem_match["memory_id"] == "mem-123"


# ---------------------------------------------------------------------------
# Tests: query_known_fixes
# ---------------------------------------------------------------------------

class TestQueryKnownFixes:
    def test_no_memory(self):
        assert query_known_fixes(None, "saturation", []) == []

    def test_memory_search(self):
        mock_memory = MagicMock()
        mock_result = MagicMock()
        mock_result.memory.content = "fix content"
        mock_result.memory.tags = ["render_fix", "success", "saturation"]
        mock_result.memory.id = "fix-1"
        mock_result.score = 0.85
        mock_memory.store.search.return_value = [mock_result]

        fixes = query_known_fixes(mock_memory, "saturation", ["interior"])
        assert len(fixes) == 1
        assert fixes[0]["score"] == 0.85

    def test_memory_search_filters_non_success(self):
        mock_memory = MagicMock()
        mock_result = MagicMock()
        mock_result.memory.content = "failed fix"
        mock_result.memory.tags = ["render_fix", "failure", "saturation"]
        mock_result.memory.id = "fix-2"
        mock_result.score = 0.9
        mock_memory.store.search.return_value = [mock_result]

        fixes = query_known_fixes(mock_memory, "saturation", [])
        assert len(fixes) == 0  # Filtered out because no "success" tag

    def test_memory_exception_handled(self):
        mock_memory = MagicMock()
        mock_memory.store.search.side_effect = RuntimeError("db error")
        fixes = query_known_fixes(mock_memory, "saturation", [])
        assert fixes == []


# ---------------------------------------------------------------------------
# Tests: record_fix_outcome
# ---------------------------------------------------------------------------

class TestRecordFixOutcome:
    def test_no_memory(self):
        # Should not raise
        record_fix_outcome(None, "saturation", Remedy("sat", "desc", "samples", "set", 128), True, [], {})

    def test_records_success(self):
        mock_memory = MagicMock()
        remedy = Remedy("saturation", "Double samples", "pathtracedsamples", "multiply", 2.0)
        record_fix_outcome(
            mock_memory,
            "saturation",
            remedy,
            success=True,
            scene_tags=["interior"],
            settings_applied={"pathtracedsamples": 128},
            frame=42,
        )
        mock_memory.add.assert_called_once()
        call_kwargs = mock_memory.add.call_args[1]
        assert "success" in call_kwargs["tags"]
        assert "saturation" in call_kwargs["tags"]
        assert call_kwargs["source"] == "auto"

    def test_records_failure(self):
        mock_memory = MagicMock()
        remedy = Remedy("saturation", "Double samples", "pathtracedsamples", "multiply", 2.0)
        record_fix_outcome(
            mock_memory,
            "saturation",
            remedy,
            success=False,
            scene_tags=[],
            settings_applied={},
        )
        call_kwargs = mock_memory.add.call_args[1]
        assert "failure" in call_kwargs["tags"]

    def test_memory_exception_handled(self):
        mock_memory = MagicMock()
        mock_memory.add.side_effect = RuntimeError("write error")
        # Should not raise
        record_fix_outcome(
            mock_memory, "saturation",
            Remedy("sat", "desc", "x", "set", 1), True, [], {},
        )
