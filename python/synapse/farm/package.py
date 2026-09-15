"""Immutable local render-package utilities. Importable without Houdini."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

QUALIFIED_BUILD = "22.0.400"
MAX_LOCAL_FRAMES = 120
MAX_LOCAL_DIMENSION = 2048
MAX_LOCAL_SAMPLES = 128


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def read_json(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def owned_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("A package path leaves this request's folder.")
    if path == root or Path(root / relative).is_symlink():
        raise ValueError("A package entry must name an owned regular file.")
    return path


def file_receipt(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Required regular file is missing: " + path.name)
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
        after = os.fstat(stream.fileno())
    current = path.stat()
    key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if not after.st_size or key(before) != key(after) or key(after) != key(current):
        raise ValueError("Required file changed while reading: " + path.name)
    return {"sha256": sha.hexdigest(), "size": after.st_size,
            "mtime_ns": after.st_mtime_ns}


def frozen_copy(source, destination, expected_sha256=None):
    source, destination = Path(source), Path(destination)
    before = file_receipt(source)
    if expected_sha256 is not None and before["sha256"] != expected_sha256:
        raise ValueError("The saved scene changed after the plan was created. Prepare again.")
    if destination.exists():
        raise ValueError("The immutable snapshot destination already exists.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    after, copied = file_receipt(source), file_receipt(destination)
    if before != after or copied["sha256"] != before["sha256"]:
        raise ValueError("An input changed during its snapshot. Prepare again.")
    return copied


def validate_local_plan(plan):
    if plan.get("profile_id") != "local":
        raise ValueError("HQueue is not configured and qualified for this installation.")
    frames = plan.get("frames", [])
    if (not frames or len(frames) > MAX_LOCAL_FRAMES or
            any(type(f) is not int for f in frames) or sorted(set(frames)) != frames):
        raise ValueError("The local profile accepts 1–120 distinct ordered integer frames.")
    if any(type(plan.get(k)) is not int or not 1 <= plan[k] <= MAX_LOCAL_DIMENSION
           for k in ("width", "height")):
        raise ValueError("The local profile is limited to 2048 by 2048 pixels.")
    if type(plan.get("samples")) is not int or not 1 <= plan["samples"] <= MAX_LOCAL_SAMPLES:
        raise ValueError("The local profile accepts 1–128 samples.")
    expected = digest({k: v for k, v in plan.items() if k != "digest"})
    if plan.get("digest") != expected:
        raise ValueError("The reviewed plan's digest does not match its contents.")


def seal_manifest(job_dir, manifest):
    root = Path(job_dir)
    records = []
    for relative in manifest.pop("file_paths"):
        path = owned_path(root, relative)
        records.append({"path": str(path.relative_to(root.resolve())).replace("\\", "/"),
                        **file_receipt(path)})
    manifest["files"] = sorted(records, key=lambda entry: entry["path"])
    manifest["manifest_digest"] = digest(manifest)
    atomic_json(root / "package.json", manifest)
    return manifest


def verify_manifest(job_dir, plan, expected_manifest_digest):
    root = Path(job_dir)
    manifest = read_json(root / "package.json")
    observed = digest({k: v for k, v in manifest.items() if k != "manifest_digest"})
    if (not expected_manifest_digest or observed != expected_manifest_digest or
            manifest.get("manifest_digest") != observed or
            manifest.get("plan_digest") != plan["digest"] or
            manifest.get("frames") != plan["frames"]):
        raise ValueError("The frozen package differs from the prepared plan.")
    seen = set()
    for entry in manifest.get("files", []):
        if entry["path"] in seen:
            raise ValueError("Duplicate immutable package entry.")
        seen.add(entry["path"])
        actual = file_receipt(owned_path(root, entry["path"]))
        if (actual["sha256"], actual["size"]) != (entry["sha256"], entry["size"]):
            raise ValueError("A frozen package input changed: " + entry["path"])
    if not seen or manifest.get("graph") not in seen:
        raise ValueError("The frozen TOP graph is missing from the package.")
    if [entry.get("frame") for entry in manifest.get("outputs", [])] != plan["frames"]:
        raise ValueError("The prepared output set differs from the requested frames.")
    for output in manifest["outputs"]:
        owned_path(root, output["path"])
    return manifest


def isolated_environment(hfs, runtime_dir):
    """Allowlist the worker environment; never forward model/application credentials."""
    hfs, runtime_dir = Path(hfs), Path(runtime_dir)
    for name in ("prefs", "temp", "appdata", "localappdata"):
        (runtime_dir / name).mkdir(parents=True, exist_ok=True)
    keep = ("SystemRoot", "WINDIR", "COMSPEC", "COMPUTERNAME", "USERNAME",
            "ProgramData", "ProgramFiles", "ProgramFiles(x86)")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    search = [str(hfs / "bin"), str(hfs / "python313")]
    search.append(str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"))
    env.update({"PATH": os.pathsep.join(search), "HFS": str(hfs),
                "HOUDINI_PATH": "&", "HOUDINI_PACKAGE_SKIP": "1",
                "HOUDINI_NO_ENV_FILE": "1", "HOUDINI_MAXTHREADS": "2",
                "HOUDINI_USER_PREF_DIR": str(runtime_dir / "prefs/houdini__HVER__"),
                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "TEMP": str(runtime_dir / "temp"), "TMP": str(runtime_dir / "temp"),
                "USERPROFILE": str(runtime_dir), "APPDATA": str(runtime_dir / "appdata"),
                "LOCALAPPDATA": str(runtime_dir / "localappdata")})
    return env


def process_identity(pid):
    """Query a PID without signal delivery; None means inaccessible/unknown."""
    if os.name != "nt":
        try:
            fields = Path("/proc/{}/stat".format(int(pid))).read_text().split()
            return {"pid": int(pid), "birth": fields[21], "alive": fields[2] != "Z"}
        except FileNotFoundError:
            return {"pid": int(pid), "alive": False}
        except OSError:
            return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, int(pid))
    if not handle:
        return {"pid": int(pid), "alive": False} if ctypes.get_last_error() == 87 else None
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        birth = (times[0].dwHighDateTime << 32) + times[0].dwLowDateTime
        return {"pid": int(pid), "birth": str(birth),
                "alive": kernel.WaitForSingleObject(handle, 0) == 258}
    finally:
        kernel.CloseHandle(handle)
