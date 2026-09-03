"""
SYNAPSE blueprint probes - H22 Solaris (P-1..P-9), World Labs bridge (B-1..B-9), spatial lane (S-1..S-3).

Run with hython on the pinned build:
    hython synapse_blueprint_probes.py --ply <fixture_500k.ply> --glb <fixture_collider.glb> --out <dir> [--only P,B,S]

Conventions (SYNAPSE):
  * Print, never assert. A probe that raises is reported BLOCKED with traceback; the sequence continues.
  * Every node-type string and parm name below is V0. Where a name is a guess it is looked up by LABEL first;
    the guess is only used if the label search finds nothing, and the output says which happened.
  * LOP types live in the `Lop` category; modern COP types in the `Cop` category; `hou.lop.*` may be absent headless.
  * Nothing is saved unless --save-hip is given. No corpus writes. No ratification.
Source: docs/intake/blueprint-h22-worldlabs-intent.md (v0.3). Landed for wave BP3, 2026-09-03.
"""
import argparse, json, math, os, struct, sys, time, traceback

try:
    import hou
except ImportError:
    print("This script must run under hython (import hou failed).")
    sys.exit(2)

# ----------------------------------------------------------------------------- harness
RESULTS = {}

def probe(pid, title):
    def deco(fn):
        def run(ctx):
            print("\n" + "=" * 78 + f"\n{pid}  {title}\n" + "=" * 78)
            t0 = time.time()
            try:
                r = fn(ctx)
                RESULTS[pid] = {"status": "RAN", "seconds": round(time.time() - t0, 2), "result": r}
            except Exception as e:  # noqa
                traceback.print_exc()
                RESULTS[pid] = {"status": "BLOCKED", "error": repr(e)}
                print(f"[{pid}] BLOCKED: {e!r}")
        run.pid = pid
        return run
    return deco

def find_type_by_label(category, needles):
    """Label search (dossier KAR-07 style). Returns [(type_name, label)] for any label containing any needle."""
    out = []
    for t in category.nodeTypes().values():
        d = (t.description() or "")
        if any(n.lower() in d.lower() for n in needles):
            out.append((t.name(), d))
    return sorted(out)

def parm_by_label(node, needles):
    """Find a parm on a node whose label contains a needle. Returns first match or None."""
    for p in node.parms():
        lab = (p.description() or "").lower()
        if any(n.lower() in lab for n in needles):
            return p
    return None

def walk_templates(ptg, needles):
    hits = []
    def walk(pt, path=""):
        for p in pt.parmTemplates():
            if isinstance(p, hou.FolderParmTemplate):
                walk(p, path + "/" + (p.label() or ""))
            else:
                lab = (p.label() or "")
                if any(n.lower() in lab.lower() for n in needles):
                    hits.append((path, p.name(), lab))
    walk(ptg)
    return hits

def prim_normals_and_centroids(src_node):
    """Vectorised prim normals + centroids: Normal SOP (primitives) + a prim wrangle, read with numpy.
    Returns (N: (n,3), C: (n,3), node) or (None, None, node) with the reason printed. Parm names `type`/`snippet`/`class` are long-stable."""
    geo_parent = src_node.parent()
    try:
        import numpy as np
    except ImportError:
        print("  numpy unavailable in this hython; falling back to per-prim loop"); return None, None, src_node
    try:
        nrm = geo_parent.createNode('normal', src_node.name() + '_N'); nrm.setInput(0, src_node); nrm.parm('type').set(2)
        wr = geo_parent.createNode('attribwrangle', src_node.name() + '_C'); wr.setInput(0, nrm); wr.parm('class').set(1)
        wr.parm('snippet').set('int pts[] = primpoints(0, @primnum); vector c = 0; foreach (int pt; pts) c += point(0, "P", pt); v@centroid = c / max(1, len(pts));')
        wr.cook(force=True); g = wr.geometry()
        N = np.asarray(g.primFloatAttribValues('N'), dtype=float).reshape(-1, 3)
        C = np.asarray(g.primFloatAttribValues('centroid'), dtype=float).reshape(-1, 3)
        return N, C, wr
    except Exception as e:
        print("  vectorised normals failed, falling back to loop:", e); return None, None, src_node

