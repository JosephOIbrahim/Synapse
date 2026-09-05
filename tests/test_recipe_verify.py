"""P1-P6 controls using detached observations, never a planted hou module."""
import copy
import hashlib
import json
import os
from dataclasses import replace

import pytest

from synapse.recipes.contracts import (
    ActionId, ActionSpec, CheckId, CheckStatus, PermissionCategory,
    RecipeInstance, RecipeSpec, RecoveryVerdict, SlotSchema,
)
from synapse.recipes import verify as v


def node(node_id, node_type, parent=None, **parms):
    return {"id": node_id, "parent_id": parent, "category": "Vop" if parent else "Lop",
            "type": node_type, "parms": parms, "flags": {}}


def scene():
    nodes = (node("material", "materiallibrary"),
             node("shader", "mtlxstandard_surface", "material", base_color=[0.5, 0.2, 0.1]),
             node("key", "light", exposure=0.0),
             node("settings", "karmarendersettings"), node("render", "usdrender_rop"))
    wire = {"src_id": "settings", "src_output": 0, "dst_id": "render", "dst_input": 0}
    actions = (
        ActionSpec(ActionId.BUILD, (), (CheckId.P1_GRAPH,), "graph", PermissionCategory.REVIEW),
        ActionSpec(ActionId.LIGHT, (SlotSchema("exposure", "float", "key.exposure"),),
                   (CheckId.P6_LOCALITY,), "field", PermissionCategory.REVIEW),
        ActionSpec(ActionId.MATERIAL, (SlotSchema("color", "color3", "shader.base_color"),),
                   (CheckId.P6_LOCALITY,), "field", PermissionCategory.REVIEW),
        ActionSpec(ActionId.RENDER, (), (CheckId.P3_RENDER_READY,), "render", PermissionCategory.APPROVE),
    )
    expectations = {"stage_node_id": "settings", "render_settings_path": "/Render/intended",
                    "render_input_connections": [wire],
                    "expected_prims": [{"path": "/hero", "type": "Sphere", "material": "/materials/hero"},
                                       {"path": "/ground", "type": "Mesh", "material": "/materials/ground"}]}
    spec = RecipeSpec("solaris.spine", "1", "2", "22.0.400", "catalog", "c3",
                      "semantic", "layout", {"verification": expectations},
                      nodes, (wire,), actions)
    owned = {n["id"]: "/stage/" + n["id"] for n in nodes}
    owned["shader"] = "/stage/material/shader"
    instance = RecipeInstance("instance", spec.recipe_id, spec.version, owned, {}, 0, "before")
    return instance, spec


def graph_observation(instance, spec):
    return {"available": True, "complete": True,
            "nodes": {n["id"]: {**copy.deepcopy(n), "path": instance.owned_node_ids[n["id"]]}
                      for n in spec.nodes},
            "connections": copy.deepcopy(list(spec.connections))}


def usd_observation():
    return {"available": True, "complete": True, "live": True, "stage": "/stage/settings",
            "prims": {"/hero": {"valid": True, "active": True, "defined": True,
                               "type": "Sphere", "bound_material": "/materials/hero", "material_valid": True, "surface_source_valid": True},
                      "/ground": {"valid": True, "active": True, "defined": True,
                                  "type": "Mesh", "bound_material": "/materials/ground", "material_valid": True, "surface_source_valid": True}}}


def readiness(instance, spec):
    branch = spec.golden_reference["verification"]["render_input_connections"]
    return {"available": True, "complete": True, "live": True, "graph": graph_observation(instance, spec), "assessment": {
        "ready": True,
        "clauses": {k: "pass" for k in v.RenderReadinessVerifier.required_clauses},
        "details": {"render_settings_path": "/Render/intended",
                    "camera_targets": ["/camera"],
                    "render_input_branch": {"expected": copy.deepcopy(branch),
                                            "observed": copy.deepcopy(branch), "complete": True}}}}


