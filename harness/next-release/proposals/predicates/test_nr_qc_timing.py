"""Closure predicate for NR-QC-TIMING (frozen rule revision 2).

Green only when harness/vision/qc_timing/timing_receipt.json is committed and every
check below holds on it. Red marker while it is not committed.

Layout of this file:
  * an independent reference of the rule (r2 sections 3.4 and 3.5), written from the
    rule's text and never imported from the harness;
  * hand-computed tables and a seeded grid that the harness's decide.py must match;
  * the receipt checks, as pure functions over a dict (``check_*``), so the
    in-memory self-test and the committed-receipt tests run the same code;
  * a self-test that builds a synthetic receipt, shows the checks accept it and
    shows each of five edits makes them fail.

Stdlib only. Reads committed files only. It never reads a frame, imports cv2,
imports the harness as a package or times anything. Nothing here sits behind a skip.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import random
import re
import subprocess
import types
from pathlib import Path


def _repo_root() -> Path:
    """Repository root from the working directory, never from this file's location."""
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / ".git").exists() and (p / "harness" / "next-release" / "graph.json").is_file():
            return p
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).resolve()
    raise AssertionError("repository root not found: run this predicate from inside the SYNAPSE checkout")


ROOT = _repo_root()
MARKER = ("NR-QC-TIMING RED: no committed timing receipt "
          "harness/vision/qc_timing/timing_receipt.json")
RECEIPT = "harness/vision/qc_timing/timing_receipt.json"
DECIDE = "harness/vision/qc_timing/decide.py"

# ---- identity constants, from the frozen rule r2 and the Q5 packet --------------------
RULE_SHA = "7d4c3bfecfe3adefb8db30b4455eca3266d9cbb5089d54986153489578a4e282"
PACKET_SHA = "7df176899dd2da66837dd0cf382942108da4ffe517fb54b0b6cba1647685f3a1"
B_SECONDS = 2.0
THRESHOLD = 0.5
TREE_COMMIT = "7f8c5ec3cf6a794691d1df47b0b167f9147e7ac5"
BLOBS = {
    "retina/firefly_scan.py": "4f78123eef87bb873e28ad68d0daf8224e2cf2aa",
    "retina/frame_reader.py": "4a6fe0d133922dfb74fc37be6016a7fabe8ade81",
}
ENV = {"python": "3.12.10", "numpy": "2.4.4", "cv2": "5.0.0", "openimageio": "3.1.15.0"}
HARNESS_SCRIPTS = [
    "harness/vision/qc_timing/decide.py",
    "harness/vision/qc_timing/stage.py",
    "harness/vision/qc_timing/run_timing.py",
    "harness/vision/qc_timing/make_receipt.py",
]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

TIER = ("char-8", "sib-v016", "sib-v017")
SINGLE = "single"
STAGE_FRAMES = {
    "char-8": [SINGLE], "sib-v016": [SINGLE], "sib-v017": [SINGLE],
    "char-9": [SINGLE], "char-10": [SINGLE], "char-12": [SINGLE],
    "char-2": [f"{n:04d}" for n in range(336, 360)],
    "char-3": [f"{n:04d}" for n in range(1, 62)],
    "char-4": [f"{n:04d}" for n in range(1, 10)],
    "char-13": [f"{n:04d}" for n in range(0, 24)],
}
ROLES = {
    "char-8": "deciding", "sib-v016": "deciding", "sib-v017": "deciding",
    "char-9": "cross-check", "char-2": "cross-check",
    "char-3": "supporting", "char-4": "supporting", "char-10": "supporting",
    "char-13": "stand-in", "char-12": "stand-in",
}
FIRST_FILE = {  # r2 3.1 / 3.14 sha256_first_file
    ("char-8", SINGLE): "a61e1bbc58509f90d298b4d3d0296b2fff46da830ee1252def2c9fe445257c87",
    ("sib-v016", SINGLE): "27a9830adbbb30ec63b8d829019183c50985c9e10de2be092cf01b50e8e592bf",
    ("sib-v017", SINGLE): "54a6edaebf2858db6f4b11ba8738c2a2a08f42bf5de0d315bddb445ed8a4289f",
    ("char-9", SINGLE): "f18d3e10aeca7c78f732ef2ae40fd225e12ff1c56064c86acfa8d33843988eb9",
    ("char-2", "0336"): "8d5bafde6b6df4372a276ab937671f364849050a4beb2461769987ff9ef1cfb9",
    ("char-3", "0001"): "38d3c6c6748a0dab6b7f95bab6b466ad21010fa5c415c852c3bb3c711a1c634a",
    ("char-4", "0001"): "e9599819d4de3902f868093852a63d9eefee7d09e15552edd73c5427351d78ac",
    ("char-10", SINGLE): "67fe2690d582c7bbbad46030d7c2683eb1a28a271deeeaec14bdd63fceed3371",
    ("char-13", "0000"): "b5df81ce597da5b3eb2b979de15e7e2241455958d8e958f2cb50d813a1758ea6",
    ("char-12", SINGLE): "86bdd346da840404364c9b5b42366aa8de3802a163065604cc569e85be3c0023",
    ("char-3", "0031"): "35ae6eace7f46a1c238b247ece2103d07405564bbac134f57b44d42230688d4e",
    ("char-3", "0061"): "7422ce05711c97379e7bd64362f434ef338df7a2837cb75bde60e5a92533c193",
}
PLACEHOLDER_BITS = 0x1000 | 0x40000 | 0x400000
DENSE_LINES = ("292", "313", "314", "352", "542", "549")
ALLOWED_LINES = set(DENSE_LINES) | {"373", "458"}
TYPES = ("medianBlur", "dilate", "erode", "connectedComponentsWithStats", "boxFilter", "imwrite")
RAW_FIELDS = ("R", "wall", "W", "S", "S_dense", "S_rest")
MEDIAN_FIELDS = ("R", "S", "S_dense", "S_rest", "W")
LEAK_MARKERS = ("synapse-build", "onedrive", "myth_and_logic")
_DRIVE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
_PROFILE = re.compile(r"[\\/]users?[\\/]|appdata", re.I)


# =======================================================================================
# Independent reference of the rule (r2 3.4 and 3.5)
# =======================================================================================
def ref_median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("median of nothing")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def ref_branch(T, RW, Floor, share, B=2.0, thr=0.5):
    if T <= B:
        return 1
    if RW > B:
        return 2
    if Floor >= B:
        return 4
    return 3 if share >= thr else 5


def ref_unit(frames):
    """Unit value from the frames of one voting unit that reached a result."""
    out = {}
    for q in ("T", "RW", "Floor", "share"):
        vals = [f[q] for f in frames]
        out[q] = ref_median(vals)
        out[q + "_min"] = min(vals)
        out[q + "_max"] = max(vals)
    out["n_frames"] = len(frames)
    out["branch"] = ref_branch(out["T"], out["RW"], out["Floor"], out["share"])
    return out


def ref_decide(frames):
    """frames: list of {id, reaches, T, RW, Floor, share}. Returns row, units, verdict."""
    ok = [f for f in frames if f["reaches"]]
    tier = [f for f in ok if f["id"] in TIER]
    c = len(tier)
    units = {}
    if c >= 2:
        units["tier"] = ref_unit(tier)
    for uid in ("char-9", "char-2"):
        sub = [f for f in ok if f["id"] == uid]
        if sub:
            units[uid] = ref_unit(sub)
    if c >= 2:
        branches = {u["branch"] for u in units.values()}
        verdict = f"branch {branches.pop()}" if len(branches) == 1 else "split"
    elif "char-9" in units and "char-2" in units:
        a, b = units["char-9"]["branch"], units["char-2"]["branch"]
        verdict = f"branch {a}" if a == b else "split"
    else:
        verdict = "no verdict"
    return {"row": c, "units": units, "voting": sorted(units), "verdict": verdict}


