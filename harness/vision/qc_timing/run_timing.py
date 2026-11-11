"""NR-QC-TIMING: the dry pass and the timed passes, in ONE process (frozen rule r2).

Run under the R4 venv with ``-B`` and PYTHONPATH set to the release tree only.
Exit codes: 0 done, 2 not quiet (what was recorded is kept), 3 an exception in
the dry pass, 4 a startup assert failed or the manifest is not clean (before any
pass), 5 a second exception on one frame (Joe's F4 ruling: the first voids the
pass and it is redone once; everything recorded so far is kept).

Nothing here imports ``retina``, ``cv2`` or ``OpenImageIO`` at module level, so the
pure helpers (process-scan parsing, call summaries, the CPU sample arithmetic)
load on stock Python for tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

EXPECTED = {
    "python": "3.12.10", "numpy": "2.4.4", "cv2": "5.0.0", "openimageio": "3.1.15.0",
    "tree_commit": "7f8c5ec3cf6a794691d1df47b0b167f9147e7ac5",
    "blobs": {
        "retina/firefly_scan.py": "4f78123eef87bb873e28ad68d0daf8224e2cf2aa",
        "retina/frame_reader.py": "4a6fe0d133922dfb74fc37be6016a7fabe8ade81",
    },
}
#: line -> substrings that line must hold in firefly_scan.py (r2 3.7)
LINE_ASSERTS = {
    292: ("cv2.medianBlur",), 313: ("cv2.dilate", "cv2.erode"), 314: ("cv2.dilate",),
    352: ("cv2.connectedComponentsWithStats",), 373: ("cv2.dilate",), 458: ("cv2.imwrite",),
    542: ("cv2.boxFilter",), 549: ("cv2.boxFilter",),
}
DENSE_LINES = (292, 313, 314, 352, 542, 549)
WRAPPED = ("medianBlur", "dilate", "erode", "connectedComponentsWithStats", "boxFilter", "imwrite")
ORDER = ("char-8", "sib-v016", "sib-v017", "char-9", "char-2",
         "char-10", "char-3", "char-4", "char-13", "char-12")
TIER = ORDER[:3]
EXIT_OK, EXIT_NOT_QUIET, EXIT_DRY_EXCEPTION, EXIT_STARTUP, EXIT_EXCEPTION_TWICE = 0, 2, 3, 4, 5


class StartupError(Exception):
    pass


class NotQuiet(Exception):
    pass


class DryPassException(Exception):
    pass


class ExceptionTwice(Exception):
    pass


# ---------------------------------------------------------------- pure helpers
def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def cpu_load(prev: Tuple[int, int, int], cur: Tuple[int, int, int]) -> float:
    """Load 0..1 from two ``GetSystemTimes`` readings (idle, kernel, user).

    Kernel time INCLUDES idle time, so busy = (kernel - idle) + user and
    total = kernel + user.
    """
    idle = cur[0] - prev[0]
    total = (cur[1] - prev[1]) + (cur[2] - prev[2])
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - idle / total))


def parse_process_list(text: str, own_pid: int) -> Dict[str, Any]:
    """Quiet-machine scan (r2 3.9) from CIM JSON (ProcessId, Name, CommandLine).

    Blocked: image name starting husk, hython or houdini (any case), or a python*
    process whose command line runs pytest, other than ``own_pid``. hserver and
    sesinetd may run. A blocker is recorded by pid and name only.
    """
    data = json.loads(text) if text.strip() else []
    if isinstance(data, dict):
        data = [data]
    blocked = []
    for p in data:
        pid, name = int(p.get("ProcessId", -1)), str(p.get("Name") or "")
        low = name.lower()
        if pid == own_pid:
            continue
        if low.startswith(("husk", "hython", "houdini")):
            blocked.append({"pid": pid, "name": name})
        elif low.startswith("python") and "pytest" in str(p.get("CommandLine") or "").lower():
            blocked.append({"pid": pid, "name": name})
    return {"scanned": len(data), "blocked": blocked}


def summarize_calls(calls: Sequence[Dict[str, Any]], overhead_ns: int = 0) -> Dict[str, Any]:
    """Per-pass split from the recorded cv2 calls.

    Each call: ``type``, ``file`` (basename), ``line``, ``inner_ns``. Calls from
    firefly_scan.py are keyed by line; anything else is an "other" line, listed
    and counted (it lands in S_rest because S_rest = S - S_dense).
    """
    lines: Dict[str, Dict[str, Any]] = {}
    other: Dict[Tuple[str, int, str], Dict[str, Any]] = {}
    types: Dict[str, Dict[str, Any]] = {}
    for c in calls:
        sec = c["inner_ns"] / 1e9
        t = types.setdefault(c["type"], {"calls": 0, "inner_s": 0.0})
        t["calls"] += 1
        t["inner_s"] += sec
        if c["file"] == "firefly_scan.py":
            e = lines.setdefault(str(c["line"]), {"calls": 0, "inner_s": 0.0})
        else:
            e = other.setdefault((c["file"], c["line"], c["type"]),
                                 {"file": c["file"], "line": c["line"], "type": c["type"], "calls": 0, "inner_s": 0.0})
        e["calls"] += 1
        e["inner_s"] += sec
    dense = sum(lines.get(str(n), {}).get("inner_s", 0.0) for n in DENSE_LINES)
    return {
        "lines": lines,
        "other_lines": sorted(other.values(), key=lambda e: (e["file"], e["line"], e["type"])),
        "types": types,
        "W": lines.get("458", {}).get("inner_s", 0.0),
        "S_dense": dense,
        "overhead_s": overhead_ns / 1e9,
    }


def order_entries(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Voters first (tier, char-9, char-2), then char-10, char-3, char-4, char-13, char-12."""
    rank = {i: n for n, i in enumerate(ORDER)}
    return sorted(entries, key=lambda e: (rank.get(e["id"], 99), str(e["frame"])))