def run(verifier, instance, spec, **context):
    result = verifier.run(verifier.check_id, instance, spec, **context)
    json.dumps(result.evidence, allow_nan=False)
    if result.status != CheckStatus.PASS:
        assert result.reason
    return result


def test_imported_checkout_is_this_worktree():
    from pathlib import Path
    assert Path(v.__file__).resolve().parents[3] == Path(__file__).resolve().parents[1]


def test_p1_graph_includes_nested_shader_and_ports():
    instance, spec = scene()
    observation = graph_observation(instance, spec)
    assert run(v.GraphVerifier(), instance, spec, observation=observation).status == CheckStatus.PASS
    observation["nodes"].pop("shader")
    assert run(v.GraphVerifier(), instance, spec, observation=observation).status == CheckStatus.FAIL


@pytest.mark.parametrize("field,value", [
    ("type", "other::2.0"), ("category", "Sop"), ("parent_id", "key"),
    ("flags", {"display": True}), ("parms", {"base_color": [0.2, 0.2, 0.2]}),
    ("path", "/stage/artist/shader"),
])
def test_p1_detects_semantic_node_mutations(field, value):
    instance, spec = scene()
    observation = graph_observation(instance, spec)
    observation["nodes"]["shader"][field] = value
    assert run(v.GraphVerifier(), instance, spec, observation=observation).status == CheckStatus.FAIL


@pytest.mark.parametrize("field", ["src_output", "dst_input"])
def test_p1_ports_are_not_just_node_pairs(field):
    instance, spec = scene()
    observation = graph_observation(instance, spec)
    observation["connections"][0][field] += 1
    assert run(v.GraphVerifier(), instance, spec, observation=observation).status == CheckStatus.FAIL


def test_p1_second_action_keeps_committed_color_and_checks_exposure():
    instance, spec = scene()
    instance.committed_slots["color"] = [0.1, 0.1, 0.8]
    observation = graph_observation(instance, spec)
    observation["nodes"]["shader"]["parms"]["base_color"] = [0.1, 0.1, 0.8]
    observation["nodes"]["key"]["parms"]["exposure"] = 2
    assert run(v.GraphVerifier(), instance, spec, observation=observation,
               action=ActionId.LIGHT, slots={"exposure": 2}).status == CheckStatus.PASS
    observation["nodes"]["shader"]["parms"]["base_color"] = [0.5, 0.2, 0.1]
    assert run(v.GraphVerifier(), instance, spec, observation=observation,
               action=ActionId.LIGHT, slots={"exposure": 2}).status == CheckStatus.FAIL


def test_p1_owned_alias_and_extra_connection_fail():
    instance, spec = scene()
    observation = graph_observation(instance, spec)
    instance.owned_node_ids["key"] = instance.owned_node_ids["settings"]
    observation["connections"].append({"src_id": "artist", "src_output": 0, "dst_id": "key", "dst_input": 0})
    result = run(v.GraphVerifier(), instance, spec, observation=observation)
    assert result.status == CheckStatus.FAIL
    assert "alias" in result.reason


def test_p2_expected_material_must_resolve_to_intended():
    instance, spec = scene()
    observation = usd_observation()
    assert run(v.USDVerifier(), instance, spec, observation=observation).status == CheckStatus.PASS
    observation["prims"]["/hero"]["bound_material"] = "/materials/wrong"
    assert run(v.USDVerifier(), instance, spec, observation=observation).status == CheckStatus.FAIL


@pytest.mark.parametrize("field,value", [("active", False), ("defined", False), ("valid", False),
                                         ("type", "Cube"), ("material_valid", False), ("surface_source_valid", False)])
def test_p2_active_defined_schema_and_material(field, value):
    instance, spec = scene()
    observation = usd_observation()
    observation["prims"]["/hero"][field] = value
    assert run(v.USDVerifier(), instance, spec, observation=observation).status == CheckStatus.FAIL