def _fr(fid, T, RW, Floor, share, reaches=True):
    return {"id": fid, "reaches": reaches, "T": T, "RW": RW, "Floor": Floor, "share": share}


# =======================================================================================
# The receipt checks (pure functions over a dict; each returns a list of problems)
# =======================================================================================
VOTING_IDS = TIER + ("char-9", "char-2")
RAN_FILES = ("harness/vision/qc_timing/run_timing.py", "harness/vision/qc_timing/decide.py")
_UNC = re.compile(r"(?<![:A-Za-z0-9])//[^/\s\"']+/[^/\s\"']")
REQUIRED_CALLS = {"292": 1, "313": 2, "314": 1}          # every scan that reaches the box filters
CONCLUSIVE_CALLS = {"352": 1, "458": 1}                  # only when the scan completes


def _d(x, k):
    """x[k] when it is a dict, else {}: a null field fails its check, never a traceback."""
    v = x.get(k) if isinstance(x, dict) else None
    return v if isinstance(v, dict) else {}


def _l(x, k):
    v = x.get(k) if isinstance(x, dict) else None
    return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []


def _close(a, b):
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)
    except (TypeError, ValueError):
        return False


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield str(k)
            yield from _walk_strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _walk_strings(v)


def _frame_key(f):
    return (f.get("id"), f.get("frame"))


def check_identity(r):
    p = []
    rule = _d(r, "rule")
    if rule.get("sha256") != RULE_SHA:
        p.append("rule sha256 is not r2's")
    if rule.get("packet_sha256") != PACKET_SHA:
        p.append("packet sha256 is not the Q5 packet's")
    if rule.get("B") != B_SECONDS:
        p.append("B is not 2.0")
    if rule.get("threshold") != THRESHOLD:
        p.append("threshold is not 0.5")
    if r.get("mode") != "timed":
        p.append(f"mode is {r.get('mode')!r}, not 'timed'")
    rul = _d(r, "rulings")
    if "(a)" not in str(rul.get("F4", "")) or "second exception stops the run" not in str(rul.get("F4", "")):
        p.append("Joe's F4 ruling is not recorded in the receipt")
    if "blocked names as they are" not in str(rul.get("F11", "")):
        p.append("Joe's F11 ruling is not recorded in the receipt")
    return p


def check_product(r):
    p = []
    prod = _d(r, "product")
    if prod.get("tree_commit") != TREE_COMMIT:
        p.append("product tree commit differs")
    if prod.get("blobs") != BLOBS:
        p.append("product blob ids differ from the two on record")
    return p


def check_environment(r):
    p = []
    env = _d(r, "environment")
    for k, v in ENV.items():
        if env.get(k) != v:
            p.append(f"environment {k} is {env.get(k)!r}, expected {v!r}")
    cores = env.get("logical_cores")
    if not (isinstance(cores, int) and cores > 0):
        p.append("logical core count missing")
    pp = _d(env, "pythonpath")
    if pp.get("entries") != 1 or pp.get("resolves_to") != "release tree":
        p.append("PYTHONPATH is not a single entry recorded as the release tree")
    th = _d(env, "threads")
    if set(th) != {"oiio", "exr", "cv2"} or not all(isinstance(v, int) and v > 0 for v in th.values()):
        p.append("environment thread counts missing")
    for f in _l(r, "frames"):
        for ps in _l(f, "passes"):
            if not ps.get("void") and ps.get("threads") != th:
                p.append(f"{f.get('id')} {f.get('frame')} pass {ps.get('index')}: thread counts differ from the run's")
    for d in _l(_d(r, "dry_pass"), "records"):
        if d.get("threads") != th:
            p.append(f"dry pass {d.get('id')}: thread counts differ")
    return p


def check_harness_binding(r, git_show=None, is_ancestor=None):
    """The harness commit and file hashes. ``git_show(commit, path) -> bytes`` and
    ``is_ancestor(commit) -> bool`` are injected so the self-test can run without git."""
    p = []
    h = _d(r, "harness")
    commit = h.get("commit", "")
    if not HEX40.match(str(commit)):
        return ["harness commit is not 40 hex"]
    if is_ancestor is not None and not is_ancestor(commit):
        p.append("harness commit is not an ancestor of HEAD")
    files = _d(h, "files")
    for s in HARNESS_SCRIPTS:
        if s not in files:
            p.append(f"harness file {s} not recorded")
    ran = _d(h, "ran")           # F5: the bytes that ran, as run_timing.py hashed them at run start
    for s in RAN_FILES:
        if not HEX64.match(str(ran.get(s, ""))) or ran.get(s) != files.get(s):
            p.append(f"{s}: the bytes that ran differ from the file at the harness commit")
    for path, digest in files.items():
        if git_show is None:
            continue
        try:
            data = git_show(commit, path)
        except Exception as exc:  # noqa: BLE001
            p.append(f"cannot read {path} at the harness commit: {exc}")
            continue
        if hashlib.sha256(data).hexdigest() != digest:
            p.append(f"harness file {path}: sha256 differs from the file at the commit")
    return p


def check_staging(r):
    p = []
    st = _d(r, "staging")
    files = _l(st, "files")
    keys = [(f.get("id"), f.get("frame")) for f in files]
    if len(set(keys)) != len(keys):
        p.append("staging lists a file twice")
    if st.get("distinct_files") != 124 or len(set(keys)) != 124:
        p.append(f"staging has {len(set(keys))} distinct files, need 124")
    for k in ("problems", "skipped"):
        if st.get(k) != 0 or isinstance(st.get(k), bool):
            p.append(f"staging {k} is {st.get(k)!r}, need 0")
    want = {(i, fr) for i, frs in STAGE_FRAMES.items() for fr in frs}
    if set(keys) != want:
        p.append(f"staged frames differ from 3.1: missing {len(want - set(keys))}, extra {len(set(keys) - want)}")
    by = {(f.get("id"), f.get("frame")): f for f in files}
    for k, f in by.items():
        if not (HEX64.match(str(f.get("source_sha256", ""))) and f.get("source_sha256") == f.get("copy_sha256")):
            p.append(f"{k}: copy sha256 does not equal the source's")
        attr = f.get("source_attributes")
        if not isinstance(attr, int) or attr & PLACEHOLDER_BITS:
            p.append(f"{k}: source attributes missing or carry a placeholder bit")
        if k[0] == "char-2" and f.get("checksums_sha256") != f.get("copy_sha256"):
            p.append(f"{k}: differs from the delivery's CHECKSUMS.sha256 entry")
    for k, digest in FIRST_FILE.items():
        if by.get(k, {}).get("copy_sha256") != digest:
            p.append(f"{k}: sha256 differs from the one on record")
    return p


def _dry_reaches(x):
    return x.get("inconclusive") is False and not x.get("exception")


