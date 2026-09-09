"""Run with isolated H22 hython; writes evidence only to the requested folder.

Uses a fresh scratch network, never the artist's live GUI or saved scene.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import hou

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT))

from synapse.server.handlers_network_layout import NetworkLayoutMixin
from synapse.server.network_layout import METADATA_KEY
from synapse.core.errors import SynapseUserError


def content(nodes):
    """Independent invariants: IDs, names/types, raw parm definitions, wiring/output."""
    return {node.path(): {
        "session_id": node.sessionId(), "type": node.type().name(),
        "parameters": {parm.name(): parm.asCode() for parm in node.parms()},
        "inputs": [(edge.inputNode().path(), edge.inputIndex(), edge.outputIndex())
                   for edge in node.inputConnections()],
        "display": node.isDisplayFlagSet(),
    } for node in nodes}


def decoration(parent):
    # H22 recreates a box's double-precision bounds on undo; round-off of
    # <1e-15 was measured. Compare visual coordinates to 1e-9 Houdini units.
    def visual_vector(value):
        return [round(component, 9) for component in value]
    return {"nodes": {node.path(): {
        "position": visual_vector(node.position()), "color": list(node.color().rgb()),
        "comment": node.comment(),
        "display_comment": node.isGenericFlagSet(hou.nodeFlag.DisplayComment),
        "box": node.parentNetworkBox().name() if node.parentNetworkBox() else None,
    } for node in parent.children()}, "boxes": {box.name(): {
        "position": visual_vector(box.position()), "size": visual_vector(box.size()),
        "color": list(box.color().rgb()), "comment": box.comment(),
        "items": sorted(item.path() for item in box.items()),
    } for box in parent.networkBoxes()}, "metadata": parent.userData(METADATA_KEY)}


def run(output):
    if hou.isUIAvailable():
        raise RuntimeError("This probe is headless only; it must not touch a live GUI")
    output.mkdir(parents=True, exist_ok=True)
    report = {"build": hou.applicationVersionString(), "ui": False,
              "source": str(ROOT), "checks": {}, "results": []}
    handler = NetworkLayoutMixin()
    geo = hou.node("/obj").createNode("geo", "layout_probe_geo")
    hero = geo.createNode("sphere", "hero_sphere")
    hero_xform = geo.createNode("xform", "hero_placement")
    hero_xform.setInput(0, hero)
    hero_xform.parm("tx").set(-1.25)
    plinth = geo.createNode("box", "plinth")
    plinth_xform = geo.createNode("xform", "plinth_placement")
    plinth_xform.setInput(0, plinth)
    plinth_xform.parm("ty").setExpression('ch("../hero_placement/tx") * 0.2')
    merge = geo.createNode("merge", "assembly")
    merge.setInput(0, hero_xform)
    merge.setInput(1, plinth_xform)
    out = geo.createNode("null", "OUTPUT")
    out.setInput(0, merge)
    out.setDisplayFlag(True)
    nodes = [hero, hero_xform, plinth, plinth_xform, merge, out]
    hero.setComment("Artist note: preserve this sentence.")
    old_box = geo.createNetworkBox("existing_section")
    old_box.setComment("Original artist section")
    old_box.addItem(hero)
    untouched = geo.createNode("null", "unrelated")
    untouched.setPosition(hou.Vector2(30, 30))
    unrelated_box = geo.createNetworkBox("unrelated_box")
    unrelated_box.setComment("Keep this section")
    unrelated_box.addItem(untouched)
    unrelated_box.fitAroundContents()
    snapshot = content([*nodes, untouched])
    untouched_decoration = decoration(geo)["nodes"][untouched.path()]
    untouched_box = decoration(geo)["boxes"][unrelated_box.name()]
    paths = [n.path() for n in nodes]
    base = {"parent": geo.path(), "nodes": paths}
    requests = [dict(base, orientation="vertical"), dict(base, orientation="horizontal"),
                dict(base, style="focus", replace_boxes=[old_box.name()]),
                dict(base, style="assets", groups=[
                    {"label": "Hero sphere", "nodes": [hero.path(), hero_xform.path()]},
                    {"label": "Display plinth", "nodes": [plinth.path(), plinth_xform.path()]},
                ], labels={hero.path(): "Hero product shape", hero_xform.path(): "Position the hero",
                           plinth.path(): "Display base", plinth_xform.path(): "Position the base",
                           merge.path(): "Shared assembly", out.path(): "Final scene output"})]
    for request in requests:
        before = decoration(geo)
        previous_labels = tuple(hou.undos.undoLabels())
        preview = handler._handle_layout_network(dict(request, dry_run=True))
        assert decoration(geo) == before, "Dry run mutated decorations"
        assert tuple(hou.undos.undoLabels()) == previous_labels, "Dry run added an undo entry"
        result = handler._handle_layout_network(request)
        after = decoration(geo)
        assert result["status"] == "updated"
        assert content([*nodes, untouched]) == snapshot, "Layout mutated scene content"
        assert after["nodes"][untouched.path()] == untouched_decoration
        assert after["boxes"][unrelated_box.name()] == untouched_box
        assert len(hou.undos.undoLabels()) == len(previous_labels) + 1
        assert hou.undos.undoLabels()[0] == result["undo_label"]
        assert hou.undos.performUndo(), "Native undo was unavailable"
        if decoration(geo) != before:
            (output / "undo-failure.json").write_text(json.dumps({
                "request": request, "before": before, "after": after,
                "after_undo": decoration(geo)}, indent=2, sort_keys=True), encoding="utf-8")
        assert decoration(geo) == before, "One undo did not restore all decorations and ownership"
        assert content([*nodes, untouched]) == snapshot, "Undo changed scene content"
        assert hou.undos.performRedo(), "Native redo was unavailable"
        assert decoration(geo) == after, "Redo did not restore the layout"
        assert content([*nodes, untouched]) == snapshot
        report["results"].append({"request": request, "result": result,
                                  "before": before, "after": after, "undo_redo": True})
    report["checks"]["composed_sop_sequence_and_undo_redo"] = True
    assert hero.comment().startswith("Artist note: preserve this sentence.")
    assert hero.comment().count("SYNAPSE ·") == 1
    before_repeat, depth = decoration(geo), len(hou.undos.undoLabels())
    repeated = handler._handle_layout_network(requests[-1])
    assert repeated["status"] == "unchanged", repeated
    assert decoration(geo) == before_repeat
    assert len(hou.undos.undoLabels()) == depth, "Idempotent request added an undo entry"
    report["checks"]["idempotent_request_keeps_undo_history"] = True
    invalid = dict(base, style="focus", replace_boxes=[unrelated_box.name()])
    try:
        handler._handle_layout_network(invalid)
    except SynapseUserError:
        pass
    else:
        raise AssertionError("Replacement of an unselected artist box was accepted")
    assert decoration(geo) == before_repeat
    assert len(hou.undos.undoLabels()) == depth
    report["checks"]["foreign_box_rejected_before_mutation"] = True
    with hou.undos.disabler():
        try:
            handler._handle_layout_network(base)
        except SynapseUserError:
            pass
        else:
            raise AssertionError("Mutation with undo disabled was accepted")
    assert decoration(geo) == before_repeat
    report["checks"]["undo_disabled_fails_closed"] = True

    guard_geo = hou.node("/obj").createNode("geo", "layout_probe_scope")
    selected = guard_geo.createNode("null", "selected")
    excluded = guard_geo.createNode("null", "not_selected")
    mixed_box = guard_geo.createNetworkBox("artist_section")
    mixed_box.setComment("An artist section containing more than this selection")
    mixed_box.addItem(selected)
    mixed_box.addItem(excluded)
    guarded_before, guard_depth = decoration(guard_geo), len(hou.undos.undoLabels())
    try:
        handler._handle_layout_network({"parent": guard_geo.path(), "nodes": [selected.path()], "style": "focus"})
    except SynapseUserError:
        pass
    else:
        raise AssertionError("Regrouping part of a foreign artist box was accepted")
    assert decoration(guard_geo) == guarded_before
    assert len(hou.undos.undoLabels()) == guard_depth
    report["checks"]["partial_artist_box_rejected_before_mutation"] = True

    # Legacy/manual formatting changes metadata bytes without changing visuals.
    # A canonicalization write is still an edit and must be reported as such.
    formatted_metadata = json.dumps(json.loads(geo.userData(METADATA_KEY)), indent=2, sort_keys=True)
    geo.setUserData(METADATA_KEY, formatted_metadata)
    metadata_depth = len(hou.undos.undoLabels())
    metadata_result = handler._handle_layout_network(requests[-1])
    assert metadata_result["status"] == "updated" and metadata_result["metadata_changed"]
    assert not metadata_result["changed_nodes"] and not metadata_result["changed_boxes"]
    assert len(hou.undos.undoLabels()) == metadata_depth + 1
    assert hou.undos.performUndo()
    assert geo.userData(METADATA_KEY) == formatted_metadata
    assert hou.undos.performRedo()
    report["checks"]["metadata_only_change_reported_and_undoable"] = True

    stage = hou.node("/stage")
    imported = stage.createNode("sopimport", "layout_probe_import")
    imported.parm("soppath").set(out.path())
    material = stage.createNode("materiallibrary", "layout_probe_material")
    material.setInput(0, imported)
    camera = stage.createNode("camera", "layout_probe_camera")
    camera.setInput(0, material)
    light = stage.createNode("light::2.0", "layout_probe_light")
    light.setInput(0, camera)
    stage_out = stage.createNode("null", "layout_probe_OUTPUT")
    stage_out.setInput(0, light)
    stage_out.setDisplayFlag(True)
    lops = [imported, material, camera, light, stage_out]
    before_content = content(lops)
    def stage_digest():
        return hashlib.sha256(stage_out.stage().Flatten().ExportToString().encode()).hexdigest()
    before_hash = stage_digest()
    for style in ("plain", "focus", "assets"):
        request = {"parent": "/stage", "nodes": [node.path() for node in lops], "style": style}
        if style == "assets":
            request["groups"] = [{"label": "Product display", "nodes": [imported.path(), material.path()]}]
        result = handler._handle_layout_network(request)
        assert content(lops) == before_content
        assert stage_digest() == before_hash, "Composed USD changed during layout"
        assert hou.undos.performUndo()
        assert stage_digest() == before_hash
        assert hou.undos.performRedo()
        assert stage_digest() == before_hash
    report["checks"]["lop_composed_stage_hash_preserved_through_undo_redo"] = True
    report["composed_stage_sha256"] = before_hash
    report["verdict"] = "PASS"
    (output / "native-layout.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"build": report["build"], "checks": report["checks"],
                      "verdict": report["verdict"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
