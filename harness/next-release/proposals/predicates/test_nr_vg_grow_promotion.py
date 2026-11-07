"""Closure predicate for NR-VG-GROW-PROMOTION (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/grow_promotion/promotion_contract.json is
committed and records: an exact target, a reference to the original state, the
approval scope and Joe's approval; a rehearsed recovery with its receipt; that the
promotion writes only through the authored-write receipt path; that nothing was
published without approval; and python/synapse/autonomy/promotion.py and
tests/test_grow_promotion.py are committed.

Red today: the contract is not committed (marker below).

Reads committed files only. It never edits a scene, launches Houdini, touches a
GPU or uses the network.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MARKER = ("NR-VG-GROW-PROMOTION RED: no committed promotion contract "
          "harness/vision/grow_promotion/promotion_contract.json")
CONTRACT = "harness/vision/grow_promotion/promotion_contract.json"


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


def test_exact_target_and_approval():
    c = _contract()
    assert c.get("exact_target") and c.get("original_state_ref") and c.get("approval_scope"), \
        "target, original state or approval scope missing"
    a = c.get("approval", {})
    assert a.get("by") == "Joe" and a.get("date"), "no approval by Joe"


def test_recovery_rehearsed_and_write_path():
    c = _contract()
    rec = c.get("recovery", {})
    assert rec.get("rehearsed") is True and rec.get("receipt_ref"), "recovery not rehearsed"
    assert c.get("writes_via") == "authored-write receipt path", "promotion must write only through the receipt path"
    assert c.get("unapproved_publication") is False, "unapproved publication not excluded"


def test_files_committed():
    for rel in ("python/synapse/autonomy/promotion.py", "tests/test_grow_promotion.py"):
        assert _committed(rel), f"{rel} is not committed"
