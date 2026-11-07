"""Closure predicate for NR-VG-GROW-CONTROLS (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/grow_controls/control_package_contract.json is
committed and: lists every control-package field the Neural Growth blueprint section 7
requires (producer, operation, backend, confidence, dimensions, dtype, ranges,
channel_semantics, coordinates, field_hashes); declares the coordinate contract
(origin, uv_domain, tile, wrap, channel_order, scalar_range, resampling); maps rotation
in turns, the scale clamp as [0.2, 1.0] and both update-mask types; pins the committed
NCA sandbox receipt by sha256; cites an amendment for reference-driven control
generation whose Status line reads ACCEPTED; lists malformed-input rejection cases;
and retina/control_package.py and tests/test_retina_control_package.py are committed.

Red today: the contract is not committed (marker below).

Reads committed files only. It never imports retina, cv2 or numpy, touches a GPU,
launches Houdini or uses the network.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MARKER = ("NR-VG-GROW-CONTROLS RED: no committed control-package contract "
          "harness/vision/grow_controls/control_package_contract.json")
CONTRACT = "harness/vision/grow_controls/control_package_contract.json"
SANDBOX = "harness/vision/nca_sandbox/nca_sandbox_receipt.json"
FIELDS = {"producer", "operation", "backend", "confidence", "dimensions", "dtype", "ranges",
          "channel_semantics", "coordinates", "field_hashes"}
COORDS = {"origin", "uv_domain", "tile", "wrap", "channel_order", "scalar_range", "resampling"}


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _contract() -> dict:
    if not _committed(CONTRACT):
        raise AssertionError(MARKER)
    return json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))


def test_contract_is_committed():
    assert isinstance(_contract(), dict)


def test_required_fields_and_coordinates():
    c = _contract()
    assert not FIELDS - set(c.get("required_fields", [])), f"missing fields: {sorted(FIELDS - set(c.get('required_fields', [])))}"
    assert not COORDS - set(c.get("coordinates", {})), f"missing coordinate conventions: {sorted(COORDS - set(c.get('coordinates', {})))}"


def test_native_mapping_matches_the_sandbox():
    c = _contract()
    n = c.get("native_mapping", {})
    assert n.get("rotation_units") == "turns", "rotation must map to turns"
    assert n.get("scale_clamp") == [0.2, 1.0], "scale clamp must be [0.2, 1.0]"
    assert set(n.get("update_mask_types", [])) == {"amplitude_weighted", "probabilistic"}, "update-mask semantics missing"
    assert _committed(SANDBOX), "the NCA sandbox receipt is not committed"
    assert c.get("nca_sandbox_receipt_sha256") == hashlib.sha256((ROOT / SANDBOX).read_bytes()).hexdigest(), \
        "contract does not pin the committed sandbox receipt"


def test_control_generation_amendment_is_ratified():
    ref = _contract().get("amendment_ref")
    assert ref and _committed(ref), "no committed amendment for reference-driven control generation"
    status = next((ln for ln in (ROOT / ref).read_text(encoding="utf-8").splitlines() if ln.startswith("**Status:**")), "")
    assert status.startswith("**Status:** ACCEPTED"), "the control-generation amendment is not ratified"


def test_rejection_cases_and_files():
    c = _contract()
    assert c.get("malformed_input_cases"), "no malformed-input rejection cases"
    for rel in ("retina/control_package.py", "tests/test_retina_control_package.py"):
        assert _committed(rel), f"{rel} is not committed"
