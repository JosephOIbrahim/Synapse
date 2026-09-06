"""Bounded real Houdini saved-network composition qualification; disposable process only."""
from pathlib import Path
import json
import sys
import hou

from synapse.cognitive.tools import scout
from synapse.host.saved_networks import SavedNetworkService, observe
from synapse.host.recipe_watch import RecipeWatch
from synapse.recipes.library import LibraryError

assert hou.applicationVersionString() == "22.0.400"
ROOT = Path(sys.argv[1]).resolve()
ROOT.mkdir(parents=True, exist_ok=False)
scout.EXPECTED_HOUDINI_VERSION = hou.applicationVersionString()
grounding = scout.synapse_scout("hou.OpNode.saveItemsToFile hou.OpNode.loadItemsFromFile hou.Parm.rawValue hou.Node.sessionId hou.nodeBySessionId hou.SubnetIndirectInput.parent hou.setUpdateMode", domain="docs", k=1, max_chars=800)
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.save(str(ROOT / "source.hiplc"))
stage = hou.node("/stage")
source = stage.createNode("subnet", "CAPTURE_SOURCE", run_init_scripts=False)
foreign = source.createNode("null", "EXTERNAL")
split = source.createNode("splitscene", "SPLIT")
split.setInput(0, foreign)
nested = source.createNode("subnet", "NESTED", run_init_scripts=False)
nested.setInput(0, split, 1)
camera = nested.createNode("camera", "CAMERA")
camera.setInput(0, nested.indirectInputs()[0])
materials = nested.createNode("materiallibrary", "MATERIALS")
surface = materials.createNode("mtlxstandard_surface", "SURFACE")
surface.parmTuple("base_color").set((.15, .33, .73))
merge = source.createNode("merge", "MERGE")
merge.setInput(0, split)
merge.setInput(1, nested)
out = source.createNode("null", "OUT")
out.setInput(0, merge)
out.setDisplayFlag(True)
outside_output = source.createNode("null", "EXTERNAL_OUT")
outside_output.setInput(0, out)
roots = (split, nested, merge, out)
for index, node in enumerate(roots):
    node.setPosition(hou.Vector2(index * 2.123456789, -index * 3.987654321))
    node.setComment("Keep this exact comment: " + node.name())
box = source.createNetworkBox("LOOK")
for node in roots:
    box.addItem(node)
box.setComment("Look development")
box.fitAroundContents()
surface.setPosition(hou.Vector2(3.123456789, -7.987654321))
for node in hou.selectedNodes():
    node.setSelected(False)
for node in roots:
    node.setSelected(True)
service = SavedNetworkService(ROOT / "library")
checks = {}
first = service.save_selection("Studio key", ["lookdev", "Hero"], "A nested authored network")
checks["usd_metadata"] = (service.library.version_path(first["recipe_id"], 1) / "recipe.usda").read_text().startswith("#usda")
checks["search_tags"] = len(service.search("hero")[0]) == 1
checks["captured_output_one"] = any(wire.get("source") == "SPLIT" and wire["output"] == 1 for wire in first["snapshot"]["wires"])
checks["external_input_reported"] = any(dep["kind"] == "input" and dep["status"] == "detached" for dep in first["snapshot"]["dependencies"])
source.setDisplayFlag(True)
positions = {node.path(): list(node.position()) for node in stage.children()}
inserted = service.restore(first["recipe_id"], 1, dependencies_reviewed=True)
copy = hou.node(inserted["path"])
checks["new_container"] = copy is not None and copy != source
checks["actual_output_one"] = copy.node("NESTED").inputConnections()[0].outputIndex() == 1
checks["nested_shader"] = copy.node("NESTED/MATERIALS/SURFACE").parmTuple("base_color").eval() == surface.parmTuple("base_color").eval()
checks["exact_positions"] = all(list(copy.node(item["name"]).position()) == item["position"] for item in first["snapshot"]["nodes"])
checks["external_input_detached"] = not copy.node("SPLIT").inputConnections()
checks["outside_output_unchanged"] = outside_output.input(0) == out
checks["existing_layout_display"] = source.isDisplayFlagSet() and all(list(hou.node(path).position()) == position for path, position in positions.items())
second_copy = service.restore(first["recipe_id"], 1, dependencies_reviewed=True)
checks["insert_twice_distinct"] = second_copy["path"] != inserted["path"]
nested.setComment("Version two")
second = service.save_identity(name="Studio key", tags=["lookdev"], notes="second",
    recipe_id=first["recipe_id"], identities=tuple((node.sessionId(), node.path()) for node in roots),
    source_scene=hou.hipFile.path(), reason="test")
checks["old_version_immutable"] = first["version"] == 1 and second["version"] == 2 and service.inspect(first["recipe_id"], 1)["notes"] == "A nested authored network"

# Negative control: corrupt the imported readback, then prove scoped cleanup.
import synapse.host.saved_networks as host_module
original_observe = host_module.observe
def misread(nodes, parent):
    result = original_observe(nodes, parent)
    if parent.name().startswith("recipe_"):
        result["nodes"][0]["comment"] = "deliberately wrong readback"
    return result
host_module.observe = misread
before_names = sorted(node.path() for node in stage.children())
try:
    service.restore(first["recipe_id"], 1, dependencies_reviewed=True)
    checks["mismatch_control_refused"] = False
except LibraryError as exc:
    checks["mismatch_control_refused"] = "did not match" in str(exc)
finally:
    host_module.observe = original_observe
checks["failed_insert_scoped_cleanup"] = before_names == sorted(node.path() for node in stage.children()) and source.isDisplayFlagSet()

# Real callback pair writes a single version before the selected nodes disappear.
for node in hou.selectedNodes():
    node.setSelected(False)
for node in roots:
    node.setSelected(True)
notices = []
watch = RecipeWatch(service, notices.append)
watch.arm("Before leaving", ["exit"], "source scene")
hou.hipFile.save(str(ROOT / "with_network.hiplc"))
hou.hipFile.load(str(ROOT / "source.hiplc"), suppress_save_prompt=True)
checks["real_exit_capture"] = not watch.armed and watch.last_result["status"] == "saved"
checks["exit_pair_deduplicated"] = len(service.search("exit", all_versions=True)[0]) == 1
checks["close_does_not_duplicate"] = len(notices) == 2
watch.close()
checks["last_result_durable"] = service.last_notice()["status"] == "saved"
record = {"verdict": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
          "build": hou.applicationVersionString(), "grounding": grounding,
          "limits": ["Disposable fixture only; no render or production scene qualification.",
                     "Dependency closure remains unverified; expression content is copied without inventory evaluation."]}
(ROOT / "results.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
print(json.dumps(record, sort_keys=True))
assert all(checks.values()), checks