def check_dry_pass(r):
    p = []
    d = _d(r, "dry_pass")
    recs = _l(d, "records")
    if sorted(str(x.get("id")) for x in recs) != sorted(TIER):
        p.append("dry pass is not on exactly the three deciding stills")
    by = {_frame_key(f): f for f in _l(r, "frames")}
    for x in recs:
        if not isinstance(x.get("inconclusive"), bool):
            p.append(f"dry pass {x.get('id')}: inconclusive flag missing")
        if not x.get("inconclusive") and not (isinstance(x.get("n_labels"), int) and isinstance(x.get("count"), int)):
            p.append(f"dry pass {x.get('id')}: n_labels or hit count missing on a conclusive frame")
        if "seq" not in x:
            p.append(f"dry pass {x.get('id')}: no sequence number")
        f = by.get((x.get("id"), SINGLE))
        if f is not None and _dry_reaches(x) != frame_reaches(f):     # F2: r2 3.8
            p.append(f"dry pass {x.get('id')}: its result differs from the frame's timed passes")
    if d.get("exception") is not None:
        p.append("dry pass recorded an exception")
    seqs = [ps.get("seq") for f in _l(r, "frames") for ps in _l(f, "passes")]
    dseq = [x.get("seq") for x in recs]
    if not seqs or not all(isinstance(s, int) for s in seqs + dseq) or max(dseq, default=0) >= min(seqs):
        p.append("dry pass does not precede the first timed pass")
    return p


def check_warmup(r):
    """F3: every frame outside the deciding tier has an untimed record before its first
    timed pass; for the three deciding stills the dry record plays that role."""
    p = []
    untimed = {(u.get("id"), u.get("frame")): u for u in _l(r, "untimed")}
    dry = {x.get("id"): x for x in _l(_d(r, "dry_pass"), "records")}
    for f in _l(r, "frames"):
        k = _frame_key(f)
        first = min((ps.get("seq") for ps in _l(f, "passes") if isinstance(ps.get("seq"), int)), default=None)
        rec = dry.get(k[0]) if k[0] in TIER else untimed.get(k)
        if first is None or rec is None or not isinstance(rec.get("seq"), int) or rec["seq"] >= first:
            p.append(f"{k}: no untimed warm-up record before its first timed pass")
    return p


def check_passes(r):
    p = []
    frames = _l(r, "frames")
    if {_frame_key(f) for f in frames} != {(i, fr) for i, frs in STAGE_FRAMES.items() for fr in frs}:
        p.append("timed frames differ from the staged set")
    for f in frames:
        k = _frame_key(f)
        good = [ps for ps in _l(f, "passes") if not ps.get("void")]
        if len(good) < 3:
            p.append(f"{k}: fewer than 3 non-void timed passes")
        for ps in _l(f, "passes"):
            tag = f"{k} pass {ps.get('index')}"
            if ps.get("void"):
                if not ps.get("void_reason"):
                    p.append(f"{tag}: void without a reason")
                # F8: a void pass shows its cause in its own record, not only in a reason string
                shows = any(_d(_d(ps, w), "scan").get("blocked") or _d(_d(ps, w), "scan").get("error")
                            for w in ("before", "after")) or bool(ps.get("exception"))
                if not shows:
                    p.append(f"{tag}: void pass shows no blocked process, scan error or exception")
                continue
            if ps.get("exception") and k[0] in VOTING_IDS:   # F4 (Joe's ruling (a))
                p.append(f"{tag}: a kept pass carries an exception on a voting frame")
            b, a = _d(ps, "before"), _d(ps, "after")
            if not (_num(b.get("cpu_sample_s")) and b["cpu_sample_s"] >= 5.0 and _num(b.get("cpu_load"))):
                p.append(f"{tag}: before-check lacks a 5 s CPU sample with its load")
            for name, chk in (("before", b), ("after", a)):
                scan = _d(chk, "scan")
                if not isinstance(scan.get("blocked"), list) or scan.get("blocked") or scan.get("error") or not scan.get("scanned"):
                    p.append(f"{tag}: {name} process scan missing, failed or shows a blocked process")
    return p


def check_split(r):
    p = []
    for f in _l(r, "frames"):
        k = _frame_key(f)
        for ps in _l(f, "passes"):
            if ps.get("void"):
                continue
            tag = f"{k} pass {ps.get('index')}"
            if not all(_num(ps.get(x)) for x in RAW_FIELDS):
                p.append(f"{tag}: raw timing fields missing")
                continue
            lines = _d(ps, "lines")
            extra = set(lines) - ALLOWED_LINES
            if extra:
                p.append(f"{tag}: observed lines outside the rule's set: {sorted(extra)}")
            other = _l(ps, "other_lines")
            if not isinstance(ps.get("other_lines"), list):
                p.append(f"{tag}: other_lines is not a list")
            if any(o.get("file") != "firefly_scan.py" for o in other):
                p.append(f"{tag}: cv2 calls from a file other than firefly_scan.py")
            if not _close(ps["S"], ps["wall"] - ps["W"]):
                p.append(f"{tag}: S is not wall - W")
            if not _close(ps["W"], _d(lines, "458").get("inner_s", 0.0)):
                p.append(f"{tag}: W is not the line-458 inner time")
            dense = sum(_d(lines, x).get("inner_s", 0.0) for x in DENSE_LINES)
            if not _close(ps["S_dense"], dense):
                p.append(f"{tag}: S_dense is not the sum of the dense lines' inner times")
            if not _close(ps["S_rest"], ps["S"] - ps["S_dense"]):
                p.append(f"{tag}: S_rest is not S - S_dense")
            types = _d(ps, "types")
            by_line = sum(v.get("calls", 0) for v in lines.values() if isinstance(v, dict)) + sum(o.get("calls", 0) for o in other)
            if not isinstance(ps.get("types"), dict) or set(types) - set(TYPES):
                p.append(f"{tag}: per-type call counts missing or unknown type")
            elif sum(v.get("calls", 0) for v in types.values() if isinstance(v, dict)) != by_line:
                p.append(f"{tag}: per-type and per-line call counts differ")
            if ps.get("exception"):
                continue          # an exception pass has no complete call record (and is void in a kept run)
            # F1: a scan that ran must show the calls that ran, line by line
            want = dict(REQUIRED_CALLS)
            need_types = {"medianBlur", "dilate", "erode"}
            conclusive = ps.get("inconclusive") is False
            if conclusive:
                want.update(CONCLUSIVE_CALLS)
                need_types |= {"connectedComponentsWithStats", "imwrite"}
            for ln, n in want.items():
                if _d(lines, ln).get("calls") != n:
                    p.append(f"{tag}: line {ln} shows {_d(lines, ln).get('calls')!r} calls, need {n}")
            for t in need_types:
                if not _d(types, t).get("calls"):
                    p.append(f"{tag}: no {t} call recorded")
            if conclusive:                                              # F10
                if not (isinstance(ps.get("n_labels"), int) and not isinstance(ps.get("n_labels"), bool)):
                    p.append(f"{tag}: n_labels missing on a conclusive pass")
                if not (isinstance(ps.get("mask_pixels"), int) and not isinstance(ps.get("mask_pixels"), bool)):
                    p.append(f"{tag}: mask_pixels missing on a conclusive pass")
    return p


def frame_medians(f):
    good = [ps for ps in _l(f, "passes") if not ps.get("void")]
    return {q: ref_median([ps[q] for ps in good]) for q in MEDIAN_FIELDS}


def frame_spread(f):
    good = [ps for ps in _l(f, "passes") if not ps.get("void")]
    return {q: {"min": min(ps[q] for ps in good), "max": max(ps[q] for ps in good)} for q in MEDIAN_FIELDS}


def frame_values(m):
    T = m["R"] + m["S"] + m["W"]
    return {"T": T, "RW": m["R"] + m["W"], "Floor": m["R"] + m["W"] + m["S_rest"],
            "share": (m["S_dense"] / T) if T > 0 else 0.0}


def frame_reaches(f):
    good = [ps for ps in _l(f, "passes") if not ps.get("void")]
    return bool(good) and all(ps.get("inconclusive") is False and not ps.get("exception") for ps in good)


