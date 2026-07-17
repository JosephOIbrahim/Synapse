"""RETINA host hook — the manifest writer + ``.done`` sentinel wiring (M1).

This is the ONLY in-process perception code (blueprint §3): thin, additive, and
by construction unable to fail the render. It runs on Houdini's main thread from
inside the render-submit path (``handlers_render._handle_render``), just before
``node.render()``. Two jobs:

1. **Manifest writer** — assemble the scene truth the out-of-process worker needs
   and write ``<product>.retina_manifest.json`` alongside the products: product
   paths, expected AOV list, resolution, camera 4x4, target prim paths + world
   bboxes, expectation blocks, scene fingerprint, renderer/denoiser/samples
   profile, frame range (blueprint §3 list). At M1 the fields the host cannot yet
   cheaply and truthfully derive (camera 4x4, prim bboxes) are recorded
   ``inconclusive`` in an explicit ``honesty`` block — never faked (§7).

2. **``.done`` sentinel + fingerprint receipt** — wire the husk-level
   ``husk_postframe`` script param so a ``.done`` drops **after pixels**, and
   stamp the manifest fingerprint into the EXR header. Both surfaces are decided
   by the live catalog, not memory (see ``configure_husk_sentinel`` for the
   verdict + evidence).

Purity: this module imports **zero ``hou``** — every Houdini touch is a method
call on the duck-typed ``node`` object the caller passes (``node.parm(...)`` etc.),
so it is fully unit-testable with a fake node and trivially phantom-clean (no
``hou.<attr>`` to verify). It imports **zero ``cv2``** (RETINA P5, pinned by
``tests/test_retina_boundary.py``).

ADDITIVE contract: this code sets ROP parms only through the caller's
restore-in-``finally`` list, so the ROP is byte-identical after the render (the
render port wave golden-pins this path — reconciliation §4.1). It NEVER mutates
an existing render-result envelope key; the handler attaches its report under a
new ``retina`` key. Any failure degrades to ``{"ok": False, ...}`` with an
honesty note; it never raises.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA = "retina_manifest/v1"
MANIFEST_SUFFIX = ".retina_manifest.json"

# The env var the husk-level sentinel script reads to locate the manifest it must
# stamp ``.done`` files for. husk (background render) inherits the host process
# env, so this is the carrier — husk-level scripts must be bare, space-free FILE
# PATHS (catalog item 2 gotcha), so an argument cannot be passed on the command
# line; the env var is the portable channel.
MANIFEST_ENV_VAR = "SYNAPSE_RETINA_MANIFEST"

# EXR header key for the in-artifact fingerprint receipt (catalog item 6:
# husk_metadata_key=synapse_retina_fingerprint -> --extra-metadata -> EXR header,
# CONFIRMED live on 22.0.368).
FINGERPRINT_METADATA_KEY = "synapse_retina_fingerprint"


class _EnvRestorer:
    """A restore-list entry (duck-typed like ``hou.Parm``'s ``.set``) that returns
    an environment variable to its prior value — ``None`` prior means *unset*, so
    restore pops it.

    ``configure_husk_sentinel`` sets a process-global env carrier
    (``SYNAPSE_RETINA_MANIFEST``); registering this on the SAME ``restore`` list
    the ROP parms use lets the handler's existing restore-in-``finally`` return
    the process env byte-identical after the render — the render port wave golden-
    pins this path (reconciliation §4.1), so a leaked carrier would drift it.
    """

    __slots__ = ("_key",)

    def __init__(self, key: str):
        self._key = key

    def set(self, value: Any) -> None:
        if value is None:
            os.environ.pop(self._key, None)
        else:
            os.environ[self._key] = value


# ---------------------------------------------------------------------------
# Pure assembly (zero hou, zero I/O) — testable in isolation
# ---------------------------------------------------------------------------

def assemble_manifest(
    *,
    rop_path: str,
    products: List[str],
    frame_range: Tuple[int, int],
    generated_at: str,
    engine: str = "unknown",
    resolution: Optional[Tuple[int, int]] = None,
    camera_matrix: Optional[List[float]] = None,
    aovs: Optional[List[str]] = None,
    targets: Optional[List[Dict[str, Any]]] = None,
    expectations: Optional[List[Dict[str, Any]]] = None,
    render_profile: Optional[Dict[str, Any]] = None,
    scene_inputs: Optional[Dict[str, Any]] = None,
    houdini_build: str = "unknown",
    claim: str = "render:file_truth",
    honesty: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build a ``retina_manifest/v1`` dict and stamp its content fingerprint.

    The ``scene_fingerprint`` is a deterministic hash of the *declared render*
    (products, frame, engine, resolution, and any ``scene_inputs`` the caller
    folds in — e.g. hip path). The top-level ``fingerprint`` is the manifest's
    own content hash (excluding the volatile ``generated_at`` and the fingerprint
    field itself), the value stamped into the EXR as the free receipt.
    """
    manifest: Dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": generated_at,
        "houdini_build": houdini_build,
        "claim": claim,
        "rop": rop_path,
        "renderer": engine,
        "frame_range": [int(frame_range[0]), int(frame_range[1])],
        "resolution": [int(resolution[0]), int(resolution[1])] if resolution else None,
        "camera_matrix": list(camera_matrix) if camera_matrix else None,
        "products": list(products),
        "aovs": list(aovs) if aovs else [],
        "targets": list(targets) if targets else [],
        "expectations": list(expectations) if expectations else [],
        "render_profile": dict(render_profile) if render_profile else {"renderer": engine},
        "honesty": dict(honesty) if honesty else {},
    }
    manifest["scene_fingerprint"] = _scene_fingerprint(
        products=products,
        frame_range=frame_range,
        engine=engine,
        resolution=resolution,
        scene_inputs=scene_inputs,
    )
    manifest["fingerprint"] = manifest_fingerprint(manifest)
    return manifest


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def _scene_fingerprint(
    *,
    products: List[str],
    frame_range: Tuple[int, int],
    engine: str,
    resolution: Optional[Tuple[int, int]],
    scene_inputs: Optional[Dict[str, Any]],
) -> str:
    payload = {
        "products": list(products),
        "frame_range": [int(frame_range[0]), int(frame_range[1])],
        "engine": engine,
        "resolution": [int(resolution[0]), int(resolution[1])] if resolution else None,
        "scene_inputs": scene_inputs or {},
    }
    return "sf1" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()[:16]


