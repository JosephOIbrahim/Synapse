"""Supervised RETINA worker: one request in, one result out (NR-WORKER-SUPERVISED).

Run by the R4 CPU worker interpreter (CPython 3.12.10 with cv2, numpy and the cp312
OpenImageIO wheel), never by Houdini::

    <worker python> -E -s -B -m retina.worker_entrypoint <request.json>

with the repository root as the working directory (it is also put on ``sys.path``
from this file's own location, so running the file by path works too). The host
side is ``python/synapse/host/retina_worker.py``; only paths and small JSON cross.

Request (``<name>.json``), protocol :data:`PROTOCOL`::

    {"protocol": PROTOCOL, "request_id": <str>, "op": <str>, "product": <abs path>,
     "subimage": <int >= 0>, "roots": [<abs dir>, ...], "mask": "beside_frame"|"none",
     "now": <ISO timestamp str or null>}

Result (``<name>.result.json`` beside the request, written atomically: ``.part``
then ``os.replace``)::

    {"protocol", "request_id", "op", "status": "ok"|"refused"|"error",
     "code": <str or null>, "pass": True|False|None, "reason": <str or null>,
     "check": <retina.events.make_check record>,
     "event": <retina.events.make_event, tier 1, checks == [check]>,
     "mask_path": <str or null>}

Rules:

* Only ops in :data:`ALLOWED_OPS` run (owner ruling QC-Q7: the firefly scan is the
  first and only one). Anything else is ``refused`` / ``op_not_allowed``.
* The product must resolve (``realpath``, symlinks and ``..`` followed) inside one
  of the declared read-only roots (I-6), else ``refused`` / ``outside_roots``. The
  check runs before any pixel is read.
* The mask path is never taken from the request: the only policies are
  ``beside_frame`` (owner ruling QC-Q4, :func:`mask_path_for`) and ``none``.
* ``pass`` is the check's verdict; ``reason`` is set exactly when ``pass`` is None.
* Any exception becomes an ``error`` result with ``pass`` None and the reason; a
  request that cannot be parsed still gets a result, because the result path comes
  from argv, not from the request. Exit status 0 means a result was written.

Imports nothing from ``synapse`` and never ``hou``. The frame reader and the scan
(which need OpenImageIO, numpy and cv2) are imported inside the operation, so a
refusal never depends on them.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from retina.events import make_check, make_event  # noqa: E402 - after the sys.path line

#: Request/result protocol tag; the host adapter carries its own copy.
PROTOCOL = "synapse.retina.worker/1"

#: The only operations this worker runs (owner ruling QC-Q7).
ALLOWED_OPS = frozenset({"fireflies"})

#: Mask policies a request may name. The path itself is always computed here.
MASK_POLICIES = frozenset({"beside_frame", "none"})

#: Name of the check each op produces (``retina.firefly_scan.firefly_check``'s).
CHECK_NAMES = {"fireflies": "firefly_scan"}

#: A request is a few hundred bytes; anything past this is not a request.
MAX_REQUEST_BYTES = 64 * 1024

_MAX_ID_LEN = 128


class Refusal(Exception):
    """The request is refused; ``code`` is machine-readable, the message says why."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code


def result_path_for(request_path: str) -> str:
    """``<dir>/<name>.json`` -> ``<dir>/<name>.result.json`` (beside the request)."""
    # PLAN_GAP: PLAN.md item 1 says the result JSON goes beside the frame; the
    # builder brief says beside the request. Implemented as: beside the request
    # (the host's per-call temp directory), so the read-only root only ever gains
    # the mask.
    base = request_path[: -len(".json")] if request_path.lower().endswith(".json") else request_path
    return base + ".result.json"