# ------------------------------------------------------------------ the machine
def _get_system_times() -> Tuple[int, int, int]:
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

    idle, kern, user = FILETIME(), FILETIME(), FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
        raise OSError("GetSystemTimes failed")
    return tuple((f.hi << 32) | f.lo for f in (idle, kern, user))  # type: ignore[return-value]


def cpu_sample(seconds: float) -> Dict[str, Any]:
    a, t0 = _get_system_times(), time.perf_counter()
    time.sleep(seconds)
    b, t1 = _get_system_times(), time.perf_counter()
    return {"cpu_sample_s": t1 - t0, "cpu_load": cpu_load(a, b)}


_CIM = ("Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | "
        "ConvertTo-Json -Compress")


def process_scan(own_pid: Optional[int] = None) -> Dict[str, Any]:
    """Scan for blockers. Any failure (timeout, bad output, no powershell) returns
    the error dict, which voids the pass and waits for a clean scan."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", _CIM],
                           capture_output=True, timeout=120)
        if r.returncode != 0:
            return {"scanned": 0, "blocked": [], "error": "process scan failed"}
        text = r.stdout.decode("utf-8", errors="replace")
        return parse_process_list(text, os.getpid() if own_pid is None else own_pid)
    except (subprocess.TimeoutExpired, OSError, ValueError, TypeError, AttributeError) as exc:
        return {"scanned": 0, "blocked": [], "error": f"process scan raised {type(exc).__name__}"}


def exception_type(text: str) -> str:
    """'scan: MemoryError: ...' -> 'scan raised MemoryError' (never a path)."""
    parts = [x.strip() for x in str(text).split(":")]
    return f"{parts[0]} raised {parts[1]}" if len(parts) > 1 else "pass raised an exception"


def file_sha256(path: str) -> str:
    """sha256 of a file with CRLF folded to LF, so it equals git's blob bytes."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def _ps(cmd: str) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def machine_info(out_dir: str) -> Dict[str, Any]:
    drive = os.path.splitdrive(os.path.abspath(out_dir))[0][:1]
    disk = _ps(f"(Get-Partition -DriveLetter {drive} | Get-Disk).FriendlyName") if drive else ""
    cpu = _ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name") or platform.processor()
    return {"cpu_model": cpu, "scratch_drive_model": disk or None}


