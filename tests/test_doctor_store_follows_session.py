"""Doctor and the write-plane probe look at the live store's folder.

Since BP12 item 1 (2026-09-29) an unsaved scene's memory store lives in its
launch session's folder, ``$HOUDINI_TEMP_DIR/untitled/sessions/<id>/.synapse``
(``host/memory_lifecycle.ensure_unsaved_base``). The doctor's resolver kept
answering the shared root, ``$HOUDINI_TEMP_DIR/untitled``, where BP12 left the
old shared store in place. On the seat (2026-11-09) that sent three readers to
the wrong folder while the store itself was healthy:

* ``moneta_substrate`` reported "no stage at .../untitled/.synapse/.moneta/
  cortex_root.usda" while the store's own USD target was
  ``.../untitled/sessions/8f837467.../.synapse/.moneta/usd``;
* ``memory_key_fingerprint`` reported NOT CHECKED (no_sidecar);
* the write-plane probe tested ``untitled/.synapse`` and said ok, for a folder
  nothing writes to.

The fixture mirrors that seat: the old shared store (no sidecar, an empty
``.moneta``), an earlier launch's session folder, and this launch's session
folder holding the sidecar and a cortex stage.

Two seat states are covered. WARM: a store is already live in this process
(the normal case once memory has been used) and the doctor must read its
folder. COLD: no store is live yet, so the doctor asks the lifecycle for this
launch's EXISTING session, and must never create one.
"""
from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

import pytest

from synapse.core.crypto import key_fingerprint
from synapse.memory import moneta_runtime as mr
from synapse.memory import store as store_mod
from synapse.server import doctor
from synapse.server import write_plane as wp

lifecycle = importlib.import_module("synapse.host.memory_lifecycle")

KEY = b"store-path-lane-test-key-0123456"
SESSION_ID = "8f837467aa0b4c1d9e2f3a4b5c6d7e8f"
EARLIER_ID = "0123456789abcdef0123456789abcdef"


def _fake_hou(hip: Path, houdini_temp: Path, is_new: bool):
    """The three reads the resolvers make, nothing else."""
    def expand(value, *_a, **_k):
        return str(houdini_temp) if value == "$HOUDINI_TEMP_DIR" else value
    return types.SimpleNamespace(
        hipFile=types.SimpleNamespace(path=lambda: str(hip), isNewFile=lambda: is_new),
        text=types.SimpleNamespace(expandString=expand),
    )


def _install_hou(monkeypatch, fake):
    # The doctor does a local ``import hou``; the store and the lifecycle read
    # store.hou. In Houdini both are the one real module.
    monkeypatch.setitem(sys.modules, "hou", fake)
    monkeypatch.setattr(store_mod, "hou", fake, raising=False)
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", True)


def _tree(root: Path):
    return sorted(str(p) for p in root.rglob("*"))


@pytest.fixture
def seat(tmp_path, monkeypatch):
    """The 2026-11-09 seat layout, with an unsaved scene open."""
    houdini_temp = tmp_path / "houdini_temp"
    shared = houdini_temp / "untitled"

    # The old shared store BP12 item 1 left in place: no sidecar, a .moneta
    # folder with no cortex in it.
    legacy = shared / ".synapse"
    (legacy / ".moneta").mkdir(parents=True)
    (legacy / "memory.jsonl").write_text("", encoding="utf-8")

    # An earlier launch's session: a real store, but not this launch's.
    earlier = shared / "sessions" / EARLIER_ID / ".synapse"
    (earlier / ".moneta").mkdir(parents=True)
    (earlier / "key.fingerprint").write_text(key_fingerprint(KEY), encoding="utf-8")

    # This launch's session folder: the live store.
    session = shared / "sessions" / SESSION_ID
    store_dir = session / ".synapse"
    (store_dir / ".moneta" / "usd").mkdir(parents=True)
    (store_dir / ".moneta" / "cortex_root.usda").write_text("#usda 1.0\n", encoding="utf-8")
    (store_dir / "key.fingerprint").write_text(key_fingerprint(KEY), encoding="utf-8")

    home = tmp_path / "home"
    (home / ".synapse").mkdir(parents=True)
    (home / ".synapse" / "encryption.key").write_bytes(KEY)

    launch = tmp_path / "bin"
    launch.mkdir()

    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("SYNAPSE_MONETA_USD_ROOT", raising=False)
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(houdini_temp))
    _install_hou(monkeypatch, _fake_hou(launch / "untitled.hip", houdini_temp, is_new=True))
    monkeypatch.setattr(store_mod, "_global_synapse", None)
    monkeypatch.setattr(lifecycle, "_unsaved_base", None)
    monkeypatch.setattr(store_mod, "_BACKEND_FALLBACK", None)

    return types.SimpleNamespace(
        tmp=tmp_path, houdini_temp=houdini_temp, shared=shared, legacy=legacy,
        earlier=earlier, session=session, store_dir=store_dir, home=home)


def _bind(monkeypatch, seat, state):
    """WARM: a store is live in this process. COLD: none is, but this launch's
    session exists in the lifecycle."""
    if state == "warm":
        monkeypatch.setattr(store_mod, "_global_synapse",
                            types.SimpleNamespace(storage_dir=seat.store_dir, store=None))
    else:
        monkeypatch.setattr(lifecycle, "_unsaved_base", seat.session)


