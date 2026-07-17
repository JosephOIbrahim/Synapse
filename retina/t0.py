"""T0 — file truth. "Did anything render, correctly, on disk?"

The cheapest rung of the tier ladder (blueprint §4): microseconds, no pixels, no
models, no tokens. It compares the host-exported **manifest** against what is
actually on disk and returns a **versioned perception event** (blueprint §3
shape). It kills the BL-007 blind-spot class — EXR not written, empty file,
missing ``.done`` sentinel, wrong resolution, missing AOVs.

What T0 checks, per the manifest's declared products:

1. **products_exist** — every declared product file is on disk.
2. **products_nonzero** — every existing product has a non-zero size.
3. **done_sentinels** — the ``<product>.done`` sentinel is present (pixels
   landed; written by the husk-level post-frame hook — see host side).
4. **product_count** — the number of products declared equals the number found.
5. **resolution** — each readable product's EXR data-window resolution equals the
   manifest's declared resolution.
6. **aovs** — each readable product carries the manifest's declared AOVs
   (multi-part aware: husk writes beauty + AOV as separate sub-images).
7. **fingerprint_receipt** — the manifest fingerprint is stamped inside the EXR
   header (``synapse_retina_fingerprint``), the free in-artifact receipt.

Honesty (blueprint §7, the Copernicus preflight-honesty rule verbatim): a check
that *cannot* run — the manifest never declared a resolution, the product isn't
an EXR this header reader understands, the AOV list is empty — returns
``pass=None`` (**inconclusive**), NEVER a silent ``pass``. The event's overall
``verdict`` is ``fail`` if any check failed, else ``inconclusive`` if any check
was inconclusive, else ``pass``.

T0 imports zero ``hou`` and (at M1) zero ``cv2`` — it reads bytes, not pixels.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import EVENT_VERSION, PERCEPTION_CHANNEL
from .exr_header import ExrHeader, ExrHeaderError, read_exr_header

TIER = 0

# A check verdict: pass True/False, or None for honest "could not run".
CheckVerdict = Optional[bool]

# Signature of the EXR reader (injectable for tests / future OIIO swap).
ExrReader = Callable[[str], ExrHeader]


def _check(name: str, passed: CheckVerdict, detail: str, **extra: Any) -> Dict[str, Any]:
    d: Dict[str, Any] = {"name": name, "pass": passed, "detail": detail}
    d.update(extra)
    return d


def _declared_products(manifest: Dict[str, Any]) -> List[str]:
    """Product paths from the manifest, tolerant of both the string-list and the
    ``[{"path": ...}]`` object forms the host writer may emit."""
    out: List[str] = []
    for entry in manifest.get("products") or []:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict) and entry.get("path"):
            out.append(str(entry["path"]))
    return out


def _done_path(product: str) -> str:
    return product + ".done"


def check_manifest_against_disk(
    manifest: Dict[str, Any],
    *,
    now: str,
    exr_reader: ExrReader = read_exr_header,
) -> Dict[str, Any]:
    """Run T0 against a manifest and the current filesystem.

    Args:
        manifest: a ``retina_manifest/v1`` dict (host-exported, or synthetic in
            tests). Only ``products``, ``resolution``, ``aovs``, ``fingerprint``
            and ``claim`` are consulted.
        now: caller-supplied ISO timestamp (this function never reads the clock,
            so the same inputs yield a byte-identical event — the
            ``perception_baseline`` purity convention).
        exr_reader: injectable header reader; defaults to the pure-python one.

    Returns:
        A versioned perception event (blueprint §3 shape) with ``tier=0``.
    """
    products = _declared_products(manifest)
    checks: List[Dict[str, Any]] = []

    # 0) A manifest with no declared products cannot be verified — inconclusive,
    # never a vacuous pass.
    if not products:
        checks.append(
            _check(
                "products_declared",
                None,
                "manifest declares no products — nothing to verify",
            )
        )
        return _event(manifest, checks, now)

    existing = [p for p in products if os.path.isfile(p)]
    missing = [p for p in products if p not in existing]

    # 1) products_exist
    checks.append(
        _check(
            "products_exist",
            not missing,
            "all declared products present" if not missing
            else f"{len(missing)} product(s) missing: {missing[:4]}",
            missing=missing,
            found=len(existing),
            declared=len(products),
        )
    )

    # 2) products_nonzero — only over the products that exist.
    if existing:
        empty = [p for p in existing if os.path.getsize(p) == 0]
        checks.append(
            _check(
                "products_nonzero",
                not empty,
                "all present products are non-empty" if not empty
                else f"{len(empty)} product(s) are 0 bytes: {empty[:4]}",
                empty=empty,
            )
        )
    else:
        checks.append(
            _check("products_nonzero", None, "no products on disk to size-check")
        )

    # 3) done_sentinels — the pixels-landed signal.
    missing_done = [p for p in products if not os.path.isfile(_done_path(p))]
    checks.append(
        _check(
            "done_sentinels",
            not missing_done,
            "all .done sentinels present" if not missing_done
            else f"{len(missing_done)} product(s) missing .done: {missing_done[:4]}",
            missing_done=missing_done,
        )
    )

    # 4) product_count — declared vs found on disk.
    checks.append(
        _check(
            "product_count",
            len(existing) == len(products),
            f"{len(existing)}/{len(products)} declared products found on disk",
            found=len(existing),
            declared=len(products),
        )
    )

    # 5/6/7) header-derived checks need a readable EXR header per product.
    declared_res = manifest.get("resolution")
    declared_aovs = [str(a) for a in (manifest.get("aovs") or [])]
    declared_fp = manifest.get("fingerprint")

    res_results: List[str] = []
    res_pass: CheckVerdict = None if not declared_res else True
    aov_missing: List[str] = []
    aov_pass: CheckVerdict = None if not declared_aovs else True
    fp_pass: CheckVerdict = None if not declared_fp else True
    fp_detail_bits: List[str] = []
    unreadable: List[str] = []

    for product in existing:
        try:
            header = exr_reader(product)
        except (ExrHeaderError, OSError) as exc:
            unreadable.append(f"{Path(product).name}: {type(exc).__name__}")
            continue

        # resolution — compare against the data window of the (first) part.
        if declared_res and len(declared_res) == 2:
            got = None
            for part in header.parts:
                if part.resolution:
                    got = part.resolution
                    break
            if got is None:
                # Readable header, but no data window => the resolution cannot be
                # read for this product. A check that CANNOT run must be
                # inconclusive, never a silent pass (blueprint §7 — the RETINA
                # thesis). Never bump a hard fail (False) back up to None: fail
                # dominates inconclusive in the roll-up.
                res_results.append(f"{Path(product).name}: no data window")
                if res_pass is not False:
                    res_pass = None
            elif [int(got[0]), int(got[1])] == [int(declared_res[0]), int(declared_res[1])]:
                res_results.append(f"{Path(product).name}: {got[0]}x{got[1]} ok")
            else:
                res_pass = False
                res_results.append(
                    f"{Path(product).name}: {got[0]}x{got[1]} != "
                    f"declared {declared_res[0]}x{declared_res[1]}"
                )

        # aovs — the union of channel names (multi-part aware) must contain each
        # declared AOV, matched leniently (declared "primid" satisfies channel
        # "primid.id" or part "primid").
        if declared_aovs:
            present = set(header.all_channel_names())
            present |= {p.name for p in header.parts if p.name}
            for part in header.parts:
                for ch in part.channels:
                    present.add(ch.name)
            for aov in declared_aovs:
                if not _aov_present(aov, present):
                    aov_missing.append(f"{Path(product).name}:{aov}")

        # fingerprint receipt — inside the EXR header.
        if declared_fp:
            got_fp = header.string_attr("synapse_retina_fingerprint")
            if got_fp is None:
                fp_pass = False  # declared a fingerprint but the artifact lacks it
                fp_detail_bits.append(f"{Path(product).name}: no receipt stamped")
            elif got_fp != str(declared_fp):
                fp_pass = False
                fp_detail_bits.append(
                    f"{Path(product).name}: receipt {got_fp!r} != {declared_fp!r}"
                )
            else:
                fp_detail_bits.append(f"{Path(product).name}: receipt ok")

    # If no product was readable, header-derived checks are inconclusive, never
    # pass — even when a resolution/AOV list was declared.
    if declared_res:
        if not res_results and unreadable:
            res_pass = None
        checks.append(
            _check(
                "resolution",
                res_pass,
                "; ".join(res_results) or "no readable product to check resolution",
                unreadable=unreadable,
            )
        )
    else:
        checks.append(
            _check("resolution", None, "manifest declared no resolution")
        )

    if declared_aovs:
        if not existing or (unreadable and len(unreadable) == len(existing)):
            aov_pass = None
        elif aov_missing:
            aov_pass = False
        checks.append(
            _check(
                "aovs",
                aov_pass,
                "all declared AOVs present" if aov_pass
                else (f"missing AOVs: {aov_missing[:6]}" if aov_pass is False
                      else "no readable product to check AOVs"),
                declared=declared_aovs,
                missing=aov_missing,
            )
        )
    else:
        checks.append(_check("aovs", None, "manifest declared no AOVs"))

    if declared_fp:
        if not fp_detail_bits and unreadable:
            fp_pass = None
        checks.append(
            _check(
                "fingerprint_receipt",
                fp_pass,
                "; ".join(fp_detail_bits) or "no readable product to check receipt",
            )
        )
    else:
        checks.append(
            _check("fingerprint_receipt", None, "manifest carried no fingerprint")
        )

    return _event(manifest, checks, now)


def _aov_present(aov: str, present: set) -> bool:
    """Lenient AOV membership: declared ``primid`` is satisfied by any of
    ``primid``, ``primid.id``, ``C.primid`` etc. (husk names AOVs
    ``part.channel``)."""
    if aov in present:
        return True
    for name in present:
        if name == aov or name.endswith("." + aov) or name.startswith(aov + "."):
            return True
    return False


def _roll_up(checks: List[Dict[str, Any]]) -> str:
    """fail > inconclusive > pass — a single red fails the frame; an inconclusive
    never masquerades as green."""
    verdicts = [c["pass"] for c in checks]
    if any(v is False for v in verdicts):
        return "fail"
    if any(v is None for v in verdicts):
        return "inconclusive"
    return "pass"


def _event(manifest: Dict[str, Any], checks: List[Dict[str, Any]], now: str) -> Dict[str, Any]:
    products = _declared_products(manifest)
    return {
        "ch": PERCEPTION_CHANNEL,
        "v": EVENT_VERSION,
        "tier": TIER,
        "claim": manifest.get("claim", "render:file_truth"),
        "checks": checks,
        "verdict": _roll_up(checks),
        # T0's proof is the receipt trail itself: the manifest + the first
        # product on disk. Higher tiers (T1+) attach rendered proof images.
        "proof": manifest.get("manifest_path") or (products[0] if products else None),
        "at": now,
    }


def emit_verdict(event: Dict[str, Any], jsonl_path: str | Path) -> None:
    """Append one verdict event as a line to the sidecar JSONL (blueprint §7:
    sidecar JSONL persistence until the customData RFC lands — NO USD writes).

    Append-only by construction, so a partial line is the worst failure mode; we
    write the whole JSON in one ``write`` call under a single open handle to keep
    each record atomic at the line level.
    """
    p = Path(jsonl_path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line)


def verify_and_emit(
    manifest: Dict[str, Any],
    *,
    now: str,
    jsonl_path: str | Path,
    exr_reader: ExrReader = read_exr_header,
) -> Dict[str, Any]:
    """Convenience: run T0 and persist the event in one call. Returns the event."""
    event = check_manifest_against_disk(manifest, now=now, exr_reader=exr_reader)
    emit_verdict(event, jsonl_path)
    return event