def stage_dump(stage, limit=200):
    from pxr import UsdGeom, Usd
    rows = []
    for i, prim in enumerate(stage.Traverse()):
        if i >= limit:
            rows.append(("...", "", "", "")); break
        kind = Usd.ModelAPI(prim).GetKind() if prim.IsModel() or prim.HasAuthoredMetadata("kind") else ""
        purpose = ""
        if prim.IsA(UsdGeom.Imageable):
            purpose = UsdGeom.Imageable(prim).GetPurposeAttr().Get() or ""
        rows.append((prim.GetPath().pathString, prim.GetTypeName(), kind, purpose))
    for r in rows:
        print("  %-60s %-22s %-12s %s" % r)
    return rows

# ----------------------------------------------------------------------------- P: H22 Solaris (dossier sec.6)
@probe("P-0", "Build pin")
def p0(ctx):
    print("Houdini:", hou.applicationVersionString())
    try:
        from pxr import Usd; print("USD:", Usd.GetVersion())
    except Exception as e: print("USD version: n/a", e)
    try:
        import MaterialX as mx; print("MaterialX:", mx.getVersionString())
    except Exception as e: print("MaterialX: n/a", e)
    return hou.applicationVersionString()

@probe("P-1", "Solaris node types cited by the talk (Lop category)")
def p1(ctx):
    cat = hou.lopNodeTypeCategory(); out = {}
    for name in ('paintinstances', 'scatterinstances', 'pointinstancer', 'copytopoints', 'edit',
                 'karmablockerlightfilter', 'karmarendersettings', 'usdrender_rop', 'renderpass',
                 'imagefilter', 'texturemateriallibrary', 'apexanimate', 'cache', 'karmafogbox',
                 'materiallibrary', 'light::2.0'):
        out[name] = hou.nodeType(cat, name) is not None
        print(f"  {name:28s} {out[name]}")
    return out

@probe("P-2", "Label search for V0 LOP names")
def p2(ctx):
    hits = find_type_by_label(hou.lopNodeTypeCategory(),
                              ('texture material', 'image filter', 'blocker', 'render pass', 'scatter instances'))
    for n, d in hits: print(f"  {n:40s} | {d}")
    return hits

@probe("P-3", "SOP-side component building: label search (Sop category)")
def p3(ctx):
    hits = find_type_by_label(hou.sopNodeTypeCategory(), ('USD Create', 'Transform USD'))
    for n, d in hits: print(f"  {n:40s} | {d}")
    ctx['sop_component_types'] = dict((d, n) for n, d in hits)
    return hits

@probe("P-4", "Equiangular MIS toggle on light::2.0 (KAR-12)")
def p4(ctx):
    ptg = hou.nodeType(hou.lopNodeTypeCategory(), 'light::2.0').parmTemplateGroup()
    hits = walk_templates(ptg, ('equiangular', 'volume sampling'))
    for h in hits: print("  ", h)
    return hits

@probe("P-5", "Scatter Instances parameter surface (labels <-> names)")
def p5(ctx):
    st = hou.nodeType(hou.lopNodeTypeCategory(), 'scatterinstances')
    if st is None:
        print("  scatterinstances not found"); return None
    rows = []
    def dump(pt, depth=0, path=""):
        for p in pt.parmTemplates():
            if isinstance(p, hou.FolderParmTemplate):
                print('  ' * depth + '[' + (p.label() or '') + ']'); dump(p, depth + 1, path + "/" + (p.label() or ""))
            else:
                rows.append({"folder": path, "name": p.name(), "label": p.label()})
                print('  ' * depth + f"{p.name():36s} | {p.label()}")
    dump(st.parmTemplateGroup())
    ctx['scatter_parms'] = rows
    ctx['scatter_max_angle'] = next((r for r in rows if 'max angle' in (r['label'] or '').lower()), None)
    return rows

@probe("P-6", "Image filter prim type + husk:orderedImageFilters targets")
def p6(ctx):
    stage_node = hou.node('/stage')
    types = [n for n, d in find_type_by_label(hou.lopNodeTypeCategory(), ('image filter',))]
    if not types:
        print("  no Image Filter LOP by label"); return None
    n = stage_node.createNode(types[0]); n.cook(force=True)
    for prim in n.stage().Traverse():
        if 'ImageFilter' in prim.GetPath().pathString or 'ImageFilter' in prim.GetTypeName():
            print("  ", prim.GetPath(), prim.GetTypeName())
    krs = stage_node.createNode('karmarendersettings'); krs.setInput(0, n); krs.cook(force=True)
    for prim in krs.stage().Traverse():
        if prim.GetTypeName() in ('RenderSettings', 'RenderProduct'):
            rel = prim.GetRelationship('husk:orderedImageFilters')
            print("  ", prim.GetPath(), prim.GetTypeName(), "orderedImageFilters ->", rel.GetTargets() if rel else "no rel")
    return types

