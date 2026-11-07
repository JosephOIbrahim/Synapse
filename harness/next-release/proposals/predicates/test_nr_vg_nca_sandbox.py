"""Closure predicate for NR-VG-NCA-SANDBOX (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/nca_sandbox/nca_profile.json (frozen tolerances,
committed before evaluation) and harness/vision/nca_sandbox/nca_sandbox_receipt.json
are committed, the receipt pins the profile by sha256, and the receipt records: a
22.0.x Houdini build; the Core and Decode node types; paired Core/Decode model hashes
with one pair id; the declared Decode colour transform (ocio with an output space, or
raw); at least two fixed-seed decodes plus one after a session restart, each within
the profile's replay tolerance; an extended rollout at or above the profile's minimum
iterations that stayed stable; stop and restart results with incomplete products
marked unusable; a scene path under one of the profile's sandbox roots that was never
saved to production; the executing provider as observed (not "automatic"); and Joe's
authorization.

Red today: the receipt is not committed (marker below).

Reads committed files only. It never launches Houdini or hython, cooks a node,
loads a model, trains, touches a GPU or uses the network - even if a receipt exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MARKER = ("NR-VG-NCA-SANDBOX RED: no committed sandbox receipt "
          "harness/vision/nca_sandbox/nca_sandbox_receipt.json")
RECEIPT = "harness/vision/nca_sandbox/nca_sandbox_receipt.json"
PROFILE = "harness/vision/nca_sandbox/nca_profile.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _receipt() -> dict:
    if not _committed(RECEIPT):
        raise AssertionError(MARKER)
    return json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))


def _profile(r: dict) -> dict:
    assert _committed(PROFILE), f"frozen profile {PROFILE} is not committed"
    raw = (ROOT / PROFILE).read_bytes()
    assert r.get("profile_sha256") == hashlib.sha256(raw).hexdigest(), "receipt does not pin the frozen profile"
    return json.loads(raw.decode("utf-8"))


def test_sandbox_receipt_is_committed():
    assert isinstance(_receipt(), dict)


def test_build_nodes_and_model_pair():
    r = _receipt()
    assert re.match(r"^22\.0\.\d+$", str(r.get("houdini_build", ""))), "no 22.0.x build recorded"
    assert {"neural_cellularautomatacore", "neural_cellularautomatadecode"} <= set(r.get("node_types", [])), \
        "Core and Decode node types not recorded"
    m = r.get("models", {})
    assert HEX64.match(str(m.get("core_sha256", ""))) and HEX64.match(str(m.get("decode_sha256", ""))), \
        "Core/Decode model hashes missing"
    assert m.get("core_pair_id") and m.get("core_pair_id") == m.get("decode_pair_id"), "Core and Decode are not one pair"


def test_decode_colour_transform_is_declared():
    d = _receipt().get("decode", {})
    assert d.get("colortransform") in ("ocio", "raw"), "Decode colour transform not declared"
    if d.get("colortransform") == "ocio":
        assert d.get("tospace"), "OCIO output space not declared"


def test_fixed_seed_replay_within_frozen_tolerance():
    r = _receipt()
    tol = float(_profile(r)["replay_tolerance"])
    reps = r.get("replays", [])
    assert len(reps) >= 3 and len({x.get("seed") for x in reps}) == 1, "need three decodes of one fixed seed"
    assert any(x.get("after_restart") is True for x in reps), "no replay after a session restart"
    assert all(float(x.get("max_abs_diff", 1e30)) <= tol for x in reps), "replay outside the frozen tolerance"


def test_extended_rollout_and_stop_restart():
    r = _receipt()
    p = _profile(r)
    ext = r.get("extended_rollout", {})
    assert int(ext.get("iterations", 0)) >= int(p["extended_rollout_min_iterations"]) and ext.get("stable") is True, \
        "extended rollout too short or unstable"
    s = r.get("stop_restart", {})
    assert s.get("stopped") is True and s.get("restarted") is True and s.get("incomplete_marked_unusable") is True, \
        "stop/restart results incomplete"


def test_sandbox_only_provider_and_authorization():
    r = _receipt()
    roots = [str(x).replace("\\", "/").lower() for x in _profile(r).get("sandbox_roots", [])]
    scene = str(r.get("scene_path", "")).replace("\\", "/").lower()
    assert roots and any(scene.startswith(x) for x in roots), "scene path is not under a declared sandbox root"
    assert r.get("saved_to_production") is False, "sandbox scene touched production"
    assert str(r.get("provider", "")).lower() not in ("", "automatic", "unknown"), "executing provider not observed"
    a = r.get("authorization", {})
    assert a.get("by") == "Joe" and a.get("date"), "no per-act authorization by Joe"
