"""Qualify staged code in two owned disposable headless Houdini processes."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile

from . import native_policy
from .registration import installed_package
from .safety import SetupError, digest, json_bytes, no_links


def accepted_report(report, phase, manifest, choice):
    """A process exit or PASS word cannot substitute for a bound measurement."""
    if not isinstance(report, dict):
        return False
    fixed = {"status": "PASS", "phase": phase, "primary_backend": "moneta",
             "source_commit": manifest["source_revision"], "native_pyd_sha256": choice["pyd_sha256"],
             "native_value": choice["value"], "encrypted_records": 3,
             "scene_save_or_reopen": True, "preference_isolated": True,
             "source_or_backend_injected": False, "native_fallbacks": {}}
    if any(report.get(key) != want for key, want in fixed.items()):
        return False
    delta, witness = report.get("native_calls_delta"), report.get("native_c_call_witness")
    if not isinstance(delta, dict) or not isinstance(witness, dict):
        return False
    return all(type(delta.get(s)) is int and delta[s] > 0 for s in ("scan", "decay")) and all(
        type(witness.get(name)) is int and witness[name] > 0 for name in ("scan", "decay_batch"))


def qualify(runtime, manifest, target, planned_package, choice):
    native_policy.recheck(choice)
    root = no_links(tempfile.mkdtemp(prefix="synapse-native-check-"))
    paths = {n: root / n for n in ("home", "preferences", "temp", "appdata", "localappdata", "empty-packages", "project")}
    for path in paths.values():
        path.mkdir()
    # Import/backend policy is the planned registration; all operational data,
    # provider settings and keys belong exclusively to this disposable fixture.
    package = installed_package(runtime, manifest, paths["home"], native_value=choice["value"], native_site=choice["site"])
    controls = {"SYNAPSE_ROOT", "PYTHONPATH", "MONETA_SRC", "PXR_PLUGINPATH_NAME", "SYNAPSE_MEMORY_BACKEND", "MONETA_NATIVE"}
    imports = [row for row in planned_package["env"] if row["var"] in controls]
    package["env"] = imports + [row for row in package["env"] if row["var"] not in controls]
    major_minor = ".".join(target["houdini"].split(".")[:2])
    pref_pattern = paths["preferences"] / "houdini__HVER__"
    pref = Path(str(pref_pattern).replace("__HVER__", major_minor))
    (pref / "packages").mkdir(parents=True)
    (pref / "packages/synapse.json").write_bytes(json_bytes(package))
    key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    (root / "PRIVATE-fixture.key").write_text(key, encoding="ascii")
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        "SYSTEMROOT", "WINDIR", "COMSPEC", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "SYSTEMDRIVE"}}
    hfs = no_links(target["hfs"])
    env.update(PATH=os.pathsep.join([str(hfs / "bin"), str(Path(env.get("SYSTEMROOT", r"C:\Windows")) / "System32")]),
               HOME=str(paths["home"]), USERPROFILE=str(paths["home"]),
               APPDATA=str(paths["appdata"]), LOCALAPPDATA=str(paths["localappdata"]),
               HOUDINI_USER_PREF_DIR=str(pref_pattern), HOUDINI_PACKAGE_DIR=str(paths["empty-packages"]),
               TEMP=str(paths["temp"]), TMP=str(paths["temp"]), HOUDINI_TEMP_DIR=str(paths["temp"]),
               HIP=str(paths["project"]), QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", SYNAPSE_ENCRYPTION_KEY=key)
    results, calls = [], []
    for phase in ("write", "reopen"):
        output = root / (phase + ".json")
        config = {"schema": "synapse-native-install-check-1", "phase": phase, "sandbox": str(root),
                  "runtime": str(runtime), "preference": str(pref), "manifest_sha256": digest(json_bytes(manifest)),
                  "native_site": choice["site"], "native_files": choice["files"], "target": target,
                  "output": str(output), "native_value": choice["value"]}
        config_path = root / (phase + "-config.json")
        config_path.write_bytes(json_bytes(config))
        command = [str(hfs / "bin/hython.exe"), str(Path(__file__).with_name("native_probe.py")), str(config_path)]
        try:
            proc = subprocess.run(command, env=env, cwd=paths["project"], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                (root / (phase + ".log")).write_bytes(exc.stdout or b"")
            (root / "failure.json").write_bytes(json_bytes({"status": "FAIL", "phase": phase, "error_type": type(exc).__name__}))
            raise SetupError(f"Native qualification could not complete in an owned disposable process; registration is unchanged. Evidence: {root}") from exc
        (root / (phase + ".log")).write_bytes(proc.stdout)
        calls.append({"command": command, "rc": proc.returncode})
        (root / "invocations.json").write_bytes(json_bytes(calls))
        try:
            report = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SetupError(f"Native qualification has no complete result; registration is unchanged. Evidence: {root}") from exc
        if proc.returncode != 0 or not accepted_report(report, phase, manifest, choice):
            raise SetupError(f"Native qualification failed; no ON registration was activated. Evidence: {root}")
        results.append(report)
        native_policy.recheck(choice)
    proof = {"status": "PASS_NATIVE_EXECUTION_AND_MIRROR_REOPEN", "scope": "planned import/backend policy; disposable data and keys",
             "native_pyd_sha256": choice["pyd_sha256"], "configuration_sha256": digest(json_bytes(planned_package)),
             "probe_package_sha256": digest(json_bytes(package)), "phases": results, "evidence_directory": str(root),
             "could_not_verify": ["Artist GUI, production stores, future machine/configuration changes"]}
    (root / "result.json").write_bytes(json_bytes(proof))
    return proof