@probe("P-7", "Render Pass schema + CLI presence")
def p7(ctx):
    from pxr import Usd, UsdRender
    s = Usd.Stage.CreateInMemory()
    rp = UsdRender.Pass.Define(s, '/Render/Passes/passA')
    print("  Pass defined:", bool(rp), "| renderSource rel:", bool(rp.CreateRenderSourceRel()))
    print("  shell check (run manually):  husk --help | findstr -- --pass")
    return bool(rp)

@probe("P-8", "Flake VOP + MaterialX version")
def p8(ctx):
    vop = hou.vopNodeTypeCategory()
    print("  mtlxflake3d:", hou.nodeType(vop, 'mtlxflake3d') is not None)
    return hou.nodeType(vop, 'mtlxflake3d') is not None

@probe("P-9", "Scatter execution / animation menus (dossier sec.5 Q2)")
def p9(ctx):
    n = hou.node('/stage').createNode('scatterinstances')
    out = {}
    for needles in (('execution mode',), ('animation',)):
        p = parm_by_label(n, needles)
        if p is None:
            print(f"  no parm with label {needles}"); continue
        out[p.name()] = (p.menuItems(), p.menuLabels())
        print(f"  {p.name()} ({p.description()}): items={p.menuItems()} labels={p.menuLabels()}")
    return out

# ----------------------------------------------------------------------------- B: World Labs bridge
def _geo_container():
    return hou.node('/obj/wl_probe') or hou.node('/obj').createNode('geo', 'wl_probe')

@probe("B-1", "Fixture PLY via file SOP: attribute schema + counts")
def b1(ctx):
    geo = _geo_container()
    f = geo.createNode('file', 'splat_ply'); f.parm('file').set(ctx['ply']); f.cook(force=True)
    g = f.geometry()
    print("  points:", g.intrinsicValue('pointcount'), "prims:", g.intrinsicValue('primitivecount'))
    for a in g.pointAttribs():
        print(f"  pt   {a.name():16s} {a.dataType()} size={a.size()}")
    for a in g.primAttribs():   print(f"  prim {a.name():16s} {a.dataType()} size={a.size()}")
    for a in g.globalAttribs(): print(f"  det  {a.name():16s} {a.dataType()} size={a.size()}")
    pts = g.points()[:3]
    for p in pts:
        print("  sample P:", p.position(), {a.name(): p.attribValue(a) for a in g.pointAttribs() if a.name() in ('opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3','f_dc_0')})
    ctx['splat_geo'] = g; ctx['splat_node'] = f
    return {"points": g.intrinsicValue('pointcount'), "attribs": [a.name() for a in g.pointAttribs()]}

