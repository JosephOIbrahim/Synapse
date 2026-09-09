"""Launch only a separate Houdini process with all probe data under one root."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from synapse_setup.safety import no_links, inside


def probe_environment(sandbox, pref):
    sandbox = no_links(sandbox)
    env = dict(os.environ)
    for name in list(env):
        if (name.startswith(("SYNAPSE", "MONETA", "ANTHROPIC", "OPENAI", "GEMINI", "NVIDIA", "GOOGLE_API", "AZURE_OPENAI", "OLLAMA"))
                or "API_KEY" in name or name in {"HOUDINI_PATH", "HOUDINI_PACKAGE_DIR", "HSITE", "PYTHONPATH", "PYTHONHOME", "PXR_PLUGINPATH_NAME"}):
            del env[name]
    paths = {"USERPROFILE": sandbox / "home", "HOME": sandbox / "home", "HIP": sandbox / "project",
             "HOUDINI_USER_PREF_DIR": pref, "HOUDINI_PACKAGE_DIR": sandbox / "empty-packages",
             "HOUDINI_TEMP_DIR": sandbox / "temp", "TEMP": sandbox / "temp", "TMP": sandbox / "temp"}
    for name, path in paths.items():
        inside(path, sandbox)
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--sandbox", required=True, type=Path)
    parser.add_argument("--hfs", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    state = json.loads((args.app / "installation.json").read_text())
    env = probe_environment(args.sandbox, Path(state["registrations"][0]["pref"]))
    command = [str(args.hfs / "bin/hython.exe"), str(Path(__file__).with_name("verify_houdini.py")),
               "--app", str(args.app), "--sandbox", str(args.sandbox), "--report", str(args.report)]
    result = subprocess.run(command, env=env, cwd=env["HIP"], capture_output=True, text=True,
                            timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    args.report.with_suffix(".stdout.txt").write_text(result.stdout, encoding="utf-8")
    args.report.with_suffix(".stderr.txt").write_text(result.stderr, encoding="utf-8")
    print(result.stdout[-12000:])
    print(result.stderr[-4000:])
    sys.exit(result.returncode)
