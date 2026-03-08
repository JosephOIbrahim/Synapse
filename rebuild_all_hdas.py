"""Rebuild all 4 sub-HDAs then the orchestrator."""
import hou
import sys
import importlib

sys.path.insert(0, r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python")

base = r"C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera\hda"

lines = []

# Clean up any existing nodes
for n in hou.node("/obj").children():
    if "cinema" in n.type().name() or n.name().startswith("__"):
        n.destroy()

# Rebuild each sub-HDA
builders = [
    ("cinema_camera.builders.build_chops_biomechanics", "build_chops_biomechanics_hda",
     base + r"\chops"),
    ("cinema_camera.builders.build_cop_anamorphic_flare", "build_cop_anamorphic_flare_hda",
     base + r"\post"),
    ("cinema_camera.builders.build_cop_sensor_noise", "build_cop_sensor_noise_hda",
     base + r"\post"),
    ("cinema_camera.builders.build_cop_stmap_aov", "build_cop_stmap_aov_hda",
     base + r"\post"),
]

for mod_name, func_name, save_dir in builders:
    try:
        mod = importlib.import_module(mod_name)
        importlib.reload(mod)
        func = getattr(mod, func_name)
        path = func(save_dir=save_dir)
        lines.append("OK: " + mod_name.split(".")[-1] + " -> " + path.split("\\")[-1])
    except Exception as e:
        lines.append("FAIL: " + mod_name.split(".")[-1] + " -> " + str(e))

# Install the rebuilt sub-HDAs
for hda_file in [
    base + r"\chops\cinema_chops_biomechanics_1.0.hda",
    base + r"\post\cinema_cop_anamorphic_flare_2.0.hda",
    base + r"\post\cinema_cop_sensor_noise_1.0.hda",
    base + r"\post\cinema_cop_stmap_aov_1.0.hda",
]:
    try:
        hou.hda.installFile(hda_file)
    except Exception:
        pass

# Clean up again before orchestrator rebuild
for n in hou.node("/obj").children():
    if "cinema" in n.type().name() or n.name().startswith("__"):
        n.destroy()

# Rebuild orchestrator
import cinema_camera.builders.build_camera_rig_orchestrator as orch_mod
importlib.reload(orch_mod)
orch_path = orch_mod.build_camera_rig_orchestrator_hda(save_dir=base)
lines.append("OK: orchestrator -> " + orch_path.split("\\")[-1])

result = "\n".join(lines)
