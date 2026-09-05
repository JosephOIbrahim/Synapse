"""Schema controls run under pytest or unittest, using no host emulation."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from synapse.blocks import fixtures
from synapse.recipes import canon
from synapse.recipes.contracts import (
    ActionId, Availability, DEMO_PHRASES, PermissionCategory, RecipeSpec, REQUIRED_CHECKS,
)
from synapse.recipes.spec import (
    RecipeSpecError, catalog_digest, catalog_ports, recipe_spec_from_dict,
    spec_to_fixture_v1, validate_recipe_spec,
)

ROOT = Path(__file__).resolve().parents[1]


def definition():
    return json.loads((ROOT / "fixtures/solaris.spine.json").read_text(encoding="utf-8"))


def node(raw, role):
    return next(n for n in raw["nodes"] if n["role"] == role)


def action(raw, aid):
    return next(a for a in raw["actions"] if a["action_id"] == aid.value)


def rehash(raw):
    # Controls repair identity hashes so structural failures cannot accidentally
    # be caught by the generic digest mismatch instead of the claimed wall.
    raw["semantic_digest"] = canon.semantic_digest(raw)
    raw["layout_digest"] = canon.layout_digest(raw)
    return raw


class SpecTests(unittest.TestCase):
    def reject(self, raw, reason):
        with self.assertRaisesRegex(RecipeSpecError, reason):
            recipe_spec_from_dict(rehash(raw))

    def test_valid_spine_loads_blocked_without_claiming_golden(self):
        spec = fixtures.load_recipe_spec("solaris.spine")
        self.assertIsInstance(spec, RecipeSpec)
        self.assertIs(spec.availability, Availability.BLOCKED)
        self.assertIs(fixtures.validate_recipe_spec(spec), Availability.BLOCKED)
        self.assertIn("PENDING_HUMAN", spec.availability_reason)
        self.assertEqual(dict(spec.golden_reference), {
            "status": "PENDING_HUMAN", "hip": None,
            "reference_render": None, "dependency_record": None,
        })

    def test_absent_golden_key_rejected(self):
        raw = definition()
        del raw["golden_reference"]
        self.reject(raw, "golden_reference key is required")

    def test_incomplete_golden_record_rejected(self):
        raw = definition()
        del raw["golden_reference"]["dependency_record"]
        self.reject(raw, "golden_reference is required")

    def test_pending_cannot_claim_artifacts(self):
        raw = definition()
        raw["golden_reference"]["hip"] = "pretend.hip"
        self.reject(raw, "PENDING_HUMAN cannot claim")

    def test_capture_metadata_cannot_claim_ready(self):
        raw = definition()
        raw["golden_reference"] = {"status": "CAPTURED", "hip": "scene.hip",
                                   "reference_render": "scene.exr", "dependency_record": {"assets": []}}
        spec = recipe_spec_from_dict(raw)
        self.assertIs(spec.availability, Availability.EXPERIMENTAL)
        self.assertIn("NOT_RUN", spec.availability_reason)

    def test_wrong_supported_build_rejected(self):
        raw = definition()
        raw["supported_build"] = "22.0.399"
        self.reject(raw, "wrong supported_build")

    def test_unresolved_type_alias_rejected(self):
        raw = definition()
        node(raw, "key_light")["type"] = "light::unresolved"
        self.reject(raw, "unresolved type alias")

    def test_grid_cannot_replace_plane(self):
        raw = definition()
        node(raw, "ground")["type"] = "grid"
        self.reject(raw, "unresolved type alias|wrong baseline type")

    def test_each_required_subgraph_is_required(self):
        for role in ("hero", "ground", "hero_shader", "hero_material", "ground_shader", "ground_material",
                     "materials", "bindings", "dome_light", "key_light", "camera", "render_settings", "render", "output"):
            with self.subTest(role=role):
                raw = definition()
                raw["nodes"].remove(node(raw, role))
                self.reject(raw, "missing subgraphs")

    def test_nested_parent_cannot_be_flattened(self):
        raw = definition()
        node(raw, "hero_shader")["parent_id"] = None
        self.reject(raw, "wrong parent")

    def test_empty_required_material_definition_rejected(self):
        raw = definition()
        node(raw, "hero_shader")["parms"] = {}
        self.reject(raw, "empty required material/parameter")

    def test_empty_library_rejected(self):
        raw = definition()
        node(raw, "materials")["parms"]["materials"]["value"] = 0
        self.reject(raw, "empty required material definitions")

    def test_binding_wrong_hero_target_rejected(self):
        raw = definition()
        node(raw, "bindings")["parms"]["primpattern1"]["value"] = "/World/wrong"
        self.reject(raw, "invalid material binding")

    def test_material_wrong_output_rejected(self):
        raw = definition()
        node(raw, "materials")["parms"]["matnode1"]["value"] = "missing_output"
        self.reject(raw, "material VOP target")

    def test_material_binding_cannot_target_a_pattern(self):
        raw = definition()
        node(raw, "materials")["parms"]["matpath1"]["value"] = "/materials/*"
        node(raw, "bindings")["parms"]["matspecpath1"]["value"] = "/materials/*"
        self.reject(raw, "material path must be an explicit prim path")

    def test_missing_material_surface_wire_rejected(self):
        raw = definition()
        raw["connections"] = [w for w in raw["connections"] if w["dst_id"] != "hero_material"]
        self.reject(raw, "incomplete material or render branch")

    def test_missing_render_branch_rejected(self):
        raw = definition()
        raw["connections"] = [w for w in raw["connections"] if w["dst_id"] != "render"]
        self.reject(raw, "incomplete material or render branch")

    def test_catalog_vop_ports_are_independently_resolved(self):
        raw = definition()
        catalog = json.loads((ROOT / "rag/catalog/h22.0.400/Vop.json").read_text(encoding="utf-8"))
        by_id = {n["id"]: n for n in raw["nodes"]}
        for wire in raw["connections"]:
            src, dst = by_id[wire["src_id"]], by_id[wire["dst_id"]]
            if src["category"] != "Vop":
                continue
            source_signature = catalog["types"][src["type"]]["wire_signature"]
            dest_signature = catalog["types"][dst["type"]]["wire_signature"]
            # The oracle is the live-harvested signature, not fixture port zero.
            self.assertEqual(source_signature["output_names"].index(wire["src_port"]), wire["src_output"])
            self.assertEqual(dest_signature["input_names"].index(wire["dst_port"]), wire["dst_input"])
            self.assertEqual(source_signature["output_data_types"][wire["src_output"]],
                             dest_signature["input_data_types"][wire["dst_input"]])

    def test_absent_vop_signature_refuses_publication(self):
        with self.assertRaisesRegex(RecipeSpecError, "no instantiated catalog signature"):
            catalog_ports({"max_inputs": 10, "parms": [{"name": "surfaceshader"}]})

    def test_missing_recorded_ports_rejected(self):
        raw = definition()
        del node(raw, "hero_shader")["ports"]
        self.reject(raw, "unresolved VOP ports")

    def test_fabricated_port_name_rejected(self):
        raw = definition()
        node(raw, "hero_shader")["ports"]["outputs"][0]["name"] = "surface_guess"
        self.reject(raw, "unresolved VOP ports")

    def test_fabricated_port_index_rejected(self):
        raw = definition()
        next(w for w in raw["connections"] if w["dst_id"] == "hero_material")["dst_input"] = 99
        self.reject(raw, "unresolved VOP ports")

    def test_fabricated_wire_port_name_rejected(self):
        raw = definition()
        next(w for w in raw["connections"] if w["dst_id"] == "hero_material")["dst_port"] = "guess"
        self.reject(raw, "unresolved VOP ports")

    def test_wrong_vop_data_type_rejected(self):
        raw = definition()
        wire = next(w for w in raw["connections"] if w["dst_id"] == "hero_material")
        ports = node(raw, "hero_material")["ports"]["inputs"]
        port = next(p for p in ports if p["data_type"] == "displacement")
        wire["dst_input"], wire["dst_port"] = port["index"], port["name"]
        self.reject(raw, "incompatible data types")

    def test_duplicate_destination_rejected(self):
        raw = definition()
        raw["connections"].append(deepcopy(raw["connections"][0]))
        self.reject(raw, "duplicate destination input")

    def test_catalog_digest_pins_actual_bytes(self):
        path = ROOT / "rag/catalog/h22.0.400/Lop.json"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        spec = fixtures.load_recipe_spec("solaris.spine")
        self.assertEqual(spec.catalog_digest, actual)
        self.assertEqual(catalog_digest(path), actual)
        self.assertNotEqual(actual, json.loads(path.read_bytes())["blake2b"])

    def test_catalog_byte_change_detected(self):
        original = Path.read_bytes
        def changed(path):
            data = original(path)
            return data + b"\n" if path.name == "Lop.json" else data
        with patch.object(Path, "read_bytes", changed):
            self.reject(definition(), "catalog_digest mismatch: Lop")

    def test_vop_digest_change_detected(self):
        raw = definition()
        raw["presentation"]["vop_catalog_digest"] = "0" * 64
        self.reject(raw, "catalog_digest mismatch: Vop")

    def test_canonicalizer_change_detected(self):
        raw = definition()
        raw["presentation"]["canonicalizer_digest"] = "0" * 64
        self.reject(raw, "canonicalizer digest/version")

    def test_stale_graph_digest_rejected(self):
        raw = definition()
        node(raw, "hero")["parms"]["radius"]["value"] += 0.25
        with self.assertRaisesRegex(RecipeSpecError, "semantic_digest mismatch"):
            recipe_spec_from_dict(raw)

    def test_stale_layout_digest_rejected(self):
        raw = definition()
        node(raw, "hero")["position"][0] += 0.25
        with self.assertRaisesRegex(RecipeSpecError, "layout_digest mismatch"):
            recipe_spec_from_dict(raw)

    def test_actions_import_frozen_contract(self):
        spec = fixtures.load_recipe_spec("solaris.spine")
        self.assertEqual({a.action_id for a in spec.actions}, set(ActionId))
        for item in spec.actions:
            self.assertEqual(item.required_checks, REQUIRED_CHECKS[item.action_id])
            self.assertEqual(item.phrases, DEMO_PHRASES[item.action_id])
            if item.action_id == ActionId.RENDER:
                self.assertIs(item.permission, PermissionCategory.APPROVE)

    def test_missing_required_check_rejected(self):
        raw = definition()
        action(raw, ActionId.RENDER)["required_checks"].pop()
        self.reject(raw, "required_checks mismatch")

    def test_render_cannot_lower_permission(self):
        raw = definition()
        action(raw, ActionId.RENDER)["permission"] = "review"
        self.reject(raw, "permission mismatch")

    def test_engine_cannot_expand_to_xpu(self):
        raw = definition()
        next(s for s in action(raw, ActionId.RENDER)["slots"] if s["key"] == "engine")["enum"].append("xpu")
        self.reject(raw, "one pinned engine enum")

    def test_nan_and_boolean_slot_bounds_rejected(self):
        for value in (float("nan"), True, None):
            with self.subTest(value=value):
                raw = definition()
                action(raw, ActionId.LIGHT)["slots"][0]["max"] = value
                self.reject(raw, "finite slot bounds")

    def test_wrong_field_binding_rejected(self):
        raw = definition()
        action(raw, ActionId.MATERIAL)["slots"][0]["binding"] = "ground_shader.base_color"
        self.reject(raw, "slot binding/type mismatch")

    def test_color_bounds_not_relaxed(self):
        raw = definition()
        action(raw, ActionId.MATERIAL)["slots"][0]["max"] = 2
        self.reject(raw, "color bounds must be 0..1")

    def test_resolution_presets_are_bounded_tuples(self):
        raw = definition()
        raw["presentation"]["resolution_presets"]["64x64"] = [100000, 100000]
        self.reject(raw, "resolution preset must be a bounded int2")

    def test_untyped_parameter_rejected(self):
        raw = definition()
        node(raw, "hero")["parms"]["radius"] = 1
        self.reject(raw, "typed parameter required")

    def test_unresolved_parameter_rejected(self):
        raw = definition()
        node(raw, "hero")["parms"]["invented"] = {"type": "float", "value": 1.0}
        self.reject(raw, "unresolved parameter")

    def test_loaded_definition_is_deeply_immutable(self):
        raw = definition()
        spec = recipe_spec_from_dict(raw)
        with self.assertRaises(TypeError):
            spec.nodes[0]["parms"]["primpath"]["value"] = "tampered"
        raw["nodes"][0]["parms"]["primpath"]["value"] = "changed original"
        self.assertNotEqual(raw["nodes"][0]["parms"]["primpath"]["value"], spec.nodes[0]["parms"]["primpath"]["value"])

    def test_direct_malformed_seam_object_raises_spec_error(self):
        spec = fixtures.load_recipe_spec("solaris.spine")
        with self.assertRaisesRegex(RecipeSpecError, "missing required fields"):
            validate_recipe_spec(replace(spec, nodes=({},)))

    def test_outer_adapter_preserves_graph_and_retains_nested_contract(self):
        spec = fixtures.load_recipe_spec("solaris.spine")
        fx = spec_to_fixture_v1(spec)
        fixtures.validate_fixture(fx)
        outer = {n["id"] for n in spec.nodes if n["parent_id"] is None}
        self.assertEqual({name for name, _ in fixtures.declared_nodes(fx)}, outer)
        expected = {(w["dst_id"], w["dst_input"], w["src_id"]) for w in spec.connections if w["src_id"] in outer}
        self.assertEqual({tuple(w) for w in fx["wires"]}, expected)
        self.assertEqual({n["id"] for n in fx["recipe_subgraphs"]["nodes"]}, {n["id"] for n in spec.nodes} - outer)
        self.assertEqual(fx["recipe_availability"], "BLOCKED")
        self.assertTrue(fx["recipe_contract_only"])
        positions = {n["name"]: i for i, n in enumerate(fx["nodes"])}
        self.assertTrue(all(positions[src] < positions[dst] for dst, _, src in fx["wires"]))

    def test_adapter_refuses_expression_loss(self):
        raw = definition()
        node(raw, "hero")["parms"]["radius"]["expression"] = {"language": "hscript", "text": "$F"}
        spec = recipe_spec_from_dict(rehash(raw))
        with self.assertRaisesRegex(RecipeSpecError, "cannot represent expressions"):
            spec_to_fixture_v1(spec)

    def test_v1_loader_cannot_execute_contract_only_v2(self):
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_fixture("solaris.spine")

    def test_v1_file_and_existing_function_outputs_unchanged(self):
        # Read HEAD's v1 source and fixture as an independent backward-
        # compatibility oracle, without creating another worktree or module.
        old_code = subprocess.check_output(["git", "show", "83ec6330:python/synapse/blocks/fixtures.py"], cwd=ROOT).decode("utf-8")
        old_bytes = subprocess.check_output(["git", "show", "83ec6330:fixtures/solaris.basic.json"], cwd=ROOT)
        actual = (ROOT / "fixtures/solaris.basic.json").read_bytes()
        self.assertEqual(actual.replace(b"\r\n", b"\n"), old_bytes.replace(b"\r\n", b"\n"))
        namespace = {"__file__": str(ROOT / "python/synapse/blocks/fixtures.py"), "__name__": "baseline_fixtures"}
        exec(compile(old_code, "HEAD:blocks/fixtures.py", "exec"), namespace)
        current = fixtures.load_fixture("solaris.basic")
        baseline = namespace["load_fixture"]("solaris.basic")
        self.assertEqual(current, baseline)
        for name in ("validate_fixture", "declared_nodes", "declared_wires", "box_name_for"):
            self.assertEqual(getattr(fixtures, name)(current), namespace[name](baseline), name)


def prove_mutations():
    """Opt-in producer: deliberately break guards in memory and watch tests red.

    Run ``python tests/test_recipe_spec.py --prove-mutations``. Patches restore
    immediately; no production file, catalog or host module is modified.
    """
    import io
    from synapse.recipes import spec as module
    from test_recipe_spec_canon import CanonTests

    original_require = module._require
    cases = [
        ("ignore supported-build guard", "wrong supported_build", SpecTests("test_wrong_supported_build_rejected")),
        ("ignore actual Lop byte digest", "catalog_digest mismatch: Lop", SpecTests("test_catalog_byte_change_detected")),
        ("ignore pending-golden honesty", "PENDING_HUMAN cannot claim", SpecTests("test_pending_cannot_claim_artifacts")),
        ("ignore VOP wire identity", "unresolved VOP ports: connection", SpecTests("test_fabricated_wire_port_name_rejected")),
        ("ignore binding target equality", "invalid material binding", SpecTests("test_binding_wrong_hero_target_rejected")),
        ("ignore material prim-path validity", "material path must be an explicit", SpecTests("test_material_binding_cannot_target_a_pattern")),
        ("ignore required topology", "missing subgraphs: incomplete", SpecTests("test_missing_render_branch_rejected")),
    ]
    results = []
    for name, prefix, test in cases:
        def bypass(condition, reason, prefix=prefix):
            return original_require(condition or reason.startswith(prefix), reason)
        with patch.object(module, "_require", bypass):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([test]))
        results.append({"mutation": name, "tests": result.testsRun,
                        "failures": len(result.failures), "errors": len(result.errors),
                        "caught": len(result.failures) == 1 and not result.errors})
    for field in ("semantic_digest", "layout_digest"):
        with patch.object(canon, field, lambda *args, **kwargs: "constant"):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([
                CanonTests("test_layout_and_semantic_independence")]))
        results.append({"mutation": field + " returns constant", "tests": result.testsRun,
                        "failures": len(result.failures), "errors": len(result.errors),
                        "caught": len(result.failures) == 1 and not result.errors})
    print(json.dumps({"mutation_controls": results}, indent=2, sort_keys=True))
    return all(result["caught"] for result in results)


if __name__ == "__main__":
    import sys
    if "--prove-mutations" in sys.argv:
        raise SystemExit(0 if prove_mutations() else 1)
    unittest.main()