def render_fractions(r):
    """Per id, the median of T / header renderTime over its frames (context only)."""
    rt = {(f.get("id"), f.get("frame")): f.get("render_time_s") for f in _l(_d(r, "staging"), "files")}
    per = {}
    for f in _l(r, "frames"):
        v, t = _d(f, "derived").get("T"), rt.get(_frame_key(f))
        if _num(v) and _num(t) and t:
            per.setdefault(f["id"], []).append(v / t)
    return {i: ref_median(v) for i, v in per.items()}


def check_medians_and_decision(r):
    p = []
    ref_frames = []
    dry = {x.get("id"): _dry_reaches(x) for x in _l(_d(r, "dry_pass"), "records")}
    for f in _l(r, "frames"):
        k = _frame_key(f)
        good = [ps for ps in _l(f, "passes") if not ps.get("void")]
        if not good or not all(all(_num(ps.get(x)) for x in RAW_FIELDS) for ps in good):
            p.append(f"{k}: no usable passes")
            continue
        flags = {ps.get("inconclusive") for ps in good}
        if len(flags) != 1 or not flags <= {True, False}:
            p.append(f"{k}: passes disagree on the inconclusive flag")
        m = frame_medians(f)
        for q in MEDIAN_FIELDS:
            if not _close(_d(f, "medians").get(q), m[q]):
                p.append(f"{k}: median {q} is not the median of its non-void passes")
        sp = frame_spread(f)
        for q in MEDIAN_FIELDS:
            for end in ("min", "max"):
                if not _close(_d(_d(f, "spread"), q).get(end), sp[q][end]):
                    p.append(f"{k}: spread {q} {end} differs from the passes")
        v = frame_values(m)
        for q, val in v.items():
            if not _close(_d(f, "derived").get(q), val):
                p.append(f"{k}: derived {q} differs from the recomputation")
        if f.get("reaches_result") is not frame_reaches(f):
            p.append(f"{k}: reaches_result differs from the passes")
        if f.get("role") != ROLES.get(f.get("id")):
            p.append(f"{k}: role differs from 3.1")
        if f.get("id") in ("char-12", "char-13") and f.get("non_voting") is not True:
            p.append(f"{k}: stand-in not marked non-voting")
        if f.get("id") not in VOTING_IDS:
            continue
        # r2 3.8: the dry pass says whether each deciding still reaches a result
        reaches = dry.get(f["id"], False) if f["id"] in TIER else frame_reaches(f)
        ref_frames.append({"id": f["id"], "reaches": reaches, **v})
    ref = ref_decide(ref_frames)
    dec = _d(r, "decision")
    if dec.get("row") != ref["row"] or ref["row"] != sum(1 for x in dry.values() if x):
        p.append(f"who-decides row {dec.get('row')} differs from the recomputed {ref['row']}")
    if sorted(dec.get("voting", []) if isinstance(dec.get("voting"), list) else []) != ref["voting"]:
        p.append("voting units differ from the recomputation")
    units = _d(dec, "units")
    for name, u in ref["units"].items():
        got = _d(units, name)
        if not got:
            p.append(f"unit {name} missing")
            continue
        for q in ("T", "RW", "Floor", "share"):
            for suffix in ("", "_min", "_max"):             # F10: the unit value and its spread
                if not _close(got.get(q + suffix), u[q + suffix]):
                    p.append(f"unit {name}: {q + suffix} differs from the recomputation")
        if got.get("branch") != u["branch"]:
            p.append(f"unit {name}: branch {got.get('branch')} differs from the recomputed {u['branch']}")
    if set(units) != set(ref["units"]):
        p.append("unit set differs from the recomputation")
    if dec.get("verdict") != ref["verdict"]:
        p.append(f"verdict {dec.get('verdict')!r} differs from the recomputed {ref['verdict']!r}")
    return p


def check_statements(r):
    p = []
    s = _d(r, "statements")
    by = {_frame_key(f): f for f in _l(r, "frames")}
    pairs = _l(_d(s, "char3_vs_char4"), "pairs")
    want_frames = [f"{n:04d}" for n in range(1, 10)]
    if [x.get("frame") for x in pairs] != want_frames:
        p.append("char-3 against char-4 is not on frames 0001-0009")
    for x in pairs:
        a, b = by.get(("char-3", x.get("frame")), {}), by.get(("char-4", x.get("frame")), {})
        try:
            ok = (_close(x["S_char3"], a["medians"]["S"]) and _close(x["S_char4"], b["medians"]["S"])
                  and _close(x["W_char3"], a["medians"]["W"]) and _close(x["W_char4"], b["medians"]["W"])
                  and x["count_char3"] == a.get("count") and x["count_char4"] == b.get("count"))
        except (KeyError, TypeError):
            ok = False
        if not ok:
            p.append(f"char-3 against char-4, frame {x.get('frame')}: values differ from the frames")
    c10 = _d(s, "char10_vs_char3")
    try:
        t3 = ref_median([by[("char-3", fr)]["derived"]["T"] for fr in STAGE_FRAMES["char-3"]])
        if not (_close(c10["T_char10"], by[("char-10", SINGLE)]["derived"]["T"]) and _close(c10["T_char3_median"], t3)):
            p.append("char-10 against char-3: T values differ from the frames")
    except (KeyError, TypeError):
        p.append("char-10 against char-3 statement missing or malformed")
    rt = _d(s, "render_time")
    got, want = _d(rt, "per_id"), render_fractions(r)
    if rt.get("context_only") is not True:
        p.append("T over header render time is not marked context only")
    if set(got) != set(want) or any(not _close(got[i], want[i]) for i in want if i in got):
        p.append("render_time.per_id differs from T over the staged header render times")
    if sorted(s.get("part0_read", []) if isinstance(s.get("part0_read"), list) else []) != ["char-2", "char-3", "char-4", "char-9"]:
        p.append("part-0 read statement missing or wrong")
    if sorted(s.get("non_voting", []) if isinstance(s.get("non_voting"), list) else []) != ["char-12", "char-13"]:
        p.append("char-12 and char-13 not marked non-voting")
    seqs = _d(s, "sequences")
    for sid in ("char-2", "char-3", "char-4", "char-13"):
        fr = STAGE_FRAMES[sid]
        try:
            ts = {x: by[(sid, x)]["derived"]["T"] for x in fr}
            slow = max(ts, key=ts.get)
            ok = (seqs[sid]["slowest_frame"] == slow and _close(seqs[sid]["slowest_T"], ts[slow])
                  and _close(seqs[sid]["frames_per_s"], len(fr) / sum(ts.values())))
        except (KeyError, TypeError, ZeroDivisionError):
            ok = False
        if not ok:
            p.append(f"sequence statement for {sid} missing or differs from the frames")
    return p


def check_producer(r, committed=None):
    p = []
    pr = _d(r, "producer")
    cmds = _d(pr, "commands")
    if set(cmds) != {"stage", "run", "make_receipt"}:
        p.append("producer command templates missing")
    scripts = pr.get("scripts", []) if isinstance(pr.get("scripts"), list) else []
    if sorted(scripts) != sorted(HARNESS_SCRIPTS[1:]):
        p.append("producer scripts are not the three repo-relative harness scripts")
    for name, c in cmds.items():
        if not any(sc in str(c) for sc in HARNESS_SCRIPTS[1:]):
            p.append(f"command template {name} names no harness script")
        if _DRIVE.search(str(c)):
            p.append(f"command template {name} carries a drive path")
    if committed is not None:
        for sc in scripts:
            if not committed(sc):
                p.append(f"producer script {sc} is not committed")
    return p