def mask_path_for(product: str, subimage: int) -> str:
    """The firefly mask beside the frame: ``beauty.0001.exr`` -> ``beauty.0001.fireflies.png``
    (``beauty.0001.sub2.fireflies.png`` for subimage 2)."""
    # PLAN_GAP: QC-Q4 rules the mask goes beside the frame, not its name.
    # Implemented as: the frame's stem + ".fireflies.png" (".subN" before it for a
    # non-zero subimage), written for clean frames too (an all-zero mask).
    directory, name = os.path.split(product)
    stem = os.path.splitext(name)[0]
    if subimage:
        stem = f"{stem}.sub{int(subimage)}"
    return os.path.join(directory, f"{stem}.fireflies.png")


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _inside(path: str, root: str) -> bool:
    """True when ``path`` is ``root`` or below it (both already normalised)."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def _read_request(request_path: str) -> Dict[str, Any]:
    try:
        size = os.path.getsize(request_path)
    except OSError as exc:
        raise Refusal("bad_request", f"cannot read the request file: {type(exc).__name__}: {exc}") from None
    if size > MAX_REQUEST_BYTES:
        raise Refusal("bad_request", f"request is {size} bytes, over the {MAX_REQUEST_BYTES} byte cap")
    try:
        with open(request_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refusal("bad_request", f"request is not readable JSON: {type(exc).__name__}: {exc}") from None
    if not isinstance(data, dict):
        raise Refusal("bad_request", f"request is a JSON {type(data).__name__}, not an object")
    return data


def _validate(req: Dict[str, Any]) -> Tuple[str, int, str, Optional[str]]:
    """Check the request; return ``(product_realpath, subimage, mask_policy, now)``.

    Order matters: the op is judged before any path, and the roots before the
    product is touched.
    """
    if req.get("protocol") != PROTOCOL:
        raise Refusal("bad_request", f"protocol {req.get('protocol')!r} is not {PROTOCOL!r}")
    op = req.get("op")
    if not isinstance(op, str) or op not in ALLOWED_OPS:
        raise Refusal("op_not_allowed", f"op {op!r} is not in the allowlist {sorted(ALLOWED_OPS)}")

    roots = req.get("roots")
    if not isinstance(roots, list) or not roots:
        raise Refusal("bad_request", "no read-only roots declared; the worker reads nothing without one")
    norm_roots: List[str] = []
    for root in roots:
        if not isinstance(root, str) or not root or not os.path.isabs(root):
            raise Refusal("bad_request", f"root {root!r} is not an absolute path")
        if not os.path.isdir(root):
            raise Refusal("bad_request", f"root {root!r} is not an existing directory")
        norm_roots.append(_norm(root))

    product = req.get("product")
    if not isinstance(product, str) or not product or not os.path.isabs(product):
        raise Refusal("bad_request", f"product {product!r} is not an absolute path")
    real = os.path.realpath(product)
    if not any(_inside(os.path.normcase(real), r) for r in norm_roots):
        raise Refusal("outside_roots",
                      f"product {product!r} resolves to {real!r}, outside the declared read-only roots")

    subimage = req.get("subimage", 0)
    if isinstance(subimage, bool) or not isinstance(subimage, int) or subimage < 0:
        raise Refusal("bad_request", f"subimage {subimage!r} is not a whole number >= 0")

    mask = req.get("mask", "beside_frame")
    if mask not in MASK_POLICIES:
        raise Refusal("bad_mask_policy",
                      f"mask policy {mask!r} is not one of {sorted(MASK_POLICIES)}; "
                      f"the mask path is never taken from a request")

    now = req.get("now")
    if now is not None and not isinstance(now, str):
        raise Refusal("bad_request", f"now {now!r} is not a string")
    return real, subimage, mask, now


def _run_fireflies(product: str, subimage: int, mask: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """frame_reader -> fireflies -> firefly_check; return ``(check, mask_path)``."""
    from retina.firefly_scan import firefly_check, fireflies
    from retina.frame_reader import read_frame

    rgb, info = read_frame(product, subimage=subimage)
    mask_path = mask_path_for(product, subimage) if mask == "beside_frame" else None
    result = fireflies(rgb, origin=info["origin"], reader=info["reader"], mask_path=mask_path)
    return firefly_check(result), result.get("mask_path")


def _error_code(exc: BaseException) -> str:
    try:
        from retina.t1 import T1Unavailable
    except Exception:  # noqa: BLE001 - classification only
        T1Unavailable = ()  # type: ignore[assignment]
    if T1Unavailable and isinstance(exc, T1Unavailable):
        return "unavailable"
    if isinstance(exc, FileNotFoundError):
        return "not_found"
    if isinstance(exc, ValueError):
        return "unreadable"
    return "exception"


def _envelope(req: Dict[str, Any], status: str, code: Optional[str], check: Dict[str, Any],
              mask_path: Optional[str], now: Optional[str]) -> Dict[str, Any]:
    passed = check["pass"]
    product = req.get("product")
    event = make_event(
        tier=1,
        claim=f"firefly scan of {product}" if isinstance(product, str) else "firefly scan",
        checks=[check],
        proof=mask_path,
        now=now if isinstance(now, str) else None,  # type: ignore[arg-type]
    )
    return {
        "protocol": PROTOCOL,
        "request_id": req.get("request_id") if isinstance(req.get("request_id"), str) else None,
        "op": req.get("op") if isinstance(req.get("op"), str) else None,
        "status": status,
        "code": code,
        "pass": passed,
        "reason": None if passed is not None else str(check["detail"]),
        "check": check,
        "event": event,
        "mask_path": mask_path,
    }


def handle(request_path: str) -> Dict[str, Any]:
    """Process one request file; always return a result dict, never raise."""
    req: Dict[str, Any] = {}
    now: Optional[str] = None
    try:
        req = _read_request(request_path)
        rid = req.get("request_id")
        if not isinstance(rid, str) or not rid or len(rid) > _MAX_ID_LEN:
            raise Refusal("bad_request", f"request_id {rid!r} is not a non-empty string")
        product, subimage, mask, now = _validate(req)
        check, mask_path = _run_fireflies(product, subimage, mask)
        return _envelope(req, "ok", None, check, mask_path, now)
    except Refusal as exc:
        status, code, why = "refused", exc.code, f"refused: {exc}"
    except Exception as exc:  # noqa: BLE001 - every failure becomes a result
        status, code, why = "error", _error_code(exc), f"{type(exc).__name__}: {exc}"
    name = CHECK_NAMES.get(req.get("op"), "worker") if isinstance(req.get("op"), str) else "worker"
    check = make_check(name, None, f"inconclusive: {why}")
    return _envelope(req, status, code, check, None, now)


def write_result(result: Dict[str, Any], result_path: str) -> None:
    """Write ``result`` atomically: ``<path>.part`` then ``os.replace``."""
    part = result_path + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, sort_keys=True, allow_nan=False)
    os.replace(part, result_path)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. 0: a result was written. 2: bad command line. 3: result not written."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        sys.stderr.write("usage: python -m retina.worker_entrypoint <request.json>\n")
        return 2
    request_path = os.path.abspath(args[0])
    result = handle(request_path)
    result_path = result_path_for(request_path)
    try:
        try:
            write_result(result, result_path)
        except ValueError as exc:
            # A non-finite float in the scan's numbers (allow_nan=False): report it
            # as an error result rather than leave the host with no result at all.
            check = make_check(result["check"]["name"], None,
                               f"inconclusive: result not serialisable: {exc}")
            write_result({**result, "status": "error", "code": "exception", "pass": None,
                          "reason": check["detail"], "check": check, "mask_path": None,
                          "event": make_event(tier=1, claim=result["event"]["claim"],
                                              checks=[check], proof=None,
                                              now=result["event"]["at"])},
                         result_path)
    except Exception as exc:  # noqa: BLE001 - reported on stderr, no result possible
        sys.stderr.write(f"could not write the result: {type(exc).__name__}: {exc}\n")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