def test_p2_missing_expected_schema_fails():
    instance, spec = scene()
    spec.golden_reference["verification"]["expected_prims"][0]["schemas"] = ["MaterialBindingAPI"]
    assert run(v.USDVerifier(), instance, spec, observation=usd_observation()).status == CheckStatus.FAIL


@pytest.mark.parametrize("verifier", [v.USDVerifier, v.RenderReadinessVerifier])
def test_t9_stage_unavailable_unknown_preserves_diagnosis(verifier):
    instance, spec = scene()
    observation = {"available": False, "reason": "stage LOP has not cooked: /stage/settings"}
    result = run(verifier(), instance, spec, observation=observation)
    assert result.status == CheckStatus.UNKNOWN
    assert "/stage/settings" in result.reason
    assert result.evidence["diagnosis"] == observation["reason"]


def test_p3_positive_and_t7_branch_removed_with_valid_camera():
    instance, spec = scene()
    observation = readiness(instance, spec)
    assert run(v.RenderReadinessVerifier(), instance, spec, observation=observation).status == CheckStatus.PASS
    observation["assessment"]["details"]["render_input_branch"]["observed"] = []
    # Deliberately leave both the camera and cached ready=True/branch=pass.
    result = run(v.RenderReadinessVerifier(), instance, spec, observation=observation)
    assert result.status == CheckStatus.FAIL
    assert "render_input_branch" in result.reason


@pytest.mark.parametrize("clause", v.RenderReadinessVerifier.required_clauses)
def test_p3_no_required_clause_can_be_omitted(clause):
    instance, spec = scene()
    observation = readiness(instance, spec)
    observation["assessment"]["clauses"].pop(clause)
    assert run(v.RenderReadinessVerifier(), instance, spec, observation=observation).status == CheckStatus.UNKNOWN


def test_p3_wrong_settings_path_fails_and_missing_capture_unknown():
    instance, spec = scene()
    observation = readiness(instance, spec)
    observation["assessment"]["details"]["render_settings_path"] = "/Render/first"
    assert run(v.RenderReadinessVerifier(), instance, spec, observation=observation).status == CheckStatus.FAIL
    spec = replace(spec, golden_reference={})
    assert run(v.RenderReadinessVerifier(), instance, spec, observation=observation).status == CheckStatus.UNKNOWN


def composition(instance):
    return {"available": True, "complete": True, "composition_errors": [],
            "node_errors": {p: [] for p in instance.owned_node_ids.values()},
            "dependencies_checked": True, "missing_assets": [], "payloads": []}


def test_p4_reports_assets_payloads_and_errors_separately():
    instance, spec = scene()
    observation = composition(instance)
    assert run(v.CompositionVerifier(), instance, spec, observation=observation).status == CheckStatus.PASS
    observation["missing_assets"] = ["missing.tx"]
    observation["payloads"] = [{"path": "/asset", "loaded": False}]
    observation["composition_errors"] = ["unresolved reference"]
    observation["node_errors"][instance.owned_node_ids["key"]] = ["node cook error"]
    result = run(v.CompositionVerifier(), instance, spec, observation=observation)
    assert result.status == CheckStatus.FAIL
    assert result.evidence["missing_assets"] == ["missing.tx"]
    assert result.evidence["unloaded_payloads"] == ["/asset"]
    assert result.evidence["composition_errors"] == ["unresolved reference"]


@pytest.mark.parametrize("key", ["dependencies_checked", "payloads", "missing_assets", "node_errors"])
def test_p4_unmeasured_channel_unknown(key):
    instance, spec = scene()
    observation = composition(instance)
    observation.pop(key)
    assert run(v.CompositionVerifier(), instance, spec, observation=observation).status == CheckStatus.UNKNOWN