def check_no_leak(r):
    bad = []
    for s in _walk_strings(r):
        norm = s.replace("\\", "/")       # parsed strings: one real backslash is one separator
        if _DRIVE.search(norm):
            bad.append(f"drive path in {s[:40]!r}")
        if _UNC.search(norm):                                  # F12: both slash forms
            bad.append(f"UNC path in {s[:40]!r}")
        if _PROFILE.search(s):
            bad.append(f"user-profile marker in {s[:40]!r}")
        low = s.lower()
        for m in LEAK_MARKERS:
            if m in low:
                bad.append(f"{m} in {s[:40]!r}")
    return bad


PURE_CHECKS = (check_identity, check_product, check_environment, check_staging, check_dry_pass,
               check_warmup, check_passes, check_split, check_medians_and_decision, check_statements,
               check_producer, check_no_leak)


def check_all_pure(r):
    out = []
    for fn in PURE_CHECKS:
        out.extend(f"{fn.__name__}: {x}" for x in fn(r))
    return out


# =======================================================================================
# A synthetic receipt, built in memory, for the self-test
# =======================================================================================
def _synthetic_pass(rng, sc, i, seq, th, inconclusive=False):
    ncalls = {"292": 1, "313": 2, "314": 1}
    if not inconclusive:
        ncalls.update({"352": 1, "542": 3, "549": 6})
    lines = {x: {"calls": n, "inner_s": sc * 0.1 * (1 + rng.random() * 0.05)} for x, n in ncalls.items()}
    W = 0.0
    if not inconclusive:
        lines["373"] = {"calls": 3, "inner_s": sc * 0.001}
        W = sc * 0.05 * (1 + rng.random() * 0.05)
        lines["458"] = {"calls": 1, "inner_s": W}
    dense = sum(lines[x]["inner_s"] for x in DENSE_LINES if x in lines)
    S = dense + sc * 0.3
    types = {"medianBlur": {"calls": 1, "inner_s": 0.0}, "dilate": {"calls": 2 if inconclusive else 5, "inner_s": 0.0},
             "erode": {"calls": 1, "inner_s": 0.0}}
    if not inconclusive:
        types.update({"connectedComponentsWithStats": {"calls": 1, "inner_s": 0.0},
                      "boxFilter": {"calls": 9, "inner_s": 0.0}, "imwrite": {"calls": 1, "inner_s": 0.0}})
    return {
        "index": i, "seq": seq, "void": False, "R": sc * 0.2 * (1 + rng.random() * 0.05), "wall": S + W, "W": W,
        "S": S, "S_dense": dense, "S_rest": S - dense, "lines": lines, "other_lines": [], "types": types,
        "inconclusive": inconclusive, "exception": None, "n_labels": None if inconclusive else 5,
        "count": None if inconclusive else 2, "mask_pixels": None if inconclusive else 2, "threads": dict(th),
        "before": {"cpu_sample_s": 5.0, "cpu_load": 0.02, "scan": {"scanned": 200, "blocked": []}},
        "after": {"scan": {"scanned": 200, "blocked": []}},
    }


def _seal(r):
    """Recompute every derived field of ``r`` from its raw passes, dry pass and staging."""
    frames = r["frames"]
    for f in frames:
        good = [p for p in f["passes"] if not p.get("void")]
        f["medians"] = frame_medians(f)
        f["spread"] = frame_spread(f)
        f["derived"] = frame_values(f["medians"])
        f["reaches_result"] = frame_reaches(f)
        f["count"] = good[0].get("count")
    by = {_frame_key(f): f for f in frames}
    dry = {x["id"]: _dry_reaches(x) for x in r["dry_pass"]["records"]}
    dec = ref_decide([{"id": f["id"], "reaches": dry[f["id"]] if f["id"] in TIER else f["reaches_result"], **f["derived"]}
                      for f in frames if f["id"] in VOTING_IDS])
    r["decision"] = {"row": dec["row"], "voting": dec["voting"], "units": dec["units"], "verdict": dec["verdict"]}
    seqs = {}
    for sid in ("char-2", "char-3", "char-4", "char-13"):
        ts = {x: by[(sid, x)]["derived"]["T"] for x in STAGE_FRAMES[sid]}
        slow = max(ts, key=ts.get)
        seqs[sid] = {"slowest_frame": slow, "slowest_T": ts[slow], "frames_per_s": len(ts) / sum(ts.values())}
    r["statements"] = {
        "char3_vs_char4": {"pairs": [
            {"frame": x, "S_char3": by[("char-3", x)]["medians"]["S"], "S_char4": by[("char-4", x)]["medians"]["S"],
             "W_char3": by[("char-3", x)]["medians"]["W"], "W_char4": by[("char-4", x)]["medians"]["W"],
             "count_char3": by[("char-3", x)]["count"], "count_char4": by[("char-4", x)]["count"]}
            for x in STAGE_FRAMES["char-4"]]},
        "char10_vs_char3": {"T_char10": by[("char-10", SINGLE)]["derived"]["T"],
                            "T_char3_median": ref_median([by[("char-3", x)]["derived"]["T"] for x in STAGE_FRAMES["char-3"]])},
        "render_time": {"context_only": True, "per_id": render_fractions(r)},
        "part0_read": ["char-9", "char-2", "char-3", "char-4"],
        "non_voting": ["char-12", "char-13"],
        "sequences": seqs,
    }
    return r


def make_synthetic(variant="clean"):
    rng = random.Random(7)
    th = {"oiio": 48, "exr": 48, "cv2": 48}
    scale = {"char-8": 3.0, "sib-v016": 3.1, "sib-v017": 2.9, "char-9": 1.5, "char-2": 0.8,
             "char-3": 0.4, "char-4": 0.4, "char-10": 0.05, "char-13": 1.2, "char-12": 1.4}
    frames, files, untimed, seq = [], [], [], 100
    for fid, frs in STAGE_FRAMES.items():
        for fr in frs:
            digest = FIRST_FILE.get((fid, fr)) or hashlib.sha256(f"{fid}/{fr}".encode()).hexdigest()
            f = {"id": fid, "frame": fr, "role": ROLES[fid], "passes": []}
            if fid in ("char-12", "char-13"):
                f["non_voting"] = True
            fl = {"id": fid, "frame": fr, "name": f"x.{fr}.exr", "bytes": 1,
                  "source_sha256": digest, "copy_sha256": digest, "source_attributes": 0x20,
                  "render_time_s": 100.0}
            if fid == "char-2":
                fl["checksums_sha256"] = digest
            files.append(fl)
            if fid not in TIER:
                seq += 1
                untimed.append({"id": fid, "frame": fr, "seq": seq, "exception": None})
            incl = variant == "inconclusive" and (fid, fr) == ("sib-v017", SINGLE)
            for i in range(3):
                seq += 1
                f["passes"].append(_synthetic_pass(rng, scale[fid], i, seq, th, incl))
            if variant == "void" and (fid, fr) == ("char-8", SINGLE):
                f["passes"].append({"index": 3, "seq": seq + 1000, "void": True, "void_reason": "scan shows ['husk.exe']",
                                    "before": {"cpu_sample_s": 5.0, "cpu_load": 0.5,
                                               "scan": {"scanned": 200, "blocked": [{"pid": 7, "name": "husk.exe"}]}},
                                    "R": 9.0, "wall": 99.0, "W": 9.0, "S": 90.0, "S_dense": 0.0, "S_rest": 90.0})
            frames.append(f)
    r = {
        "mode": "timed",
        "rule": {"revision": 2, "sha256": RULE_SHA, "packet_sha256": PACKET_SHA, "B": 2.0, "threshold": 0.5},
        "rulings": {"F4": "F4: (a) - void the pass and redo it once, a second exception stops the run, predicate red "
                          "on any kept pass with an exception on a voting frame.",
                    "F11": "F11: keep r2 3.9's blocked names as they are."},
        "product": {"tree_commit": TREE_COMMIT, "blobs": dict(BLOBS)},
        "environment": {**ENV, "logical_cores": 48, "threads": th,
                        "pythonpath": {"entries": 1, "resolves_to": "release tree"}},
        "harness": {"commit": "a" * 40, "files": {s: "b" * 64 for s in HARNESS_SCRIPTS},
                    "ran": {s: "b" * 64 for s in RAN_FILES}},
        "staging": {"distinct_files": 124, "problems": 0, "skipped": 0, "files": files},
        "untimed": untimed,
        "dry_pass": {"exception": None, "records": [
            {"id": i, "seq": 1 + n, "inconclusive": variant == "inconclusive" and i == "sib-v017",
             "n_labels": None if (variant == "inconclusive" and i == "sib-v017") else 5,
             "count": None if (variant == "inconclusive" and i == "sib-v017") else 2,
             "exception": None, "threads": dict(th)} for n, i in enumerate(TIER)]},
        "frames": frames,
        "producer": {"commands": {
            "stage": "<R4_PYTHON> -B harness/vision/qc_timing/stage.py --rule <RULE_R2>",
            "run": "<R4_PYTHON> -B harness/vision/qc_timing/run_timing.py --manifest <STAGE_MANIFEST> --out <RUN_DIR>",
            "make_receipt": "<R4_PYTHON> -B harness/vision/qc_timing/make_receipt.py --run <RUN_DIR>"},
            "scripts": HARNESS_SCRIPTS[1:]},
    }
    return _seal(r)


