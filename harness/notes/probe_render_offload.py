"""F5a render-offload probe — PROBE ONLY, no production-path change.

Part of the freeze-relief forge (spec: docs/reviews/ui-freeze-fix-spec-2026-08-14.md,
"### F5 — Zombie-proof renders", re-scoped post-crucible). F5 as a default flip was
ruled FATAL twice; this script exists to replace the contested premise with live
measurement on Joe's licensed Houdini 22.0.400 before any F5b design is allowed.

HOW TO RUN (live only — imports cleanly outside Houdini by design):

    "C:\\Program Files\\Side Effects Software\\Houdini 22.0.400\\bin\\hython.exe" probe_render_offload.py

Run it on the host + license that production SYNAPSE uses. Run plain
``python probe_render_offload.py`` anywhere to confirm the file imports and
compiles clean with no Houdini present — every item reports UNKNOWN and the
script exits 0.

WHAT IT ESTABLISHES (prints PASS / FAIL / UNKNOWN + the exact invocation used):

    (a) Can husk launch and load the Karma delegate headless from a
        SYNAPSE-style call on this host and license? Probed as a MATRIX:
        direct husk.exe WITHOUT ``--indie`` vs direct husk.exe WITH
        ``--indie`` — the two halves of the contested evidence below differ
        on this axis, so both are measured.
    (b) What does ``node.render()`` do when dispatched on a BACKGROUND-mode
        Karma ROP (``usdrender_rop`` with ``soho_foreground=0``) from the
        SYNAPSE code path — return-immediately (background launch), raise, or
        block-until-pixels (silent synchronous)? Tested with a trivial scene
        rendered small so the answer is measured in seconds.
    (c) The correct completion signal for automation renders: the current
        SYNAPSE contract is file-exists poll on return. The probe also rides
        the husk-level ``husk_postframe`` script (sentinel .done file) and
        reports which signal actually marks "pixels on disk", with mtimes.

CONTESTED-EVIDENCE RECONCILIATION (the reason this probe exists):

    python/synapse/server/handlers_render.py:336-338 (``_handle_render_bounded``
    docstring) carries: "on Indie the out-of-process husk path cannot load the
    Karma delegate (verified live 2026-07-17, ``Unable to load render plugin:
    karma`` with zero output, ``--indie`` flag included)" — i.e. a FAILING
    direct husk launch that passed the ``--indie`` flag explicitly.

    harness/notes/perception_truth_22.0.368.json carries, same day (probe
    timestamp 2026-07-17T01:30:49Z), same license category
    (licenseCategoryType.Indie), transport hython-headless on 22.0.368:
    "H21-era Indie-silently-no-ops-headless-husk does NOT hold on 22.0.368:
    husk wrote real multi-part EXRs headless on Indie, CPU and XPU"
    (``key_finding_indie``) — i.e. a SUCCEEDING husk path where husk
    auto-detected the license; no explicit ``--indie`` appears anywhere in
    that file's recorded invocations.

    Both records are live-verified; both are real. Which invocation differs is
    UNKNOWN — that is what this probe measures. If item (a) splits PASS(no
    flag)/FAIL(with ``--indie``), the differing invocation is named: the
    explicit ``--indie`` flag itself. If both pass, the 336-338 failure must
    have involved something else (environment, delegate discovery, prior
    build) and item (a)'s recorded argv/env becomes the ground truth either
    way. Until this probe runs on 22.0.400, NO husk-offload claim may ship —
    and per the spec, F5b remains gated on this result AND Joe's sign-off.

COST / SAFETY: builds a throwaway scene in the current HIP (sphere + light +
camera + karmarendersettings + one usdrender_rop), writes outputs to the
system temp dir, one trivial frame at low resolution. It never touches the
production render handlers, defaults, or any existing scene nodes outside the
nodes it creates. Safe to re-run; each run uses fresh node names.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# stdlib-only module level. ALL hou/pxr imports live inside main()/helpers so
# this file imports and compiles clean outside Houdini (forge hard rule).
# ---------------------------------------------------------------------------

RESULTS: dict = {}
WORKDIR: Path | None = None
HUSK_TIMEOUT_S = 240.0
RENDER_POLL_TIMEOUT_S = 180.0
PLUGIN_ERROR_SENTINEL = "Unable to load render plugin"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(item: str, verdict: str, **fields) -> None:
    entry = {"verdict": verdict, **_json_safe(fields)}
    RESULTS[item] = entry
    print(f"[{item}] {verdict}")
    for key, val in entry.items():
        if key == "verdict":
            continue
        print(f"    {key}: {val}")


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _write_sentinel_script() -> Path:
    """Space-free husk --postframe-equivalent sentinel (husk execs the file;
    it does not import it — __name__ == 'builtins' on that surface)."""
    done_path = (WORKDIR / "f5a_pixel_done").resolve()
    script = WORKDIR / "f5a_sentinel_postframe.py"
    script.write_text(
        "import sys, time, pathlib, os\n"
        f"p = pathlib.Path({str(done_path)!r})\n"
        "p.write_text(__import__('json').dumps(\n"
        "    {'utc': time.time(), 'source': 'f5a_probe'}))\n"
        "sys.stderr.write('[f5a.sentinel] wrote %s\\n' % p)\n",
        encoding="utf-8",
    )
    return script


def _probe_a_husk_direct(husk_exe: str) -> None:
    """(a) direct husk.exe launch, with and without the explicit --indie flag."""
    if not Path(husk_exe).exists():
        _record("a_husk_delegate_load", "UNKNOWN",
                reason=f"husk.exe not found at {husk_exe}")
        return

    variants = {
        "without_--indie": ([], WORKDIR / "f5a_husk_direct_plain.exr"),
        "with_--indie": (["--indie"], WORKDIR / "f5a_husk_direct_indie.exr"),
    }
    per_variant = {}
    for label, (extra_flags, exr_path) in variants.items():
        # One .usda per variant so each variant's EXR is attributable.
        variant_usda = WORKDIR / f"f5a_probe_{label.replace('-', '')}.usda"
        if not _author_usda(variant_usda, exr_path):
            per_variant[label] = {"usda_author": "failed"}
            continue
        argv = [husk_exe] + list(extra_flags) + [str(variant_usda)]
        rec = {"argv": " ".join(argv)}
        try:
            t0 = time.monotonic()
            proc = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=HUSK_TIMEOUT_S, env=os.environ.copy(),
            )
            rec["wall_s"] = round(time.monotonic() - t0, 2)
            rec["exit_code"] = proc.returncode
            rec["plugin_error"] = PLUGIN_ERROR_SENTINEL in (proc.stdout + proc.stderr)
            # An EXR landing on disk is the delegate-loaded proof
            # (Software=Karma is stamped into the header by husk; existence
            # + non-zero size suffices).
            rec["exr_written"] = exr_path.exists() and exr_path.stat().st_size > 0
            rec["stderr_tail"] = "\\n".join(
                (proc.stderr or "").strip().splitlines()[-5:])
        except subprocess.TimeoutExpired:
            rec["timeout"] = True
        except OSError as exc:
            rec["os_error"] = str(exc)
        per_variant[label] = rec

    no_flag = per_variant.get("without_--indie", {})
    with_flag = per_variant.get("with_--indie", {})
    exr_ok = no_flag.get("exr_written", False)

    if any(r.get("timeout") or r.get("os_error") for r in per_variant.values()):
        verdict = "UNKNOWN"
    elif (not no_flag.get("plugin_error")) and no_flag.get("exit_code") == 0 and exr_ok:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    if (not no_flag.get("plugin_error")) and no_flag.get("exr_written") \
            and with_flag.get("plugin_error"):
        reconciliation = ("SPLIT — husk loads the Karma delegate WITHOUT the "
                          "explicit --indie flag and FAILS with it ('"
                          + PLUGIN_ERROR_SENTINEL + "'). The differing "
                          "invocation between handlers_render.py:336-338 and "
                          "perception_truth_22.0.368.json is the --indie flag "
                          "itself.")
    elif not with_flag.get("plugin_error") and not no_flag.get("plugin_error"):
        reconciliation = ("NO SPLIT — husk loads the delegate with and without "
                          "--indie on this build/license. The 336-338 2026-07-17 "
                          "failure was NOT caused by the flag; the argv/env "
                          "recorded here is the new ground truth.")
    else:
        reconciliation = ("BOTH variants failed to load the delegate — "
                          "perception_truth's success does not reproduce here.")

    _record("a_husk_delegate_load", verdict,
            build=_build_stamp(), license=_license_stamp(),
            exr_written=exr_ok, variants=per_variant,
            reconciliation=reconciliation)


def _classify_render_semantics(dt_return: float, exr_at_return: bool) -> str:
    if exr_at_return:
        return "BLOCKS_UNTIL_PIXELS (synchronous dispatch)"
    return "RETURNS_BEFORE_PIXELS (background launch; caller must poll/sentinel)"


def _probe_b_and_c_render_background(hou, lop_output_dir: Path) -> None:
    """(b) node.render() under soho_foreground=0; (c) completion signal."""
    stage_net = hou.node("/stage").createNode("lopnet",
                                              f"f5a_probe_lopnet_{int(time.time())}")
    sphere = stage_net.createNode("sphere")
    light = stage_net.createNode("distantlight")
    light.parm("intensity").set(1200)
    light.setInput(0, sphere)
    cam = stage_net.createNode("camera")
    cam.setInput(0, light)
    if cam.parmTuple("t") is not None:
        cam.parmTuple("t").set((0, 0, 6))
    settings = stage_net.createNode("karmarendersettings")
    settings.setInput(0, cam)

    exr_path = (lop_output_dir / "f5a_node_render.exr").as_posix()
    cam_prim = cam.parm("primpath")
    for parm_name, value in (
        ("picture", exr_path),
        ("camera", cam_prim.evalAsString() if cam_prim is not None else "/camera1"),
        ("engine", "cpu"),
    ):
        parm = settings.parm(parm_name)
        if parm is not None:
            try:
                parm.set(value)
            except hou.Error:
                pass  # probe records, never mutates production
    # Lowest-cost frame: small, 1 sample, no denoise if the parms exist.
    for parm_name, value in (("resolutionx", 240), ("resolutiony", 180),
                             ("pathtracedsamples", 1)):
        parm = settings.parm(parm_name)
        if parm is not None:
            try:
                parm.set(value)
            except hou.Error:
                pass

    sentinel_script = _write_sentinel_script()
    out_net = hou.node("/out")
    rop = out_net.createNode("usdrender_rop",
                             f"f5a_probe_rop_{int(time.time())}")
    rop.parm("loppath").set(settings.path())
    rop.parm("soho_foreground").set(0)  # THE probed premise: background mode
    t_parm = rop.parm("trange")
    if t_parm is not None:
        t_parm.set(1)  # single frame
    # (c) husk-level postframe sentinel on the ROP (husk_t*=enable toggle form)
    for toggle_name, path_name in (("husk_tpostframe", "husk_postframe"),):
        tp, pp = rop.parm(toggle_name), rop.parm(path_name)
        if tp is not None and pp is not None:
            tp.set(1)
            pp.set(str(sentinel_script).replace("\\", "/"))

    exr_file = Path(exr_path)
    if exr_file.exists():
        exr_file.unlink()
    done_file = WORKDIR / "f5a_pixel_done"
    if done_file.exists():
        done_file.unlink()

    invocation = (f"{rop.path()}.render(frame_range=(1, 1)) with "
                  f"soho_foreground=0, loppath={settings.path()}")
    raise_rec = None
    t0 = time.monotonic()
    try:
        rop.render(frame_range=(1, 1))
    except Exception as exc:  # noqa: BLE001 - probe records whatever render does
        raise_rec = f"{type(exc).__name__}: {exc}"
    dt_return = time.monotonic() - t0
    exr_at_return = exr_file.exists() and exr_file.stat().st_size > 0

    if raise_rec is not None:
        _record("b_node_render_background", "FAIL", semantics="RAISES",
                raise_info=raise_rec, invocation=invocation)
        _record("c_completion_signal", "UNKNOWN",
                reason="render raised; no completion path to measure")
        return

    semantics = _classify_render_semantics(dt_return, exr_at_return)

    # Poll for completion: exr mtime stability and sentinel mtime.
    exr_landed = None
    sentinel_landed = None
    deadline = time.monotonic() + RENDER_POLL_TIMEOUT_S
    last_size = -1
    while time.monotonic() < deadline:
        if exr_landed is None and exr_file.exists():
            size = exr_file.stat().st_size
            if size > 0 and size == last_size:
                exr_landed = exr_file.stat().st_mtime
            last_size = size
        if sentinel_landed is None and done_file.exists():
            sentinel_landed = done_file.stat().st_mtime
        if exr_landed is not None and sentinel_landed is not None:
            break
        time.sleep(0.5)

    if exr_landed is None and sentinel_landed is None:
        _record("b_node_render_background", "UNKNOWN",
                semantics=semantics, dt_return_s=round(dt_return, 2),
                invocation=invocation,
                note="no output within poll window; render may have queued "
                     "and never completed, or the delegate failed silently")
        _record("c_completion_signal", "UNKNOWN",
                reason="no completion observed at any signal surface")
        return

    _record("b_node_render_background", "PASS",
            semantics=semantics, dt_return_s=round(dt_return, 2),
            invocation=invocation,
            implication=("a background flip would BREAK the synchronous "
                         "file-on-return contract" if not exr_at_return else
                         "node.render() stays synchronous even in background "
                         "mode on this build"))

    delta = (None if sentinel_landed is None or exr_landed is None
             else round(sentinel_landed - exr_landed, 3))
    if sentinel_landed is not None:
        c_verdict = "PASS"
        recommendation = (
            "husk-level husk_postframe sentinel is the pixel-accurate signal "
            "(fires after the EXR lands); file-exists poll on return is the "
            "acceptable fallback ONLY when soho_foreground makes render() "
            "synchronous. Under a true background return, file-exists poll "
            "PLUS sentinel (or poll loop) is required — return-immediately "
            "carries no completion guarantee.")
    else:
        c_verdict = "PASS" if exr_landed is not None else "UNKNOWN"
        recommendation = (
            "sentinel did not fire (check husk_tpostframe/husk_postframe parm "
            "names on this build); file-exists poll remains the working "
            "signal — confirm mtime stability, not mere existence.")
    _record("c_completion_signal", c_verdict,
            exr_landed=mtime_iso(exr_landed),
            sentinel_landed=mtime_iso(sentinel_landed),
            sentinel_minus_exr_s=delta, recommendation=recommendation)


def mtime_iso(ts):
    return (None if ts is None else
            datetime.fromtimestamp(ts, timezone.utc).isoformat())


def _author_usda(path: Path, exr_path: Path) -> bool:
    """Author a minimal renderable stage via pxr (inside hython)."""
    try:
        from pxr import Gf, Usd, UsdGeom, UsdLux, UsdRender
    except ImportError:
        return False
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.Xform.Define(stage, "/root")
    sph = UsdGeom.Sphere.Define(stage, "/root/sphere")
    sph.CreateRadiusAttr(0.5)
    light = UsdLux.DistantLight.Define(stage, "/root/light")
    light.CreateIntensityAttr(1500)
    light.CreateAngleAttr(0.53)
    cam = UsdGeom.Camera.Define(stage, "/root/cam")
    cam.AddTranslateOp().Set(Gf.Vec3d(0, 0, 5))
    cam.CreateProjectionAttr("perspective")
    settings = UsdRender.Settings.Define(stage, "/Render/settings")
    settings.CreateCameraRel().SetTargets(["/root/cam"])
    try:
        settings.CreateResolutionAttr().Set(Gf.Vec2i(240, 180))
    except Exception:
        pass
    product = UsdRender.Product.Define(stage, "/Render/product")
    product.CreateProductNameAttr(str(exr_path).replace("\\", "/"))
    try:
        settings.CreateProductsRel().SetTargets([product.GetPath().pathString])
    except Exception:
        pass
    stage.GetRootLayer().Save()
    return True


def _build_stamp(hou_module=None) -> str:
    if hou_module is None:
        return "standalone (no hou)"
    try:
        return hou_module.applicationVersionString()
    except Exception:  # noqa: BLE001
        return "unknown"


def _license_stamp(hou_module=None) -> str:
    if hou_module is None:
        return "standalone (no hou)"
    try:
        return str(hou_module.licenseCategoryType())
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    global WORKDIR
    WORKDIR = Path(tempfile.mkdtemp(prefix="synapse_f5a_probe_"))
    print("=" * 72)
    print("F5a render-offload probe — PROBE ONLY, no production-path change")
    print(f"workdir: {WORKDIR}")
    print("=" * 72)

    try:
        import hou  # noqa: PLC0415 — deferred by design (standalone-safe)
    except ImportError:
        print()
        print("Not running under hython — all items UNKNOWN by design.")
        print("Run live on H22.0.400:")
        print('  "C:\\Program Files\\Side Effects Software\\'
              'Houdini 22.0.400\\bin\\hython.exe" probe_render_offload.py')
        for item in ("a_husk_delegate_load", "b_node_render_background",
                     "c_completion_signal"):
            _record(item, "UNKNOWN", transport="no-hou (standalone invocation)")
        _flush_results()
        return 0

    _record("0_environment", "PASS",
            build=_build_stamp(hou), license=_license_stamp(hou),
            python=sys.version.split()[0],
            ui_available=str(hou.isUIAvailable()))

    hfs = os.environ.get("HFS", "")
    husk_exe = str(Path(hfs) / "bin" / ("husk.exe" if os.name == "nt" else "husk"))
    _probe_a_husk_direct(husk_exe)

    try:
        _probe_b_and_c_render_background(hou, WORKDIR)
    except Exception as exc:  # noqa: BLE001 — the probe reports, never hides
        _record("b_node_render_background", "UNKNOWN",
                reason=f"scene-build raised before render: "
                       f"{type(exc).__name__}: {exc}")
        _record("c_completion_signal", "UNKNOWN",
                reason="blocked by (b) scene-build failure")

    _flush_results()
    return 0


def _flush_results() -> None:
    out = Path(__file__).with_suffix("")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_path = out.parent / f"probe_render_offload.results.{stamp}.json"
    payload = {"probe": "F5a render-offload", "timestamp_utc": _utcnow(),
               "workdir": str(WORKDIR), "results": RESULTS}
    try:
        results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nResults written: {results_path}")
    except OSError as exc:
        print(f"\n(results file not writable: {exc} — stdout above is the record)")


if __name__ == "__main__":
    raise SystemExit(main())
