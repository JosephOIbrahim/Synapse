"""BP3-PROBE supplementary measurement (INDEPENDENT of the blueprint probe; edits nothing).
Purpose: turn three UNKNOWNs into facts:
  1. Real collider triangle count (blueprint probe measured 2 PACKED prims, not tris) -> D2.2 + gate G-1 evidence.
  2. Normal-class breakdown on the UNPACKED collider (S-2 was degenerate on packed prims).
  3. EXR pixel stats (B-7 render errored 'no render camera'; script only checked size>4096) -> D2.4 non-zero-pixel truth.
Print, never assert. Run under hython 22.0.400:
  hython bp3_supplementary.py <collider.glb> <b7_wl_fixture.exr>
"""
import hou, sys, traceback
glb = sys.argv[1]; exr = sys.argv[2]
print("=== BP3 SUPPLEMENTARY MEASUREMENT ===")
print("Houdini:", hou.applicationVersionString())

# 1 + 2: collider unpack + triangulate + normal classes
try:
    geo = hou.node('/obj').createNode('geo', 'sup_collider')
    g1 = geo.createNode('gltf', 'load')
    fp = g1.parm('filename') or g1.parm('file')
    if fp is None:  # label fallback (mirrors B-3), gltf::2.0 renames the parm
        for pr in g1.parms():
            if 'file' in (pr.description() or '').lower():
                fp = pr; break
    print("  gltf file parm resolved:", fp.name() if fp else None)
    fp.set(glb); g1.cook(force=True)
    packed = g1.geometry()
    print("  packed prims:", packed.intrinsicValue('primitivecount'), "packed points:", packed.intrinsicValue('pointcount'))
    up = geo.createNode('unpack'); up.setInput(0, g1); up.cook(force=True)
    gu = up.geometry()
    print("  UNPACKED prims (polys):", gu.intrinsicValue('primitivecount'), "points:", gu.intrinsicValue('pointcount'))
    bb = gu.boundingBox(); print("  UNPACKED bbox min", bb.minvec(), "max", bb.maxvec())
    div = geo.createNode('divide'); div.setInput(0, up)  # default convex->tris (numsides=3)
    div.cook(force=True); gt = div.geometry()
    ntri = gt.intrinsicValue('primitivecount')
    print("  TRIANGULATED prim count (tris):", ntri)
    print("  100k-200k window:", "WITHIN" if 100000 <= ntri <= 200000 else ("BELOW" if ntri < 100000 else "ABOVE"))
    try:
        import numpy as np
        nrm = geo.createNode('normal'); nrm.setInput(0, up); nrm.parm('type').set(2); nrm.cook(force=True)
        N = np.asarray(nrm.geometry().primFloatAttribValues('N'), dtype=float).reshape(-1, 3)
        ang = np.degrees(np.arccos(np.clip(-N[:, 1], -1.0, 1.0)))  # raw-up=(0,-1,0) per WL-EX-05
        for thr in (20, 35, 45):
            floor = int((ang < thr).sum()); wall = int(((ang > 90 - thr) & (ang < 90 + thr)).sum()); ceil = int((ang > 180 - thr).sum())
            print(f"  UNPACKED normal-class max_angle={thr}: floor={floor} wall={wall} ceil={ceil} other={len(N)-floor-wall-ceil} of {len(N)} polys")
    except Exception as e:
        print("  numpy classification failed:", repr(e))
except Exception:
    traceback.print_exc()

# 3: EXR pixel stats
print("--- EXR stats ---")
try:
    import OpenImageIO as oiio
    buf = oiio.ImageBuf(exr); spec = buf.spec()
    st = oiio.ImageBufAlgo.computePixelStats(buf)
    print("  EXR res", spec.width, "x", spec.height, "channels", spec.nchannels, spec.channelnames)
    print("  min:", list(st.min)); print("  max:", list(st.max)); print("  avg:", list(st.avg))
    print("  NON-ZERO pixels:", any(abs(x) > 1e-9 for x in list(st.max)))
except Exception as e:
    print("  OpenImageIO unavailable:", repr(e))