def manifest_fingerprint(manifest: Dict[str, Any]) -> str:
    """Deterministic content fingerprint of a manifest, stable across renders of
    the same declared work. Excludes ``generated_at`` (a clock read) and any
    prior ``fingerprint`` so the value is a pure function of the declared render.
    """
    stable = {k: v for k, v in manifest.items() if k not in ("generated_at", "fingerprint")}
    return "rm1" + hashlib.sha256(_canonical_bytes(stable)).hexdigest()[:16]


def manifest_path_for(product_path: str) -> str:
    """Sibling manifest path for a product: ``<stem>.retina_manifest.json`` in the
    product's directory (per-product so per-frame renders never collide)."""
    directory, filename = os.path.split(product_path)
    stem = filename
    for ext in (".exr", ".EXR"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    else:
        stem = os.path.splitext(filename)[0] or filename
    return os.path.join(directory, stem + MANIFEST_SUFFIX)


# ---------------------------------------------------------------------------
# Atomic write (zero hou)
# ---------------------------------------------------------------------------

def write_manifest_atomic(manifest: Dict[str, Any], manifest_path: str) -> bool:
    """Write ``manifest`` to ``manifest_path`` atomically (``.tmp`` + ``replace``).

    Does NOT create the parent directory — the manifest rides *alongside the
    products*, whose directory the render path already ensured. If the directory
    is absent (a test path, or a token-dir not yet created), returns ``False``
    without side effects rather than fabricating a directory. Never raises.
    """
    parent = os.path.dirname(manifest_path) or "."
    if not os.path.isdir(parent):
        return False
    tmp = manifest_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, manifest_path)
        return True
    except OSError as exc:
        logger.warning("RETINA: manifest write failed (%s): %s", manifest_path, exc)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False


