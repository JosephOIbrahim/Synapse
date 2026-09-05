"""Identity controls derived from single-field mutations, not fixture hashes."""
from copy import deepcopy

import unittest
from unittest.mock import patch

from synapse.blocks import canonical as c3
from synapse.recipes import canon


def graph():
    return {"nodes": [
        {"id": "a", "parent_id": None, "category": "Lop", "type": "sphere",
         "parms": {"label": {"type": "str", "value": "2026-09-04T12:00:00 anon:artist"}},
         "expressions": {}, "flags": {"display": False}, "position": [0, 0]},
        {"id": "b", "parent_id": None, "category": "Lop", "type": "null",
         "parms": {}, "expressions": {}, "flags": {"display": True}, "position": [0, -1]},
    ], "connections": [{"src_id": "a", "src_output": 0, "dst_id": "b", "dst_input": 0}]}


def context():
    return canon.stage_canonicalization_record(
        frame=1, time=0, load_rules=[["/", "all"]],
        layers=[{"identifier": "root.usda", "content_digest": "root-content"}],
        resolver_identity={"plugin": "test-resolver", "context": "test-context"},
        dependency_identity={},
    )


class CanonTests(unittest.TestCase):
    def test_layout_and_semantic_independence(self):
        original = graph()
        moved = deepcopy(original)
        moved["nodes"][0]["position"][0] += 1
        assert canon.semantic_digest(moved) == canon.semantic_digest(original)
        assert canon.layout_digest(moved) != canon.layout_digest(original)
        edited = deepcopy(original)
        edited["nodes"][0]["parms"]["label"]["value"] += " changed"
        assert canon.semantic_digest(edited) != canon.semantic_digest(original)
        assert canon.layout_digest(edited) == canon.layout_digest(original)

    def test_each_authored_dimension_changes_identity_0(self):
        key, value = ('type', 'plane')
        original = graph()
        changed = deepcopy(original)
        changed["nodes"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_each_authored_dimension_changes_identity_1(self):
        key, value = ('parent_id', 'b')
        original = graph()
        changed = deepcopy(original)
        changed["nodes"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_each_authored_dimension_changes_identity_2(self):
        key, value = ('category', 'Vop')
        original = graph()
        changed = deepcopy(original)
        changed["nodes"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_each_authored_dimension_changes_identity_3(self):
        key, value = ('expressions', {'x': {'language': 'hscript', 'text': '$F'}})
        original = graph()
        changed = deepcopy(original)
        changed["nodes"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_each_authored_dimension_changes_identity_4(self):
        key, value = ('flags', {'display': True})
        original = graph()
        changed = deepcopy(original)
        changed["nodes"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_each_authored_dimension_changes_identity_5(self):
        key, value = ('ports', {'output_names': ['different']})
        original = graph()
        changed = deepcopy(original)
        changed["nodes"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_wire_identity_changes_digest_0(self):
        key, value = ('src_output', 1)
        original = graph()
        changed = deepcopy(original)
        changed["connections"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_wire_identity_changes_digest_1(self):
        key, value = ('dst_input', 1)
        original = graph()
        changed = deepcopy(original)
        changed["connections"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_wire_identity_changes_digest_2(self):
        key, value = ('src_id', 'b')
        original = graph()
        changed = deepcopy(original)
        changed["connections"][0][key] = value
        assert canon.semantic_digest(changed) != canon.semantic_digest(original)

    def test_record_order_is_not_authored_state(self):
        original = graph()
        reordered = deepcopy(original)
        reordered["nodes"].reverse()
        assert canon.semantic_digest(original) == canon.semantic_digest(reordered)
        assert canon.layout_digest(original) == canon.layout_digest(reordered)

    def test_tiny_numeric_difference_and_expression_text_are_preserved(self):
        original = graph()
        original["nodes"][0]["parms"] = {"x": {"type": "float", "value": 1.0}}
        changed = deepcopy(original)
        changed["nodes"][0]["parms"]["x"]["value"] += 1e-14
        assert canon.semantic_digest(original) != canon.semantic_digest(changed)

    def test_only_explicit_path_parameters_receive_approved_tokens(self):
        original = graph()
        original["nodes"][0]["parms"]["file"] = {"type": "path", "value": "C:/scene/render/a.exr"}
        portable = deepcopy(original)
        portable["nodes"][0]["parms"]["file"]["value"] = "$HIP/render/a.exr"
        assert canon.semantic_digest(original, path_tokens={"$HIP": "C:/scene"}) == canon.semantic_digest(portable)
        original["nodes"][0]["parms"]["file"]["value"] = "C:/scenery/render/a.exr"
        assert canon.semantic_digest(original, path_tokens={"$HIP": "C:/scene"}) != canon.semantic_digest(portable)
        with self.assertRaisesRegex(ValueError, "unapproved"):
            canon.semantic_digest(original, path_tokens={"$ARBITRARY": "C:/scene"})
        with self.assertRaisesRegex(ValueError, "absolute"):
            canon.semantic_digest(original, path_tokens={"$OS": "sphere"})

    def test_stage_reuses_c3_and_records_all_context(self):
        calls = []
        def observe(text, env):
            calls.append((text, env))
            return "normalized by existing c3"
        record = context()
        with patch.object(c3, "canonicalize_usda", observe):
            result = canon.canonicalize_stage("stage text", record, path_tokens={})
        assert calls == [("stage text", {})]
        assert result["context"] == record
        assert result["canonical_text"] == "normalized by existing c3"
        for key in ("frame", "time", "load_rules", "layers", "resolver_identity", "dependency_identity"):
            changed = deepcopy(record)
            changed[key] = "different"
            assert canon.digest(changed) != canon.digest(record)

    def test_stage_missing_identity_and_nonfinite_authored_state_reject(self):
        with self.assertRaisesRegex(ValueError, "resolver"):
            canon.stage_canonicalization_record(frame=1, time=0, load_rules=[], layers=["root"],
                                                resolver_identity={}, dependency_identity={})
        with self.assertRaises(ValueError):
            canon.digest({"authored": float("nan")})

    def test_new_modules_import_without_houdini_in_fresh_process(self):
        # The repository conftest installs its pre-existing suite fake. A fresh
        # subprocess checks the production module without relying on that resident.
        import os
        import subprocess
        import sys
        from pathlib import Path
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "python"),
                   PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-c",
            "import sys; from synapse.recipes import canon, spec; "
            "from synapse.blocks.fixtures import load_recipe_spec; load_recipe_spec('solaris.spine'); "
            "assert 'hou' not in sys.modules and 'pxr' not in sys.modules"],
            env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