# --------------------------------------------------------------- instrumentation
class Instrument:
    """Wraps cv2 attributes with timers. Product files are not touched."""

    def __init__(self, cv2: Any) -> None:
        self.cv2 = cv2
        self.real: Dict[str, Any] = {}
        self.active = False
        self.calls: List[Dict[str, Any]] = []
        self.overhead_ns = 0
        self.n_labels: Optional[int] = None

    def install(self) -> None:
        for name in WRAPPED:
            self.real[name] = getattr(self.cv2, name)
            setattr(self.cv2, name, self._wrap(name, self.real[name]))

    def restore(self) -> None:
        for name, fn in self.real.items():
            setattr(self.cv2, name, fn)
        self.real.clear()

    def _wrap(self, name: str, fn: Any) -> Any:
        def wrapper(*a: Any, **k: Any) -> Any:
            o0 = time.perf_counter_ns()
            if not self.active:
                return fn(*a, **k)
            f = sys._getframe(1)
            file, line = os.path.basename(f.f_code.co_filename), f.f_lineno
            t0 = time.perf_counter_ns()
            ret = fn(*a, **k)
            t1 = time.perf_counter_ns()
            self.calls.append({"type": name, "file": file, "line": line, "inner_ns": t1 - t0})
            if name == "connectedComponentsWithStats":
                self.n_labels = int(ret[0])
            self.overhead_ns += (time.perf_counter_ns() - o0) - (t1 - t0)
            return ret
        return wrapper

    def begin(self) -> None:
        self.calls, self.overhead_ns, self.n_labels, self.active = [], 0, None, True

    def end(self) -> Dict[str, Any]:
        self.active = False
        return summarize_calls(self.calls, self.overhead_ns)


# ---------------------------------------------------------------------- startup
def read_threads(oiio: Any, cv2: Any) -> Dict[str, int]:
    return {"oiio": int(oiio.get_int_attribute("threads")),
            "exr": int(oiio.get_int_attribute("exr_threads")),
            "cv2": int(cv2.getNumThreads())}


def startup_checks() -> Dict[str, Any]:
    """Every assert of the brief. Raises StartupError naming the first failure."""
    py = platform.python_version()
    if py != EXPECTED["python"]:
        raise StartupError(f"Python {py}, need {EXPECTED['python']}")
    try:
        import numpy
        import cv2
        import OpenImageIO as oiio
    except ImportError as exc:
        raise StartupError(f"import failed: {exc}") from exc
    for name, got in (("numpy", numpy.__version__), ("cv2", cv2.__version__), ("openimageio", oiio.__version__)):
        if got != EXPECTED[name]:
            raise StartupError(f"{name} {got}, need {EXPECTED[name]}")
    entries = [e for e in os.environ.get("PYTHONPATH", "").split(os.pathsep) if e]
    if len(entries) != 1:
        raise StartupError(f"PYTHONPATH must be a single entry, found {len(entries)}")
    tree = os.path.abspath(entries[0])
    try:
        import retina.firefly_scan as fs
        import retina.frame_reader as fr
    except ImportError as exc:
        raise StartupError(f"retina does not import: {exc}") from exc
    blobs = {}
    for rel, mod in (("retina/firefly_scan.py", fs), ("retina/frame_reader.py", fr)):
        path = os.path.abspath(mod.__file__)
        try:
            under = os.path.normcase(os.path.commonpath([path, tree])) == os.path.normcase(tree)
        except ValueError:
            under = False
        if not under:
            raise StartupError(f"{rel} does not resolve under PYTHONPATH")
        with open(path, "rb") as fh:
            data = fh.read()
        blobs[rel] = git_blob_id(data)
        if blobs[rel] != EXPECTED["blobs"][rel]:
            raise StartupError(f"{rel} blob id {blobs[rel]} is not {EXPECTED['blobs'][rel]}")
        if rel.endswith("firefly_scan.py"):
            src = data.decode("utf-8").split("\n")
    for n, needles in LINE_ASSERTS.items():
        text = src[n - 1]
        if not all(s in text for s in needles):
            raise StartupError(f"firefly_scan.py line {n} does not hold {needles}: {text.strip()!r}")
    r = subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or r.stdout.strip() != EXPECTED["tree_commit"]:
        raise StartupError("the release tree's HEAD is not the pinned commit")
    return {
        "python": py, "numpy": numpy.__version__, "cv2": cv2.__version__, "openimageio": oiio.__version__,
        "logical_cores": os.cpu_count(), "threads": read_threads(oiio, cv2),
        "pythonpath": {"entries": 1, "resolves_to": "release tree"},
        "product": {"tree_commit": EXPECTED["tree_commit"], "blobs": blobs},
    }


