"""Native fixed-lookdev build, preservation and negative_control battery.

Run only in a disposable Houdini 22.0.400 hython process with a caller-enforced
time limit and isolated preferences. Refuses GUI/wrong-build execution. Uses
the real graph handler and run_on_main; no bridge, render, export or model call.
The negative controls alter a detached copy of the real composed USD stage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import threading
import uuid

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "python"), str(REPO)]

import hou
from pxr import Sdf, Usd
from synapse.server.handlers_solaris_graph import SolarisGraphMixin
from synapse.server import main_thread, solaris_lookdev


def _snapshot(root):
    """Compare authored state without evaluating parameter expressions."""
    result = {}
    for node in (root,) + root.allSubChildren(recurse_in_locked_nodes=False):
        wires = []
        for wire in node.inputConnections():
            source = wire.inputItem()
            indirect = wire.subnetIndirectInput()
            wires.append({"input": wire.inputIndex(), "output": wire.inputItemOutputIndex(),
                          "source": source.path() if source is not None else None,
                          "indirect": indirect.path() if indirect is not None else None})
        flags = {}
        for name in ("isDisplayFlagSet", "isRenderFlagSet", "isBypassed"):
            getter = getattr(node, name, None)
            if callable(getter):
                flags[name] = bool(getter())
        result[node.path()] = {"id": node.sessionId(), "type": node.type().name(),
                               "position": list(node.position()), "comment": node.comment(),
                               "parms": {parm.name(): parm.rawValue() for parm in node.parms()},
                               "wires": sorted(wires, key=lambda wire: wire["input"]), "flags": flags}
    return result


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _request(parent, name, layout="vertical", color=None):
    return {"parent": parent.path(), "template": "copernicus_lookdev", "layout": layout,
            "template_params": {"name": name, "base_color": color or [0.18, 0.04, 0.01],
                                "noise_type": "perlin", "frequency": 4.0, "octaves": 3}}


class _DetachedOutput:
    """Only the verifier's output accessor is adapted; USD data is real."""
    def __init__(self, stage):
        self._stage = stage

    def stage(self, *, ignore_errors):
        assert ignore_errors is False
        return self._stage

    def errors(self):
        return ()