# ---------------------------------------------------------------------------
# Best-effort node reads (all via duck-typed node methods — zero hou.<attr>)
# ---------------------------------------------------------------------------

def _read_raw(parm: Any) -> Any:
    """Token-preserving raw read of a parm, mirroring the handler's ``_parm_raw``
    (kept local so this module needs no ``hou`` import)."""
    try:
        return parm.unexpandedString()
    except Exception:
        try:
            return parm.eval()
        except Exception:
            return None


def _first_parm(node: Any, names: Tuple[str, ...]) -> Optional[Any]:
    for name in names:
        try:
            parm = node.parm(name)
        except Exception:
            parm = None
        if parm is not None:
            return parm
    return None


def _best_effort_resolution(
    node: Any, resolution: Optional[Tuple[int, int]], honesty: Dict[str, str]
) -> Optional[Tuple[int, int]]:
    if resolution and resolution[0] and resolution[1]:
        return int(resolution[0]), int(resolution[1])
    rx = _first_parm(node, ("resolutionx", "res_user1"))
    ry = _first_parm(node, ("resolutiony", "res_user2"))
    if rx is not None and ry is not None:
        try:
            w, h = int(rx.eval()), int(ry.eval())
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    honesty["resolution"] = "inconclusive: no explicit resolution and ROP res parms unreadable"
    return None


def _best_effort_samples(node: Any) -> Optional[int]:
    parm = _first_parm(node, ("pathtracedsamples", "samplesperpixel", "vm_samplesx"))
    if parm is None:
        return None
    try:
        return int(parm.eval())
    except Exception:
        return None


def _best_effort_denoiser(node: Any) -> Optional[bool]:
    parm = _first_parm(node, ("denoise_enable", "enabledenoiser", "karma:global:denoiseenable"))
    if parm is None:
        return None
    try:
        return bool(parm.eval())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# .done sentinel + fingerprint receipt wiring
# ---------------------------------------------------------------------------