@probe("B-2", "Raw frame: bounds before/after Y,Z flip; where the mass sits")
def b2(ctx):
    g = ctx['splat_geo']
    bb = g.boundingBox(); print("  raw bbox   min", bb.minvec(), "max", bb.maxvec())
    ys = sorted(p.position().y() for p in g.points()[::max(1, g.intrinsicValue('pointcount') // 20000)])
    print("  raw y median", ys[len(ys)//2], "| 5%", ys[len(ys)//20], "| 95%", ys[-len(ys)//20])
    print("  WL-EX-05 says +y is DOWN in raw: floor should sit near the 95% end, ceiling/sky near 5%. Check that against the numbers above.")
    flipped = hou.Matrix4((1,0,0,0, 0,-1,0,0, 0,0,-1,0, 0,0,0,1))
    mn, mx = bb.minvec() * flipped, bb.maxvec() * flipped
    print("  after scale(1,-1,-1): corners", mn, mx, "(min/max swap on Y,Z is expected)")
    print("  handedness: not decidable numerically. Open the fixture in the viewer with the Marble world beside it; a mirrored lane means the flip needs a rotation, not a scale (B-2 manual).")
    return {"raw_min": list(bb.minvec()), "raw_max": list(bb.maxvec())}

@probe("B-3", "Collider GLB via gltf SOP: counts, bounds, normal classes in raw frame")
def b3(ctx):
    geo = _geo_container()
    types = [n for n, d in find_type_by_label(hou.sopNodeTypeCategory(), ('gltf',))]
    print("  gltf-ish SOP types:", types)
    tname = 'gltf' if hou.nodeType(hou.sopNodeTypeCategory(), 'gltf') else (types[0] if types else None)
    if not tname: print("  no glTF SOP"); return None
    n = geo.createNode(tname, 'collider_glb')
    p = n.parm('filename') or parm_by_label(n, ('file',))
    p.set(ctx['glb']); n.cook(force=True)
    g = n.geometry()
    print("  prims:", g.intrinsicValue('primitivecount'), "points:", g.intrinsicValue('pointcount'))
    bb = g.boundingBox(); print("  collider raw bbox min", bb.minvec(), "max", bb.maxvec())
    if 'splat_geo' in ctx:
        sb = ctx['splat_geo'].boundingBox()
        print("  splat/collider size ratio:", [round(a/b, 3) if b else None for a, b in zip(sb.sizevec(), bb.sizevec())],
              "| center delta:", sb.center() - bb.center())
    # normal classes in RAW frame (+y is down per WL-EX-05, so raw "up" is -y). One vectorised pass; both signs reported.
    t0 = time.time(); N, C, wnode = prim_normals_and_centroids(n)
    if N is not None:
        import numpy as np
        ang = np.degrees(np.arccos(np.clip(N[:, 1], -1.0, 1.0)))     # angle to +y
        for label, a in (("raw-up=(0,-1,0) per WL-EX-05", 180.0 - ang), ("(0,1,0)", ang)):
            counts = {"floor<35": int((a < 35).sum()), "wall>55": int(((a > 55) & (a < 125)).sum()),
                      "ceil<35(opposite)": int((a > 145).sum())}
            counts["other"] = int(len(a) - sum(counts.values())); print(f"  up={label}: {counts}")
        ctx['collider_N'] = N; ctx['collider_C'] = C
    else:
        print("  (loop fallback) skipping class counts; S-2 will do a reduced pass")
    print(f"  normals/centroids computed in {time.time()-t0:.2f}s")
    ctx['collider_geo'] = g; ctx['collider_node'] = n
    return {"prims": g.intrinsicValue('primitivecount'), "bbox": [list(bb.minvec()), list(bb.maxvec())]}

@probe("B-4", "Do app exports carry scale/ground metadata? PLY header + GLB JSON extras")
def b4(ctx):
    found = {}
    with open(ctx['ply'], 'rb') as fh:
        header = b""
        while b"end_header" not in header and len(header) < 20000:
            header += fh.readline()
    lines = header.decode('ascii', 'replace').splitlines()
    print("  PLY header lines:", len(lines))
    for ln in lines:
        if ln.startswith(('comment', 'obj_info', 'format')): print("   ", ln)
    found['ply_comments'] = [ln for ln in lines if ln.startswith(('comment', 'obj_info'))]
    with open(ctx['glb'], 'rb') as fh:
        magic, ver, length = struct.unpack('<III', fh.read(12)); clen, ctype = struct.unpack('<II', fh.read(8))
        js = json.loads(fh.read(clen).decode('utf-8'))
    print("  GLB asset:", js.get('asset')); print("  GLB top-level extras:", js.get('extras'))
    for s in js.get('scenes', []): print("  scene extras:", s.get('extras'))
    for nd in js.get('nodes', [])[:20]: print("  node:", nd.get('name'), "extras:", nd.get('extras'), "scale:", nd.get('scale'), "rot:", nd.get('rotation'))
    found['glb_asset'] = js.get('asset'); found['glb_extras'] = js.get('extras')
    print("  Any metric_scale_factor / ground_plane_offset above? If none: BLU-04 = TRUE (derive in Intent 3).")
    return found

@probe("B-5", "Splat tooling present on this build (SOP / LOP / COP label search)")
def b5(ctx):
    out = {}
    for label, cat in (("SOP", hou.sopNodeTypeCategory()), ("LOP", hou.lopNodeTypeCategory())):
        out[label] = find_type_by_label(cat, ('gsplat', 'gaussian', 'splat'))
        print(f"  {label}:"); [print(f"    {n:40s} | {d}") for n, d in out[label]]
    try:
        cop = hou.nodeTypeCategories().get('Cop')
        out['COP'] = find_type_by_label(cop, ('gsplat', 'gaussian', 'splat')) if cop else []
        print("  COP (modern):"); [print(f"    {n:40s} | {d}") for n, d in out['COP']]
    except Exception as e: print("  COP category lookup failed:", e)
    return out

@probe("B-6", "SOP-side component: splat=render, collider=proxy; walk the stage (kinds, purposes)")
def b6(ctx):
    types = ctx.get('sop_component_types', {})
    comp = next((n for d, n in types.items() if 'create component' in d.lower()), None)
    prox = next((n for d, n in types.items() if 'proxy' in d.lower()), None)
    print("  USD Create Component ->", comp, "| USD Create Proxy Geometry ->", prox)
    stage_node = hou.node('/stage')
    if not comp:
        # Fallback path (no cascade): two SOP Imports + merge + Python LOP that authors kind/purpose with pxr. Parm names here are stable.
        print("  no SOP-side component node on this build -> LOP-side fallback (sopimport x2 + merge + pythonscript). Path recorded as 'lop_fallback'.")
        si_s = stage_node.createNode('sopimport', 'wl_splat'); si_s.parm('soppath').set(ctx['splat_node'].path()); si_s.parm('primpath').set('/WL_fixture/geo/splat')
        si_c = stage_node.createNode('sopimport', 'wl_collider'); si_c.parm('soppath').set(ctx['collider_node'].path()); si_c.parm('primpath').set('/WL_fixture/geo/collider')
        mg = stage_node.createNode('merge', 'wl_merge'); mg.setInput(0, si_s); mg.setInput(1, si_c)
        py = stage_node.createNode('pythonscript', 'wl_kind_purpose'); py.setInput(0, mg)
        py.parm('python').set(
            "from pxr import Usd, UsdGeom\n"
            "stage = hou.pwd().editableStage()\n"
            "root = stage.GetPrimAtPath('/WL_fixture')\n"
            "if not root: root = UsdGeom.Xform.Define(stage, '/WL_fixture').GetPrim()\n"
            "Usd.ModelAPI(root).SetKind('component')\n"
            "for path, purpose in (('/WL_fixture/geo/splat','render'), ('/WL_fixture/geo/collider','proxy')):\n"
            "    p = stage.GetPrimAtPath(path)\n"
            "    if p: UsdGeom.Imageable(p).CreatePurposeAttr(purpose)\n")
        py.cook(force=True); print("  stage after LOP fallback:"); rows = stage_dump(py.stage())
        ctx['stage_node'] = py; ctx['component_path'] = 'lop_fallback'
        out = os.path.join(ctx['out'], 'b6_wl_component.usdc'); py.stage().Export(out)
        print(f"  exported {out}: {os.path.getsize(out)/1e6:.1f} MB  (SH payload evidence for sec.2.5 property 3)")
        return rows
    ctx['component_path'] = 'sop_component'
    geo = _geo_container()
    c = geo.createNode(comp, 'wl_component')
    c.setInput(0, ctx['splat_node'])
    if prox:
        pg = geo.createNode(prox, 'collider_as_proxy')
        try: pg.setInput(1, ctx['collider_node'])          # second input = hand-made proxy (H22S-SOP-02); index V0
        except Exception as e: print("  proxy SOP second input failed:", e); pg.setInput(0, ctx['collider_node'])
        try: c.setInput(1, pg)                              # component proxy input index V0
        except Exception as e: print("  could not wire proxy into component:", e)
    else:
        print("  no proxy SOP found by label; component built from splat only")
    for needles, val in ((('name','component'), 'WL_fixture'), (('kind',), 'component')):
        p = parm_by_label(c, needles)
        if p is not None and p.parmTemplate().type() == hou.parmTemplateType.String:
            try: p.set(val); print(f"  set {p.name()} = {val}")
            except Exception as e: print("  parm set failed", p.name(), e)
    c.cook(force=True)
    si = stage_node.createNode('sopimport', 'wl_import'); si.parm('soppath').set(c.path()); si.cook(force=True)
    print("  stage after SOP Import:"); rows = stage_dump(si.stage())
    ctx['stage_node'] = si
    out = os.path.join(ctx['out'], 'b6_wl_component.usdc'); si.stage().Export(out)
    print(f"  exported {out}: {os.path.getsize(out)/1e6:.1f} MB  (SH payload evidence for sec.2.5 property 3; production path = payload this file)")
    return rows

@probe("B-7", "Karma XPU render of the component: author camera + light BEFORE render settings, bind the render camera (BP4 B-7 fix)")
def b7(ctx):
    if 'stage_node' not in ctx: print("  BLOCKED: B-6 did not produce a stage"); return None
    stage_node = hou.node('/stage')
    # BP4 B-7 fix. BP3's black EXR was a PROBE BUG, not a Karma verdict: the camera was
    # created AFTER the karmarendersettings and its prim was never bound (KRS.camera
    # defaulted to /cameras/camera1 != the authored /cameras/wl_cam -> 6x "No render
    # camera defined"), and no light was authored (husk Total Lights 0 -> black RGB).
    # Fix: author the camera AND a light BEFORE the render settings, then bind the render
    # camera relationship to the authored camera prim. Resolution left at the KRS default
    # (1280x720). Only this block changes. See review §11.3 / mission BP4-B7FIX.
    cam = stage_node.createNode('camera', 'wl_cam'); cam.setInput(0, ctx['stage_node'])
    cam_path = cam.parm('primpath').eval() if cam.parm('primpath') else '/cameras/wl_cam'
    light = None
    for ltype in ('domelight::3.0', 'domelight', 'distantlight::2.0', 'distantlight'):
        if hou.nodeType(hou.lopNodeTypeCategory(), ltype) is not None:
            light = stage_node.createNode(ltype, 'wl_key'); break
    if light is not None:
        light.setInput(0, cam); print("  authored light:", light.type().name(), "(before render settings)")
    else:
        print("  WARNING: no dome/distant light type resolved; render will be unlit")
    krs = stage_node.createNode('karmarendersettings', 'wl_krs'); krs.setInput(0, light or cam)
    kc = krs.parm('camera') or parm_by_label(krs, ('camera',))
    if kc is not None:
        try: kc.set(cam_path); print("  render camera bound:", kc.name(), "=", cam_path)
        except Exception as e: print("   camera bind failed:", e)
    else:
        print("  WARNING: no camera parm on KRS; render camera unbound")
    for needles, val in ((('engine',), 'xpu'), (('resolution',), None)):
        p = parm_by_label(krs, needles); print("  krs parm by label", needles, "->", p.name() if p else None, "| menu:", p.menuItems() if p and p.menuItems() else "")
        if p and val and val in (p.menuItems() or []): p.set(val)
    rop = stage_node.createNode('usdrender_rop', 'wl_render'); rop.setInput(0, krs)
    out = os.path.join(ctx['out'], 'b7_wl_fixture.exr')
    for needles, val in ((('output picture', 'output'), out), (('renderer',), 'BRAY_HdKarma')):
        p = parm_by_label(rop, needles); print("  rop parm by label", needles, "->", p.name() if p else None)
        if p:
            try: p.set(val)
            except Exception as e: print("   set failed:", e)
    rop.render(frame_range=(1, 1)); time.sleep(1)
    ok = os.path.exists(out) and os.path.getsize(out) > 4096
    print("  EXR written:", ok, out, os.path.getsize(out) if os.path.exists(out) else 0, "bytes")
    print("  Non-zero pixel check: measured externally via oiiotool/iinfo (BP4 T3); the EXR size flag above is NOT a render-success signal.")
    return {"exr": out, "exists": ok, "camera": cam_path, "light": (light.type().name() if light else None)}

@probe("B-8", "Chisel round-trip (MANUAL - prints the checklist)")
def b8(ctx):
    for s in ("1. SOP blocking: two walls, one doorway (2.0 m), floor plane, a null named CAMERA at 1.6 m.",
              "2. Export GLB (gltf ROP). Record units assumed (m) and axis (Y-up).",
              "3. Marble -> Chisel -> Upload a glb or fbx -> position -> Panorama Camera at the CAMERA marker -> prompt -> Generate.",
              "4. Note whether the upload arrived Y-up, metric, mirrored. That answers Open Q5.",
              "5. Export the generated world (Standard plan) -> run B-1..B-4 on it."):
        print("  ", s)
    return "manual"

@probe("B-9", "scatterinstances with a purpose=proxy source (Open Q1)")
def b9(ctx):
    if 'stage_node' not in ctx: print("  BLOCKED: needs B-6 stage"); return None
    stage_node = hou.node('/stage')
    proto = stage_node.createNode('sphere', 'proto_sphere')
    sc = stage_node.createNode('scatterinstances', 'wl_scatter'); sc.setInput(0, ctx['stage_node']); sc.setInput(1, proto)
    src = parm_by_label(sc, ('prim pattern', 'source'))
    coll = next((r[0] for r in RESULTS.get('B-6', {}).get('result') or [] if r[0].endswith('/collider') or 'collider' in r[0]), None)
    print("  source parm:", src.name() if src else None, "| collider prim:", coll)
    if src and coll: src.set(coll)
    sc.cook(force=True)
    print("  stage after scatter (recipe prim expected; instances expand in Hydra, not on the stage):"); stage_dump(sc.stage(), 60)
    print("  Visual confirmation needed in the Karma viewport (H22S-SI-03: on by default there).")
    return "semi-manual"

# ----------------------------------------------------------------------------- S: spatial lane
@probe("S-1", "Organization walk: kinds, purposes, extents on the fixture component")
def s1(ctx):
    from pxr import UsdGeom, Usd
    if 'stage_node' not in ctx: print("  BLOCKED: needs B-6"); return None
    st = ctx['stage_node'].stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy'])
    for prim in st.Traverse():
        if prim.IsA(UsdGeom.Xformable):
            r = bc.ComputeWorldBound(prim).ComputeAlignedRange()
            print(f"  {prim.GetPath().pathString:50s} kind={Usd.ModelAPI(prim).GetKind() or '-':12s} min={r.GetMin()} max={r.GetMax()}")
    return "printed"

@probe("S-2", "Surface classes on the collider vs the scatter Up Axis mask threshold")
def s2(ctx):
    g = ctx.get('collider_geo')
    if g is None: print("  BLOCKED: needs B-3"); return None
    ma = ctx.get('scatter_max_angle'); print("  scatter Max Angle parm (from P-5):", ma)
    t0 = time.time()
    if ctx.get('collider_N') is not None:
        import numpy as np
        N, C = ctx['collider_N'], ctx['collider_C']
        a = 180.0 - np.degrees(np.arccos(np.clip(N[:, 1], -1.0, 1.0)))   # angle to raw-up (0,-1,0) per WL-EX-05
        for thr in (20, 35, 45):
            print(f"  max_angle={thr}: floor={int((a<thr).sum())} wall={int(((a>90-thr)&(a<90+thr)).sum())} ceil={int((a>180-thr).sum())}")
        fy = C[a < 35, 1]
        if fy.size:
            hist, edges = np.histogram(fy, bins=50); k = int(hist.argmax())
            print(f"  floor faces {fy.size} | median y {np.median(fy):.3f} | dominant bin {edges[k]:.3f}..{edges[k+1]:.3f} ({int(hist[k])} faces)")
            ctx['floor_y_raw'] = float(np.median(fy[(fy >= edges[k]) & (fy <= edges[k+1])]))
            print("  -> dominant floor y = DERIVED ground_plane_offset candidate (raw frame). Compare with B-4 vendor value if any.")
        print(f"  S-2 in {time.time()-t0:.2f}s (budget: < 5 s on a 200k-tri collider)"); return {"floor_faces": int(fy.size)}
    up = hou.Vector3(0, -1, 0); floor_y = []                                  # loop fallback, reduced: every 4th prim
    for prim in g.prims()[::4]:
        n = prim.normal(); a = math.degrees(math.acos(max(-1.0, min(1.0, n.dot(up)))))
        if a < 35: floor_y.append(prim.vertices()[0].point().position().y())
    if floor_y:
        floor_y.sort(); ctx['floor_y_raw'] = floor_y[len(floor_y)//2]; print(f"  (loop, 1/4 sample) floor faces {len(floor_y)} | median y {ctx['floor_y_raw']:.3f}")
    print(f"  S-2 in {time.time()-t0:.2f}s"); return {"floor_faces": len(floor_y)}

@probe("S-3", "Frustum membership from a spawn camera (Camera-mask analogue)")
def s3(ctx):
    g = ctx.get('collider_geo')
    if g is None: print("  BLOCKED: needs B-3"); return None
    bb = g.boundingBox(); c = bb.center()
    floor_y = ctx.get('floor_y_raw', bb.maxvec().y())                     # raw frame: floor is toward +y (down); eye = floor - 1.6
    eye = hou.Vector3(c.x(), floor_y - 1.6, c.z()); fwd = hou.Vector3(0, 0, 1); hfov = math.radians(45)
    t0 = time.time(); inside = total = 0
    if ctx.get('collider_C') is not None:
        import numpy as np
        V = ctx['collider_C'] - np.array([eye.x(), eye.y(), eye.z()]); z = V[:, 2]; ok = z > 0
        inside = int((ok & (np.abs(V[:, 0]) < z * math.tan(hfov)) & (np.abs(V[:, 1]) < z * math.tan(hfov * 0.5625))).sum()); total = int(len(V))
    else:
        for prim in g.prims()[::4]:
            v = prim.vertices()[0].point().position() - eye; total += 1; z = v.dot(fwd)
            if z > 0 and abs(v.x()) / z < math.tan(hfov) and abs(v.y()) / z < math.tan(hfov * 0.5625): inside += 1
    print(f"  eye={eye} (floor_y_raw={floor_y:.3f}) fwd={fwd} | faces in frustum: {inside}/{total} ({100.0*inside/max(1,total):.1f}%) in {time.time()-t0:.2f}s")
    print("  Compare against scatterinstances Camera mask with the same camera (visual, Karma viewport).")
    return {"inside": inside, "total": total}

# ----------------------------------------------------------------------------- main
# --only accepts GROUP letters (P,B,S) or specific probe ids (e.g. "B-7"). A probe id
# pulls its prerequisite chain (PROBE_DEPS) so it can run standalone; every probe not in
# the resolved run set is recorded NOT_RUN in probe_results.json (skip != pass).
PROBE_DEPS = {          # transitive prerequisites, expanded to a closure at run time
    'B-6': ['P-3', 'B-1', 'B-3'],   # component build needs the SOP-side type search + splat + collider
    'B-7': ['B-6'],                 # render needs the built component stage
}

def _resolve_run_set(only, order):
    tokens = [x.strip().upper() for x in only.split(',') if x.strip()]
    letters = {t for t in tokens if '-' not in t}
    ids = {t for t in tokens if '-' in t}
    run = {fn.pid for fn in order if fn.pid[0] in letters}
    def _closure(pid):
        run.add(pid)
        for dep in PROBE_DEPS.get(pid, []):
            if dep not in run: _closure(dep)
    for pid in ids:
        _closure(pid)
    return run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ply', required=True); ap.add_argument('--glb', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--only', default='P,B,S', help="comma list of GROUPS (P,B,S) or probe ids (e.g. B-7); a probe id pulls its prereq chain, the rest read NOT_RUN")
    ap.add_argument('--save-hip', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ctx = {'ply': a.ply, 'glb': a.glb, 'out': a.out}
    order = [p0, p1, p2, p3, p4, p5, p6, p7, p8, p9, b1, b2, b3, b4, b5, b6, b7, b8, b9, s1, s2, s3]
    run_set = _resolve_run_set(a.only, order)
    for fn in order:
        if fn.pid in run_set or fn.pid == "P-0":
            fn(ctx)
        else:
            RESULTS.setdefault(fn.pid, {"status": "NOT_RUN"})
    if a.save_hip:
        hp = os.path.join(a.out, 'synapse_blueprint_probes.hip'); hou.hipFile.save(hp); print("\nHIP saved:", hp)
    with open(os.path.join(a.out, 'probe_results.json'), 'w') as fh:
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != 'result' or isinstance(vv, (str, int, float, dict, list, bool, type(None)))}
                   for k, v in RESULTS.items()}, fh, indent=2, default=str)
    total = sum(v.get('seconds', 0) for v in RESULTS.values())
    print("\nSUMMARY:"); [print(f"  {k:5s} {v['status']:8s} {v.get('seconds', '')}") for k, v in RESULTS.items()]
    print(f"  total probe wall time: {total:.1f}s  (sec.6 budget: 1800 s) | component path: {ctx.get('component_path', 'n/a')}")

if __name__ == '__main__':
    main()
