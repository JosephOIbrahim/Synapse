"""Write the NR-VG-GPU-BUILD-LOCK receipt for the OpenCV 5.1 CUDA build.

Reads the build evidence and writes ``build_lock_receipt.json`` beside this
script. Standard library only. It configures, builds and installs nothing,
never imports cv2 and never touches a GPU: it parses the configure log, the
CMake cache, the install manifest, the staged recipe and the orchestrator's
run summaries, and sha256-hashes the installed native files.

Usage::

    python make_receipt.py --evidence-dir <folder holding the g1 run summaries>

The evidence folder is a required argument and is never written into the
receipt; files there are cited by name. Every recorded path is repo-relative
or under the ruled build root (R3: E:/OpenCV5.1_Prep). The generator refuses
to write (exit 2) when any other drive path would land in the receipt, and
exits 1 without writing when the evidence is missing or inconsistent.

The receipt carries no generation timestamp, so a re-run against unchanged
evidence reproduces it byte for byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

NODE = "NR-VG-GPU-BUILD-LOCK"
SCHEMA = "nr-vg-gpu-build-lock/1"
GENERATOR = "harness/vision/gpu_build_lock/make_receipt.py"
RECEIPT_NAME = "build_lock_receipt.json"

RULED_ROOT = "E:/OpenCV5.1_Prep"  # R3
OPENCV_SHA = "e4f78fbcf1a773fbed69e14500e8b734963eb585"
CONTRIB_SHA = "b67a855188a3d683813731010f6d39ac614733a4"
# Modules the R2 change-mask chain needs in the GENERATED (not the requested) list.
R2_MODULES = ("core", "imgproc", "cudaarithm", "cudafilters", "python3")
NATIVE_SUFFIXES = (".dll", ".exe", ".pyd")
CACHE_KEYS = (
    "OPENCV_ENABLE_NONFREE",
    "PYTHON3_LIMITED_API",
    "PYTHON3_VERSION_STRING",
    "CMAKE_BUILD_TYPE",
    "CUDA_ARCH_BIN",
    "CMAKE_CUDA_ARCHITECTURES",
    "BUILD_LIST",
)
MISMATCH_KEYS = ("mismatch_px", "mismatch_edge_px", "mismatch_interior_px")

# R4. The base interpreter sits outside the ruled root, so this generator does
# not read it: it is recorded by version and digest as measured by the
# orchestrator on 2026-11-08.
BASE_INTERPRETER = {
    "implementation": "CPython",
    "version": "3.12.10",
    "sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a",
    "provenance": "orchestrator measurement 2026-11-08; not recomputed here (outside this generator's read scope)",
}
# A transcribed digest must still be a digest: 64 lowercase hex characters.
if not re.fullmatch(r"[0-9a-f]{64}", BASE_INTERPRETER["sha256"]):
    raise SystemExit("make_receipt: BASE_INTERPRETER sha256 is not 64 hex characters")

AUTHORIZATION = {
    "by": "Joe",
    "date": "2026-11-08",
    "words": (
        "ultrathink scaffold running work with subagent teams that are focused on the /goal of "
        "getting Open CV 5.1 GPU version up and working on synapse locally and commit, git push, "
        "git release using CTO Best Practices."
    ),
    "kind": "goal-level go",
    "covers": ["configure", "build", "install"],
    "scope": (
        "One goal-level go that covers this window's configure, build and install acts. "
        "Recorded as that single goal-level authorization, not as separate per-act grants."
    ),
}

EVIDENCE_REQUIRED = (
    "g1-configure-summary.json",
    "g1-build-summary.json",
    "gpu-smoke-result.json",
    "worker-wheels.sha256.txt",
)
# Hashed and cited by name when present. Only g1_build.ps1 is read, and only
# for its parallelism switches; the others are never parsed.
EVIDENCE_CITED = (
    "readiness-before-configure.json",
    "g1_configure.ps1",
    "g1_build.ps1",
    "gpu_smoke.py",
)


class ReceiptError(RuntimeError):
    """The evidence is missing, inconsistent, or points outside the ruled root."""


def _fwd(p: object) -> str:
    return str(p).replace("\\", "/")


def _norm(p: object) -> str:
    return posixpath.normpath(_fwd(p)).lower()


def _under(path: object, root: object) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + "/")


def _inside(path: object, root: object, what: str) -> str:
    if not path or not _under(path, root):
        raise ReceiptError(f"{what} is not under {_fwd(root)}: {_fwd(path)}")
    return posixpath.normpath(_fwd(path))


def _sha256(path: object) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _text(path: object) -> str:
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def _json(path: object):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _pick(d: dict, keys) -> dict:
    return {k: d[k] for k in keys if k in d}


def _cmake_bool(value) -> bool | None:
    if value is None:
        return None
    v = str(value).strip().upper()
    if v in ("ON", "TRUE", "1", "YES", "Y"):
        return True
    if v in ("OFF", "FALSE", "0", "NO", "N"):
        return False
    return None


_DEFINE = re.compile(r"^-D([A-Za-z0-9_]+)(?::[A-Za-z]+)?=(.*)$")
_FLAGS_WITH_VALUE = ("-S", "-B", "-G", "-A", "-T")


def _cmake_args(tokens) -> dict:
    """Map configure arguments to {key: value}: -S/-B/-G/-A/-T by flag, -D by name."""
    out: dict = {}
    it = iter(str(t) for t in tokens)
    for tok in it:
        if tok in _FLAGS_WITH_VALUE:
            out[tok] = next(it, "")
        elif (m := _DEFINE.match(tok)) is not None:
            out[m.group(1)] = m.group(2)
        else:
            out[f"arg {tok}"] = "present"
    return out


def _flag_value(tokens: list, flag: str) -> str | None:
    """The value after ``flag`` (or in ``flag=value``) in an argument list; None when absent."""
    for k, tok in enumerate(tokens):
        if tok == flag:
            return tokens[k + 1] if k + 1 < len(tokens) else ""
        if tok.startswith(flag + "="):
            return tok.split("=", 1)[1]
    return None


_CACHE_LINE = re.compile(r"^([^#/:=\s][^:=]*):([A-Z]+)=(.*)$")


def _cmake_cache(text: str) -> dict:
    out: dict = {}
    for line in text.splitlines():
        m = _CACHE_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(3)
    return out


_UTC = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z$")


def _ts(value: object) -> datetime:
    m = _UTC.match(str(value))
    if not m:
        raise ReceiptError(f"unparseable UTC timestamp: {value!r}")
    base = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return base + timedelta(microseconds=int((m.group(2) or "")[:6].ljust(6, "0")))


def _z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha_in_name(name: str, prefix: str) -> str:
    m = re.fullmatch(re.escape(prefix) + r"-([0-9a-f]{40})", name)
    if not m:
        raise ReceiptError(f"source folder {name!r} does not carry a {prefix} commit")
    return m.group(1)


def _manifest_commits(node) -> dict:
    """Collect {folder name: commit} from every {path, commit} object in the manifest."""
    found: dict = {}
    if isinstance(node, dict):
        path, commit = node.get("path"), node.get("commit")
        if isinstance(path, str) and isinstance(commit, str):
            found[posixpath.basename(_fwd(path).rstrip("/"))] = commit
        for value in node.values():
            found.update(_manifest_commits(value))
    elif isinstance(node, list):
        for value in node:
            found.update(_manifest_commits(value))
    return found


_ASSIGN = re.compile(r"^([A-Z_]+)\s*=\s*\[", re.M)
_JOIN_LITERAL = re.compile(r"os\.path\.join\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_JOIN_ENV = re.compile(
    r"os\.path\.join\(\s*os\.getenv\(\s*'([A-Za-z_][A-Za-z0-9_]*)'\s*,\s*'([^']*)'\s*\)\s*,\s*'([^']*)'\s*\)"
)
_CUDA_FOLDER = re.compile(r"/CUDA/(v[0-9.]+)/?$", re.I)


def _loader_folders(text: str, what: str) -> list:
    """Folders a cv2 config*.py file adds, in file order. A literal folder must sit
    under the ruled root; an environment-variable folder is recorded by name, with
    its default reduced to the CUDA toolkit folder version (the literal is withheld)."""
    hits = []
    for m in _JOIN_LITERAL.finditer(text):
        folder = _inside(posixpath.join(_fwd(m.group(1)), m.group(2)), RULED_ROOT, f"{what} folder")
        hits.append((m.start(), {"path": folder}))
    for m in _JOIN_ENV.finditer(text):
        cuda = _CUDA_FOLDER.search(_fwd(m.group(2)))
        hits.append((m.start(), {
            "env": m.group(1),
            "subdir": m.group(3),
            "default_toolkit_folder": cuda.group(1) if cuda else None,
            "default_literal": "withheld: outside the ruled root",
        }))
    return [entry for _, entry in sorted(hits, key=lambda hit: hit[0])]


_DRIVE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
_HOST_MARKERS = re.compile(r"[\\/]users?[\\/]|appdata", re.I)


def find_leaks(text: str, host_markers: tuple = ()) -> list:
    """Snippets of every drive path in ``text`` outside the ruled root, plus any
    user-profile marker and any of ``host_markers`` (the evidence folder's own
    path parts, supplied at run time so no host folder name is committed here).
    Empty means the text is safe to commit."""
    root = RULED_ROOT.lower()
    bad = []
    for m in _DRIVE.finditer(text):
        head = text[m.start(): m.start() + len(root) + 1].lower()
        if not (head.startswith(root) and head[len(root):] in ("", "/", '"')):
            bad.append(text[m.start(): m.start() + 72])
    bad.extend(text[max(0, m.start() - 24): m.end() + 24] for m in _HOST_MARKERS.finditer(text))
    low = text.lower()
    for marker in host_markers:
        at = low.find(marker.lower())
        if marker and at >= 0:
            bad.append(text[max(0, at - 24): at + len(marker) + 24])
    return bad


def build_receipt(evidence_dir: Path) -> dict:
    ev = Path(evidence_dir)
    absent = [n for n in EVIDENCE_REQUIRED if not (ev / n).is_file()]
    if absent:
        raise ReceiptError(f"evidence missing: {', '.join(absent)}")
    cfg = _json(ev / "g1-configure-summary.json")
    run = _json(ev / "g1-build-summary.json")
    smoke = _json(ev / "gpu-smoke-result.json")
    stamp = str(cfg["stamp"])
    args_name = f"g1-configure-args-{stamp}.json"
    if not (ev / args_name).is_file():
        raise ReceiptError(f"evidence missing: {args_name}")
    used = _cmake_args(_json(ev / args_name))

    prep = RULED_ROOT + "/02_OpenCV_Setup/preparation"
    recipe_path = prep + "/Current_Configure.json"
    recipe = _json(recipe_path)
    staged = _cmake_args(recipe.get("configure_arguments", []))
    later_raw = recipe.get("later_build_arguments") or []
    staged_build = [str(t) for t in later_raw] if isinstance(later_raw, list) else str(later_raw).split()

    build_dir = _inside(used.get("-B"), RULED_ROOT, "configure build folder (-B)")
    src_dir = _inside(used.get("-S"), RULED_ROOT, "configure source folder (-S)")
    contrib_dir = posixpath.dirname(
        _inside(used.get("OPENCV_EXTRA_MODULES_PATH"), RULED_ROOT, "OPENCV_EXTRA_MODULES_PATH"))
    install_prefix = _inside(used.get("CMAKE_INSTALL_PREFIX"), RULED_ROOT, "CMAKE_INSTALL_PREFIX")

    # Sources: the folder names the build consumed, cross-checked against the
    # preparation manifest, then against the pinned pair.
    opencv_sha = _sha_in_name(posixpath.basename(src_dir), "opencv")
    contrib_sha = _sha_in_name(posixpath.basename(contrib_dir), "opencv_contrib")
    prep_manifest = prep + "/Preparation_Manifest.json"
    commits = _manifest_commits(_json(prep_manifest))
    if (commits.get(posixpath.basename(src_dir)) != opencv_sha
            or commits.get(posixpath.basename(contrib_dir)) != contrib_sha):
        raise ReceiptError("the configure source folders and Preparation_Manifest.json disagree on the commits")
    if (opencv_sha, contrib_sha) != (OPENCV_SHA, CONTRIB_SHA):
        raise ReceiptError("the built sources are not the pinned opencv / opencv_contrib pair")

    # Modules: the list configure GENERATED, read from the configure log.
    cfg_log = _inside(cfg.get("log"), RULED_ROOT, "configure log")
    log_text = _text(cfg_log)
    generated, gen_line = None, None
    for number, line in enumerate(log_text.splitlines(), 1):
        m = re.search(r"To be built:\s*(\S.*?)\s*$", line)
        if m:
            generated, gen_line = m.group(1).split(), number
            break
    if generated is None:
        raise ReceiptError("the configure log has no 'To be built:' line")
    if sorted(generated) != sorted(str(cfg.get("to_be_built", "")).split()):
        raise ReceiptError("the configure log and g1-configure-summary.json disagree on the generated modules")
    r2_missing = sorted(set(R2_MODULES) - set(generated))
    ocv_version = re.search(r"General configuration for OpenCV\s+(\S+)", log_text)
    cuda_ver = re.search(r"NVIDIA CUDA:\s+YES \(ver ([0-9.]+)(?:,\s*([^)]*))?\)", log_text)
    gpu_arch = re.search(r"NVIDIA GPU arch:\s+(\S[^\r\n]*?)\s*$", log_text, re.M)

    # CMake cache and the worker venv the binding was built for.
    cache_path = build_dir + "/CMakeCache.txt"
    cache = _cmake_cache(_text(cache_path))
    py_exe = _inside(cache.get("PYTHON3_EXECUTABLE"), RULED_ROOT, "PYTHON3_EXECUTABLE")
    if _norm(py_exe) != _norm(used.get("PYTHON3_EXECUTABLE", "")):
        raise ReceiptError("CMakeCache PYTHON3_EXECUTABLE differs from the configure arguments")
    worker_venv = posixpath.dirname(posixpath.dirname(py_exe))
    site = _inside(cache.get("PYTHON3_PACKAGES_PATH"), worker_venv, "PYTHON3_PACKAGES_PATH")
    venv_version = None
    for line in _text(worker_venv + "/pyvenv.cfg").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() in ("version", "version_info"):
            venv_version = value.strip()

    # Install manifest: where cv2 landed.
    manifest_path = build_dir + "/install_manifest.txt"
    entries = [ln.strip() for ln in _text(manifest_path).splitlines() if ln.strip()]
    listed = {_norm(e) for e in entries}
    pyds = [e for e in entries
            if re.search(r"/cv2/python-[0-9.]+/cv2\.cp[0-9]+-[^/]*\.pyd$", _fwd(e), re.I)]
    if len(pyds) != 1:
        raise ReceiptError(f"expected one installed cv2 extension, found {len(pyds)}")
    cv2_ext = _inside(pyds[0], worker_venv, "installed cv2 extension")
    abi_tag = re.search(r"cv2\.(cp[0-9]+)-", posixpath.basename(cv2_ext)).group(1)
    cv2_file = _inside(smoke.get("cv2_file"), worker_venv, "cv2 file the smoke run imported")
    if _norm(cv2_file) not in listed:
        raise ReceiptError("the cv2 file the smoke run imported is not in install_manifest.txt")

    # Native files: everything under the install prefix x64/vc17/bin, plus the binding.
    bin_dir = Path(install_prefix, "x64", "vc17", "bin")
    bin_files = sorted((p for p in bin_dir.iterdir() if p.is_file()), key=lambda p: p.name.lower())
    natives = [p for p in bin_files if p.suffix.lower() in NATIVE_SUFFIXES]
    if not natives:
        raise ReceiptError("no native files under the install prefix x64/vc17/bin")
    native_files = []
    for p in [*natives, Path(cv2_ext)]:
        posix = posixpath.normpath(p.as_posix())
        native_files.append({
            "path": posix,
            "sha256": _sha256(p),
            "bytes": p.stat().st_size,
            "in_install_manifest": _norm(posix) in listed,
        })

    # The cv2 loader config files decide where Windows resolves the DLLs from.
    cv2_dir = Path(site, "cv2")
    loader_files, binaries_paths, extension_paths = [], [], []
    for p in sorted(cv2_dir.glob("config*.py"), key=lambda p: p.name.lower()):
        text = _text(p)
        assigns = _ASSIGN.search(text)
        name = assigns.group(1) if assigns else None
        folders = _loader_folders(text, p.name)
        if name == "BINARIES_PATHS":
            binaries_paths.extend(folders)
        elif name == "PYTHON_EXTENSIONS_PATHS":
            extension_paths.extend(folders)
        loader_files.append({"path": posixpath.normpath(p.as_posix()), "sha256": _sha256(p), "assigns": name})
    init_text = _text(cv2_dir / "__init__.py")

    # Measured windows.
    t_cfg = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    cfg_secs = int(cfg["seconds"])
    b, i = run["build"], run["install"]
    b0, b1, i0, i1 = _ts(b["started"]), _ts(b["ended"]), _ts(i["started"]), _ts(i["ended"])
    if not (t_cfg + timedelta(seconds=cfg_secs) <= b0 < b1 <= i0 <= i1):
        raise ReceiptError("the configure, build and install windows are out of order")
    build_log = _inside(b.get("log"), RULED_ROOT, "build log")
    install_log = _inside(i.get("log"), RULED_ROOT, "install log")
    windows = [
        {
            "name": "configure",
            "started": _z(t_cfg),
            "ended": _z(t_cfg + timedelta(seconds=cfg_secs)),
            "seconds": cfg_secs,
            "measured": True,
            "timing": "started = the run stamp (1 s resolution); seconds measured by a clock around "
                      "the cmake call; ended = stamp + measured seconds",
            "exit_code": int(cfg["exit_code"]),
            "log": cfg_log,
            "log_sha256": _sha256(cfg_log),
        },
        {
            "name": "build",
            "command": b["command"],
            "started": b["started"],
            "ended": b["ended"],
            "seconds": b.get("seconds"),
            "measured": True,
            "timing": "started and ended are the build script's own UTC timestamps",
            "exit_code": int(b["exit_code"]),
            "warnings": b.get("warnings"),
            "log": build_log,
            "log_sha256": _sha256(build_log),
        },
        {
            "name": "install",
            "command": i["command"],
            "started": i["started"],
            "ended": i["ended"],
            "seconds": round((i1 - i0).total_seconds(), 3),
            "measured": True,
            "timing": "started and ended are the build script's own UTC timestamps; seconds = ended - started",
            "exit_code": int(i["exit_code"]),
            "log": install_log,
            "log_sha256": _sha256(install_log),
        },
    ]

    build_script = ev / "g1_build.ps1"
    script = _text(build_script) if build_script.is_file() else ""
    par = re.search(r"--parallel\s+(\d+)", str(b["command"]))
    mp = re.search(r"/MP(\d+)", script)
    parallelism = {
        "cmake_parallel": int(par.group(1)) if par else None,
        "cl_mp": int(mp.group(1)) if mp else None,
        "below_normal_priority": "BelowNormal" in script,
        "source": "the build command; g1_build.ps1",
    }

    vc = None
    for line in smoke.get("cuda_build_info") or []:
        m = re.match(r"Version control:\s+(.*)$", str(line))
        if m:
            vc = m.group(1).strip()
            break

    checks = {
        "configure_exit_zero": int(cfg["exit_code"]) == 0,
        "build_exit_zero": int(b["exit_code"]) == 0,
        "install_exit_zero": int(i["exit_code"]) == 0,
        "r2_chain_modules_generated": not r2_missing,
        "cv2_inside_worker_venv": _under(cv2_ext, worker_venv) and _under(cv2_file, worker_venv),
        "native_files_in_install_manifest": all(f["in_install_manifest"] for f in native_files),
    }
    nvcc = _fwd(cache.get("CMAKE_CUDA_COMPILER", ""))
    toolkit_folder = re.search(r"/CUDA/(v[0-9.]+)/bin/nvcc(?:\.exe)?$", nvcc, re.I)
    dev = smoke.get("device") or {}

    return {
        "node": NODE,
        "schema": SCHEMA,
        "generator": GENERATOR,
        "verdict": {"state": "built" if all(checks.values()) else "not_built", "checks": checks},
        "build_root": RULED_ROOT,
        "sources": {
            "opencv": opencv_sha,
            "opencv_contrib": contrib_sha,
            "opencv_dir": src_dir,
            "opencv_contrib_dir": contrib_dir,
            "anchors": [
                "configure -S source folder name",
                "OPENCV_EXTRA_MODULES_PATH folder name",
                "Preparation_Manifest.json commit fields",
            ],
            "binary_version_control": vc,
        },
        "modules": {
            "source": "configure_log",
            "generated": generated,
            "log": cfg_log,
            "log_line": gen_line,
            "requested_build_list": [m for m in str(cache.get("BUILD_LIST", "")).split(",") if m],
            "r2_chain_required": list(R2_MODULES),
            "r2_chain_missing": r2_missing,
        },
        "python": {
            "version": cache.get("PYTHON3_VERSION_STRING"),
            "abi_tag": abi_tag,
            "limited_api": _cmake_bool(cache.get("PYTHON3_LIMITED_API")),
            "basis": "version: CMakeCache PYTHON3_VERSION_STRING; abi_tag: the installed extension's file name; "
                     "limited_api: CMakeCache PYTHON3_LIMITED_API",
            "worker_venv_version": venv_version,
            "numpy": smoke.get("numpy"),
            "base_interpreter": BASE_INTERPRETER,
        },
        "install": {
            "command": i["command"],
            "exit_code": int(i["exit_code"]),
            "worker_venv": worker_venv,
            "cv2_file": cv2_file,
            "cv2_extension": cv2_ext,
            "install_prefix": install_prefix,
            "install_manifest": {"path": manifest_path, "entries": len(entries), "sha256": _sha256(manifest_path)},
            "staged_recipe_had_install_step": "--install" in staged_build,
        },
        "native_files": native_files,
        "native_files_skipped": [p.name for p in bin_files if p not in natives],
        "loader_files": loader_files,
        "cmake_cache": {"path": cache_path, "sha256": _sha256(cache_path), **{k: cache.get(k) for k in CACHE_KEYS}},
        "toolchain": {
            "generator": cache.get("CMAKE_GENERATOR"),
            "platform": cache.get("CMAKE_GENERATOR_PLATFORM"),
            "toolset": cache.get("CMAKE_GENERATOR_TOOLSET"),
            "system_version": used.get("CMAKE_SYSTEM_VERSION"),
            "cmake_version": ".".join(cache.get(f"CMAKE_CACHE_{part}_VERSION", "?")
                                      for part in ("MAJOR", "MINOR", "PATCH")),
            "opencv_version": ocv_version.group(1) if ocv_version else None,
            "cuda_toolkit": {
                "version": cuda_ver.group(1) if cuda_ver else None,
                "libraries": cuda_ver.group(2).split() if cuda_ver and cuda_ver.group(2) else [],
                "toolkit_folder": toolkit_folder.group(1) if toolkit_folder else None,
                "gpu_arch": gpu_arch.group(1) if gpu_arch else None,
            },
            "parallelism": parallelism,
        },
        "cuda_dll_resolution": {
            "loader": "cv2/__init__.py",
            "loader_calls_add_dll_directory": "os.add_dll_directory" in init_text,
            "binaries_paths": binaries_paths,
            "python_extensions_paths": extension_paths,
            "toolkit_at_build": toolkit_folder.group(1) if toolkit_folder else None,
            "toolkit_at_build_basis": "CMakeCache CMAKE_CUDA_COMPILER",
            "cuda_path_env_at_build": "not captured in the evidence set",
            "consequence": "the CUDA runtime DLLs the binding loads come from the folder CUDA_PATH names "
                           "at import time, plus bin/x64; a CUDA_PATH naming another toolkit changes "
                           "which runtime loads",
        },
        "recipe": {
            "staged": recipe_path,
            "staged_sha256": _sha256(recipe_path),
            "staged_status": recipe.get("status"),
            "candidate": recipe.get("candidate"),
            "configure_args_evidence": args_name,
            "configure_deltas": [
                {"key": k, "staged": staged.get(k), "used": used.get(k)}
                for k in sorted(set(staged) | set(used)) if staged.get(k) != used.get(k)
            ],
            "build_deltas": [
                {
                    "step": "build",
                    "staged_parallel": _flag_value(staged_build, "--parallel"),
                    "used_parallel": _flag_value(str(b["command"]).split(), "--parallel"),
                    "used": b["command"],
                },
                {"step": "install", "staged_had_install_step": "--install" in staged_build, "used": i["command"]},
            ],
        },
        "build_windows": windows,
        "authorization": AUTHORIZATION,
        "smoke": {
            "evidence": "gpu-smoke-result.json",
            **_pick(smoke, ("python", "numpy", "cv2_version", "cuda_device_count")),
            "cv2_file": cv2_file,
            "device": {
                "compute_capability": f"{dev.get('majorVersion')}.{dev.get('minorVersion')}",
                "total_memory_bytes": dev.get("totalMemory"),
                "multiprocessor_count": dev.get("multiProcessorCount"),
            },
            "cpu_changed_px": smoke.get("cpu_changed_px"),
            "gpu_naive_vs_cpu": _pick(smoke.get("gpu_naive_vs_cpu") or {}, MISMATCH_KEYS),
            "gpu_padded_vs_cpu": _pick(smoke.get("gpu_padded_vs_cpu") or {}, MISMATCH_KEYS),
            "gpu_padded_bytes_identical": smoke.get("gpu_padded_bytes_identical"),
            "cuda_build_info": [str(ln) for ln in smoke.get("cuda_build_info") or []
                                if str(ln).startswith(("NVIDIA CUDA", "NVIDIA GPU arch"))],
            "loaded_modules_count": len(smoke.get("loaded_modules") or []),
        },
        "worker_wheels": [
            {"file": parts[2], "sha256": parts[0], "bytes": int(parts[1])}
            for parts in (ln.split() for ln in _text(ev / "worker-wheels.sha256.txt").splitlines())
            if len(parts) == 3 and re.fullmatch(r"[0-9a-f]{64}", parts[0])
        ],
        "evidence": {
            "run_records": [
                {"name": n, "sha256": _sha256(ev / n)}
                for n in (*EVIDENCE_REQUIRED, args_name, *EVIDENCE_CITED) if (ev / n).is_file()
            ],
            "build_root_files": [
                {"path": p, "sha256": _sha256(p)} for p in (prep_manifest,)
            ],
        },
        "limits": [
            f"The binary does not embed its source commit (cv2 build information reports version control "
            f"as {vc!r}); the commit identity rests on the source folder names in the configure arguments "
            f"and the commit fields of Preparation_Manifest.json.",
            "The base interpreter's sha256 is the orchestrator's 2026-11-08 measurement; this generator "
            "does not recompute it.",
            "The CUDA runtime DLLs (cudart, npp, cublas, cufft) load at import time from the folder "
            "CUDA_PATH names plus bin/x64; they sit outside the ruled root and are not digested here.",
            "The configure end time is derived from the run stamp plus the measured seconds (1 s "
            "resolution); build and install times are the build script's own UTC timestamps.",
            "The smoke run recorded an empty loaded-module list; the loaded-module witness belongs to "
            "the CUDA backend's witness().",
            "The CUDA_PATH environment value at build time is not in the evidence set; the toolkit the "
            "build used is recorded from CMakeCache (cuda_dll_resolution.toolkit_at_build).",
            "Preparation_Manifest.json in the ruled root is digested, not advanced: its state block still "
            "reads " + ", ".join(f"{k}={v}" for k, v in sorted((_json(prep_manifest).get("state") or {}).items()))
            + ". This receipt is the record of the build; the prep project's own flags are its owner's.",
        ],
    }


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--evidence-dir", required=True, type=Path,
                        help="folder holding the g1 run summaries (read only; never recorded)")
    args = parser.parse_args(argv)
    try:
        receipt = build_receipt(args.evidence_dir)
    except (ReceiptError, KeyError, OSError, ValueError) as exc:
        print(f"make_receipt: no receipt written: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(receipt, indent=2, ensure_ascii=True) + "\n"
    ev_parts = tuple(p for p in Path(args.evidence_dir).resolve().parts[1:] if len(p) > 3)
    leaks = find_leaks(text, ev_parts)
    if leaks:
        print(f"make_receipt: refusing to write; these would record a path outside {RULED_ROOT}:",
              file=sys.stderr)
        for snippet in leaks:
            print(f"  {snippet}", file=sys.stderr)
        return 2
    out = Path(__file__).resolve().parent / RECEIPT_NAME
    tmp = out.with_name(out.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, out)
    print(f"wrote {RECEIPT_NAME}: verdict {receipt['verdict']['state']}; "
          f"{len(receipt['native_files'])} native files digested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
