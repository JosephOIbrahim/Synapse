"""SYNAPSE render-freeze repro scene builder.

Builds the smallest graph that forces a real render (so the freeze reproduces),
on BOTH a Karma path (/stage) and a Mantra control (/out), then saves
$HIP/freeze_repro.hip. A distant light gives non-black pixels so a render that
actually executed is distinguishable from a no-op.

Run in Houdini's Python Shell:
    exec(open(r'C:\\Users\\User\\SYNAPSE\\scripts\\build_freeze_repro.py').read())

Then per cell, set the engine/res on /stage/karmarendersettings1 and render
exactly one frame (see the operator card). Verify-live note: confirm the parm
names (engine / resolutionx / resolutiony) on 22.0.368 via node.parms() before
trusting them — adjust in-UI if the build differs.
"""

import hou

st = hou.node("/stage")

# --- Karma path (/stage): sphere -> camera -> light -> rendersettings -> ROP ---
sph = st.createNode("sphere", "sphere1")
cam = st.createNode("camera", "camera1"); cam.setInput(0, sph)
lit = st.createNode("distantlight", "distantlight1"); lit.setInput(0, cam)
krs = st.createNode("karmarendersettings", "karmarendersettings1"); krs.setInput(0, lit)
rop = st.createNode("usdrender_rop", "usdrender_rop1")
rop.parm("loppath").set(krs.path())
try:
    krs.parm("camera").set("/cameras/camera1")
except Exception:
    pass
for n in (sph, cam, lit, krs, rop):
    n.moveToGoodPosition()

# --- Mantra control (/obj + /out): the "is it just Karma?" leg -----------------
ob = hou.node("/obj")
g = ob.createNode("geo", "geo1"); g.createNode("sphere", "sphere1")
mc = ob.createNode("cam", "cam1")
ob.createNode("hlight", "hlight1")
mr = hou.node("/out").createNode("ifd", "mantra1")
mr.parm("camera").set(mc.path())
mr.parm("vm_picture").set("$HIP/.synapse/mantra_$F4.exr")

path = hou.text.expandString("$HIP/freeze_repro.hip")
hou.hipFile.save(path)
print("[build_freeze_repro] saved %s" % path)
print("  Karma  : /stage/usdrender_rop1  (engine/res on /stage/karmarendersettings1)")
print("  Mantra : /out/mantra1           (res on the ROP)")
print("  Next: arm scripts/render_watch.ps1, then render ONE frame per the operator card.")
