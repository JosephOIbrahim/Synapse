"""RETINA ``.done`` sentinel — the husk post-frame hook script.

husk runs THIS file as its ``--postframe-script`` (wired onto the ROP's
``husk_postframe`` param by ``retina_manifest.configure_husk_sentinel``). It fires
~5ms **after** the frame's EXR is written (perception_truth_22.0.368.json item 2),
which is the whole point: it is the pixels-landed signal the out-of-process worker
waits on. The ROP-level post-render script fires at USD-generation time, before
pixels — this rides the husk level instead, deliberately.

Constraints this file lives under (all from catalog item 2):

* It is passed to husk as a **bare, space-free file path** — husk rejects inline
  code (``too many positional options``), so all parameters arrive via the
  environment, not the command line. The manifest location arrives in
  ``SYNAPSE_RETINA_MANIFEST`` (set by the host before render; husk inherits the
  host process env on the background-render path).
* It runs inside **husk's Python** (Houdini's interpreter). It therefore imports
  **zero third-party** modules and — importantly — **zero ``hou``** (it does pure
  filesystem work) and **zero ``cv2``** (RETINA P5). It must never throw in a way
  that aborts husk's frame lifecycle, so every path is guarded.

What it does: read the manifest, and for each declared product drop a
``<product>.done`` sidecar carrying a small JSON receipt. Presence of ``.done``
IS the signal; the JSON body is a convenience for the worker/audit.

Honesty (blueprint §7): if the manifest env var is unset or the manifest is
unreadable, it cannot resolve product paths — it logs to stderr and, when a
fallback path is provided via ``SYNAPSE_RETINA_DONE_FALLBACK``, writes a single
``.done`` marked ``inconclusive`` there rather than silently doing nothing.
"""

from __future__ import annotations

import json
import os
import sys
import time

MANIFEST_ENV_VAR = "SYNAPSE_RETINA_MANIFEST"
FALLBACK_ENV_VAR = "SYNAPSE_RETINA_DONE_FALLBACK"


def _log(msg: str) -> None:
    # stderr only — husk captures it; never raise out of a logging call.
    try:
        sys.stderr.write(f"[retina.sentinel] {msg}\n")
    except Exception:
        pass


def _write_done(product_path: str, payload: dict) -> bool:
    done_path = str(product_path) + ".done"
    try:
        with open(done_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, sort_keys=True)
        return True
    except OSError as exc:
        _log(f"could not write {done_path}: {exc}")
        return False


def _products_from_manifest(manifest: dict) -> list:
    out = []
    for entry in manifest.get("products") or []:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict) and entry.get("path"):
            out.append(str(entry["path"]))
    return out


def run(manifest_env: str = MANIFEST_ENV_VAR) -> int:
    """Drop ``.done`` for every product in the env-pointed manifest.

    Returns the number of sentinels written (0 on any honest failure). Never
    raises — husk's frame lifecycle must not be disturbed by the receipt.
    """
    now = time.time()
    manifest_path = os.environ.get(manifest_env)

    if not manifest_path:
        _log(f"{manifest_env} unset — cannot resolve products")
        return _fallback(now, reason=f"{manifest_env}_unset")

    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        _log(f"manifest unreadable at {manifest_path}: {exc}")
        return _fallback(now, reason="manifest_unreadable")

    products = _products_from_manifest(manifest)
    if not products:
        _log("manifest declares no products")
        return _fallback(now, reason="no_products")

    written = 0
    fingerprint = manifest.get("fingerprint")
    for product in products:
        payload = {
            "status": "rendered",
            "product": product,
            "fingerprint": fingerprint,
            "written_at": now,
            "written_by": "retina_sentinel_postframe",
        }
        if _write_done(product, payload):
            written += 1
    _log(f"wrote {written}/{len(products)} .done sentinel(s)")
    return written


def _fallback(now: float, *, reason: str) -> int:
    """Honest degrade: if a fallback path is provided, drop an inconclusive
    ``.done`` there so the failure is visible on disk, not silent."""
    fallback = os.environ.get(FALLBACK_ENV_VAR)
    if not fallback:
        return 0
    payload = {
        "status": "inconclusive",
        "reason": reason,
        "written_at": now,
        "written_by": "retina_sentinel_postframe",
    }
    return 1 if _write_done(fallback, payload) else 0


if __name__ == "__main__":
    run()
