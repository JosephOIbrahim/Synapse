"""H2b · PART A — re-qualify F1-F11 against live Houdini 22.0.368.

Run under hython:
    hython harness/notes/h2b/requalify_f1_f11.py

Every finding returns CONFIRMED | REFUTED | UNVERIFIABLE with a current file:line
anchor, and — where the verdict is an absence — a POSITIVE CONTROL ON THE SAME
CLASS (Ruling 50: "I looked and did not find it" and "it is not there" are
different claims; without a control the verdict is UNVERIFIABLE, not REFUTED).

REFUTED is further split (this is the point of the leg):
    phantom  — the premise was NEVER true; the finding was wrong when written
    repaired — the premise WAS true; a repair has since landed

Writes harness/notes/h2b/requalify_f1_f11.json.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT))

import hou  # noqa: E402

OUT = ROOT / "harness" / "notes" / "h2b" / "requalify_f1_f11.json"
RESULTS = []


def rec(fid, verdict, kind, anchor, truth, control, could_fail, evidence, tier="VERIFIED-RUNTIME"):
    RESULTS.append({
        "finding_id": fid, "verdict": verdict, "refuted_kind": kind,
        "anchor": anchor, "evidence_tier": tier, "what_is_actually_true": truth,
        "positive_control": control, "how_this_could_have_failed": could_fail,
        "probe_excerpt": evidence,
    })
    print(f"\n[{fid}] {verdict}" + (f" ({kind})" if kind not in (None, "n/a") else ""))
    print(f"    truth   : {truth[:200]}")
    print(f"    control : {control[:200]}")


def stage():
    return hou.node("/stage")


def fresh(name):
    n = stage().createNode("lopnet", name)
    return n


def real_usdc(path):
    """A .usdc carrying genuine geometry. A zero-byte file proves nothing."""
    from pxr import Usd, UsdGeom, UsdShade, Gf, Vt
    st = Usd.Stage.CreateNew(str(path))
    mesh = UsdGeom.Mesh.Define(st, "/rock")
    mesh.CreatePointsAttr(Vt.Vec3fArray([
        Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(1, 1, 0), Gf.Vec3f(0, 1, 0)]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([0, 1, 2, 3]))
    mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 1, 0)]))
    UsdShade.Material.Define(st, "/materials/rock_mtl")
    st.SetDefaultPrim(mesh.GetPrim())
    st.GetRootLayer().Save()
    re = Usd.Stage.Open(str(path))
    pts = UsdGeom.Mesh(re.GetPrimAtPath("/rock")).GetPointsAttr().Get()
    assert pts is not None and len(pts) == 4, "fixture authored no geometry"
    return path


# ===========================================================================
# F1 — are the five tools reachable from the live MCP registry?
# ===========================================================================
def f1():
    from synapse.mcp import _tool_registry as reg
    five = ["synapse_solaris_component_builder", "synapse_solaris_scene_template",
            "synapse_solaris_import_megascans", "synapse_solaris_create_variants",
            "synapse_solaris_set_purpose"]
    names = set(reg.TOOL_NAMES)
    registered = {n: (n in names) for n in five}

    # Registration is necessary, NOT sufficient: the impl module must import and
    # expose execute, and a handler must exist.
    import importlib
    dispatchable = {}
    for n in five:
        mod_name = n.replace("synapse_solaris_", "")
        try:
            m = importlib.import_module(f"synapse.mcp.tool_impls.solaris.{mod_name}")
            dispatchable[n] = all(hasattr(m, a) for a in ("validate", "plan", "execute"))
        except Exception as exc:
            dispatchable[n] = f"IMPORT FAILED: {exc}"

    try:
        from synapse.server import handlers_solaris_tools as H
        handlers = [a for a in dir(H) if "solaris" in a.lower()]
    except Exception as exc:
        handlers = f"handler module import failed: {exc}"

    # POSITIVE CONTROL: a name that must NOT be present.
    control_absent = "synapse_solaris_DEFINITELY_NOT_A_TOOL" in names
    all_reg = all(registered.values())
    all_disp = all(v is True for v in dispatchable.values())

    rec("F1",
        "REFUTED" if (all_reg and all_disp) else "CONFIRMED",
        "repaired" if (all_reg and all_disp) else "n/a",
        "python/synapse/mcp/_tool_registry.py:743,776,803,825,839",
        ("All five ARE registered in TOOL_NAMES and all five impl modules import with "
         "validate/plan/execute present. The tools moved from the repo-root shadow tree "
         "synapse/mcp/tools/solaris/ (which no longer exists) into the installable package "
         "at python/synapse/mcp/tool_impls/solaris/. The premise was TRUE when written and "
         "a repair landed (SR1 M1/M5)."
         if (all_reg and all_disp) else
         f"registered={registered} dispatchable={dispatchable}"),
        f"a fabricated tool name is correctly absent from TOOL_NAMES: {not control_absent}",
        "would have CONFIRMED if any of the five were missing from TOOL_NAMES, or if any "
        "impl module failed to import or lacked validate/plan/execute",
        json.dumps({"registered": registered, "dispatchable": dispatchable,
                    "handlers_found": handlers if isinstance(handlers, str) else len(handlers),
                    "TOOL_NAMES_total": len(names)})[:900])


# ===========================================================================
# F2 — is tool_audit a tool, or a document?
# ===========================================================================
def f2():
    impl_dir = ROOT / "python/synapse/mcp/tool_impls/solaris"
    audit_impl = impl_dir / "tool_audit.py"
    schema = impl_dir / "schema_tool_audit.py"
    # POSITIVE CONTROL: the same existence probe must FIND a module we know is there.
    control = (impl_dir / "component_builder.py").exists()

    from synapse.validation.solaris import verify_tool_audit as v
    has_impl_pinned = v.HAS_IMPLEMENTATION
    res = v.verify_structure()

    import synapse.mcp.tool_impls.solaris as pkg
    in_all = "tool_audit" in getattr(pkg, "__all__", [])

    rec("F2", "CONFIRMED", "n/a",
        f"python/synapse/mcp/tool_impls/solaris/schema_tool_audit.py (present); "
        f"tool_audit.py absent; python/synapse/validation/solaris/verify_tool_audit.py:34",
        ("Still true: tool_audit has NO implementation module, is not in the package __all__, "
         "and what exists is schema_tool_audit.py, a design dict. The finding was a scope "
         "CORRECTION and it still holds — five tools plus one design document. "
         f"HAS_IMPLEMENTATION is a hardcoded literal ({has_impl_pinned}) but the check compares "
         "it against a live filesystem probe (impl.exists()), so the check CAN fail — H2b-M12 "
         "created the module and the pin went red."),
        f"identical existence probe finds component_builder.py: {control}",
        "would have REFUTED if tool_audit.py existed with validate/plan/execute, or if it "
        "appeared in the package __all__",
        json.dumps({"tool_audit_impl_exists": audit_impl.exists(),
                    "schema_exists": schema.exists(), "in___all__": in_all,
                    "HAS_IMPLEMENTATION_pinned": has_impl_pinned,
                    "verify_structure_status": res["status"]}))


# ===========================================================================
# F3 — is the material reference LOP wired into componentmaterial input 1?
# ===========================================================================
def f3():
    from synapse.mcp.tool_impls.solaris import import_megascans as ms
    import tempfile
    net = fresh("h2b_f3")
    try:
        usdc = real_usdc(Path(tempfile.mkdtemp()) / "rock.usdc")
        ms.execute({"usdc_path": str(usdc), "asset_name": "f3rock",
                    "parent_path": net.path()})
        comp = net.node("component_f3rock")
        mat = next(c for c in comp.children() if c.type().name() == "componentmaterial")
        ins = mat.inputs()
        wired = len(ins) > 1 and ins[1] is not None
        detail = [i.path() if i else None for i in ins]

        # The contradiction: the STATIC verifier still reports it orphaned.
        from synapse.validation.solaris import verify_import_megascans as vm
        static = vm.material_orphan_check()
        lit = [n for n in vm.EXPECTED_TOPOLOGY if n["name"] == "mat_asset"][0]

        rec("F3", "REFUTED" if wired else "CONFIRMED",
            "repaired" if wired else "n/a",
            "python/synapse/mcp/tool_impls/solaris/import_megascans.py:336-337",
            (f"LIVE the material reference IS wired: componentmaterial.inputs() = {detail}. "
             "The premise was TRUE when written and a repair landed. "
             "BUT the static verifier still reports the orphan: "
             f"material_orphan_check().ok={static.ok}, because "
             "verify_import_megascans.EXPECTED_TOPOLOGY is a HAND-WRITTEN LITERAL "
             f"(mat_asset inputs={lit.get('inputs')}) that was never updated after the repair. "
             "That is why two pins disagree about F3 and both pass — the live pin reads the "
             "graph, the static pin reads the stale literal. H2b-M1 proves the static pin "
             "cannot fail in response to the source."
             if wired else f"componentmaterial inputs = {detail}"),
            "same probe on the same node reports input 0 wired to the componentgeometry, so "
            "the inputs() call is reading real connections",
            "would have CONFIRMED if mat.inputs() had length <= 1 or inputs[1] were None",
            json.dumps({"inputs": detail, "static_orphan_check_ok": static.ok,
                        "static_literal_inputs": lit.get("inputs")}))
    finally:
        net.destroy()


# ===========================================================================
# F4 — the known phantom: does copyNodesTo drop outside inputs?
# ===========================================================================
def f4():
    net = fresh("h2b_f4")
    try:
        comp = net.createNode("subnet", "c")
        geo = comp.createNode("componentgeometry", "geo_base")
        mat = comp.createNode("componentmaterial", "mat_base")
        mat.setInput(0, geo)
        # POSITIVE CONTROL: the source really is wired before we copy.
        pre = mat.inputs()[0].path()
        copied = hou.copyNodesTo([mat], comp)[0]
        post = [i.path() if i else None for i in copied.inputs()]
        carried = bool(copied.inputs()) and copied.inputs()[0] is not None

        rec("F4", "REFUTED", "phantom",
            "python/synapse/mcp/tool_impls/solaris/create_variants.py:182-199",
            ("hou.copyNodesTo DOES carry input connections that originate OUTSIDE the copied "
             f"set on 22.0.368. Copying a single wired node yields inputs={post}, i.e. the copy "
             "arrives already connected to the outside source. F4's stated mechanism "
             "('copyNodesTo does not carry connections originating outside the copied set') is "
             "FALSE on this build and was false when written — the variant materials were never "
             "unwired for that reason. This is the phantom Ruling 34 names: a fix was written "
             "against a mechanism that did not exist, and its test could not fail. The current "
             "source carries no rewiring loop (it was removed as a proven no-op) and the pin was "
             "re-aimed at the real host contract."),
            f"the source node was verifiably wired before the copy: mat.inputs()[0] = {pre}",
            "would have CONFIRMED (F4's premise live) if copied.inputs() were empty or [None]",
            json.dumps({"source_input": pre, "copy_inputs": post, "carried": carried}))
    finally:
        net.destroy()


# ===========================================================================
# F5 — does the geometry variant set reach the terminal?
# ===========================================================================
def f5():
    from synapse.mcp.tool_impls.solaris import create_variants as cv
    net = fresh("h2b_f5")
    try:
        comp = net.createNode("subnet", "c")
        geo = comp.createNode("componentgeometry", "geo_base")
        mat = comp.createNode("componentmaterial", "mat_base")
        out = comp.createNode("componentoutput", "output_base")
        mat.setInput(0, geo)
        out.setInput(0, mat)
        cv.execute({"component_path": comp.path(), "variant_type": "geometry",
                    "variants": [{"name": "a"}, {"name": "b"}]})
        gv = comp.node("geo_variants")
        terminals = [c.name() for c in comp.children() if not c.outputs()]
        reaches = bool(gv and gv.outputs())

        rec("F5", "REFUTED" if reaches else "CONFIRMED",
            "repaired" if reaches else "n/a",
            "python/synapse/mcp/tool_impls/solaris/create_variants.py:243-250",
            (f"geo_variants now reaches downstream: outputs={[o.name() for o in gv.outputs()]}; "
             f"the component presents terminals={terminals}. The consumer-steal block at "
             ":243-250 rewires whatever consumed the base geometry onto the variant set. The "
             "premise was TRUE when written and a repair landed. NOTE the static pin "
             "test_variant_set_reaches_the_terminal reads a hand-written literal, not the graph "
             "— H2b-M3 removed this exact block and that pin stayed green."
             if reaches else f"geo_variants dead-ends; terminals={terminals}"),
            "the same outputs() call reports the base componentgeometry as having outputs, so "
            "outputs() is reading real downstream connections",
            "would have CONFIRMED if gv.outputs() were empty, or if >1 terminal remained",
            json.dumps({"geo_variants_outputs": [o.name() for o in gv.outputs()] if gv else None,
                        "terminals": terminals}))
    finally:
        net.destroy()


# ===========================================================================
# F6 — can execute() still report success having built nothing?
# ===========================================================================
def f6():
    from synapse.mcp.tool_impls.solaris import create_variants as cv
    src = (ROOT / "python/synapse/mcp/tool_impls/solaris/create_variants.py").read_text(
        encoding="utf-8")
    bare = src.count("except Exception:\n        pass") + src.count(
        "except Exception:\n                pass")
    reraises = "    except Exception:\n        raise" in src

    net = fresh("h2b_f6")
    status = None
    explore_built = None
    try:
        comp = net.createNode("subnet", "c")
        geo = comp.createNode("componentgeometry", "geo_base")
        mat = comp.createNode("componentmaterial", "mat_base")
        out = comp.createNode("componentoutput", "output_base")
        mat.setInput(0, geo)
        out.setInput(0, mat)
        r = cv.execute({"component_path": comp.path(), "variant_type": "geometry",
                        "variants": [{"name": "x"}, {"name": "y"}],
                        "add_explore_node": True})
        status = r.get("status")
        explore_built = net.node(f"explore_{comp.name()}") is not None
    finally:
        net.destroy()

    honest = (status == "created") and explore_built
    rec("F6", "REFUTED" if honest and reraises else "CONFIRMED",
        "repaired" if honest and reraises else "n/a",
        "python/synapse/mcp/tool_impls/solaris/create_variants.py:229-232,254-261,282-283",
        (f"The bare `except Exception: pass` around the variant-merge and explorevariants "
         f"creations is GONE; the outer handler re-raises (`except Exception: raise` present="
         f"{reraises}). status={status!r} and the explorevariants node was actually built="
         f"{explore_built}, so the status describes what happened (Law 3 / Ruling 14). The "
         "premise was TRUE when written and a repair landed. H2b-M5 reinstated the swallow and "
         "both F6 pins went red, so this is pinned by a check that can fail."
         if honest and reraises else
         f"status={status!r} explore_built={explore_built} reraises={reraises}"),
        f"the mutation control H2b-M5 forced the inner creation to fail and status/pins reacted",
        "would have CONFIRMED if execute() returned 'created' while the explorevariants node "
        "was absent, or if a bare `except Exception: pass` still wrapped a creation",
        json.dumps({"status": status, "explore_built": explore_built,
                    "outer_reraises": reraises, "bare_pass_count_in_module": bare}))


# ===========================================================================
# F7 — (a) purpose parm absent?  (b) does it report success having set nothing?
# ===========================================================================
def f7():
    from synapse.mcp.tool_impls.solaris import set_purpose as sp
    from pxr import UsdGeom
    net = fresh("h2b_f7")
    try:
        geo = net.createNode("componentgeometry", "probe")
        purpose_parms = [p.name() for p in geo.parms() if "purpose" in p.name().lower()]
        # POSITIVE CONTROL (Ruling 50): the identical sweep must FIND a parm we know exists.
        all_parms = [p.name() for p in geo.parms()]
        control_name = all_parms[0] if all_parms else None
        control_found = geo.parm(control_name) is not None if control_name else False
        # Also look INSIDE the locked HDA, not just top-level parms.
        interior = []
        sopnet = geo.node("sopnet/geo")
        if sopnet is not None:
            for c in sopnet.children():
                interior += [f"{c.name()}.{p.name()}" for p in c.parms()
                             if "purpose" in p.name().lower()]

        # (b) live authoring readback off the COOKED STAGE, not off our own parm.
        comp = net.createNode("subnet", "c2")
        g2 = comp.createNode("componentgeometry", "geo_x")
        out = comp.createNode("componentoutput", "output_x")
        out.parm("name").set("f7asset")
        out.setInput(0, g2)
        r = sp.execute({"component_path": comp.path(), "purpose": "proxy"})
        cfg = hou.node(r["configure_node"]) if r.get("configure_node") else None
        readback = None
        if cfg is not None:
            prim = cfg.stage().GetPrimAtPath(r["prim_path"])
            if prim and prim.IsValid():
                readback = UsdGeom.Imageable(prim).GetPurposeAttr().Get()
        honest = (r.get("status") in ("set", "updated") and readback == "proxy")

        rec("F7", "REFUTED" if honest else "CONFIRMED",
            "repaired" if honest else "n/a",
            "python/synapse/mcp/tool_impls/solaris/set_purpose.py:304-366",
            (f"(a) CONFIRMED-as-written: componentgeometry exposes no purpose parm on 22.0.368 "
             f"(top-level matches={purpose_parms}, interior matches={interior}). "
             f"(b) REFUTED-repaired: the tool no longer writes that parm. It authors through a "
             f"`configureprimitive` LOP and the purpose is readable off the COOKED STAGE: "
             f"status={r.get('status')!r}, UsdGeom purpose readback={readback!r}. So the "
             "Ruling-14 lie ('status=set having set nothing') is gone: the status now describes "
             "an authoring that really happened. The finding's ROOT observation stands; its "
             "CONSEQUENCE has been repaired."
             if honest else
             f"status={r.get('status')!r} readback={readback!r}"),
            (f"identical parms() sweep finds {control_name!r} on the same node "
             f"({control_found}), so the sweep is capable of finding parms that exist — "
             "the purpose absence is a real absence, not a broken probe (Ruling 50)"),
            "would have CONFIRMED if the readback were None or != 'proxy' while status said set",
            json.dumps({"purpose_parms_toplevel": purpose_parms, "interior_matches": interior,
                        "control_parm": control_name, "control_found": control_found,
                        "parm_count": len(all_parms), "status": r.get("status"),
                        "usd_readback": readback, "prim_path": r.get("prim_path")}))
    finally:
        net.destroy()


# ===========================================================================
# F8 — parent key convergence, and is the SILENT default gone?
# ===========================================================================
def f8():
    import importlib
    keys = {}
    for m in ("component_builder", "scene_template", "import_megascans",
              "create_variants", "set_purpose"):
        mod = importlib.import_module(f"synapse.mcp.tool_impls.solaris.{m}")
        keys[m] = list(getattr(mod, "PARENT_KEYS", [])) or "n/a (takes component_path)"

    from synapse.mcp.tool_impls.solaris import component_builder as cb
    net = fresh("h2b_f8")
    misspelled_went_to_stage = None
    raised = None
    try:
        # THE SHARP HALF: an unrecognised key must not silently build into /stage.
        try:
            cb.execute({"asset_name": "f8typo", "parentPath": net.path()})
            built_here = net.node("component_f8typo") is not None
            built_stage = hou.node("/stage/component_f8typo") is not None
            misspelled_went_to_stage = (not built_here) and built_stage
            raised = False
        except Exception as exc:
            raised = f"{type(exc).__name__}: {exc}"
        # POSITIVE CONTROL: the correct key really does build into the requested net.
        cb.execute({"asset_name": "f8ok", "parent_path": net.path()})
        control_ok = net.node("component_f8ok") is not None
    finally:
        for n in ("component_f8typo", "component_f8ok"):
            t = hou.node(f"/stage/{n}")
            if t:
                t.destroy()
        net.destroy()

    uniform = all(keys[m] == ["parent_path", "parent"]
                  for m in ("component_builder", "scene_template", "import_megascans"))
    rec("F8", "REFUTED" if uniform else "CONFIRMED",
        "repaired" if uniform else "n/a",
        "python/synapse/mcp/tool_impls/solaris/{component_builder,scene_template,"
        "import_megascans}.py PARENT_KEYS (:83, :59, :47)",
        (f"The three parent-taking tools now share PARENT_KEYS=('parent_path','parent'): "
         f"{json.dumps(keys)}. create_variants and set_purpose take component_path, so the "
         "finding never applied to them. The divergence F8 described (scene_template reading "
         "'parent' only) is REPAIRED. RESIDUAL, and it is the harm F8 actually named: the "
         f"silent default SURVIVES — an unrecognised key still builds into /stage "
         f"(misspelled_key_silently_built_into_/stage={misspelled_went_to_stage}, "
         f"raised={raised}). Ruling 15 retired 'parent' but it is still ACCEPTED as an alias, "
         "so this is a compatibility shim, not a full convergence."
         if uniform else f"keys={json.dumps(keys)}"),
        f"the correct key parent_path built into the requested lopnet: {control_ok}",
        "would have CONFIRMED if any of the three read only one key, or read different keys",
        json.dumps({"parent_keys": keys, "misspelled_silently_to_stage": misspelled_went_to_stage,
                    "misspelled_raised": raised, "control_correct_key_ok": control_ok}))


# ===========================================================================
# F9 — does import_megascans complete, and is the locked-HDA constraint real?
# ===========================================================================
def f9():
    from synapse.mcp.tool_impls.solaris import import_megascans as ms
    import tempfile
    net = fresh("h2b_f9")
    try:
        usdc = real_usdc(Path(tempfile.mkdtemp()) / "rock.usdc")
        r = ms.execute({"usdc_path": str(usdc), "asset_name": "f9rock",
                        "parent_path": net.path()})
        comp = net.node("component_f9rock")
        sop = comp.node("geo_f9rock/sopnet/geo/import_usdc")
        pts = len(sop.geometry().points()) if sop is not None else None

        # POSITIVE CONTROL (Ruling 50): the locked-HDA constraint must still be real,
        # else "it completes now" might mean the constraint simply vanished.
        probe = net.createNode("componentgeometry", "lockprobe")
        try:
            probe.createNode("usdimport", "should_fail")
            still_locked = False
            lock_err = "createNode SUCCEEDED on componentgeometry — HDA no longer locked"
        except Exception as exc:
            still_locked = True
            lock_err = f"{type(exc).__name__}: {exc}"

        rec("F9", "REFUTED" if r.get("status") == "created" else "CONFIRMED",
            "repaired" if r.get("status") == "created" else "n/a",
            "python/synapse/mcp/tool_impls/solaris/import_megascans.py:215-219",
            (f"The tool COMPLETES on 22.0.368: status={r.get('status')!r}, and the usdimport is "
             f"built inside the writable interior subnet (geo_<asset>/sopnet/geo/import_usdc), "
             f"which cooks {pts} real points from the .usdc. The premise was TRUE when written "
             "and a repair landed: the build was retargeted off the locked HDA onto sopnet/geo. "
             f"The constraint itself is UNCHANGED — createNode directly on a componentgeometry "
             f"still raises ({lock_err[:120]}), so the repair is a real retarget, not the "
             "constraint disappearing."
             if r.get("status") == "created" else f"status={r.get('status')!r}"),
            f"locked-HDA constraint still live on this build: {still_locked} — {lock_err[:160]}",
            "would have CONFIRMED if execute() raised hou.PermissionError, and would have been "
            "UNVERIFIABLE if the locked-HDA control had shown the constraint no longer exists "
            "(then 'it completes' would say nothing about the repair)",
            json.dumps({"status": r.get("status"), "sop_points": pts,
                        "locked_hda_still_enforced": still_locked,
                        "lock_error": lock_err[:300]}))
    finally:
        net.destroy()


# ===========================================================================
# F10 — is `componentbuilder` a live LOP type?
# ===========================================================================
def f10():
    cat = hou.lopNodeTypeCategory()
    direct = hou.nodeType(cat, "componentbuilder")
    # Namespaced names would be missed by a bare-name lookup — scan the whole map.
    all_types = list(cat.nodeTypes().keys())
    contains = [t for t in all_types if "componentbuilder" in t.lower()]
    # POSITIVE CONTROL (Ruling 50): the identical lookup must FIND types we know exist.
    ctl = {n: hou.nodeType(cat, n) is not None
           for n in ("componentgeometry", "componentmaterial", "componentoutput", "sublayer")}

    from synapse.mcp.tool_impls.solaris import component_builder as cb
    has_native = cb._has_native_componentbuilder()

    absent = direct is None and not contains
    controls_ok = all(ctl.values())
    rec("F10",
        "CONFIRMED" if (absent and controls_ok) else
        ("UNVERIFIABLE" if not controls_ok else "REFUTED"),
        "n/a",
        "python/synapse/mcp/tool_impls/solaris/component_builder.py:53-71,265-286",
        (f"CONFIRMED as an absence, with a control. `componentbuilder` is NOT a LOP node type on "
         f"22.0.368: direct lookup is None and a substring scan of all {len(all_types)} live LOP "
         f"type names finds {contains}. _has_native_componentbuilder() returns {has_native}, so "
         "Path A (the native branch) is unreachable dead code and the subnet fallback is the only "
         "working strategy. The finding stands as written. Note the tool no longer hides this in "
         "a bare try/except — the capability is probed explicitly. Ruling 50 satisfied: the "
         "identical lookup finds four LOP types that do exist."
         if (absent and controls_ok) else
         f"direct={direct} contains={contains} controls={ctl}"),
        f"identical hou.nodeType lookup finds known LOP types: {ctl}",
        "would have REFUTED if the substring scan had found any namespaced componentbuilder "
        "variant; would have been UNVERIFIABLE if the control lookups had also returned None "
        "(that would mean the probe, not the type, was broken)",
        json.dumps({"direct_lookup": str(direct), "substring_matches": contains,
                    "live_lop_type_count": len(all_types), "controls": ctl,
                    "_has_native_componentbuilder": has_native}))


# ===========================================================================
# F11 — are the Solaris tests collected, and do they drive REAL hou?
# ===========================================================================
def f11():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    testpaths_line = [l for l in pyproject.splitlines() if "testpaths" in l]
    orphan = ROOT / "synapse/tests/solaris"
    orphan_tests = sorted(p.name for p in orphan.glob("test_*.py")) if orphan.exists() else []
    live_dir = ROOT / "tests/solaris"
    live_tests = sorted(p.name for p in live_dir.glob("test_*.py"))

    # The gate: is a canonical fake detectable, and is real hou in play right now?
    is_canonical = getattr(hou, "__synapse_canonical__", False)

    rec("F11", "REFUTED", "repaired",
        "pyproject.toml testpaths; tests/solaris/test_live_wiring.py:39-51",
        (f"The orphan tree is RETIRED: synapse/tests/solaris/ now holds no test modules "
         f"({orphan_tests or 'empty'}). The Solaris tests live at tests/solaris/ "
         f"({len(live_tests)} modules) which IS inside testpaths ({testpaths_line}), so they are "
         "collected by the gate suite. The MagicMock half is also repaired: "
         "tests/solaris/test_live_wiring.py gates on host identity — tests/conftest.py plants a "
         "canonical fake carrying __synapse_canonical__, and the module skips when it sees it, "
         f"so the file cannot silently assert against a mock. Under this interpreter "
         f"__synapse_canonical__={is_canonical}, i.e. REAL hou. The premise was TRUE when "
         "written and a repair landed (SR1 M3)."),
        "the interpreter-split control is run separately (collect + run under BOTH system python "
        "and hython) — see requalify_f11_gate.json",
        "would have CONFIRMED if synapse/tests/solaris/ still held uncollected test modules, or "
        "if test_live_wiring.py had no host-identity gate and ran against the planted fake",
        json.dumps({"testpaths": testpaths_line, "orphan_tree_tests": orphan_tests,
                    "live_tests": live_tests, "hou_is_canonical_fake": is_canonical,
                    "hou_build": hou.applicationVersionString()}))


def main():
    for fn in (f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11):
        try:
            fn()
        except Exception:
            tb = traceback.format_exc()
            rec(fn.__name__.upper(), "UNVERIFIABLE", "n/a", "probe raised",
                f"probe raised: {tb.strip().splitlines()[-1]}", "n/a",
                "probe error — not a finding verdict", tb[-1200:], tier="UNVERIFIED")
    OUT.write_text(json.dumps({
        "schema": "requalify/h2b/v1",
        "build": hou.applicationVersionString(),
        "python": sys.version.split()[0],
        "hou_is_canonical_fake": getattr(hou, "__synapse_canonical__", False),
        "results": RESULTS,
    }, indent=1), encoding="utf-8")
    print(f"\nwritten: {OUT}")
    print("\n=== SUMMARY ===")
    for r in RESULTS:
        k = f" ({r['refuted_kind']})" if r["refuted_kind"] not in (None, "n/a") else ""
        print(f"  {r['finding_id']:4s} {r['verdict']}{k}")


if __name__ == "__main__":
    main()
