"""Run with hython in an isolated seat. No model requests or scene operations."""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import traceback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--sandbox", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    sandbox = args.sandbox.resolve()
    for variable in ("USERPROFILE", "HOUDINI_USER_PREF_DIR", "HIP"):
        value = Path(os.environ.get(variable, "")).resolve()
        if not value.is_relative_to(sandbox) or value == sandbox:
            raise RuntimeError("Probe requires an isolated " + variable)
    state = json.loads((args.app / "installation.json").read_text())
    root = Path(state["active"]).resolve()
    if not root.is_relative_to(args.app.resolve()):
        raise RuntimeError("Installed runtime escaped application root")
    result = {"scope": "Separate headless Houdini process and offscreen Qt panel; not the artist GUI", "checks": {}}
    try:
        import hou
        result["houdini"] = ".".join(map(str, hou.applicationVersion()))
        result["python"] = sys.version
        # Import from Houdini's resolved package environment, without adding
        # the source checkout or its Python directories to sys.path.
        import synapse
        if not Path(synapse.__file__).resolve().is_relative_to(root):
            raise RuntimeError("Houdini imported a different SYNAPSE installation: " + synapse.__file__)
        result["checks"]["package_resolution"] = synapse.__file__
        for name in ("anthropic", "pydantic", "pydantic_core", "jiter", "websockets", "filelock", "shared", "retina", "host.cache_host_probe", "mcp_tools_memory", "moneta"):
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(root):
                raise RuntimeError(name + " was supplied by the machine rather than the installed payload: " + str(path))
            result["checks"][name] = str(path)
        from synapse.memory.moneta_runtime import moneta_available, schema_registered
        result["checks"]["moneta_import"] = moneta_available()
        result["checks"]["moneta_usd_schema"] = schema_registered()
        if not result["checks"]["moneta_usd_schema"]:
            raise RuntimeError("Bundled Moneta USD schema did not register")
        from PySide6 import QtWidgets
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.synapse_panel import createInterface
        widget = createInterface()
        widget.resize(560, 840)
        application.processEvents()
        result["checks"]["offscreen_panel_constructed"] = type(widget).__name__
        from synapse.server.doctor import run_doctor
        doctor = run_doctor({}, home=Path(os.environ["USERPROFILE"]))
        # Keep diagnostics as a separate report; warning rows for absent optional
        # substrates are not presented as installation failures or as passes.
        (args.report.parent / "houdini-doctor.json").write_text(json.dumps(doctor, indent=2, default=str), encoding="utf-8")
        result["checks"]["doctor_executed"] = True
        result["doctor_report"] = str(args.report.parent / "houdini-doctor.json")
        widget.close()
        result["status"] = "PASS"
    except Exception:
        result["status"] = "FAIL"
        result["error"] = traceback.format_exc()
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