def images(tmp_path):
    instance, spec = scene()
    # Byte files are synthetic decoder inputs, not fake EXR claims.
    output = tmp_path / "current.synthetic"
    reference = tmp_path / "reference.synthetic"
    output.write_bytes(b"current pixels")
    reference.write_bytes(b"reference pixels")
    identity = v.file_identity(output)
    width, height = 64, 64
    rgb = [[[0.5, 0.1, 0.1] if y < height//2 else [0.2, 0.3, 0.2]
            for x in range(width)] for y in range(height)]
    frame = {"width": width, "height": height, "channels": ["R", "G", "B"], "pixels": rgb}
    spec.golden_reference["verification"]["image"] = {
        "reference_path": str(reference), "reference_sha256": v.file_identity(reference)["sha256"],
        "regions": [{"name": "hero", "bounds": [0, 0, width, height//2]},
                    {"name": "ground", "bounds": [0, height//2, width, height]}],
    }
    decoded = {str(output): copy.deepcopy(frame), str(reference): copy.deepcopy(frame)}
    job = {"job_id": "job", "terminal": True, "state": "SUCCEEDED", "exit_code": 0,
           "started_ns": identity["mtime_ns"] - 1, "output_path": str(output),
           "resolution": [width, height], "samples": 1}
    return instance, spec, {"render_job": job, "output_path": str(output),
                            "prior_artifacts": [], "image_reader": lambda path: decoded[str(path)]}, decoded


def test_p5_measures_reference_regions_from_pixels(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.PASS
    hero = result.evidence["regions"][0]
    assert hero["reference"]["pixels"] == 64 * (64//2)
    assert hero["observed"]["coverage"] == 1.0
    assert hero["observed"]["mean_rgb"] == pytest.approx([0.5, 0.1, 0.1])


def test_t8_old_output_rejected_on_identity_independent_of_content_reader(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    context["prior_artifacts"] = [v.file_identity(context["output_path"])]
    context["image_reader"] = lambda _: pytest.fail("stale file must be rejected before decoding")
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.FAIL
    assert result.evidence["stale_matches"][0]["same_file"] is True


def test_t8_copied_old_content_rejected_even_with_new_file_identity(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    previous = tmp_path / "previous.synthetic"
    previous.write_bytes((tmp_path / "current.synthetic").read_bytes())
    old = v.file_identity(previous)
    old["mtime_ns"] -= 1000000
    context["prior_artifacts"] = [old]
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.FAIL
    assert result.evidence["stale_matches"][0]["same_content"]
    assert not result.evidence["stale_matches"][0]["same_file"]


def test_t8_fresh_nonblack_wrong_scene_rejected_on_content_alone(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    decoded[context["output_path"]]["pixels"] = [[[0.1, 0.1, 0.9]] * 64 for _ in range(64)]
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.FAIL
    assert result.evidence["stale_matches"] == []
    assert "reference content mismatch" in result.reason


def test_p5_dark_missing_hero_fails_coverage(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    for row in decoded[context["output_path"]]["pixels"][:32]:
        row[:] = [[0.0, 0.0, 0.0]] * 64
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.FAIL
    assert result.evidence["regions"][0]["coverage_delta"] == 1.0


@pytest.mark.parametrize("mutation,reason", [
    ("nan", "non-finite"), ("dimensions", "dimensions"), ("channels", "channels"),
    ("old_mtime", "predates"), ("samples", "samples"), ("failed_job", "did not succeed"),
])
def test_p5_rejects_invalid_image_or_job(tmp_path, mutation, reason):
    instance, spec, context, decoded = images(tmp_path)
    frame = decoded[context["output_path"]]
    if mutation == "nan":
        frame["pixels"][0][0][0] = float("nan")
    elif mutation == "dimensions":
        frame["width"] = 32
    elif mutation == "channels":
        frame["channels"] = ["R", "G", "B", "A"]
    elif mutation == "old_mtime":
        context["render_job"]["started_ns"] += 1000000
    elif mutation == "samples":
        context["render_job"]["samples"] = 4
    else:
        context["render_job"].update(state="FAILED", exit_code=1)
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.FAIL
    assert reason in result.reason


@pytest.mark.parametrize("missing", ["render_job", "prior_artifacts", "output_path"])
def test_p5_missing_measurement_unknown(tmp_path, missing):
    instance, spec, context, decoded = images(tmp_path)
    context.pop(missing)
    assert run(v.ImageSmokeVerifier(), instance, spec, **context).status == CheckStatus.UNKNOWN


def test_p5_inflight_job_unknown_and_no_read(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    context["render_job"]["terminal"] = False
    context["image_reader"] = lambda _: pytest.fail("in-flight job cannot be verified")
    assert run(v.ImageSmokeVerifier(), instance, spec, **context).status == CheckStatus.UNKNOWN


def test_p5_missing_reader_unknown_retains_reason(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    def unavailable(_):
        raise v.EvidenceUnavailable("OpenImageIO not installed")
    context["image_reader"] = unavailable
    result = run(v.ImageSmokeVerifier(), instance, spec, **context)
    assert result.status == CheckStatus.UNKNOWN
    assert "OpenImageIO" in result.reason


def test_p5_file_modified_during_read_unknown(tmp_path):
    instance, spec, context, decoded = images(tmp_path)
    reader = context["image_reader"]
    def mutate(path):
        if str(path) == context["output_path"]:
            with open(path, "ab") as handle:
                handle.write(b"changed")
        return reader(path)
    context["image_reader"] = mutate
    assert run(v.ImageSmokeVerifier(), instance, spec, **context).status == CheckStatus.UNKNOWN


def snapshots(instance, spec):
    nodes = {n["id"]: {**copy.deepcopy(n), "path": instance.owned_node_ids[n["id"]]} for n in spec.nodes}
    nodes["artist"] = node("artist", "null", authored_opinion="preserve")
    return nodes, v.semantic_snapshot(nodes, spec.connections, scope="/stage + artist USD opinions", complete=True)


def test_p6_field_locality_and_second_edit_preserve_first():
    instance, spec = scene()
    nodes, before = snapshots(instance, spec)
    nodes["shader"]["parms"]["base_color"] = [0.1, 0.1, 0.8]
    middle = v.semantic_snapshot(nodes, spec.connections, scope=before["scope"], complete=True)
    first = run(v.LocalityVerifier(), instance, spec, before=before, after=middle,
                action=ActionId.MATERIAL, slots={"color": [0.1, 0.1, 0.8]}, recovery=RecoveryVerdict.NOT_NEEDED)
    assert first.status == CheckStatus.PASS
    instance.committed_slots["color"] = [0.1, 0.1, 0.8]
    nodes["key"]["parms"]["exposure"] = 2.0
    after = v.semantic_snapshot(nodes, spec.connections, scope=before["scope"], complete=True)
    second = run(v.LocalityVerifier(), instance, spec, before=middle, after=after,
                 action=ActionId.LIGHT, slots={"exposure": 2}, recovery=RecoveryVerdict.NOT_NEEDED)
    assert second.status == CheckStatus.PASS
    assert second.evidence["changed"] == ["node/key/parms/exposure"]


def test_p6_artist_change_fails_and_rollback_residue_measured():
    instance, spec = scene()
    nodes, before = snapshots(instance, spec)
    nodes["key"]["parms"]["exposure"] = 1.0
    nodes["artist"]["parms"]["authored_opinion"] = "clobbered"
    after = v.semantic_snapshot(nodes, spec.connections, scope=before["scope"], complete=True)
    result = run(v.LocalityVerifier(), instance, spec, before=before, after=after, rollback=after,
                 action=ActionId.LIGHT, slots={"exposure": 1}, recovery=RecoveryVerdict.RESIDUE, mutation_terminal=True)
    assert result.status == CheckStatus.FAIL
    assert "node/artist/parms/authored_opinion" in result.evidence["forbidden"]
    assert "node/artist/parms/authored_opinion" in result.evidence["rollback_residue"]


def test_p6_clean_recovery_measures_restore_without_claiming_operation_success():
    instance, spec = scene()
    nodes, before = snapshots(instance, spec)
    nodes["key"]["parms"]["exposure"] = 1.0
    after = v.semantic_snapshot(nodes, spec.connections, scope=before["scope"], complete=True)
    result = run(v.LocalityVerifier(), instance, spec, before=before, after=after, rollback=before,
                 action=ActionId.LIGHT, slots={"exposure": 1}, recovery=RecoveryVerdict.RESTORED, mutation_terminal=True)
    assert result.status == CheckStatus.PASS
    assert result.evidence["rollback_residue"] == []
    # Only P6 passed: this says nothing about the failed operation's receipt.


def test_p6_unknown_recovery_or_forged_digest_unknown():
    instance, spec = scene()
    nodes, before = snapshots(instance, spec)
    assert run(v.LocalityVerifier(), instance, spec, before=before, after=before,
               action=ActionId.LIGHT, slots={}, recovery=RecoveryVerdict.UNKNOWN).status == CheckStatus.UNKNOWN
    forged = {**before, "digest": "fake"}
    assert run(v.LocalityVerifier(), instance, spec, before=before, after=forged,
               action=ActionId.LIGHT, slots={}, recovery=RecoveryVerdict.NOT_NEEDED).status == CheckStatus.UNKNOWN


def test_p6_build_additions_and_second_build_noop():
    instance, spec = scene()
    artist = {"artist": node("artist", "null", opinion="keep")}
    before = v.semantic_snapshot(artist, [], scope="/stage", complete=True)
    nodes = {**artist, **{n["id"]: {**n, "path": instance.owned_node_ids[n["id"]]} for n in spec.nodes}}
    after = v.semantic_snapshot(nodes, spec.connections, scope="/stage", complete=True)
    for pre in (before, after):
        assert run(v.LocalityVerifier(), instance, spec, before=pre, after=after,
                   action=ActionId.BUILD, recovery=RecoveryVerdict.NOT_NEEDED).status == CheckStatus.PASS


def test_p6_build_cannot_reset_artist_or_existing_owned_parm():
    instance, spec = scene()
    nodes, after = snapshots(instance, spec)
    nodes["key"]["parms"]["exposure"] = 99
    before = v.semantic_snapshot(nodes, spec.connections, scope=after["scope"], complete=True)
    assert run(v.LocalityVerifier(), instance, spec, before=before, after=after,
               action=ActionId.BUILD, recovery=RecoveryVerdict.NOT_NEEDED).status == CheckStatus.FAIL


def test_semantic_snapshot_ignores_layout_but_not_expression_or_ports():
    n = {"x": node("x", "light", exposure={"expression": "2*$F", "value": 2})}
    first = v.semantic_snapshot(n, [], scope="/stage", complete=True)
    n["x"]["position"] = [10, 20]
    assert v.semantic_snapshot(n, [], scope="/stage", complete=True)["digest"] == first["digest"]
    n["x"]["parms"]["exposure"]["expression"] = "$F+1"
    assert v.semantic_snapshot(n, [], scope="/stage", complete=True)["digest"] != first["digest"]


@pytest.mark.parametrize("cls", list(v.VERIFIERS.values()))
def test_wrong_predicate_is_not_run(cls):
    instance, spec = scene()
    verifier = cls()
    other = next(c for c in CheckId if c != verifier.check_id)
    assert verifier.run(other, instance, spec).status == CheckStatus.NOT_RUN


def test_injected_observer_failure_retained_and_no_host_fallback():
    instance, spec = scene()
    class Unreachable:
        def observe(self, *args, **kwargs):
            raise TimeoutError("main thread busy")
    result = run(v.USDVerifier(Unreachable()), instance, spec)
    assert result.status == CheckStatus.UNKNOWN
    assert "main thread busy" in result.reason


def test_p6_edit_cannot_add_a_binding_to_empty_pretend_complete_scope():
    instance, spec = scene()
    before = v.semantic_snapshot({}, [], scope="/stage", complete=True)
    after = v.semantic_snapshot({"key": {"parms": {"exposure": 2}}}, [], scope="/stage", complete=True)
    result = run(v.LocalityVerifier(), instance, spec, before=before, after=after,
                 action=ActionId.LIGHT, slots={"exposure": 2}, recovery=RecoveryVerdict.NOT_NEEDED)
    assert result.status == CheckStatus.UNKNOWN
    assert "pre-state omits" in result.reason


def test_p6_no_clean_recovery_claim_while_mutation_may_still_run():
    instance, spec = scene()
    nodes, before = snapshots(instance, spec)
    result = run(v.LocalityVerifier(), instance, spec, before=before, after=before, rollback=before,
                 action=ActionId.LIGHT, slots={}, recovery=RecoveryVerdict.RESTORED)
    assert result.status == CheckStatus.UNKNOWN
    assert "terminal" in result.reason


def test_parameter_aliases_require_observed_type_and_shape():
    assert v.HostObserver._parameter_type("float", 3, "color3") == "color3"
    assert v.HostObserver._parameter_type("string", 1, "str") == "str"
    assert v.HostObserver._parameter_type("string", 3, "color3") != "color3"
    assert v.HostObserver._parameter_type("float", 1, "color3") != "color3"


def test_p3_replacing_render_node_type_cannot_reuse_valid_stage():
    instance, spec = scene()
    observation = readiness(instance, spec)
    observation["graph"]["nodes"]["render"]["type"] = "null"
    result = run(v.RenderReadinessVerifier(), instance, spec, observation=observation)
    assert result.status == CheckStatus.FAIL
    assert "type/parent/flags" in result.reason


def test_semantic_snapshot_field_keys_cannot_alias_node_and_parameter_paths():
    nodes = {"a": {"parms": {"b": 1}}, "a/parms": {"b": 2}}
    observed = v.semantic_snapshot(nodes, [], scope="/stage", complete=True)
    assert len(observed["fields"]) == 2
    assert set(observed["fields"]) == {"node/a/parms/b", "node/a~1parms/b"}


def test_parameter_menu_and_toggle_aliases():
    assert v.HostObserver._parameter_type("menu", 1, "enum") == "enum"
    assert v.HostObserver._parameter_type("toggle", 1, "bool") == "bool"
    assert v.HostObserver._parameter_type("float", 1, "enum") != "enum"


def test_module_imports_without_hou_or_pxr_in_fresh_process():
    import subprocess
    import sys
    from pathlib import Path
    code = """
import importlib.abc
import sys
sys.path.insert(0, "python")
class NoHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("hou", "pxr"):
            raise ImportError("host deliberately absent")
sys.meta_path.insert(0, NoHost())
from synapse.recipes import verify
assert not verify.HOU_AVAILABLE
assert not verify.PXR_AVAILABLE
assert "hou" not in sys.modules
assert "pxr" not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", code],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_ambiguous_committed_slot_name_cannot_update_two_targets():
    instance, spec = scene()
    duplicate = replace(spec.actions[2], slots=(SlotSchema("exposure", "float", "shader.base_color"),))
    spec = replace(spec, actions=(spec.actions[0], spec.actions[1], duplicate, spec.actions[3]))
    instance.committed_slots["exposure"] = 2
    result = run(v.GraphVerifier(), instance, spec, observation=graph_observation(instance, spec))
    assert result.status == CheckStatus.UNKNOWN
    assert "ambiguous slot key" in result.reason
