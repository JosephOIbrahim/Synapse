"""Warm the Karma XPU OptiX kernel cache — at a moment YOU choose.

The first XPU render after a Houdini install or NVIDIA driver update compiles
render kernels (documented up to ~2 minutes, solaris/karma_xpu.html) and holds
the whole UI while it does — that fixed cost is what froze the 64x64 sphere.
This script pays it NOW, on a throwaway 32x32 render, so the first real render
doesn't. Official alternative: Render menu > "Pre-compile Karma XPU Render
Kernels". The cache persists per major release
(%LOCALAPPDATA%/NVIDIA/OptixCache/Houdini22.0) until a driver/Houdini update.

Run in Houdini's Python Shell (the UI WILL pause while kernels compile — that
is the point of doing it now, not mid-work):

    exec(open(r'C:\\Users\\User\\SYNAPSE\\scripts\\prewarm_xpu.py').read())

HONESTY CHECK built in: the OptiX cache file count is measured before/after.
On Indie the ROP render path may no-op (the husk delegate is license-gated),
in which case the delta is 0 and this script SAYS SO and points you at the
Render-menu precompile / a viewport XPU flick instead — it never claims a
warmup it can't prove. Temp nodes are removed in the finally; the scene is
left untouched (one undo group).
"""

import os
import time

import hou


def _cache_file_count():
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
        os.path.join("~", "AppData", "Local"))
    path = os.path.join(local, "NVIDIA", "OptixCache", "Houdini22.0")
    n = 0
    try:
        for _root, _dirs, files in os.walk(path):
            n += len(files)
    except OSError:
        pass
    return path, n


_t0 = time.time()
_cache_path, _before = _cache_file_count()
print("[prewarm_xpu] OptiX cache: %s (%d files before)" % (_cache_path, _before))
print("[prewarm_xpu] Building throwaway 32x32 XPU render — the UI will pause "
      "while kernels compile. That's the point.")

_nodes = []
st = hou.node("/stage")
try:
    with hou.undos.group("SYNAPSE: prewarm XPU kernels"):
        sph = st.createNode("sphere", "__synapse_prewarm_sphere")
        cam = st.createNode("camera", "__synapse_prewarm_cam")
        cam.setInput(0, sph)
        lit = st.createNode("distantlight", "__synapse_prewarm_light")
        lit.setInput(0, cam)
        krs = st.createNode("karmarendersettings", "__synapse_prewarm_krs")
        krs.setInput(0, lit)
        rop = st.createNode("usdrender_rop", "__synapse_prewarm_rop")
        rop.parm("loppath").set(krs.path())
        _nodes = [sph, cam, lit, krs, rop]

        for pn, val in (("engine", "xpu"), ("resolutionx", 32),
                        ("resolutiony", 32)):
            p = krs.parm(pn)
            if p is not None:
                p.set(val)
        cp = krs.parm("camera")
        if cp is not None:
            cp.set("/cameras/__synapse_prewarm_cam")
        out = hou.text.expandString("$HOUDINI_TEMP_DIR") + "/synapse_prewarm.exr"
        for pn in ("outputimage", "picture"):
            p = rop.parm(pn)
            if p is not None:
                p.set(out)
                break

        rop.render(frame_range=(1, 1), verbose=False)
finally:
    for n in reversed(_nodes):
        try:
            n.destroy()
        except Exception:
            pass

_elapsed = time.time() - _t0
_, _after = _cache_file_count()
print("[prewarm_xpu] Render call returned in %.1fs; cache %d -> %d files."
      % (_elapsed, _before, _after))
if _after > _before:
    print("[prewarm_xpu] WARM — kernels compiled and cached. XPU renders now "
          "skip the cold-compile stall until the next driver/Houdini update.")
else:
    print("[prewarm_xpu] NO cache delta — the ROP render path likely no-op'd "
          "(Indie license gates the husk delegate). Use Render menu > "
          "'Pre-compile Karma XPU Render Kernels', or flick the viewport to "
          "Karma XPU once, then re-run this to verify the delta.")
