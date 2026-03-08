"""Build the demo .hip via Synapse."""
import hou
import sys
import os
import importlib

# Set env var so the builder can find HDAs
os.environ["CINEMA_CAMERA_PATH"] = r"C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera"

sys.path.insert(0, r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python")
sys.path.insert(0, r"C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera\examples")

import build_focus_pull_example as mod
importlib.reload(mod)

save_path = os.path.join(
    os.environ["CINEMA_CAMERA_PATH"],
    "examples",
    "cinema_rig_focus_pull_example.hip",
)

result_path = mod.build_focus_pull_example(save_path=save_path)
result = "Demo scene saved: " + result_path