def configure_husk_sentinel(
    node: Any,
    *,
    manifest_path: str,
    fingerprint: str,
    sentinel_script: str,
    restore: List[Tuple[Any, Any]],
    honesty: Dict[str, str],
) -> Dict[str, Any]:
    """Wire the ``.done`` sentinel + the in-EXR fingerprint receipt onto the ROP.

    THE TIMING RULING (perception_truth_22.0.368.json item 2, live on 22.0.368):
    the ROP-level ``postrender``/``postframe`` scripts fire at **USD-generation
    time** (measured +212ms, in the calling process AFTER husk exits) — they run
    BEFORE pixels exist on the husk path, so they are the WRONG surface for a
    pixels-done sentinel. The husk-level params (``husk_postframe`` /
    ``husk_postrender`` -> ``husk --postframe-script`` / ``--postrender-script``)
    fire **+5ms after the EXR is written**. Therefore the ``.done`` sentinel rides
    ``husk_postframe`` (per-frame, fires after that frame's pixels). Evidence:
    item 2 ``timing_output`` (EXR mtime=118.897; husk_postframe t=118.902).

    MECHANISM (how the script actually fires): husk **execs** the sentinel FILE at
    that +5ms mark with a globals dict whose ``__name__ == "builtins"`` (assayer-
    proved live), NOT ``"__main__"``. The sentinel's module-foot guard fires
    ``run()`` on that ``"builtins"`` surface, so the ``.done`` genuinely drops on a
    real render — the M1 build's ``if __name__ == "__main__"`` guard never did
    (dead-sentinel showstopper, fixed in ``retina_sentinel_postframe``).

    GOTCHA (item 2): husk-level script params pass on the husk command line and
    MUST be a bare, **space-free FILE PATH** (inline code triggers
    ``husk: too many positional options``). So we point ``husk_postframe`` at the
    committed sentinel script file and carry the manifest location in an env var;
    if the script path contains a space we refuse and flag inconclusive rather
    than emit a broken husk command line.

    RECEIPT (item 6, CONFIRMED live): ``husk_metadata_key`` /
    ``husk_metadata_value`` -> ``husk --extra-metadata KEY VALUE`` -> the value
    lands in the EXR header. We stamp ``synapse_retina_fingerprint=<fingerprint>``
    so the manifest fingerprint travels inside the artifact.

    Every parm set is appended to ``restore`` FIRST (WP4 restore-in-finally), so
    the ROP is byte-identical after the render. Best-effort throughout; a missing
    parm is honesty-flagged, never fatal.
    """
    report: Dict[str, Any] = {"done_wired": False, "receipt_wired": False}

    if " " in sentinel_script:
        honesty["done_sentinel"] = (
            "inconclusive: sentinel script path contains a space — husk-level "
            "scripts must be space-free file paths (catalog item 2); .done not wired"
        )
        report["done_reason"] = "sentinel_script_path_has_space"
        return report

    # Carrier: husk (background render) inherits this env; the sentinel reads it.
    # Register a restore of the PRIOR value on the SAME restore list the ROP parms
    # use (WP4), so the handler's finally returns the process env byte-identical
    # after the render — a leaked carrier would drift the golden-pinned render
    # path (reconciliation §4.1).
    restore.append((_EnvRestorer(MANIFEST_ENV_VAR), os.environ.get(MANIFEST_ENV_VAR)))
    os.environ[MANIFEST_ENV_VAR] = manifest_path

    # .done sentinel — prefer per-frame husk_postframe; fall back to husk_postrender.
    done_parm = _first_parm(node, ("husk_postframe", "husk_postrender"))
    if done_parm is not None:
        try:
            restore.append((done_parm, _read_raw(done_parm)))
            done_parm.set(sentinel_script)
            report["done_wired"] = True
            report["done_param"] = getattr(done_parm, "name", lambda: "?")()
            report["sentinel_script"] = sentinel_script
        except Exception as exc:
            honesty["done_sentinel"] = f"inconclusive: husk script param set failed: {exc}"
    else:
        honesty["done_sentinel"] = (
            "inconclusive: ROP has no husk_postframe/husk_postrender param "
            "(non-husk render path?) — .done not wired"
        )

    # Fingerprint receipt — husk_metadata_key/value (index-free, then indexed).
    key_parm = _first_parm(node, ("husk_metadata_key", "husk_metadata_key1"))
    val_parm = _first_parm(node, ("husk_metadata_value", "husk_metadata_value1"))
    if key_parm is not None and val_parm is not None:
        try:
            restore.append((key_parm, _read_raw(key_parm)))
            restore.append((val_parm, _read_raw(val_parm)))
            key_parm.set(FINGERPRINT_METADATA_KEY)
            val_parm.set(fingerprint)
            report["receipt_wired"] = True
        except Exception as exc:
            honesty["fingerprint_receipt"] = f"inconclusive: husk_metadata set failed: {exc}"
    else:
        honesty["fingerprint_receipt"] = (
            "inconclusive: ROP has no husk_metadata_key/value param — "
            "fingerprint receipt not stamped into EXR"
        )

    return report


# ---------------------------------------------------------------------------
# The one entry point the render handler calls (never raises)
# ---------------------------------------------------------------------------