# =======================================================================================
# Receipt access: "committed" means the bytes at HEAD (F13)
# =======================================================================================
def _head_bytes(rel: str):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{rel}"], capture_output=True, timeout=60)
    return r.stdout if r.returncode == 0 else None


def _committed(rel: str) -> bool:
    return _head_bytes(rel) is not None


def _head_checked(rel: str):
    """The bytes at HEAD; AssertionError when the working copy differs from them."""
    head = _head_bytes(rel)
    if head is None:
        return None
    wc = ROOT / rel
    if wc.is_file() and wc.read_bytes().replace(b"\r\n", b"\n") != head.replace(b"\r\n", b"\n"):
        raise AssertionError(f"{rel}: the working copy differs from HEAD; commit it first")
    return head


def _receipt() -> dict:
    head = _head_checked(RECEIPT)
    if head is None:
        raise AssertionError(MARKER)
    return json.loads(head.decode("utf-8"))


def _git_show(commit, path):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{path}"], capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip())
    return r.stdout


def _is_ancestor(commit):
    r = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"],
                       capture_output=True, timeout=60)
    return r.returncode == 0


def _load_decide():
    head = _head_checked(DECIDE)
    if head is None:
        raise AssertionError(f"{DECIDE} is not committed")
    mod = types.ModuleType("qc_timing_decide")
    exec(compile(head.decode("utf-8"), DECIDE, "exec"), mod.__dict__)
    return mod


# =======================================================================================
# 1. The reference, on tables written by hand from the rule's text
# =======================================================================================
BRANCH_TABLE = [
    # T, RW, Floor, share, expected
    (1.0, 0.5, 0.8, 0.9, 1),
    (2.0, 3.0, 4.0, 0.9, 1),        # T = B is branch 1 even with RW over B
    (2.5, 2.1, 2.2, 0.1, 2),
    (3.0, 2.0, 2.0, 0.9, 4),        # Floor = B is branch 4
    (3.0, 1.0, 2.5, 0.9, 4),
    (3.0, 1.0, 1.99, 0.5, 3),       # share = 0.5 is branch 3
    (3.0, 1.0, 1.5, 0.75, 3),
    (3.0, 1.0, 1.5, 0.49, 5),
    (3.0, 2.0000001, 2.5, 0.9, 2),
]


def test_reference_branch_table():
    for T, RW, Fl, sh, want in BRANCH_TABLE:
        assert ref_branch(T, RW, Fl, sh) == want, (T, RW, Fl, sh, want)


def _vals(k):
    return {1: (1.0, 0.5, 0.8, 0.9), 2: (5.0, 3.0, 4.0, 0.5), 3: (4.0, 1.0, 1.5, 0.8),
            4: (4.0, 1.0, 3.0, 0.8), 5: (4.0, 1.0, 1.5, 0.2)}[k]


def test_reference_who_decides_rows():
    # c = 3: tier, char-9, char-2 all in branch 3.
    fr = [_fr(i, *_vals(3)) for i in TIER] + [_fr("char-9", *_vals(3))] + [_fr("char-2", *_vals(3))] * 3
    d = ref_decide(fr)
    assert (d["row"], d["voting"], d["verdict"]) == (3, ["char-2", "char-9", "tier"], "branch 3")
    # c = 2: the third still has no result; the tier value is the mean of the two.
    fr = [_fr("char-8", 3.0, 1.0, 1.5, 0.6), _fr("sib-v016", 5.0, 1.0, 1.5, 0.8),
          _fr("sib-v017", 99, 99, 99, 0.0, reaches=False),
          _fr("char-9", *_vals(3)), _fr("char-2", *_vals(3))]
    d = ref_decide(fr)
    assert d["row"] == 2 and d["verdict"] == "branch 3"
    assert d["units"]["tier"]["T"] == 4.0 and d["units"]["tier"]["share"] == 0.7
    # c = 1: the lone still is reported and does not vote; char-9 and char-2 decide.
    fr = [_fr("char-8", *_vals(1)), _fr("sib-v016", 0, 0, 0, 0, reaches=False),
          _fr("sib-v017", 0, 0, 0, 0, reaches=False),
          _fr("char-9", *_vals(4)), _fr("char-2", *_vals(4))]
    d = ref_decide(fr)
    assert (d["row"], d["voting"], d["verdict"]) == (1, ["char-2", "char-9"], "branch 4")
    # c = 0: same two decide.
    fr = [_fr(i, 0, 0, 0, 0, reaches=False) for i in TIER] + [_fr("char-9", *_vals(2)), _fr("char-2", *_vals(2))]
    assert ref_decide(fr)["verdict"] == "branch 2" and ref_decide(fr)["row"] == 0


def test_reference_split_and_missing_units():
    base = [_fr(i, *_vals(3)) for i in TIER]
    # a split: the tier says 3, char-9 says 1
    d = ref_decide(base + [_fr("char-9", *_vals(1)), _fr("char-2", *_vals(3))])
    assert d["verdict"] == "split"
    # c = 3, char-9 without a result: it does not vote, the other two agree
    d = ref_decide(base + [_fr("char-9", *_vals(1), reaches=False), _fr("char-2", *_vals(3))])
    assert d["verdict"] == "branch 3" and d["voting"] == ["char-2", "tier"]
    # c = 3, neither cross-check reaches a result: the tier votes alone (3.5, derived)
    d = ref_decide(base + [_fr("char-9", *_vals(1), reaches=False), _fr("char-2", *_vals(1), reaches=False)])
    assert d["verdict"] == "branch 3" and d["voting"] == ["tier"]
    # c = 1 and char-9 has no result: no verdict
    one = [_fr("char-8", *_vals(3)), _fr("sib-v016", 0, 0, 0, 0, reaches=False), _fr("sib-v017", 0, 0, 0, 0, reaches=False)]
    assert ref_decide(one + [_fr("char-9", *_vals(3), reaches=False), _fr("char-2", *_vals(3))])["verdict"] == "no verdict"
    # c = 1 and the two deciders disagree: split
    assert ref_decide(one + [_fr("char-9", *_vals(3)), _fr("char-2", *_vals(5))])["verdict"] == "split"
    # nothing reaches a result: no verdict
    assert ref_decide([_fr(i, 0, 0, 0, 0, reaches=False) for i in TIER])["verdict"] == "no verdict"


