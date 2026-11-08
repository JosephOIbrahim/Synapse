"""NR-GPU-QUALIFICATION parity CLI: the R2 change-mask chain on CUDA against the CPU reference.

Run from the repository root.

  python harness/next-release/gpu/qualification/parity.py --mode cpu --out FILE
      The cpu_reference run: retina.t1.change_mask on every fixture. Writes, per fixture id, the
      mask digest beside the fixture's construction digest, plus the interpreter, numpy and cv2
      versions, cv2.__file__, and the reference identity this environment measures. It prints
      that identity: a cpu_reference ruling (OD-10) has to name exactly that string.

  python harness/next-release/gpu/qualification/parity.py --mode gpu --out FILE
      The worker run (R4 runtime): retina.backend_cuda.change_mask_cuda on every fixture, with the
      in-process retina.t1.change_mask as a cross-check. Writes gpu_mask_sha256,
      cpu_inprocess_mask_sha256, the first differing pixel when they differ, last_dispatch()
      after each fixture, and witness().

  python harness/next-release/gpu/qualification/parity.py profile --cpu FILE --by WHO \
      --date YYYY-MM-DD --identity TEXT --out harness/next-release/gpu/qualification_profile.json
      Freezes the profile: fixture ids, each fixture's construction digest, expected_mask_sha256
      from the cpu-mode file, and cpu_reference_ruling {by, date, identity} copied from the
      arguments, never defaulted. Refuses an identity the cpu-mode file did not measure, the
      user-site cv2 4.12.0, and overwriting a frozen profile without --replace.

  python harness/next-release/gpu/qualification/parity.py assemble --gpu FILE --cpu FILE \
      --profile harness/next-release/gpu/qualification_profile.json \
      --build-lock harness/vision/gpu_build_lock/build_lock_receipt.json \
      --out harness/next-release/gpu_qualification.json
      Writes the qualification receipt with exactly the fields the draft predicate
      harness/next-release/gpu/test_qualification_contract.py reads. A fixture whose digests
      disagree also carries first_difference and expected_mask_sha256, so a failing receipt
      keeps its evidence.

Mask digest: sha256 of the C-contiguous uint8 mask bytes, with shape and dtype beside it. The
parity criterion is identical mask bytes (G0-PROPOSED); a mismatch is recorded with
coordinates and never toleranced.

Standard library plus numpy. cv2 is reached only through retina.t1 and retina.backend_cuda,
both imported lazily, so this file imports, and its offline tests run, with no cv2.

Exit codes: 0 done; 1 a parity mismatch or an unqualified receipt was recorded; 2 refused and
nothing written; 3 not computed (CUDA or the CPU path unavailable; the file says why).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import importlib.util
import json
import platform
import re
import sys
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]

R2_OPS = ("absdiff", "threshold", "morphology_open", "morphology_close")
SCHEMA = 1
KIND_CPU = "nr-gpu-qualification/parity-cpu"
KIND_GPU = "nr-gpu-qualification/parity-gpu"
KIND_PROFILE = "nr-gpu-qualification/profile"
OFF_PIN_CV2 = "4.12.0"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
USER_PROFILE_PATH = re.compile(r"[a-z]:[\\/]+users[\\/]", re.IGNORECASE)

EXIT_OK, EXIT_MISMATCH, EXIT_REFUSED, EXIT_NOT_COMPUTED = 0, 1, 2, 3


def load_fixtures():
    """The sibling fixtures module, loaded by path: works as a script, under pytest, from any cwd."""
    name = "nr_gpu_qualification_fixtures"
    mod = sys.modules.get(name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(name, HERE / "fixtures.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return mod


# ---------------------------------------------------------------------------
# Digests, mask transport, differences
# ---------------------------------------------------------------------------

def mask_digest(mask) -> dict:
    """sha256 of the C-contiguous uint8 bytes, with shape and dtype beside it."""
    if not isinstance(mask, np.ndarray):
        raise TypeError(f"mask is a {type(mask).__name__}, not a numpy array")
    if mask.dtype != np.uint8:
        raise TypeError(f"mask dtype is {mask.dtype}, not uint8")
    c = np.ascontiguousarray(mask)
    return {"sha256": hashlib.sha256(c.tobytes()).hexdigest(),
            "shape": [int(n) for n in c.shape], "dtype": str(c.dtype)}


def encode_mask(mask: np.ndarray) -> str:
    return base64.b64encode(zlib.compress(np.ascontiguousarray(mask).tobytes(), 9)).decode("ascii")


def decode_mask(text: str, shape) -> np.ndarray:
    raw = zlib.decompress(base64.b64decode(text.encode("ascii")))
    return np.frombuffer(raw, dtype=np.uint8).reshape([int(n) for n in shape]).copy()


def first_difference(gpu: np.ndarray, cpu: np.ndarray) -> dict | None:
    """The first differing pixel in C order with both values and the count; None when equal."""
    if gpu.shape != cpu.shape:
        return {"shape_mismatch": {"gpu": [int(n) for n in gpu.shape], "cpu": [int(n) for n in cpu.shape]}}
    where = np.argwhere(gpu != cpu)
    if where.size == 0:
        return None
    pos = [int(v) for v in where[0]]
    out = {"row": pos[0], "col": pos[1]} if len(pos) == 2 else {"index": pos}
    out.update(gpu=int(gpu[tuple(pos)]), cpu=int(cpu[tuple(pos)]), differing_px=int(len(where)))
    return out


# ---------------------------------------------------------------------------
# Environment and the cpu_reference identity
# ---------------------------------------------------------------------------

def _cv2_distribution() -> str | None:
    try:
        from importlib import metadata
        names = sorted(set(metadata.packages_distributions().get("cv2") or []))
        return ", ".join(f"{n} {metadata.version(n)}" for n in names) or None
    except Exception:
        return None


def environment(t1) -> dict:
    """Interpreter, numpy and cv2 facts, with cv2 read from the module retina.t1 imported."""
    cv2 = getattr(t1, "cv2", None)
    return {
        "interpreter": {"implementation": platform.python_implementation(),
                        "version": platform.python_version()},
        "numpy_version": np.__version__,
        "cv2_version": getattr(cv2, "__version__", None),
        "cv2_file": getattr(cv2, "__file__", None),
        "cv2_distribution": _cv2_distribution(),
    }


def reference_identity(doc: dict) -> str:
    """The cpu_reference identity a cpu-mode file measures; an OD-10 ruling names this string."""
    interp = doc.get("interpreter") or {}
    return (f"cv2 {doc.get('cv2_version')} ({doc.get('cv2_distribution') or 'no pip distribution'})"
            f" on {interp.get('implementation')} {interp.get('version')}"
            f" with numpy {doc.get('numpy_version')}")


# ---------------------------------------------------------------------------
# The two measuring modes
# ---------------------------------------------------------------------------

def _import(name: str):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(name)


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def run_cpu(t1=None, env=None) -> tuple[dict, int]:
    """retina.t1.change_mask on every fixture. t1 and env are injectable for offline tests."""
    fx = load_fixtures()
    if t1 is None:
        t1 = _import("retina.t1")
    env = dict(env) if env is not None else environment(t1)
    fixtures, rc = {}, EXIT_OK
    for fid in fx.FIXTURE_IDS:
        before, after, t, r = fx.build(fid)
        rec = {"construction_sha256": fx.construction_digest(before, after, t, r),
               "diff_threshold": t, "morph_radius": r}
        try:
            mask = t1.change_mask(before, after, diff_threshold=t, morph_radius=r)
            d = mask_digest(mask)
        except Exception as exc:
            rec["error"] = _error(exc)
            rc = EXIT_NOT_COMPUTED
        else:
            rec.update(mask_sha256=d["sha256"], mask_shape=d["shape"], mask_dtype=d["dtype"],
                       changed_px=int(np.count_nonzero(mask)), mask_zlib_b64=encode_mask(mask))
        fixtures[fid] = rec
    doc = {"kind": KIND_CPU, "schema": SCHEMA, "mode": "cpu", **env, "fixtures": fixtures}
    doc["reference_identity"] = reference_identity(doc)
    return doc, rc


def _dispatch(backend) -> dict:
    return {str(k): str(v) for k, v in dict(backend.last_dispatch()).items()}


def run_gpu(backend=None, t1=None, env=None) -> tuple[dict, int]:
    """retina.backend_cuda.change_mask_cuda on every fixture, cross-checked against the
    in-process retina.t1.change_mask on freshly built planes. Never falls back to the CPU."""
    fx = load_fixtures()
    if t1 is None:
        t1 = _import("retina.t1")
    env = dict(env) if env is not None else environment(t1)
    doc = {"kind": KIND_GPU, "schema": SCHEMA, "mode": "gpu", **env, "fixtures": {}}
    if backend is None:
        try:
            backend = _import("retina.backend_cuda")
        except Exception as exc:
            doc["cuda_status"] = {"available": False,
                                  "reason": f"retina.backend_cuda not importable: {_error(exc)}"}
            return doc, EXIT_NOT_COMPUTED
    try:
        ok, reason = backend.cuda_status()
    except Exception as exc:  # the contract says it never raises; record it if it does
        ok, reason = False, f"cuda_status raised {_error(exc)}"
    doc["cuda_status"] = {"available": bool(ok), "reason": str(reason)}
    doc["operations"] = [str(op) for op in getattr(backend, "OPERATIONS", ())]
    computed, mismatched = True, False
    for fid in fx.FIXTURE_IDS:
        before, after, t, r = fx.build(fid)
        built = fx.construction_digest(before, after, t, r)
        rec = {"construction_sha256": built, "diff_threshold": t, "morph_radius": r}
        gpu = cpu = None
        try:
            gpu = backend.change_mask_cuda(before, after, diff_threshold=t, morph_radius=r)
            rec["dispatch"] = _dispatch(backend)
            g = mask_digest(gpu)
            if fx.construction_digest(before, after, t, r) != built:
                raise RuntimeError("the backend changed its input planes")
        except Exception as exc:
            rec["gpu_error"] = _error(exc)
            gpu, computed = None, False
        else:
            rec.update(gpu_mask_sha256=g["sha256"], gpu_mask_shape=g["shape"],
                       gpu_mask_dtype=g["dtype"], gpu_changed_px=int(np.count_nonzero(gpu)),
                       gpu_mask_zlib_b64=encode_mask(gpu))
        before2, after2, _, _ = fx.build(fid)
        try:
            cpu = t1.change_mask(before2, after2, diff_threshold=t, morph_radius=r)
            c = mask_digest(cpu)
        except Exception as exc:
            rec["cpu_inprocess_error"] = _error(exc)
            cpu, computed = None, False
        else:
            rec.update(cpu_inprocess_mask_sha256=c["sha256"], cpu_inprocess_mask_shape=c["shape"])
        if gpu is not None and cpu is not None:
            diff = first_difference(gpu, cpu)
            rec["identical"] = diff is None
            if diff is not None:
                rec["first_difference"] = diff
                mismatched = True
        doc["fixtures"][fid] = rec
    try:
        doc["last_dispatch"] = _dispatch(backend)
    except Exception as exc:
        doc["last_dispatch"] = {"error": _error(exc)}
    try:
        doc["witness"] = backend.witness()
    except Exception as exc:
        doc["witness"] = {"error": _error(exc)}
    if not ok or not computed:
        return doc, EXIT_NOT_COMPUTED
    return doc, EXIT_MISMATCH if mismatched else EXIT_OK


# ---------------------------------------------------------------------------
# Profile and receipt
# ---------------------------------------------------------------------------

def _user_paths(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj] if USER_PROFILE_PATH.search(obj) else []
    if isinstance(obj, dict):
        return [s for k, v in obj.items() for s in _user_paths(k) + _user_paths(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in _user_paths(v)]
    return []


def _mode_doc_problems(doc, kind: str, fx) -> list[str]:
    if not isinstance(doc, dict) or doc.get("kind") != kind or doc.get("schema") != SCHEMA:
        return [f"not a {kind} schema {SCHEMA} file"]
    recs = doc.get("fixtures") or {}
    if set(recs) != set(fx.FIXTURE_IDS):
        return [f"{kind}: fixture ids {sorted(recs)} are not {sorted(fx.FIXTURE_IDS)}"]
    cpu = kind == KIND_CPU
    digest_key, mask_key = ("mask_sha256", "mask_zlib_b64") if cpu else ("gpu_mask_sha256", "gpu_mask_zlib_b64")
    p = []
    if not cpu and not (doc.get("cuda_status") or {}).get("available"):
        p.append(f"gpu-mode file: CUDA unavailable: {(doc.get('cuda_status') or {}).get('reason')}")
    for fid in fx.FIXTURE_IDS:
        rec = recs[fid]
        if rec.get("construction_sha256") != fx.construction_digest(*fx.build(fid)):
            p.append(f"{kind}: fixture {fid} was not built by this fixtures.py")
        errors = sorted(k for k in rec if k.endswith("error"))
        if errors:
            p.append(f"{kind}: fixture {fid} was not computed: {rec[errors[0]]}")
        elif not HEX64.match(str(rec.get(digest_key, ""))) or not isinstance(rec.get(mask_key), str):
            p.append(f"{kind}: fixture {fid} carries no mask digest or mask")
    return p


def build_profile(cpu_doc: dict, cpu_file_sha256: str, *, by: str, date: str,
                  identity: str) -> tuple[dict, list[str]]:
    fx = load_fixtures()
    p = _mode_doc_problems(cpu_doc, KIND_CPU, fx)
    if p:
        return {}, p
    measured = reference_identity(cpu_doc)
    if identity != measured:
        p.append(f"--identity is not the identity the cpu-mode file measured: {measured!r}")
    if OFF_PIN_CV2 in measured or str(cpu_doc.get("cv2_version")) == OFF_PIN_CV2:
        p.append("the user-site cv2 4.12.0 is never the oracle")
    if not str(by).strip():
        p.append("--by is empty")
    if not ISO_DATE.match(str(date)):
        p.append("--date is not YYYY-MM-DD")
    fixtures = {}
    for fid in fx.FIXTURE_IDS:
        rec = cpu_doc["fixtures"][fid]
        fixtures[fid] = {
            "status": fx.STATUS[fid],
            "relation": fx.RELATIONS[fid],
            "construction_sha256": rec["construction_sha256"],
            "diff_threshold": rec["diff_threshold"],
            "morph_radius": rec["morph_radius"],
            "expected_mask_sha256": rec["mask_sha256"],
            "expected_mask_shape": rec["mask_shape"],
            "expected_mask_dtype": rec["mask_dtype"],
        }
    profile = {
        "kind": KIND_PROFILE,
        "schema": SCHEMA,
        "chain": "R2: retina/t1.py change_mask - absdiff, strict threshold, morphological open, close",
        "operations": list(R2_OPS),
        "criterion": ("identical mask bytes (G0-PROPOSED): sha256 of the C-contiguous uint8 mask, "
                      "shape and dtype beside it"),
        "fixtures": fixtures,
        "expected_from_cpu_file_sha256": cpu_file_sha256,
        "cpu_reference_ruling": {"by": by, "date": date, "identity": identity},
    }
    p += [f"the profile would carry a user-profile path: {s}" for s in _user_paths(profile)]
    return profile, p


def build_receipt(gpu_doc: dict, cpu_doc: dict, profile: dict, *, profile_sha256: str,
                  build_lock_sha256: str) -> tuple[dict, list[str], list[str]]:
    """(receipt, refusals, unqualified). Refusals mean nothing may be written; unqualified lines
    say why the written receipt cannot turn the predicate green."""
    fx = load_fixtures()
    refusals = _mode_doc_problems(cpu_doc, KIND_CPU, fx) + _mode_doc_problems(gpu_doc, KIND_GPU, fx)
    if not isinstance(profile, dict) or profile.get("kind") != KIND_PROFILE or profile.get("schema") != SCHEMA:
        refusals.append("the profile was not written by this tool")
    elif set(profile.get("fixtures") or {}) != set(fx.FIXTURE_IDS):
        refusals.append("the profile's fixture ids differ from this fixtures.py")
    if refusals:
        return {}, refusals, []
    for fid in fx.FIXTURE_IDS:
        if profile["fixtures"][fid].get("construction_sha256") != cpu_doc["fixtures"][fid]["construction_sha256"]:
            refusals.append(f"fixture {fid}: the profile froze a different construction")
    identity = reference_identity(cpu_doc)
    if OFF_PIN_CV2 in identity:
        refusals.append("the user-site cv2 4.12.0 is never the oracle")
    dispatch = {}
    for op in R2_OPS:
        off = [fid for fid in fx.FIXTURE_IDS
               if (gpu_doc["fixtures"][fid].get("dispatch") or {}).get(op) != "cuda"]
        dispatch[op] = "cuda" if not off else "not cuda in: " + ", ".join(off)
    witness = gpu_doc.get("witness") if isinstance(gpu_doc.get("witness"), dict) else {}
    fixtures, mismatched = {}, []
    for fid in fx.FIXTURE_IDS:
        g, c, e = gpu_doc["fixtures"][fid], cpu_doc["fixtures"][fid], profile["fixtures"][fid]
        entry = {"gpu_mask_sha256": g["gpu_mask_sha256"], "cpu_mask_sha256": c["mask_sha256"]}
        same = (g["gpu_mask_sha256"] == c["mask_sha256"] == e.get("expected_mask_sha256")
                and list(g["gpu_mask_shape"]) == list(c["mask_shape"])
                == list(e.get("expected_mask_shape") or []))
        if not same:
            entry["first_difference"] = first_difference(
                decode_mask(g["gpu_mask_zlib_b64"], g["gpu_mask_shape"]),
                decode_mask(c["mask_zlib_b64"], c["mask_shape"]))
            entry["expected_mask_sha256"] = e.get("expected_mask_sha256")
            mismatched.append(f"fixture {fid}: GPU, cpu_reference and profile digests are not all equal")
        fixtures[fid] = entry
    receipt = {
        "profile_sha256": profile_sha256,
        "build_lock_sha256": build_lock_sha256,
        "backend_witness": {"dispatch": dispatch,
                            "loaded_modules": [str(m) for m in witness.get("loaded_modules") or []],
                            "cv2_file": witness.get("cv2_file")},
        "fixtures": fixtures,
        "cpu_reference": {"identity": identity},
    }
    refusals += [f"the receipt would carry a user-profile path: {s}" for s in _user_paths(receipt)]
    unqualified = mismatched + [f"dispatch {op}: {v}" for op, v in dispatch.items() if v != "cuda"]
    if not receipt["backend_witness"]["loaded_modules"] or not receipt["backend_witness"]["cv2_file"]:
        unqualified.append("the backend witness lists no loaded modules or no cv2.__file__")
    return receipt, refusals, unqualified


# ---------------------------------------------------------------------------
# Files and the command line
# ---------------------------------------------------------------------------

def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    return str(o)


def write_json(path, obj) -> str:
    """Deterministic UTF-8 JSON with LF line ends (the repo pins *.json to LF); returns its sha256."""
    data = (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True, default=_json_default)
            + "\n").encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _refuse(problems) -> int:
    for line in problems:
        print(f"REFUSED: {line}", file=sys.stderr)
    return EXIT_REFUSED


def _cmd_profile(argv) -> int:
    ap = argparse.ArgumentParser(prog="parity.py profile",
                                 description="Freeze the qualification profile from a cpu-mode file.")
    ap.add_argument("--cpu", required=True, help="cpu-mode file whose digests become expected_mask_sha256")
    ap.add_argument("--by", required=True, help="who ruled the cpu_reference identity (copied, never defaulted)")
    ap.add_argument("--date", required=True, help="date of that ruling, YYYY-MM-DD")
    ap.add_argument("--identity", required=True, help="the ruled identity; must equal the measured one")
    ap.add_argument("--out", required=True, help="normally harness/next-release/gpu/qualification_profile.json")
    ap.add_argument("--replace", action="store_true", help="re-freeze an existing profile")
    a = ap.parse_args(argv)
    try:
        cpu_doc, cpu_sha = read_json(a.cpu), _sha256_file(a.cpu)
    except (OSError, ValueError) as exc:
        return _refuse([f"cannot read {a.cpu}: {_error(exc)}"])
    profile, problems = build_profile(cpu_doc, cpu_sha, by=a.by, date=a.date, identity=a.identity)
    if Path(a.out).exists() and not a.replace:
        problems.append(f"{a.out} exists and a profile is frozen; pass --replace to re-freeze it")
    if problems:
        return _refuse(problems)
    sha = write_json(a.out, profile)
    print(f"profile written: {len(profile['fixtures'])} fixtures, sha256 {sha}")
    return EXIT_OK


def _cmd_assemble(argv) -> int:
    ap = argparse.ArgumentParser(prog="parity.py assemble",
                                 description="Write the qualification receipt the draft predicate reads.")
    ap.add_argument("--gpu", required=True, help="gpu-mode file from the worker run")
    ap.add_argument("--cpu", required=True, help="cpu-mode file from the cpu_reference run")
    ap.add_argument("--profile", required=True, help="the frozen profile the receipt pins by sha256")
    ap.add_argument("--build-lock", required=True, help="the build-lock receipt the receipt pins by sha256")
    ap.add_argument("--out", required=True, help="normally harness/next-release/gpu_qualification.json")
    a = ap.parse_args(argv)
    try:
        gpu_doc, cpu_doc, profile = read_json(a.gpu), read_json(a.cpu), read_json(a.profile)
        profile_sha, lock_sha = _sha256_file(a.profile), _sha256_file(a.build_lock)
    except (OSError, ValueError) as exc:
        return _refuse([f"cannot read an input: {_error(exc)}"])
    receipt, refusals, unqualified = build_receipt(
        gpu_doc, cpu_doc, profile, profile_sha256=profile_sha, build_lock_sha256=lock_sha)
    if refusals:
        return _refuse(refusals)
    sha = write_json(a.out, receipt)
    for line in unqualified:
        print(f"NOT QUALIFIED: {line}", file=sys.stderr)
    verdict = "NOT qualified" if unqualified else "qualified"
    print(f"receipt written: {len(receipt['fixtures'])} fixtures, sha256 {sha}, {verdict}")
    return EXIT_MISMATCH if unqualified else EXIT_OK


def _cmd_run(argv) -> int:
    ap = argparse.ArgumentParser(prog="parity.py", description=__doc__.splitlines()[0],
                                 epilog="Subcommands: profile, assemble (see the module docstring).")
    ap.add_argument("--mode", choices=("cpu", "gpu"), required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        doc, rc = run_cpu() if a.mode == "cpu" else run_gpu()
    except ImportError as exc:
        print(f"NOT COMPUTED: {_error(exc)}", file=sys.stderr)
        return EXIT_NOT_COMPUTED
    sha = write_json(a.out, doc)
    for fid, rec in doc["fixtures"].items():
        if a.mode == "cpu":
            print(f"{fid}: {rec.get('mask_sha256') or rec.get('error')} changed_px={rec.get('changed_px')}")
        else:
            print(f"{fid}: gpu={rec.get('gpu_mask_sha256') or rec.get('gpu_error')} "
                  f"identical={rec.get('identical')} first_difference={rec.get('first_difference')}")
    if a.mode == "cpu":
        print(f"reference identity: {doc['reference_identity']}")
    else:
        print(f"cuda_status: {doc.get('cuda_status')}")
    print(f"{a.mode}-mode file written: sha256 {sha}, exit {rc}")
    return rc


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["profile"]:
        return _cmd_profile(argv[1:])
    if argv[:1] == ["assemble"]:
        return _cmd_assemble(argv[1:])
    return _cmd_run(argv)


if __name__ == "__main__":
    sys.exit(main())
