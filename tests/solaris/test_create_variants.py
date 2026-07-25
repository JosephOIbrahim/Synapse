"""
Tests for synapse_solaris_create_variants — RELAY-SOLARIS Phase 3
"""

import pytest

from synapse.mcp.tool_impls.solaris.create_variants import validate, plan, _SOURCE_PATTERN


class TestCreateVariantsValidation:

    def test_rejects_missing_component_path(self):
        with pytest.raises(Exception, match="component_path is required"):
            validate({"variant_type": "material", "variants": [{"name": "a"}, {"name": "b"}]})

    def test_rejects_invalid_variant_type(self):
        with pytest.raises(Exception, match="variant_type"):
            validate({
                "component_path": "/stage/comp",
                "variant_type": "color",
                "variants": [{"name": "a"}, {"name": "b"}],
            })

    def test_rejects_single_variant(self):
        with pytest.raises(Exception, match="At least 2"):
            validate({
                "component_path": "/stage/comp",
                "variant_type": "material",
                "variants": [{"name": "only_one"}],
            })

    def test_rejects_variant_without_name(self):
        with pytest.raises(Exception, match="name"):
            validate({
                "component_path": "/stage/comp",
                "variant_type": "material",
                "variants": [{"name": "a"}, {}],
            })

    def test_accepts_valid_material_variants(self):
        validate({
            "component_path": "/stage/comp",
            "variant_type": "material",
            "variants": [{"name": "red"}, {"name": "blue"}],
        })

    def test_accepts_valid_geometry_variants(self):
        validate({
            "component_path": "/stage/comp",
            "variant_type": "geometry",
            "variants": [{"name": "lod0"}, {"name": "lod1"}],
        })


class TestCreateVariantsPlan:

    def test_material_plan_duplicates_component_material(self):
        ops = plan({
            "component_path": "/stage/comp",
            "variant_type": "material",
            "variants": [{"name": "red"}, {"name": "blue"}],
        })
        dup_ops = [o for o in ops if o.get("op") == "duplicate_component_material"]
        assert len(dup_ops) == 2
        assert dup_ops[0]["name"] == "red"
        assert dup_ops[1]["name"] == "blue"

    def test_geometry_plan_creates_geometry_variants_node(self):
        ops = plan({
            "component_path": "/stage/comp",
            "variant_type": "geometry",
            "variants": [{"name": "lod0"}, {"name": "lod1"}],
        })
        geo_var_ops = [o for o in ops if o.get("node_type") == "componentgeometryvariants"]
        assert len(geo_var_ops) == 1

    def test_plan_includes_explore_by_default(self):
        ops = plan({
            "component_path": "/stage/comp",
            "variant_type": "material",
            "variants": [{"name": "a"}, {"name": "b"}],
        })
        explore_ops = [o for o in ops if o.get("node_type") == "explorevariants"]
        assert len(explore_ops) == 1

    def test_plan_skips_explore_when_disabled(self):
        ops = plan({
            "component_path": "/stage/comp",
            "variant_type": "material",
            "variants": [{"name": "a"}, {"name": "b"}],
            "add_explore_node": False,
        })
        explore_ops = [o for o in ops if o.get("node_type") == "explorevariants"]
        assert len(explore_ops) == 0

    def test_plan_includes_provenance(self):
        ops = plan({
            "component_path": "/stage/comp",
            "variant_type": "material",
            "variants": [{"name": "a"}, {"name": "b"}],
        })
        prov = [o for o in ops if o.get("op") == "stamp_provenance"]
        assert prov[0]["source_pattern"] == _SOURCE_PATTERN


class TestF6HonestStatus:
    """F6/Ruling 14 — source-level pin: no bare `except Exception: pass` may
    stand between a failed build step and a status of "created".

    This is a pure-Python assertion on purpose: the defect is a control-flow
    shape, not a host behaviour, so it does not need Houdini to be falsifiable.
    The live counterpart is
    `test_live_wiring.py::test_f6_create_variants_status_is_honest_live`.
    """

    def _execute_source(self):
        import ast
        import inspect
        import textwrap

        from synapse.mcp.tool_impls.solaris import create_variants as mod

        src = textwrap.dedent(inspect.getsource(mod.execute))
        return ast.parse(src)

    def test_execute_swallows_no_exception_silently(self):
        import ast

        tree = self._execute_source()
        swallowed = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler)
            and all(isinstance(stmt, ast.Pass) for stmt in node.body)
        ]
        assert not swallowed, (
            "bare `except Exception: pass` in create_variants.execute — a "
            "swallowed failure followed by status='created' is a lie (Law 3)"
        )