def install_retina_hooks(
    node: Any,
    *,
    product_path: str,
    frame: int,
    engine: str,
    node_type: str,
    resolution: Optional[Tuple[int, int]],
    restore: List[Tuple[Any, Any]],
    generated_at: str,
    sentinel_script: str,
    retina_payload: Optional[Dict[str, Any]] = None,
    houdini_build: str = "unknown",
    hip_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble + write the manifest and wire the ``.done`` sentinel/receipt.

    Returns a report dict (attached by the handler under a new ``retina``
    result key). Best-effort and total: any failure is caught and reported as
    ``{"ok": False, "error": ..., "honesty": {...}}`` — the render is never
    affected.
    """
    honesty: Dict[str, str] = {}
    payload = retina_payload if isinstance(retina_payload, dict) else {}
    try:
        # Declared claim/targets/expectations/aovs come from the caller's payload
        # when present (the mutation intent, plumbed in M3); absent at M1 -> empty
        # + honesty-flagged, never fabricated.
        claim = str(payload.get("claim") or "render:file_truth")
        targets = payload.get("targets") if isinstance(payload.get("targets"), list) else []
        expectations = (
            payload.get("expectations") if isinstance(payload.get("expectations"), list) else []
        )
        aovs = payload.get("aovs") if isinstance(payload.get("aovs"), list) else []
        if not aovs:
            honesty["aovs"] = "inconclusive: no AOV list declared (M1 thin — declared in M3)"
        if not targets:
            honesty["targets"] = "inconclusive: no target prims declared (M1 thin — declared in M3)"

        res = _best_effort_resolution(node, resolution, honesty)

        # camera_matrix: the worker needs it to project prim bboxes (M2+); T0
        # (M1) does not. Read it only if the caller already resolved it; otherwise
        # honesty-flag rather than run heavy stage introspection in the thin hook.
        camera_matrix = payload.get("camera_matrix") if isinstance(
            payload.get("camera_matrix"), list
        ) else None
        if camera_matrix is None:
            honesty["camera_matrix"] = (
                "inconclusive: camera 4x4 not exported at M1 (thin hook); "
                "T0 file-truth does not require it — wired for the T1 projection tier"
            )

        render_profile: Dict[str, Any] = {"renderer": engine, "node_type": node_type}
        samples = _best_effort_samples(node)
        if samples is not None:
            render_profile["samples"] = samples
        denoiser = _best_effort_denoiser(node)
        if denoiser is not None:
            render_profile["denoiser"] = denoiser

        scene_inputs = {"hip": hip_path} if hip_path else {}

        manifest_path = manifest_path_for(product_path)
        manifest = assemble_manifest(
            rop_path=_safe_path(node),
            products=[product_path],
            frame_range=(int(frame), int(frame)),
            generated_at=generated_at,
            engine=engine,
            resolution=res,
            camera_matrix=camera_matrix,
            aovs=aovs,
            targets=targets,
            expectations=expectations,
            render_profile=render_profile,
            scene_inputs=scene_inputs,
            houdini_build=houdini_build,
            claim=claim,
            honesty=honesty,
        )
        # Record where the manifest lives so T0's proof line can point at it.
        manifest["manifest_path"] = manifest_path

        written = write_manifest_atomic(manifest, manifest_path)
        if not written:
            honesty["manifest"] = (
                "inconclusive: product directory absent at hook time — manifest not written"
            )

        # Only wire the .done sentinel (and set the env carrier) when the
        # manifest actually landed — a sentinel pointed at a manifest that was
        # never written has nothing to resolve, and setting the process-global
        # env carrier without a manifest is a pointless side effect.
        if written:
            sentinel_report = configure_husk_sentinel(
                node,
                manifest_path=manifest_path,
                fingerprint=manifest["fingerprint"],
                sentinel_script=sentinel_script,
                restore=restore,
                honesty=honesty,
            )
        else:
            sentinel_report = {
                "done_wired": False,
                "receipt_wired": False,
                "skipped": "manifest_not_written",
            }

        return {
            "ok": bool(written),
            "manifest_path": manifest_path,
            "manifest_written": written,
            "fingerprint": manifest["fingerprint"],
            "scene_fingerprint": manifest["scene_fingerprint"],
            "sentinel": sentinel_report,
            "honesty": honesty,
        }
    except Exception as exc:  # total: the eye never destabilizes the hand (P5)
        logger.warning("RETINA: host hook degraded (non-blocking): %s", exc)
        return {"ok": False, "error": str(exc), "honesty": honesty or {"hook": "exception"}}


def _safe_path(node: Any) -> str:
    try:
        return node.path()
    except Exception:
        return "<unknown-rop>"