def test_reference_char2_median_even_count():
    fr = [_fr("char-2", t, 1.0, 1.5, 0.8) for t in (1.0, 3.0, 5.0, 100.0)]
    u = ref_decide(fr + [_fr("char-9", *_vals(3))])["units"]["char-2"]
    assert u["T"] == 4.0 and u["T_min"] == 1.0 and u["T_max"] == 100.0


# =======================================================================================
# 2. The harness's decision code must agree with the reference
# =======================================================================================
def _agree(dec, fr):
    got, want = dec.decide(fr), ref_decide(fr)
    assert got["verdict"] == want["verdict"], fr
    assert got["row"] == want["row"] and sorted(got["voting"]) == want["voting"], fr
    for name, u in want["units"].items():
        for q in ("T", "RW", "Floor", "share"):
            assert math.isclose(got["units"][name][q], u[q], rel_tol=1e-12), (name, q)
        assert got["units"][name]["branch"] == u["branch"]


def test_harness_decide_matches_reference_on_tables():
    dec = _load_decide()
    for T, RW, Fl, sh, want in BRANCH_TABLE:
        assert dec.branch(T, RW, Fl, sh, 2.0, 0.5) == want
    cases = [
        [_fr(i, *_vals(3)) for i in TIER] + [_fr("char-9", *_vals(3)), _fr("char-2", *_vals(3))],
        [_fr(i, *_vals(3)) for i in TIER] + [_fr("char-9", *_vals(1)), _fr("char-2", *_vals(3))],
        [_fr("char-8", *_vals(1)), _fr("sib-v016", 0, 0, 0, 0, reaches=False),
         _fr("sib-v017", 0, 0, 0, 0, reaches=False), _fr("char-9", *_vals(4)), _fr("char-2", *_vals(4))],
        [_fr(i, 0, 0, 0, 0, reaches=False) for i in TIER] + [_fr("char-9", *_vals(2)), _fr("char-2", *_vals(2))],
        [_fr(i, 0, 0, 0, 0, reaches=False) for i in TIER],
        [_fr(i, *_vals(3)) for i in TIER[:2]] + [_fr("sib-v017", 0, 0, 0, 0, reaches=False),
                                                  _fr("char-9", 0, 0, 0, 0, reaches=False),
                                                  _fr("char-2", 0, 0, 0, 0, reaches=False)],
    ]
    for fr in cases:
        _agree(dec, fr)


def test_harness_decide_matches_reference_on_seeded_grid():
    dec = _load_decide()
    rng = random.Random(0)
    edges = [0.0, 0.5, 1.0, 1.99, 2.0, 2.01, 3.0, 5.0]
    for _ in range(3000):
        def one():
            vals = sorted(rng.choice(edges) if rng.random() < 0.4 else rng.uniform(0, 6) for _ in range(3))
            sh = rng.choice([0.0, 0.49, 0.5, 0.51, 1.0, rng.random()])
            return vals[2], vals[0], vals[1], sh   # T >= Floor >= RW
        fr = [_fr(i, *one(), reaches=rng.random() < 0.8) for i in TIER]
        fr.append(_fr("char-9", *one(), reaches=rng.random() < 0.8))
        fr += [_fr("char-2", *one(), reaches=rng.random() < 0.8) for _ in range(rng.randint(1, 5))]
        T, RW, Fl, sh = one()
        assert dec.branch(T, RW, Fl, sh, 2.0, 0.5) == ref_branch(T, RW, Fl, sh)
        _agree(dec, fr)


# =======================================================================================
# 3. The recomputation self-test: the checks accept a good receipt and can fail
# =======================================================================================
def test_selftest_clean_synthetic_receipt_passes_every_pure_check():
    for variant in ("clean", "void", "inconclusive"):     # a completed-then-inconclusive scan is accepted too
        assert check_all_pure(make_synthetic(variant)) == [], variant
    assert check_harness_binding(make_synthetic()) == []       # no git: shape and the bytes that ran


def _fails(mutate, variant="clean", seal=False):
    r = make_synthetic(variant)
    mutate(r)
    if seal:
        _seal(r)
    return check_all_pure(r) + check_harness_binding(r)


def _frame(r, fid, fr=SINGLE):
    return [f for f in r["frames"] if f["id"] == fid and f["frame"] == fr][0]


def _has(errs, text):
    return any(text in x for x in errs)


def test_selftest_rejects_a_changed_pass_median():
    def m(r):
        r["frames"][0]["medians"]["R"] *= 1.5
    assert _has(_fails(m), "median R")


def test_selftest_rejects_a_void_pass_counted():
    def m(r):
        v = [p for p in r["frames"][0]["passes"] if p.get("void")][0]
        v["void"] = False          # the void pass now counts, medians were built without it
    errs = _fails(m, "void")
    assert _has(errs, "median") or _has(errs, "before-check")


def test_selftest_rejects_a_changed_branch():
    def m(r):
        u = r["decision"]["units"]["tier"]
        u["branch"] = 1 if u["branch"] != 1 else 2
    assert _has(_fails(m), "branch")


def test_selftest_rejects_a_changed_verdict():
    def m(r):
        r["decision"]["verdict"] = "branch 9"
    assert _has(_fails(m), "verdict")


def test_selftest_rejects_a_changed_who_decides_row():
    def m(r):
        r["decision"]["row"] = 1
    assert _has(_fails(m), "row")


def test_selftest_rejects_identity_split_leak_and_staging_edits():
    cases = {
        "mode": lambda r: r.__setitem__("mode", "smoke"),
        "rule": lambda r: r["rule"].__setitem__("sha256", "0" * 64),
        "split": lambda r: r["frames"][5]["passes"][0].__setitem__("S_dense", 123.0),
        "line": lambda r: r["frames"][5]["passes"][0]["lines"].__setitem__("999", {"calls": 1, "inner_s": 0.0}),
        "leak": lambda r: r["producer"]["commands"].__setitem__("run", "C:/x/y.py"),
        "count": lambda r: r["staging"]["files"].pop(),
        "copy": lambda r: r["staging"]["files"][0].__setitem__("copy_sha256", "0" * 64),
        "blocked": lambda r: r["frames"][3]["passes"][0]["after"]["scan"].__setitem__("blocked", [{"pid": 1, "name": "husk.exe"}]),
        "threads": lambda r: r["frames"][3]["passes"][1]["threads"].__setitem__("cv2", 4),
        "placeholder": lambda r: r["staging"]["files"][2].__setitem__("source_attributes", 0x1000 | 0x20),
        "dry": lambda r: r["dry_pass"]["records"][0].__setitem__("seq", 10 ** 6),
        "fewpasses": lambda r: r["frames"][7]["passes"].pop(),
    }
    for name, mut in cases.items():
        assert _fails(mut), f"edit {name!r} was not caught"