def _run_on_main():
    assert threading.get_ident() == threading.main_thread().ident
    assert not hou.isUIAvailable(), "This destructive probe is headless-only"
    assert hou.applicationVersionString() == "22.0.400", "Probe is qualified only on Houdini 22.0.400"
    stage = hou.node("/stage")
    if stage is None:
        raise RuntimeError("No Solaris stage network")
    name = "lookdev_probe_" + uuid.uuid4().hex[:12]
    assert stage.node(name) is None
    owner = stage.createNode("subnet", name, exact_type_name=True, run_init_scripts=False)
    owner_id = owner.sessionId()
    report = {"version": hou.applicationVersionString(), "owner": owner.path(), "checks": [],
              "limits": ["Graph and composed USD only; texture pixels and Karma appearance are not measured.",
                         "Detached USD mutations test verifier refusal, not edits to the live fixture.",
                         "No render/export, bridge/model request or artist GUI is exercised."]}
    def passed(name, **evidence):
        report["checks"].append({"name": name, "verdict": "PASS", **evidence})

    try:
        assert not owner.children(), "Expected a fresh, empty owned parent"
        harness = SolarisGraphMixin()
        request = _request(owner, "first")
        first = harness._handle_solaris_build_graph(request)
        first_root = hou.node(first["root"])
        assert first["status"] == "created" and first["verification"]["usd"] == "verified"
        assert first["resolution"] == [256, 256]
        assert first["display_node"] == first_root.path() and first_root.isDisplayFlagSet()
        assert first["display_changed"] is True  # H22 requires the sole LOP to display.
        assert first["verification"]["rendered_appearance"] == "not checked"
        passed("first build in empty parent reports its new display", result=first)

        before = _snapshot(owner)
        collision = None
        try:
            harness._handle_solaris_build_graph(request)
        except ValueError as error:
            collision = str(error)
        assert collision and "already exists" in collision, "Same-name second action must refuse"
        assert _snapshot(owner) == before, "Naming collision changed existing state"
        passed("negative control same-name second action preserves all state", state_sha256=_digest(before))

        first_state = _snapshot(first_root)
        second = harness._handle_solaris_build_graph(_request(owner, "second", "horizontal", [0.03, 0.15, 0.4]))
        second_root = hou.node(second["root"])
        assert _snapshot(first_root) == first_state, "Second fixture changed first positions/wires/parms/display"
        assert first_root.isDisplayFlagSet() and not second_root.isDisplayFlagSet()
        assert second["display_node"] == first_root.path() and second["display_changed"] is False
        names = ("asset", "textures", "camera", "key", "preview_settings", "output0")
        positions = [tuple(second_root.node(node_name).position()) for node_name in names]
        assert all(a[0] < b[0] and a[1] == b[1] for a, b in zip(positions, positions[1:])), positions
        passed("second horizontal fixture preserves first and existing display", first_state_sha256=_digest(first_state), horizontal_positions=positions)

        prior = _snapshot(owner)
        real_material_wire = solaris_lookdev._material_wire
        wired = []
        def fail_after_real_material_wire(*args, **kwargs):
            result = real_material_wire(*args, **kwargs)
            wired.append(result)
            if result["label"] == "specular_roughness":
                raise RuntimeError("LOOKDEV_PROBE_AFTER_REAL_MATERIAL_WIRE")
            return result
        solaris_lookdev._material_wire = fail_after_real_material_wire
        failed = None
        try:
            try:
                harness._handle_solaris_build_graph(_request(owner, "injected_failure"))
            except RuntimeError as error:
                failed = str(error)
        finally:
            solaris_lookdev._material_wire = real_material_wire
        assert failed and "LOOKDEV_PROBE_AFTER_REAL_MATERIAL_WIRE" in failed
        assert [wire["label"] for wire in wired] == ["base_color", "specular_roughness"]
        assert owner.node("injected_failure") is None
        assert _snapshot(owner) == prior, "Ordinary failure left residue or changed prior state"
        passed("negative control failure after real material wires cleans only new root", wired_before_failure=wired, prior_state_sha256=_digest(prior))

        verification = first["verification"]
        color = hou.node(first["controls"]["base_color"])
        roughness = hou.node(first["controls"]["roughness"])
        live_output = hou.node(first["output"])
        live_stage = live_output.stage(ignore_errors=False)
        flat = live_stage.Flatten()
        detached = Usd.Stage.Open(flat)
        assert detached.GetRootLayer().identifier != live_stage.GetRootLayer().identifier
        detached_output = _DetachedOutput(detached)
        def verify_detached():
            return solaris_lookdev._verify_stage(detached_output, verification["geometry"], verification["material"],
                                                color, roughness, verification["camera"], verification["render_settings"])
        assert verify_detached()["usd"] == "verified"
        passed("real composed USD copy passes independent verifier readback")

        mesh = detached.GetPrimAtPath(verification["geometry"])
        uv = mesh.GetAttribute("primvars:st")
        original_uv = uv.Get()
        assert uv.Set([original_uv[0]] * len(original_uv))
        refused = None
        try:
            verify_detached()
        except RuntimeError as error:
            refused = str(error)
        assert refused and "UV" in refused, "Degenerate actual USD UVs were accepted"
        assert uv.Set(original_uv)
        assert verify_detached()["usd"] == "verified"
        passed("negative control degenerate UVs refuse then corrected copy verifies")

        binding = mesh.GetRelationship("material:binding")
        original_binding = binding.GetTargets()
        assert binding.SetTargets([Sdf.Path("/materials/NOT_THE_FIXTURE")])
        refused = None
        try:
            verify_detached()
        except RuntimeError as error:
            refused = str(error)
        assert refused and "binding" in refused.lower(), "Wrong actual USD material binding was accepted"
        assert binding.SetTargets(original_binding)
        assert verify_detached()["usd"] == "verified"
        assert _snapshot(owner) == prior, "Detached negative controls changed the real fixture"
        passed("negative control wrong binding refuses then corrected copy verifies")
        report["verdict"] = "PASS"
        return report
    finally:
        assert owner.sessionId() == owner_id, "Refuse cleanup of a replaced owner"
        owner.destroy()
        assert stage.node(name) is None, "Owned test scope was not removed"


def run():
    before = main_thread.main_thread_direct_stats()["count"]
    report = main_thread.run_on_main(_run_on_main, label="probe:copernicus_lookdev")
    after = main_thread.main_thread_direct_stats()["count"]
    assert after > before, "Real main-thread direct dispatch did not execute"
    report["real_run_on_main_calls"] = after - before
    report["owned_scope_removed"] = True
    report["source_sha256"] = {path.relative_to(REPO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        Path(__file__), REPO / "python/synapse/server/solaris_lookdev.py",
        REPO / "python/synapse/server/copernicus_texture.py",
        REPO / "python/synapse/server/handlers_solaris_graph.py",
        REPO / "python/synapse/server/main_thread.py")}
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PASS: fixed Copernicus lookdev build, preservation, cleanup and USD negative controls")
