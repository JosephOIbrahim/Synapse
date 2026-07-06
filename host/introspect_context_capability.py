"""
host/introspect_context_capability.py  —  C.0 probe: per-context create-capability (HOST LAYER)
================================================================================================

C track, EXPLORE phase (``harness/notes/spec-C-context-capability.md`` §4). Measures
SYNAPSE's REAL ability to CREATE in each Houdini context (SOP/LOP/COP/TOP/DOP/MAT) by
driving its own live dispatch seam — ``SynapseHandler.handle(SynapseCommand)`` — the same
surface the live WS transport calls. Raw ``hou`` is used ONLY for verification reads,
frame stepping, and revert deletes; every mutation goes through a registered handler verb.
A needed verb absent from the registry is a GAP entry ("no handler verb: <what>"), never
a guessed call and never a crash — the registry IS the phantom gate at this layer.

RUN IT INSIDE THE TARGET BUILD (hython only):

    hython host/introspect_context_capability.py                        # full catalog
    hython host/introspect_context_capability.py --context sop --out X  # one context
    hython host/introspect_context_capability.py --out Y                # full, custom path

Full catalog lands at ``harness/notes/context_capability_21.json`` (major-pinned name;
``houdini_version`` inside carries the full build — mirrors connectivity_21.json). Writes
are atomic (.tmp + os.replace); rc 0 iff the artifact was written. Boot clears the hip
(``suppress_save_prompt=True``); the probe never saves a hip, never touches user prefs,
never reaches the network.

Node-type + parm provenance (probe truth > guessed spelling):
  * verified live 21.0.671 — harness/notes/verified_connectivity_21.0.671.json:
    Object/{geo,dopnet,topnet}, Sop/{box,scatter}, Cop2/{noise,null}, Top/wedge,
    Dop/{pyrosolver,vellumsolver,rbdpackedobject,rigidbodysolver}, Lop/{null,
    materiallibrary,assignmaterial,pythonscript,domelight}
  * authored U.5 catalog (lop_solaris_knowledge_21.json): Lop/{sphere,distantlight,cube}
  * repo single-source (synapse.core.mtlx_types, live-exercised): mtlximage
  * UNVERIFIED as spelled, frozen by the spec's golden intent: Dop/{smokeobject,
    smokesolver,volumesource} — if the live build refuses them the golden fails
    HONESTLY and that failure IS the C.5 target.
  * UsdLux parm encodings come from harness/notes/verified_usdlux_encodings_21.0.671.json
    (scalars_verified only — punycode is probe-generated, never hand-guessed).

Known traps honored: ``editableStage()`` is None outside a LOP cook (all stage reads go
through ``node.stage()``); there is no ``hou.lopNetworks()``; the TOP golden GENERATES
work items, it does not cook (cooking is the ``local_cook_3`` EXTENDED observation).

``hou`` and ``synapse`` are imported inside functions so this module also imports
cleanly on stock Python for the pure test suite (same posture as the sibling probes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "context_capability/v1"
_REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = _REPO / "harness" / "notes" / "context_capability_21.json"

# Frozen contexts-map keys (spec §4) and the six that carry golden/extended runs.
CONTEXTS = ("sop", "lop", "cop", "top", "dop", "mat", "generic")
PROBEABLE = ("sop", "lop", "cop", "top", "dop", "mat")

# Verified UsdLux punycode encodings — harness/notes/verified_usdlux_encodings_21.0.671.json
# scalars_verified. Hardcoded HERE (not via aliases.py) so the probe measures the raw
# handler surface with ground-truth names; a phantom parm is a gap, not a guess.
_USDLUX_INTENSITY = "xn__inputsintensity_i0a"

# Cheap-cook budget knobs (spec: full run < ~3 min headless).
_SCATTER_NPTS = 64          # scatter counts small
_DOP_DIVSIZE = 0.5          # coarse smoke divisions
_DOP_FRAMES = (1, 2, 3)     # DOP cooks 3 frames, no more
_UNDO_UNWIND_CAP = 40       # bounded unwind attempts per context


# ---------------------------------------------------------------------------
# Step failure taxonomy. _VerbAbsent is the registry-gate miss (the frozen
# "no handler verb: <what>" gap text); _StepFail wraps a handler-level refusal
# (SynapseResponse.success False). Anything else is a plain exception — all
# three land as ok:false step records; none aborts the run.
# ---------------------------------------------------------------------------

class _StepFail(Exception):
    pass


class _VerbAbsent(Exception):
    def __init__(self, verb: str):
        super().__init__(f"no handler verb: {verb}")
        self.verb = verb


class _Driver:
    """The one seam to Houdini mutations: SynapseHandler.handle(SynapseCommand).

    Registry membership is checked BEFORE every call — an absent verb raises
    _VerbAbsent (recorded gap), so the probe can never invent a command. A
    success=False response raises _StepFail carrying the handler's own error
    text (the honest detail the catalog wants).
    """

    def __init__(self, handler, command_cls):
        self._handler = handler
        self._command_cls = command_cls
        self._seq = 0

    @property
    def registered_types(self):
        return list(self._handler._registry.registered_types)

    def has(self, verb: str) -> bool:
        return self._handler._registry.has(verb)

    def call(self, verb: str, **payload):
        if not self.has(verb):
            raise _VerbAbsent(verb)
        self._seq += 1
        cmd = self._command_cls(
            type=verb, id=f"ctxprobe-{self._seq:04d}", payload=payload,
            sequence=self._seq,
        )
        resp = self._handler.handle(cmd)
        if not resp.success:
            raise _StepFail(f"{verb}: {resp.error or 'handler returned success=False'}")
        return resp.data if isinstance(resp.data, dict) else {}


def _run_steps(steps, records, gaps):
    """Run (name, fn) steps sequentially. Every failure is a record + a gap
    entry; a failed step never aborts the remaining steps (later cascades fail
    with their own honest details — deterministic: same code => same gaps)."""
    for name, fn in steps:
        try:
            detail = fn()
            records.append({"step": name, "ok": True,
                            "detail": str(detail or "ok")[:300]})
        except _VerbAbsent as e:
            records.append({"step": name, "ok": False, "detail": str(e)})
            gaps.append(str(e))
        except Exception as e:  # noqa: BLE001 — honest failure, never a crash
            records.append({"step": name, "ok": False,
                            "detail": f"{type(e).__name__}: {e}"[:300]})
            gaps.append(name)


# ---------------------------------------------------------------------------
# Command classification (frozen rule, spec §4): prefix cops_->cop, tops_->top;
# the Solaris/USD/stage family -> lop; the material family -> mat; generic node
# verbs -> generic; everything else (memory, render, hda, session, ...) lands in
# the top-level `unclassified` list. sop and dop get NO dedicated verbs — SOP
# creation flows entirely through generic verbs, and the empty dop list is the
# dedicated-verb VOID the review sweep flags (ADVISORY).
# ---------------------------------------------------------------------------

_FAMILY = {
    # generic node verbs — usable in every context
    "create_node": "generic", "delete_node": "generic", "connect_nodes": "generic",
    "network_explain": "generic", "get_parm": "generic", "set_parm": "generic",
    "set_keyframe": "generic", "execute_python": "generic", "execute_vex": "generic",
    "inspect_node": "generic", "undo": "generic", "redo": "generic",
    # Solaris / USD / stage family
    "get_stage_info": "lop", "get_usd_attribute": "lop", "set_usd_attribute": "lop",
    "set_usd_primvar": "lop", "create_usd_prim": "lop", "modify_usd_prim": "lop",
    "reference_usd": "lop", "set_payload_loadstate": "lop",
    "create_point_instancer": "lop", "shot_render_ready": "lop", "query_prims": "lop",
    "manage_variant_set": "lop", "manage_collection": "lop",
    "configure_light_linking": "lop", "solaris_validate_ordering": "lop",
    "solaris_assemble_chain": "lop", "solaris_build_graph": "lop",
    "solaris_shotsetup_karma_xpu": "lop", "assess_render_ready": "lop",
    # material family (create_material et al. author INTO Solaris, but the
    # material verbs are the mat context's dedicated surface; matlib_bind is
    # material-by-name — one context each, never two)
    "create_material": "mat", "create_textured_material": "mat",
    "assign_material": "mat", "read_material": "mat", "matlib_bind": "mat",
    # `wedge` is the one un-prefixed TOPs verb (cooks a wedge TOP)
    "wedge": "top",
}


def _classify(verbs):
    by_ctx = {c: [] for c in CONTEXTS}
    unclassified = []
    for v in sorted(verbs):
        if v.startswith("cops_"):
            by_ctx["cop"].append(v)
        elif v.startswith("tops_"):
            by_ctx["top"].append(v)
        elif v in _FAMILY:
            by_ctx[_FAMILY[v]].append(v)
        else:
            unclassified.append(v)
    return by_ctx, unclassified


# ---------------------------------------------------------------------------
# Shared verification helpers (hou reads only)
# ---------------------------------------------------------------------------

def _find_prim(hou, node_path, type_name):
    """First prim of `type_name` on node.stage() — editableStage() is None
    outside a LOP cook, so stage reads ALWAYS go through node.stage()."""
    node = hou.node(node_path)
    if node is None:
        raise _StepFail(f"verify: node {node_path} not found")
    stage = node.stage()
    if stage is None:
        raise _StepFail(f"verify: node.stage() is None on {node_path}")
    for prim in stage.Traverse():
        if str(prim.GetTypeName()) == type_name:
            return prim
    raise _StepFail(f"verify: no {type_name} prim on {node_path}'s stage")


def _no_cook_error(result):
    """Handlers that build a pythonscript LOP report cook failure as data
    (cook_error key) rather than raising — surface it as a step failure."""
    if isinstance(result, dict) and result.get("cook_error"):
        raise _StepFail(str(result["cook_error"])[:280])
    return result


def _undo_unwind_step(drv, hou, roots):
    """EXTENDED observation (observed, not gated): drive the registered `undo`
    verb until every probe root is gone, bounded. Headless hython usually runs
    with the undo manager disabled — recording that truth is the point."""
    def _fn():
        remaining = [p for p in roots if hou.node(p) is not None]
        if not remaining:
            raise _StepFail("nothing to unwind (no probe roots survived the run)")
        for i in range(_UNDO_UNWIND_CAP):
            drv.call("undo")
            if all(hou.node(p) is None for p in roots):
                return f"undo unwound {len(remaining)} probe root(s) in {i + 1} step(s)"
        raise _StepFail(
            f"{_UNDO_UNWIND_CAP} undo steps left probe roots standing "
            "(undo stack likely disabled/empty under headless hython)")
    return ("undo_unwind", _fn)


def _revert(hou, roots):
    """Delete the probe's root containers (hou delete is sanctioned for revert)
    and VERIFY gone. Reverse order so children-of-children fall first."""
    problems = []
    for path in reversed(roots):
        node = hou.node(path)
        if node is not None:
            try:
                node.destroy()
            except Exception as e:  # noqa: BLE001
                problems.append(f"{path}: destroy failed ({e})")
        if hou.node(path) is not None:
            problems.append(f"{path}: still present after destroy")
    return (len(problems) == 0), ("; ".join(problems)[:300] or "all probe roots gone")


# ---------------------------------------------------------------------------
# Per-context probes. Each returns the context entry dict (sans `commands`).
# Steps share state via `st`; every created top-level container path goes into
# `roots` for undo_unwind + revert. Order: GOLDEN -> EXTENDED -> undo_unwind
# (extended observation) -> revert.
# ---------------------------------------------------------------------------

def _probe_sop(drv, hou):
    st, roots = {}, []

    def s_container():
        r = drv.call("create_node", parent="/obj", type="geo", name="ctxprobe_sop")
        st["geo"] = r["path"]; roots.append(r["path"])
        return r["path"]

    def s_box():
        r = drv.call("create_node", parent=st.get("geo", "/obj/ctxprobe_sop"),
                     type="box", name="ctxprobe_box")
        st["box"] = r["path"]
        return r["path"]

    def s_scale():
        drv.call("set_parm", node=st.get("box", ""), parm="scale", value=2.0)
        return "box scale=2.0"

    def s_scatter():
        r = drv.call("create_node", parent=st.get("geo", "/obj/ctxprobe_sop"),
                     type="scatter", name="ctxprobe_scatter")
        st["scatter"] = r["path"]
        drv.call("set_parm", node=r["path"], parm="npts", value=_SCATTER_NPTS)
        return f"{r['path']} npts={_SCATTER_NPTS}"

    def s_wire():
        drv.call("connect_nodes", source=st.get("box", ""), target=st.get("scatter", ""))
        return "box -> scatter"

    def s_cook_verify():
        node = hou.node(st.get("scatter", ""))
        if node is None:
            raise _StepFail("verify: scatter node missing")
        geo = node.geometry()  # pulls the cook
        if geo is None:
            raise _StepFail("verify: scatter cooked no geometry")
        pc = geo.intrinsicValue("pointcount")
        if not pc or pc <= 0:
            raise _StepFail(f"verify: pointcount={pc} (expected > 0)")
        return f"pointcount={pc}"

    golden_steps, gaps = [], []
    _run_steps([
        ("create_geo_container", s_container),
        ("create_box", s_box),
        ("set_box_scale", s_scale),
        ("create_scatter", s_scatter),
        ("wire_box_to_scatter", s_wire),
        ("cook_verify_pointcount", s_cook_verify),
    ], golden_steps, gaps)

    def x_vex():
        r = drv.call("execute_vex", snippet="@P += (rand(@ptnum) - 0.5) * 0.05;",
                     input_node=st.get("box", ""))
        if r.get("errors"):
            raise _StepFail("; ".join(str(e) for e in r["errors"])[:280])
        # no input_node fallback creates /obj/synapse_vex_temp — track any
        # /obj-rooted container the wrangle landed in so revert stays total.
        wparent = str(r.get("node", "")).rsplit("/", 1)[0]
        if wparent.startswith("/obj/") and wparent.count("/") == 2 and wparent not in roots:
            roots.append(wparent)
        return r.get("node", "wrangle ok")

    def x_boolean():
        r2 = drv.call("create_node", parent=st.get("geo", "/obj/ctxprobe_sop"),
                      type="box", name="ctxprobe_box2")
        rb = drv.call("create_node", parent=st.get("geo", "/obj/ctxprobe_sop"),
                      type="boolean", name="ctxprobe_bool")
        drv.call("connect_nodes", source=st.get("box", ""), target=rb["path"],
                 target_input=0)
        drv.call("connect_nodes", source=r2["path"], target=rb["path"], target_input=1)
        node = hou.node(rb["path"])
        if node is None or node.geometry() is None:
            raise _StepFail("boolean cooked no geometry")
        return f"{rb['path']} union cooked"

    def x_group():
        rg = drv.call("create_node", parent=st.get("geo", "/obj/ctxprobe_sop"),
                      type="groupcreate", name="ctxprobe_group")
        drv.call("connect_nodes", source=st.get("box", ""), target=rg["path"])
        node = hou.node(rg["path"])
        if node is None or node.geometry() is None:
            raise _StepFail("groupcreate cooked no geometry")
        return rg["path"]

    extended = []
    _run_steps([
        ("vex_wrangle", x_vex),
        ("boolean_union", x_boolean),
        ("group_create", x_group),
        _undo_unwind_step(drv, hou, roots),
    ], extended, gaps)

    revert_ok, revert_detail = _revert(hou, roots)
    golden = {"ok": all(s["ok"] for s in golden_steps), "steps": golden_steps,
              "revert_ok": revert_ok}
    if not revert_ok:
        gaps.append(f"revert: {revert_detail}")
    return {"golden": golden, "extended": extended, "gaps": gaps}


def _probe_lop(drv, hou):
    st, roots = {}, []

    def s_sphere():
        r = drv.call("create_node", parent="/stage", type="sphere",
                     name="ctxprobe_sphere")
        st["sphere"] = r["path"]; roots.append(r["path"])
        return r["path"]

    def s_radius():
        drv.call("set_parm", node=st.get("sphere", ""), parm="radius", value=2.5)
        return "radius=2.5"

    def s_verify():
        prim = _find_prim(hou, st.get("sphere", ""), "Sphere")
        st["sphere_prim"] = str(prim.GetPath())
        attr = prim.GetAttribute("radius")
        val = attr.Get() if attr and attr.IsValid() else None
        if val is None or abs(float(val) - 2.5) > 1e-6:
            raise _StepFail(f"verify: radius attr={val} (expected 2.5)")
        return f"{st['sphere_prim']} radius={float(val)}"

    golden_steps, gaps = [], []
    _run_steps([
        ("create_stage_sphere", s_sphere),
        ("set_sphere_radius", s_radius),
        ("verify_stage_prim", s_verify),
    ], golden_steps, gaps)

    sphere_prim = lambda: st.get("sphere_prim", "/ctxprobe_sphere")  # noqa: E731

    def x_mtlx():
        r = drv.call("create_material", node=st.get("sphere", ""),
                     name="ctxprobe_lopmtl", base_color=[0.8, 0.2, 0.1])
        roots.append(r["matlib_path"])
        ra = drv.call("assign_material", node=r["matlib_path"],
                      prim_pattern=sphere_prim(),
                      material_path=r["material_usd_path"])
        roots.append(ra["node_path"])
        return f"{r['material_usd_path']} assigned via {ra['node_path']}"

    def x_light():
        r = drv.call("create_node", parent="/stage", type="distantlight",
                     name="ctxprobe_light")
        roots.append(r["path"])
        drv.call("set_parm", node=r["path"], parm=_USDLUX_INTENSITY, value=2.0)
        prim = _find_prim(hou, r["path"], "DistantLight")
        attr = prim.GetAttribute("inputs:intensity")
        val = attr.Get() if attr and attr.IsValid() else None
        if val is None or abs(float(val) - 2.0) > 1e-6:
            raise _StepFail(f"inputs:intensity={val} (expected 2.0)")
        return f"{prim.GetPath()} inputs:intensity={float(val)}"

    def x_variant():
        r = _no_cook_error(drv.call(
            "manage_variant_set", node=st.get("sphere", ""), prim_path=sphere_prim(),
            action="create", variant_set="ctxprobe_vset", variants=["a", "b"]))
        if r.get("node"):
            roots.append(r["node"])
        return f"variant set on {sphere_prim()}"

    def x_collection():
        r = _no_cook_error(drv.call(
            "manage_collection", node=st.get("sphere", ""), prim_path=sphere_prim(),
            action="create", collection_name="ctxprobe_coll", paths=[sphere_prim()]))
        if r.get("node"):
            roots.append(r["node"])
        return f"collection on {sphere_prim()}"

    def x_instancer():
        r = _no_cook_error(drv.call(
            "create_point_instancer", node=st.get("sphere", ""),
            prim_path="/ctxprobe_instancer", prototypes=[sphere_prim()],
            positions=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]))
        if r.get("created_node"):
            roots.append(r["created_node"])
        return f"instances={r.get('instance_count')}"

    extended = []
    _run_steps([
        ("mtlx_in_lop", x_mtlx),
        ("usdlux_light", x_light),
        ("variant_set", x_variant),
        ("collection", x_collection),
        ("point_instancer", x_instancer),
        _undo_unwind_step(drv, hou, roots),
    ], extended, gaps)

    revert_ok, revert_detail = _revert(hou, roots)
    golden = {"ok": all(s["ok"] for s in golden_steps), "steps": golden_steps,
              "revert_ok": revert_ok}
    if not revert_ok:
        gaps.append(f"revert: {revert_detail}")
    return {"golden": golden, "extended": extended, "gaps": gaps}


def _probe_cop(drv, hou):
    # The golden drives the VERIFIED COP surface: cops_create_network (cop2net)
    # with Cop2/noise + Cop2/null — both live-probed in the connectivity catalog.
    # The modern `copnet` category has NO verified generator spelling ("noise"
    # exists only as Cop2 in the catalogs), and the whole cops_* tool family is
    # built on cop2net — probing an unverified modern spelling would manufacture
    # a phantom failure, not measure capability.
    st, roots = {}, []

    def s_network():
        r = drv.call("cops_create_network", parent="/obj", name="ctxprobe_cop",
                     initial_nodes=["noise"])
        st["net"] = r["network_path"]; roots.append(r["network_path"])
        init = r.get("initial_nodes") or []
        if not init:
            raise _StepFail("network created but no noise node inside")
        st["noise"] = init[0]["path"]
        return f"{st['net']} + {st['noise']}"

    def s_null():
        r = drv.call("cops_create_node", parent=st.get("net", ""), type="null",
                     name="ctxprobe_out")
        st["out"] = r["path"]
        return r["path"]

    def s_wire():
        drv.call("cops_connect", source=st.get("noise", ""), target=st.get("out", ""))
        return "noise -> null"

    def s_cook():
        r = drv.call("cops_batch_cook", nodes=[st.get("out", "")])
        if r.get("cooked") != 1:
            first = (r.get("results") or [{}])[0]
            raise _StepFail(f"cook failed: {first.get('message') or first.get('errors')}")
        return "cooked 1/1"

    def s_layer():
        r = drv.call("cops_read_layer_info", node=st.get("out", ""))
        if r.get("cook_status") == "error":
            raise _StepFail(f"cook_status=error: {r.get('errors')}")
        return (f"cook_status={r.get('cook_status')} resolution={r.get('resolution')} "
                f"planes={len(r.get('planes') or [])}")

    golden_steps, gaps = [], []
    _run_steps([
        ("create_cop_network", s_network),
        ("create_null", s_null),
        ("wire_noise_to_null", s_wire),
        ("cook", s_cook),
        ("read_layer_info", s_layer),
    ], golden_steps, gaps)

    def x_ptex():
        r = drv.call("cops_procedural_texture", parent=st.get("net", ""),
                     resolution=[256, 256], name="ctxprobe_ptex")
        return r.get("path", "created")

    def x_aovs():
        # exr_path is authored as a parm string only — nothing cooks the file
        # node here, so no disk IO happens headless.
        r = drv.call("cops_composite_aovs", parent="/obj",
                     exr_path="$HIP/ctxprobe_aovs.exr",
                     aov_list=["beauty", "diffuse"], name="ctxprobe_aovcomp")
        if r.get("network_path"):
            roots.append(r["network_path"])
        return f"{r.get('network_path')} layers={len(r.get('layers') or [])}"

    def x_to_mtlx():
        # mtlximage is the repo's single-sourced MaterialX VOP spelling
        # (synapse.core.mtlx_types.MTLX_IMAGE) and carries a real `file` parm.
        ri = drv.call("create_node", parent="/mat", type="mtlximage",
                      name="ctxprobe_mtlximg")
        roots.append(ri["path"])
        r = drv.call("cops_to_materialx", cop_path=st.get("noise", ""),
                     material_node=ri["path"], input_name="file")
        if not str(r.get("op_path", "")).startswith("op:"):
            raise _StepFail(f"op path not authored: {r.get('op_path')}")
        return r["op_path"]

    extended = []
    _run_steps([
        ("procedural_texture", x_ptex),
        ("composite_aovs", x_aovs),
        ("cops_to_materialx", x_to_mtlx),
        _undo_unwind_step(drv, hou, roots),
    ], extended, gaps)

    revert_ok, revert_detail = _revert(hou, roots)
    golden = {"ok": all(s["ok"] for s in golden_steps), "steps": golden_steps,
              "revert_ok": revert_ok}
    if not revert_ok:
        gaps.append(f"revert: {revert_detail}")
    return {"golden": golden, "extended": extended, "gaps": gaps}


def _probe_top(drv, hou):
    st, roots = {}, []

    def s_topnet():
        r = drv.call("create_node", parent="/obj", type="topnet", name="ctxprobe_top")
        st["topnet"] = r["path"]; roots.append(r["path"])
        return r["path"]

    def s_wedge():
        r = drv.call("tops_setup_wedge", topnet_path=st.get("topnet", ""),
                     wedge_name="ctxprobe_wedge",
                     attributes=[{"name": "ctxval", "type": "float",
                                  "start": 0.0, "end": 1.0, "steps": 3}])
        st["wedge"] = r["wedge_node"]
        return r["wedge_node"]

    def s_count():
        drv.call("set_parm", node=st.get("wedge", ""), parm="wedgecount", value=3)
        return "wedgecount=3"

    def s_generate():
        # GENERATE, not cook — the frozen golden rule for TOPs.
        r = drv.call("tops_generate_items", node=st.get("wedge", ""))
        return f"generated item_count={r.get('item_count')}"

    def s_verify():
        r = drv.call("tops_get_work_items", node=st.get("wedge", ""),
                     include_attributes=False)
        total = r.get("total_items")
        if total != 3:
            raise _StepFail(f"total_items={total} (expected 3)")
        return "3 work items"

    golden_steps, gaps = [], []
    _run_steps([
        ("create_topnet", s_topnet),
        ("setup_wedge", s_wedge),
        ("set_wedgecount_3", s_count),
        ("generate_items", s_generate),
        ("verify_3_work_items", s_verify),
    ], golden_steps, gaps)

    def x_cook():
        r = drv.call("tops_cook_node", node=st.get("wedge", ""), blocking=True)
        if r.get("status") not in ("cooked", "cooking"):
            raise _StepFail(f"status={r.get('status')}: {r.get('error')}")
        return f"status={r.get('status')} work_items={r.get('work_items')}"

    def x_stats():
        r = drv.call("tops_get_cook_stats", node=st.get("topnet", ""))
        if (r.get("total_items") or 0) < 3:
            raise _StepFail(f"total_items={r.get('total_items')} (expected >= 3)")
        return f"total_items={r.get('total_items')} by_state={r.get('by_state')}"

    extended = []
    _run_steps([
        ("local_cook_3", x_cook),
        ("cook_stats", x_stats),
        _undo_unwind_step(drv, hou, roots),
    ], extended, gaps)

    revert_ok, revert_detail = _revert(hou, roots)
    golden = {"ok": all(s["ok"] for s in golden_steps), "steps": golden_steps,
              "revert_ok": revert_ok}
    if not revert_ok:
        gaps.append(f"revert: {revert_detail}")
    return {"golden": golden, "extended": extended, "gaps": gaps}


def _probe_dop(drv, hou):
    # No dop_* verb family exists — the golden runs entirely on GENERIC verbs.
    # If they refuse DOP context the golden fails honestly: that IS C.5's target.
    st, roots = {}, []

    def s_dopnet():
        r = drv.call("create_node", parent="/obj", type="dopnet", name="ctxprobe_dop")
        st["dopnet"] = r["path"]; roots.append(r["path"])
        return r["path"]

    def s_smokeobject():
        r = drv.call("create_node", parent=st.get("dopnet", ""),
                     type="smokeobject", name="ctxprobe_smoke")
        st["smoke"] = r["path"]
        return r["path"]

    def s_smokesolver():
        r = drv.call("create_node", parent=st.get("dopnet", ""),
                     type="smokesolver", name="ctxprobe_solver")
        st["solver"] = r["path"]
        return r["path"]

    def s_wire():
        drv.call("connect_nodes", source=st.get("smoke", ""),
                 target=st.get("solver", ""))
        return "smokeobject -> smokesolver"

    def s_divsize():
        drv.call("set_parm", node=st.get("smoke", ""), parm="divsize",
                 value=_DOP_DIVSIZE)
        return f"divsize={_DOP_DIVSIZE}"

    def s_cook3():
        # Frame stepping via hou is sanctioned; each pull cooks the sim to the
        # playhead. 3 frames at coarse divisions keeps this well under budget.
        solver = hou.node(st.get("solver", ""))
        if solver is None:
            raise _StepFail("verify: solver node missing")
        for f in _DOP_FRAMES:
            hou.setFrame(f)
            solver.cook(force=True)
        return f"cooked frames {_DOP_FRAMES[0]}..{_DOP_FRAMES[-1]}"

    def s_verify():
        smoke = hou.node(st.get("smoke", ""))
        if smoke is None:
            raise _StepFail("verify: smokeobject node missing")
        sim = smoke.simulation()
        objs = sim.objects() if sim is not None else ()
        if not objs:
            raise _StepFail("verify: simulation has no objects")
        density = objs[0].findSubData("density")
        if density is None:
            raise _StepFail(
                f"verify: sim object '{objs[0].name()}' carries no density field")
        return f"objects={len(objs)} density=present on '{objs[0].name()}'"

    golden_steps, gaps = [], []
    _run_steps([
        ("create_dopnet", s_dopnet),
        ("create_smokeobject", s_smokeobject),
        ("create_smokesolver", s_smokesolver),
        ("wire_object_to_solver", s_wire),
        ("set_coarse_divisions", s_divsize),
        ("cook_3_frames", s_cook3),
        ("verify_density_field", s_verify),
    ], golden_steps, gaps)

    def _mk_create(step_type, name):
        def _fn():
            r = drv.call("create_node", parent=st.get("dopnet", ""),
                         type=step_type, name=name)
            return r["path"]
        return _fn

    def x_rbd():
        ro = drv.call("create_node", parent=st.get("dopnet", ""),
                      type="rbdpackedobject", name="ctxprobe_rbdobj")
        rs = drv.call("create_node", parent=st.get("dopnet", ""),
                      type="rigidbodysolver", name="ctxprobe_rbdsolver")
        drv.call("connect_nodes", source=ro["path"], target=rs["path"])
        return f"{ro['path']} -> {rs['path']}"

    extended = []
    _run_steps([
        ("sop_volumesource", _mk_create("volumesource", "ctxprobe_volsrc")),
        ("pyrosolver", _mk_create("pyrosolver", "ctxprobe_pyro")),
        ("vellum_min", _mk_create("vellumsolver", "ctxprobe_vellum")),
        ("rbd_min", x_rbd),
        _undo_unwind_step(drv, hou, roots),
    ], extended, gaps)

    try:
        hou.setFrame(1)  # leave the playhead where the next context expects it
    except Exception:  # noqa: BLE001
        pass
    revert_ok, revert_detail = _revert(hou, roots)
    golden = {"ok": all(s["ok"] for s in golden_steps), "steps": golden_steps,
              "revert_ok": revert_ok}
    if not revert_ok:
        gaps.append(f"revert: {revert_detail}")
    return {"golden": golden, "extended": extended, "gaps": gaps}


def _probe_mat(drv, hou):
    st, roots = {}, []

    def s_anchor():
        # Lop/null is probe-confirmed — the lightest possible stage anchor for
        # the handler chain (create_usd_prim et al. wire after an existing LOP).
        r = drv.call("create_node", parent="/stage", type="null",
                     name="ctxprobe_mat_anchor")
        st["anchor"] = r["path"]; roots.append(r["path"])
        return r["path"]

    def s_box():
        r = _no_cook_error(drv.call(
            "create_usd_prim", node=st.get("anchor", ""),
            prim_path="/ctxprobe_box", prim_type="Cube"))
        st["boxlop"] = r["created_node"]; roots.append(r["created_node"])
        return f"Cube at /ctxprobe_box via {r['created_node']}"

    def s_material():
        r = drv.call("create_material", node=st.get("boxlop", st.get("anchor", "")),
                     name="ctxprobe_mtl", base_color=[0.9, 0.1, 0.1])
        st["matlib"] = r["matlib_path"]; st["mat_usd"] = r["material_usd_path"]
        roots.append(r["matlib_path"])
        return f"{r['material_usd_path']} ({r['shader_type']})"

    def s_assign():
        r = drv.call("assign_material", node=st.get("matlib", ""),
                     prim_pattern="/ctxprobe_box",
                     material_path=st.get("mat_usd", ""))
        st["assign"] = r["node_path"]; roots.append(r["node_path"])
        return r["node_path"]

    def s_read():
        r = drv.call("read_material", node=st.get("assign", ""),
                     prim_path="/ctxprobe_box")
        if not r.get("has_material") or not r.get("material_path"):
            raise _StepFail(f"binding not visible: has_material={r.get('has_material')} "
                            f"material_path={r.get('material_path')!r}")
        return f"bound to {r['material_path']}"

    golden_steps, gaps = [], []
    _run_steps([
        ("create_stage_anchor", s_anchor),
        ("create_probe_box", s_box),
        ("create_material", s_material),
        ("assign_material", s_assign),
        ("read_material_verify", s_read),
    ], golden_steps, gaps)

    def x_textured():
        # Procedural texture input, no file IO: point diffuse_map at a live COP
        # via the op: protocol (nothing ever cooks the image path headless).
        rc = drv.call("cops_create_network", parent="/obj", name="ctxprobe_mat_cop",
                      initial_nodes=["noise"])
        roots.append(rc["network_path"])
        init = rc.get("initial_nodes") or []
        noise = init[0]["path"] if init else rc["network_path"]
        r = drv.call("create_textured_material",
                     node=st.get("assign", st.get("anchor", "")),
                     name="ctxprobe_tex", diffuse_map=f"op:{noise}")
        if r.get("matlib_path"):
            roots.append(r["matlib_path"])
        return f"{r.get('matlib_path')} diffuse=op:{noise}"

    def x_lightlink():
        rl = drv.call("create_node", parent="/stage", type="distantlight",
                      name="ctxprobe_mat_light")
        roots.append(rl["path"])
        prim = _find_prim(hou, rl["path"], "DistantLight")
        r = _no_cook_error(drv.call(
            "configure_light_linking", node=rl["path"],
            light_path=str(prim.GetPath()), action="include",
            geo_paths=["/ctxprobe_box"]))
        if r.get("node"):
            roots.append(r["node"])
        return f"light-link {prim.GetPath()} -> /ctxprobe_box"

    extended = []
    _run_steps([
        ("textured_material", x_textured),
        ("light_linking", x_lightlink),
        _undo_unwind_step(drv, hou, roots),
    ], extended, gaps)

    revert_ok, revert_detail = _revert(hou, roots)
    golden = {"ok": all(s["ok"] for s in golden_steps), "steps": golden_steps,
              "revert_ok": revert_ok}
    if not revert_ok:
        gaps.append(f"revert: {revert_detail}")
    return {"golden": golden, "extended": extended, "gaps": gaps}


_PROBES = {
    "sop": _probe_sop, "lop": _probe_lop, "cop": _probe_cop,
    "top": _probe_top, "dop": _probe_dop, "mat": _probe_mat,
}


def _generic_entry():
    # `generic` is the classification bucket for context-agnostic verbs — its
    # capability is exercised THROUGH the six real contexts above, so its golden
    # is vacuously true with zero steps (deterministic, never misleading gaps).
    return {"golden": {"ok": True, "steps": [], "revert_ok": None},
            "extended": [], "gaps": []}


# ---------------------------------------------------------------------------
# Catalog assembly
# ---------------------------------------------------------------------------

def build_catalog(only: str = None) -> dict:
    import hou

    # The probe drives the WORKTREE's package, not any installed copy.
    pkg_root = str(_REPO / "python")
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    import synapse
    from synapse.server.handlers import SynapseHandler
    from synapse.core.protocol import SynapseCommand

    hou.hipFile.clear(suppress_save_prompt=True)  # frozen boot rule; never saved

    drv = _Driver(SynapseHandler(), SynapseCommand)
    registered = drv.registered_types
    by_ctx, unclassified = _classify(registered)

    run_order = PROBEABLE if only is None else (only,)
    contexts = {}
    for ctx in run_order:
        try:
            entry = _PROBES[ctx](drv, hou)
        except Exception as e:  # noqa: BLE001 — a context crash never aborts the run
            entry = {"golden": {"ok": False,
                                "steps": [{"step": "probe_internal_error", "ok": False,
                                           "detail": f"{type(e).__name__}: {e}"[:300]}],
                                "revert_ok": None},
                     "extended": [], "gaps": ["probe_internal_error"]}
        contexts[ctx] = {
            "commands": by_ctx.get(ctx, []),
            "golden": entry["golden"],
            "extended": entry["extended"],
            "gaps": entry["gaps"],
        }
    if only is None:
        gen = _generic_entry()
        contexts["generic"] = {"commands": by_ctx.get("generic", []), **gen}

    # blake2b covers `contexts` ONLY — generated/summary/unclassified sit outside
    # the digest (the timestamp must never break determinism of the stamped truth).
    stamp = hashlib.blake2b(
        json.dumps(contexts, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    summary = {ctx: {"golden_ok": bool(entry["golden"]["ok"]),
                     "gaps": len(entry["gaps"])}
               for ctx, entry in contexts.items()}
    return {
        "schema": SCHEMA,
        "houdini_version": hou.applicationVersionString(),
        "synapse_version": getattr(synapse, "__version__", "unknown"),
        "generated": datetime.now(timezone.utc).isoformat(),
        "handler_command_count": len(registered),
        "contexts": contexts,
        "unclassified": unclassified,
        "summary": summary,
        "blake2b": stamp,
    }


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(tmp, path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--context", choices=PROBEABLE, default=None,
                    help="probe ONE context (artifact carries just that context)")
    ap.add_argument("--out", default=None,
                    help="artifact path (cwd-relative); default = "
                         "harness/notes/context_capability_21.json")
    a = ap.parse_args(argv)

    catalog = build_catalog(only=a.context)
    out_fp = Path(a.out) if a.out else DEFAULT_OUT
    _atomic_write(out_fp, catalog)  # rc 0 iff this write landed

    parts = []
    for ctx in CONTEXTS:
        s = catalog["summary"].get(ctx)
        if s is not None:
            parts.append(f"{ctx}:{'OK' if s['golden_ok'] else 'FAIL'}/{s['gaps']}")
    sys.stdout.write(
        f"CONTEXT-CAPABILITY: build={catalog['houdini_version']} "
        f"commands={catalog['handler_command_count']} "
        f"[{' '.join(parts)}] blake2b={catalog['blake2b'][:12]} -> {out_fp}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
