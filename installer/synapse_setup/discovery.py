"""Read-only Windows/Houdini discovery. No hou import, registry writes or keys."""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess

TESTED_BUILD = "22.0.400"


def run(command, *, env=None, timeout=20):
    return subprocess.run(command, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def documents_dir():
    if os.name == "nt":
        # CSIDL_PERSONAL resolves the current user's redirected Known Folder.
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
            return Path(buf.value)
    return Path.home() / "Documents"


def preference_candidates(version, environ=None, home=None, documents=None):
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    docs = documents_dir() if documents is None else Path(documents)
    major_minor = ".".join(version.split(".")[:2])
    entries = []
    override = env.get("HOUDINI_USER_PREF_DIR")
    if override:
        expanded = override.replace("__HVER__", major_minor)
        entries.append((Path(os.path.expandvars(expanded)), "HOUDINI_USER_PREF_DIR"))
    entries.append((docs / ("houdini" + major_minor), "Windows Documents (redirected folder supported)"))
    for base in (home / "Documents", home / "OneDrive/Documents",
                 *(Path(env[k]) / "Documents" for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial") if env.get(k))):
        path = base / ("houdini" + major_minor)
        if path.is_dir():
            entries.append((path, "Existing preference folder"))
    seen, result = set(), []
    for path, source in entries:
        key = os.path.normcase(str(path.resolve()))
        if key not in seen:
            result.append({"path": str(path), "source": source})
            seen.add(key)
    return result


def hconfig(hfs: Path, pref=None):
    env = os.environ.copy()
    if pref is not None:
        env["HOUDINI_USER_PREF_DIR"] = str(pref)
    result = run([str(hfs / "bin/hconfig.exe"), "-a"], env=env)
    if result.returncode:
        raise ValueError(f"Houdini configuration check failed ({result.returncode}): {hfs}")
    # Never expose the unfiltered output: hconfig can include credentials.
    allowed = {"HOUDINI_USER_PREF_DIR", "HFS", "HOUDINI_VERSION", "HOUDINI_PACKAGE_DIR", "HSITE"}
    return {k: v for k, v in re.findall(r"^([A-Z_0-9]+)\s*:=\s*['\"](.*?)['\"]\s*$", result.stdout, re.M) if k in allowed}


def file_version(path):
    if os.name != "nt":
        return None
    api = ctypes.windll.version
    size = api.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(str(path), 0, size, buf):
        return None
    ptr, count = ctypes.c_void_p(), ctypes.c_uint()
    if not api.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(count)):
        return None
    data = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32))
    # SideFX encodes 22.0.400 as Windows file version 22.0.0.400.
    return f"{data[2] >> 16}.{data[2] & 65535}.{data[3] & 65535}"


def validate_houdini(hfs):
    hfs = Path(hfs).resolve()
    if not (hfs / "bin/hconfig.exe").is_file() or not (hfs / "bin/houdini.exe").is_file():
        raise ValueError("Choose the Houdini application folder containing bin/houdini.exe and bin/hconfig.exe.")
    version = file_version(hfs / "bin/houdini.exe")
    if not version:
        raise ValueError(f"Cannot read Houdini's executable version: {hfs}")
    interpreters = sorted(hfs.glob("python*/python.exe"), reverse=True)
    actual = None
    for exe in interpreters:
        # Houdini includes empty compatibility directories: execute the candidate.
        try:
            result = run([str(exe), "-I", "-S", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"])
            if result.returncode == 0 and re.fullmatch(r"3\.\d+", result.stdout.strip()):
                actual = result.stdout.strip()
                break
        except (OSError, subprocess.TimeoutExpired):
            continue
    if actual not in {"3.11", "3.13"}:
        raise ValueError(f"Houdini Python {actual or 'unavailable'} has no bundled SYNAPSE native SDK. Supported payload ABIs: 3.11 and 3.13.")
    return {"hfs": str(hfs), "version": version, "python": actual,
            "tested": version == TESTED_BUILD and actual == "3.13"}


def discover():
    roots = set()
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if os.environ.get(key):
            roots.update((Path(os.environ[key]) / "Side Effects Software").glob("Houdini *"))
    if os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Side Effects Software", 0, winreg.KEY_READ | view) as base:
                        for i in range(winreg.QueryInfoKey(base)[0]):
                            name = winreg.EnumKey(base, i)
                            if name.startswith("Houdini "):
                                with winreg.OpenKey(base, name) as sub:
                                    try:
                                        roots.add(Path(winreg.QueryValueEx(sub, "InstallPath")[0]))
                                    except OSError:
                                        pass
                except OSError:
                    pass
    entries, errors = [], []
    for root in sorted(roots, reverse=True):
        if not (root / "bin/houdini.exe").is_file():
            continue
        try:
            entry = validate_houdini(root)
            candidates = preference_candidates(entry["version"])
            try:
                config = hconfig(root)
                if config.get("HOUDINI_USER_PREF_DIR"):
                    candidates.insert(0, {"path": config["HOUDINI_USER_PREF_DIR"], "source": "Houdini hconfig (current launch environment)"})
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                errors.append(str(exc))
            entry["preferences"] = candidates
            entries.append(entry)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))
    entries.sort(key=lambda x: (x["tested"], tuple(map(int, x["version"].split(".")))), reverse=True)
    return {"installations": entries, "errors": errors}


def running_houdini():
    if os.name != "nt":
        return []
    # tasklist is read-only and avoids requiring PowerShell scripts or WMI.
    import csv
    result = run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/tasklist.exe"), "/FO", "CSV", "/NH"])
    if result.returncode:
        raise ValueError("Cannot check running Houdini sessions. Try again after saving and closing Houdini.")
    names = {"houdini.exe", "houdinifx.exe", "hindie.exe", "hescape.exe", "hython.exe", "hbatch.exe", "hserverdummy.exe"}
    return [{"name": row[0], "pid": row[1]} for row in csv.reader(result.stdout.splitlines()) if len(row) > 1 and row[0].lower() in names]


def external_package_dirs(hfs=None):
    env = os.environ
    dirs = [Path(x) for x in env.get("HOUDINI_PACKAGE_DIR", "").split(";") if x and "$" not in x]
    if env.get("HSITE"):
        dirs.extend(Path(env["HSITE"]).glob("houdini*/packages"))
    if hfs:
        dirs.append(Path(hfs) / "packages")
    return dirs
