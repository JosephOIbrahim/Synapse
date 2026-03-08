"""Install sub-HDAs then rebuild orchestrator HDA."""
import hou
import sys
import importlib

base = r"C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera\hda"

# Install all 4 sub-HDAs first
hdas = [
    base + r"\chops\cinema_chops_biomechanics_1.0.hda",
    base + r"\post\cinema_cop_anamorphic_flare_2.0.hda",
    base + r"\post\cinema_cop_sensor_noise_1.0.hda",
    base + r"\post\cinema_cop_stmap_aov_1.0.hda",
]

installed = []
for h in hdas:
    try:
        hou.hda.installFile(h)
        installed.append(h.split("\\")[-1])
    except Exception as e:
        installed.append("FAIL: " + str(e))

# Delete existing instances
for name in ["cinema_rig_test", "__cinema_rig_builder",
             "cinema_camera_rig_orchestrator_hda"]:
    old = hou.node("/obj/" + name)
    if old:
        old.destroy()

# Also delete any cinema::camera_rig instances
for n in hou.node("/obj").children():
    if n.type().name() == "cinema::camera_rig":
        n.destroy()

# Reload and rebuild the orchestrator
sys.path.insert(0, r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python")
import cinema_camera.builders.build_camera_rig_orchestrator as mod
importlib.reload(mod)

hda_path = mod.build_camera_rig_orchestrator_hda(save_dir=base)

result = "Installed: " + str(installed) + "\n" + "HDA rebuilt: " + hda_path