# ------------------------------------------------------------------- one pass
def run_one(path: str, mask_path: Optional[str], inst: Instrument, fr_mod: Any, fs_mod: Any) -> Dict[str, Any]:
    """R then fireflies() with the wrappers on. Never raises: an exception is recorded."""
    rec: Dict[str, Any] = {"exception": None}
    rgb = info = None
    t = time.perf_counter()
    try:
        rgb, info = fr_mod.read_frame(path, subimage=0)
    except Exception as exc:  # noqa: BLE001
        rec["exception"] = f"read: {type(exc).__name__}: {exc}"
    rec["R"] = time.perf_counter() - t
    summ = summarize_calls([])
    wall, result = 0.0, None
    if rec["exception"] is None:
        inst.begin()
        t = time.perf_counter()
        try:
            result = fs_mod.fireflies(rgb, origin=info["origin"], reader=info["reader"], mask_path=mask_path)
        except Exception as exc:  # noqa: BLE001
            rec["exception"] = f"scan: {type(exc).__name__}: {exc}"
        wall = time.perf_counter() - t
        summ = inst.end()
    rec.update(summ)
    rec["wall"] = wall
    rec["S"] = wall - rec["W"]
    rec["S_rest"] = rec["S"] - rec["S_dense"]
    rec["n_labels"] = inst.n_labels
    rec.update({"inconclusive": True, "count": None, "mask_pixels": None, "nonfinite_pixels": None,
                "firefly_check_pass": None, "check_disagrees": None, "width": None, "height": None, "origin": None})
    if rgb is not None:
        rec["height"], rec["width"] = int(rgb.shape[0]), int(rgb.shape[1])
        rec["origin"] = list(info["origin"])
    if result is not None:
        rec["inconclusive"] = bool(result.get("inconclusive"))
        rec["count"] = result.get("count")
        rec["mask_pixels"] = result.get("pixel_count")
        rec["nonfinite_pixels"] = result.get("nonfinite_pixels")
        try:
            verdict = fs_mod.firefly_check(result)["pass"]
        except Exception as exc:  # noqa: BLE001
            verdict = f"error: {type(exc).__name__}"
        rec["firefly_check_pass"] = verdict
        rec["check_disagrees"] = bool(rec["inconclusive"]) != (verdict is None)
    return rec