def _capture_usd_root(monkeypatch):
    """Record the stage the substrate check would open, through the real
    usd_root resolution, without importing Moneta or pxr."""
    seen = {}

    def provenance(usd_root=None):
        seen["hint"] = usd_root
        seen["stage"] = mr._resolve_usd_root(usd_root)[0]
        return {"available": True, "version": "test", "file": "test",
                "schema_registered": True, "schema_registered_reason": "test",
                "schema_in_use": None, "schema_in_use_reason": "test",
                "usd_root_inspected": seen["stage"]}

    monkeypatch.setattr(mr, "moneta_provenance", provenance)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    return seen


# --------------------------------------------------------------------------
# Unsaved scene: the three readers find the session folder
# --------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["warm", "cold"])
def test_key_fingerprint_reads_the_session_sidecar(seat, monkeypatch, state):
    _bind(monkeypatch, seat, state)
    res = doctor.check_memory_key_fingerprint(home=seat.home)
    assert res["storage_dir"] == str(seat.store_dir), res
    assert res["reason"] != "no_sidecar", res
    assert res["status"] == "match", res


@pytest.mark.parametrize("state", ["warm", "cold"])
def test_substrate_check_opens_the_session_stage(seat, monkeypatch, state):
    _bind(monkeypatch, seat, state)
    seen = _capture_usd_root(monkeypatch)
    check = doctor._check_moneta_substrate()
    assert seen["hint"] == str(seat.store_dir / ".moneta"), seen
    stage = Path(seen["stage"])
    assert stage == seat.store_dir / ".moneta" / "cortex_root.usda", seen
    assert stage.is_relative_to(seat.session), seen
    assert stage.exists()
    assert check["result"]["usd_root_inspected"] == seen["stage"], check


@pytest.mark.parametrize("state", ["warm", "cold"])
def test_write_plane_probes_the_session_store(seat, monkeypatch, state):
    _bind(monkeypatch, seat, state)
    assert wp.resolve_memory_target_dir() == seat.store_dir


# --------------------------------------------------------------------------
# Cold doctor, no session for this launch yet: report nothing, create nothing
# --------------------------------------------------------------------------

@pytest.mark.parametrize("leftover", ["none", "other_temp_root"])
def test_cold_doctor_reports_no_store_and_creates_no_session(seat, monkeypatch, leftover):
    """No store is live and this launch has no session yet. The shared root's
    old store and the earlier launch's session are NOT this launch's store, so
    the doctor reports no store dir; it must not mint a session id or create a
    folder to get an answer. A session left over from another temp root is not
    this launch's either (ensure_unsaved_base would replace it), and the
    doctor must leave it exactly as it found it."""
    stale = seat.tmp / "other_temp" / "untitled" / "sessions" / "old"
    if leftover == "other_temp_root":
        monkeypatch.setattr(lifecycle, "_unsaved_base", stale)
    expected_base = stale if leftover == "other_temp_root" else None
    before = _tree(seat.tmp)

    res = doctor.check_memory_key_fingerprint(home=seat.home)
    assert res["status"] == "not_checked", res
    assert res["reason"] == "no_store_dir", res

    seen = _capture_usd_root(monkeypatch)
    doctor._check_moneta_substrate()
    assert seen["hint"] is None, seen

    target = wp.resolve_memory_target_dir()
    assert target.is_relative_to(seat.shared / "sessions"), target
    assert not target.is_relative_to(seat.legacy), target
    assert not target.is_relative_to(seat.earlier.parent), target

    assert lifecycle._unsaved_base == expected_base
    assert _tree(seat.tmp) == before


# --------------------------------------------------------------------------
# Saved scene: unchanged, <hip_dir>/.synapse
# --------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["warm", "cold"])
def test_saved_scene_still_resolves_its_hip_dir(seat, monkeypatch, state):
    show = seat.tmp / "show"
    show.mkdir()
    hip = show / "shot_v001.hip"
    hip.write_text("", encoding="utf-8")
    _install_hou(monkeypatch, _fake_hou(hip, seat.houdini_temp, is_new=False))

    # Before the store exists: the folder it would be created in.
    assert doctor._resolve_store_dir() is None
    assert wp.resolve_memory_target_dir() == show / ".synapse"

    store_dir = show / ".synapse"
    store_dir.mkdir()
    (store_dir / "key.fingerprint").write_text(key_fingerprint(KEY), encoding="utf-8")
    if state == "warm":
        monkeypatch.setattr(store_mod, "_global_synapse",
                            types.SimpleNamespace(storage_dir=store_dir, store=None))

    assert doctor._resolve_store_dir() == store_dir
    assert wp.resolve_memory_target_dir() == store_dir
    res = doctor.check_memory_key_fingerprint(home=seat.home)
    assert res["storage_dir"] == str(store_dir), res
    assert res["status"] == "match", res
    seen = _capture_usd_root(monkeypatch)
    doctor._check_moneta_substrate()
    assert seen["hint"] == str(store_dir / ".moneta"), seen