def test_selftest_f1_dead_instrument_and_unwrapped_calls_are_caught():
    def dead(r):                       # S01: no cv2 calls recorded anywhere, resealed to be self-consistent
        for f in r["frames"]:
            for p in f["passes"]:
                p.update(lines={}, types={}, other_lines=[], S_dense=0.0, W=0.0, S=p["wall"], S_rest=p["wall"])
    assert _has(_fails(dead, seal=True), "line 292")

    def erode_unwrapped(r):            # S02 / r2: erode never wrapped
        for f in r["frames"]:
            for p in f["passes"]:
                p["lines"]["313"]["calls"] = 1
                p["types"].pop("erode")
    errs = _fails(erode_unwrapped, seal=True)
    assert _has(errs, "line 313") and _has(errs, "no erode call")

    def imwrite_unwrapped(r):          # r3: imwrite never wrapped, so W is 0 and line 458 absent
        for f in r["frames"]:
            for p in f["passes"]:
                p["lines"].pop("458")
                p["types"].pop("imwrite")
                p.update(W=0.0, S=p["wall"], S_rest=p["wall"] - p["S_dense"])
    errs = _fails(imwrite_unwrapped, seal=True)
    assert _has(errs, "line 458") and _has(errs, "no imwrite call")

    def other_file(r):
        r["frames"][3]["passes"][0]["other_lines"] = [{"file": "elsewhere.py", "line": 9, "type": "boxFilter",
                                                         "calls": 1, "inner_s": 0.0}]
        r["frames"][3]["passes"][0]["types"]["boxFilter"]["calls"] += 1
    assert _has(_fails(other_file), "other than firefly_scan.py")


def test_selftest_f2_the_dry_pass_decides_the_row():
    def all_inconclusive(r):           # S03: dry says nothing reached a result; the row stays 2
        for d in r["dry_pass"]["records"]:
            d.update(inconclusive=True, n_labels=None, count=None)
    errs = _fails(all_inconclusive)
    assert _has(errs, "dry pass") and _has(errs, "row")

    def sib_differs(r):                # S04: dry says conclusive, timed says sib-v017 is not
        for p in _frame(r, "sib-v017")["passes"]:
            p.update(inconclusive=True, n_labels=None, count=None, mask_pixels=None)
    errs = _fails(sib_differs, seal=True)
    assert _has(errs, "its result differs from the frame's timed passes")


def test_selftest_f3_untimed_warm_up_records_are_required():
    def drop(r):
        r["untimed"] = [u for u in r["untimed"] if not (u["id"] == "char-3" and u["frame"] == "0020")]
    assert _has(_fails(drop), "warm-up")

    def late(r):
        u = [u for u in r["untimed"] if u["id"] == "char-10"][0]
        u["seq"] = 10 ** 7
    assert _has(_fails(late), "warm-up")


def test_selftest_f4_a_kept_pass_with_an_exception_on_a_voting_frame_is_red():
    def deterministic(r):              # S08
        for p in _frame(r, "char-9")["passes"]:
            p.update(exception="read: OSError", inconclusive=True, count=None, n_labels=None)

    def transient(r):                  # X02: one kept pass, one frame of char-2
        _frame(r, "char-2", "0345")["passes"][1].update(exception="scan: MemoryError", inconclusive=True, count=None)
    assert _has(_fails(deterministic, seal=True), "kept pass carries an exception")
    assert _has(_fails(transient, seal=True), "kept pass carries an exception")
    # the same exception on a void pass that shows it is fine
    def voided(r):
        f = _frame(r, "char-9")
        v = copy.deepcopy(f["passes"][0])
        v.update(index=3, void=True, void_reason="scan raised MemoryError", exception="scan: MemoryError")
        f["passes"].append(v)
    assert _fails(voided, seal=True) == []


def test_selftest_f5_the_bytes_that_ran_must_equal_the_commit():
    assert _has(_fails(lambda r: r["harness"]["ran"].__setitem__(RAN_FILES[0], "c" * 64)), "bytes that ran")
    assert _has(_fails(lambda r: r["harness"].pop("ran")), "bytes that ran")


def test_selftest_f6_staging_problems_and_skips_must_be_zero():
    assert _has(_fails(lambda r: r["staging"].update(problems=7, skipped=2)), "staging problems")
    assert _has(_fails(lambda r: r["staging"].pop("skipped")), "staging skipped")


def test_selftest_f8_a_void_pass_must_show_its_cause():
    def invented(r):                   # S05
        f = _frame(r, "char-9")
        v = copy.deepcopy(f["passes"][0])
        v.update(index=3, void=True, void_reason="looked slow", R=9.0)
        f["passes"].append(v)
    assert _has(_fails(invented), "shows no blocked process")

    def scan_error(r):
        f = _frame(r, "char-9")
        v = copy.deepcopy(f["passes"][0])
        v.update(index=3, void=True, void_reason="before process scan failed")
        v["before"]["scan"] = {"scanned": 0, "blocked": [], "error": "process scan failed"}
        f["passes"].append(v)
    assert _fails(scan_error) == []


def test_selftest_f10_spread_render_time_and_pass_counts_are_checked():
    assert _has(_fails(lambda r: r["decision"]["units"]["tier"].update(T_min=0.0, T_max=99.0)), "T_min")      # S06
    assert _has(_fails(lambda r: r["statements"]["render_time"].update(per_id={"char-8": 123.0})), "render_time")  # S07
    assert _has(_fails(lambda r: _frame(r, "char-8")["spread"]["R"].update(max=99.0)), "spread R max")      # S10

    def no_counts(r):                  # S11
        for p in _frame(r, "char-8")["passes"]:
            p.pop("n_labels")
            p.pop("mask_pixels")
    errs = _fails(no_counts)
    assert _has(errs, "n_labels") and _has(errs, "mask_pixels")


def test_selftest_f12_unc_paths_are_leaks_in_both_slash_forms():
    for form in ("\\\\fileserver\\share\\x.exr", "//fileserver/share/x.exr"):
        assert _fails(lambda r, form=form: r["environment"].__setitem__("cpu_model", form)), form
    assert not check_no_leak({"a": "https://example.org/a/b", "b": "a//b/c", "c": "<R4_PYTHON>"})


def test_selftest_f15_null_fields_fail_with_a_reason_not_a_traceback():
    for key in list(make_synthetic()):
        r = make_synthetic()
        r[key] = None
        assert check_all_pure(r) + check_harness_binding(r), f"null {key!r} passed"
    r = make_synthetic()
    r["frames"][0]["medians"] = None
    r["frames"][0]["passes"][0]["lines"] = None
    r["frames"][1]["spread"] = None
    r["decision"]["units"] = None
    r["statements"]["char3_vs_char4"] = None
    r["staging"]["files"][0] = None
    assert check_all_pure(r)


def test_selftest_committed_means_the_bytes_at_head():
    assert _committed("harness/next-release/graph.json")
    assert not _committed("harness/vision/qc_timing/no_such_file_anywhere.json")


# =======================================================================================
# 4. The committed receipt (red until it is committed)
# =======================================================================================
def test_receipt_is_committed():
    r = _receipt()
    assert isinstance(r, dict) and r, "the committed receipt is empty"


def _group(fn):
    errs = fn(_receipt())
    assert not errs, "; ".join(errs[:8])


def test_receipt_identity_product_and_environment():
    r = _receipt()
    errs = check_identity(r) + check_product(r) + check_environment(r)
    assert not errs, "; ".join(errs[:8])


def test_receipt_harness_is_bound_to_a_commit_and_its_files():
    errs = check_harness_binding(_receipt(), _git_show, _is_ancestor)
    assert not errs, "; ".join(errs[:8])


def test_receipt_staging():
    _group(check_staging)


def test_receipt_dry_pass():
    _group(check_dry_pass)


def test_receipt_warm_up_records():
    _group(check_warmup)


def test_receipt_passes_and_quiet_checks():
    _group(check_passes)


def test_receipt_split_per_pass():
    _group(check_split)


def test_receipt_medians_units_and_verdict_recompute():
    _group(check_medians_and_decision)


def test_receipt_statements():
    _group(check_statements)


def test_receipt_producer():
    errs = check_producer(_receipt(), _committed)
    assert not errs, "; ".join(errs[:8])


def test_receipt_has_no_leak():
    _group(check_no_leak)