# ----------------------------------------------------------------------- driver
class Run:
    def __init__(self, args: argparse.Namespace, env: Dict[str, Any], inst: Instrument,
                 fr_mod: Any, fs_mod: Any, oiio: Any, cv2: Any) -> None:
        self.a, self.env, self.inst, self.fr, self.fs, self.oiio, self.cv2 = args, env, inst, fr_mod, fs_mod, oiio, cv2
        self.out = args.out
        self.seq = 0
        self.mono0 = time.monotonic_ns()
        self.raw_path = os.path.join(self.out, "raw.jsonl")
        self.log_path = os.path.join(self.out, "run.log")
        self.smoke = bool(args.smoke)
        self.exc_count: Dict[Tuple[str, str], int] = {}

    # records
    def emit(self, rec: Dict[str, Any]) -> None:
        self.seq += 1
        rec["seq"] = self.seq
        rec["wall_clock"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        rec["monotonic_ns"] = time.monotonic_ns() - self.mono0
        with open(self.raw_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
        brief = "{kind:7s} {id:9s} {frame:6s} p{index} {tag}".format(
            kind=rec["kind"], id=rec["id"], frame=str(rec["frame"]), index=rec.get("index", "-"),
            tag=("VOID " + str(rec.get("void_reason")) if rec.get("void") else
                 "R={:.3f} S={:.3f} W={:.3f} incl={}".format(rec.get("R", 0), rec.get("S", 0), rec.get("W", 0),
                                                              rec.get("inconclusive"))))
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(brief + "\n")

    def mask(self, e: Dict[str, Any], tag: str) -> str:
        return os.path.join(self.out, "masks", e["id"], f"{e['frame']}_{tag}.png")

    def check_threads(self) -> Dict[str, int]:
        now = read_threads(self.oiio, self.cv2)
        if now != self.env["threads"]:
            raise StartupError(f"thread counts changed: {now} vs {self.env['threads']}")
        return now

    def untimed(self, e: Dict[str, Any], kind: str) -> Dict[str, Any]:
        rec = run_one(e["path"], self.mask(e, kind), self.inst, self.fr, self.fs)
        rec.update({"kind": kind, "id": e["id"], "frame": e["frame"], "void": False, "threads": self.check_threads()})
        self.emit(rec)
        return rec

    def checks_pass(self, before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> Optional[str]:
        for name, c in (("before", before), ("after", after)):
            if c is None:
                continue
            scan = c.get("scan", {})
            if scan.get("error"):
                return f"{name} {scan['error']}"
            if scan.get("blocked"):
                return f"{name} scan shows {[b['name'] for b in scan['blocked']]}"
        return None

    def wait_quiet(self) -> None:
        deadline = time.monotonic() + self.a.max_wait_min * 60
        while True:
            scan = self.scan()
            if not scan.get("error") and not scan["blocked"]:
                return
            if time.monotonic() >= deadline:
                raise NotQuiet("not quiet")
            time.sleep(30)

    def scan(self) -> Dict[str, Any]:
        try:
            return process_scan()
        except (subprocess.TimeoutExpired, UnicodeError, OSError, ValueError) as exc:
            return {"scanned": 0, "blocked": [], "error": f"process scan raised {type(exc).__name__}"}

    def timed(self, e: Dict[str, Any], index: int) -> None:
        key = (e["id"], str(e["frame"]))
        while True:
            before = {**cpu_sample(self.a.cpu_sample_s), "scan": self.scan()}
            why = self.checks_pass(before, None)
            if why and not self.smoke:
                self.emit({"kind": "timed", "id": e["id"], "frame": e["frame"], "index": index,
                           "void": True, "void_reason": why, "before": before})
                self.wait_quiet()
                continue
            rec = run_one(e["path"], self.mask(e, f"p{index}"), self.inst, self.fr, self.fs)
            after = {"scan": self.scan()}
            why = why or self.checks_pass({}, after)
            rec.update({"kind": "timed", "id": e["id"], "frame": e["frame"], "index": index,
                        "before": before, "after": after, "threads": self.check_threads()})
            if rec.get("exception"):
                # Joe's F4 ruling (a): the pass is void and redone once; a second
                # exception on the same frame stops the run.
                rec.update({"void": True, "void_reason": exception_type(rec["exception"])})
                self.emit(rec)
                self.exc_count[key] = self.exc_count.get(key, 0) + 1
                if self.exc_count[key] >= 2:
                    raise ExceptionTwice(f"{key[0]} {key[1]}")
                continue
            if why and not self.smoke:
                rec.update({"void": True, "void_reason": why})
                self.emit(rec)
                self.wait_quiet()
                continue
            rec["void"] = False
            if why:
                rec["check_failed_report_only"] = why
            self.emit(rec)
            return

    def done_counts(self) -> Tuple[Dict[Tuple[str, str], int], set]:
        """Non-void, exception-free timed passes per frame, and the ids whose dry
        pass is on record (a dry pass that raised does not count)."""
        counts: Dict[Tuple[str, str], int] = {}
        dry: set = set()
        if os.path.isfile(self.raw_path):
            with open(self.raw_path, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    self.seq = max(self.seq, int(r.get("seq", 0)))
                    if r["kind"] == "dry" and not r.get("exception"):
                        dry.add(r["id"])
                    if r["kind"] == "timed" and not r.get("void") and not r.get("exception"):
                        k = (r["id"], str(r["frame"]))
                        counts[k] = counts.get(k, 0) + 1
        return counts, dry

    def go(self, entries: List[Dict[str, Any]]) -> int:
        try:
            return self._go(entries)
        except NotQuiet:
            return EXIT_NOT_QUIET
        except ExceptionTwice:
            return EXIT_EXCEPTION_TWICE

    def _go(self, entries: List[Dict[str, Any]]) -> int:
        entries = order_entries(entries)
        counts, dry_ids = self.done_counts() if self.a.resume else ({}, set())
        tier = [e for e in entries if e["id"] in TIER]
        dry_here: set = set()
        for e in tier:
            if e["id"] in dry_ids:
                continue          # a resume redoes the dry pass only for the ids it lacks
            if self.untimed(e, "dry")["exception"]:
                return EXIT_DRY_EXCEPTION
            dry_here.add(e["id"])
        for e in entries:
            have = counts.get((e["id"], str(e["frame"])), 0)
            if have >= self.a.passes:
                continue
            # The dry pass is the tier's untimed warm-up (3.8); every other frame
            # (and every frame after --resume) gets one untimed pass first.
            if e["id"] not in dry_here:
                self.untimed(e, "untimed")
            for k in range(have, self.a.passes):
                self.timed(e, k)
        return EXIT_OK


def load_entries(args: argparse.Namespace) -> List[Dict[str, Any]]:
    if args.smoke:
        if not args.smoke_frames:
            raise SystemExit("--smoke needs --smoke-frames")
        return [{"id": TIER[i] if i < 3 else f"smoke-{i}", "frame": "single", "path": os.path.abspath(p)}
                for i, p in enumerate(args.smoke_frames)]
    with open(args.manifest, encoding="utf-8") as fh:
        man = json.load(fh)
    if man.get("problems") or man.get("skipped") or len(man.get("files", [])) != 124:
        raise StartupError("the manifest is not clean: problems, skipped files, or not 124 files")
    return [{"id": f["id"], "frame": f["frame"], "path": f["staged_path"]} for f in man["files"]]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--manifest", help="stage.py's local manifest")
    p.add_argument("--out", required=True, help="run directory, outside the repo")
    p.add_argument("--passes", type=int, default=3)
    p.add_argument("--max-wait-min", type=float, default=240.0)
    p.add_argument("--cpu-sample-s", type=float, default=5.0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--smoke-frames", nargs="*")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.smoke and (args.passes < 3 or args.cpu_sample_s < 5.0 or not args.manifest):
        print("a timed run needs --manifest, --passes >= 3 and --cpu-sample-s >= 5", file=sys.stderr)
        return EXIT_STARTUP
    try:
        env = startup_checks()
    except StartupError as exc:
        print(f"STARTUP ASSERT FAILED: {exc}", file=sys.stderr)
        return EXIT_STARTUP
    try:
        entries = load_entries(args)
    except StartupError as exc:
        print(f"MANIFEST REFUSED: {exc}", file=sys.stderr)
        return EXIT_STARTUP
    import cv2
    import OpenImageIO as oiio
    import retina.firefly_scan as fs
    import retina.frame_reader as fr
    os.makedirs(args.out, exist_ok=True)
    env.update(machine_info(args.out))
    # F5: the bytes that ran. make_receipt.py refuses unless these equal the blobs
    # at the recorded harness commit.
    qdir = "harness/vision/qc_timing/"
    ran = {qdir + "run_timing.py": file_sha256(os.path.abspath(__file__)),
           qdir + "decide.py": file_sha256(os.path.join(os.path.dirname(os.path.abspath(__file__)), "decide.py"))}
    with open(os.path.join(args.out, "run.json"), "w", encoding="utf-8") as fh:
        json.dump({"mode": "smoke" if args.smoke else "timed", "command_line": [sys.executable] + sys.argv,
                   "passes": args.passes, "cpu_sample_s": args.cpu_sample_s, "environment": env,
                   "harness_files": ran}, fh, indent=1)
    inst = Instrument(cv2)
    inst.install()
    run = Run(args, env, inst, fr, fs, oiio, cv2)
    try:
        code = run.go(entries)
        if code == EXIT_NOT_QUIET:
            print("NOT QUIET: giving up; what was recorded is kept", file=sys.stderr)
        elif code == EXIT_EXCEPTION_TWICE:
            print("A SECOND EXCEPTION on one frame: stopped; what was recorded is kept", file=sys.stderr)
        return code
    except StartupError as exc:
        print(f"ASSERT FAILED: {exc}", file=sys.stderr)
        return EXIT_STARTUP
    finally:
        inst.restore()


if __name__ == "__main__":
    sys.exit(main())
