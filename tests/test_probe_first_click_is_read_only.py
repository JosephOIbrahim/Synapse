"""The first-click probe must not touch the artist's conversation store.

FAILS IF: probe_first_click._prepare_env() leaves the conversation store pointing at the
place the panel really uses.

WHY THIS TEST EXISTS. The probe's own docstring claimed READ-ONLY, and it was not.
SYNAPSE_PANEL_SETTINGS isolates the panel's SETTINGS only; the conversation store resolves
from the HIP directory, or from a SHARED temp directory when hou is absent
(server/session_store.py:57). So merely constructing SynapsePanel() ran
load_conversation_scoped(), which parks the live conversation with os.replace(target, prev)
at session_store.py:250 -- destroying whatever was already parked there.

Measured on 2026-09-21, seeding a store with a live conversation and an already-parked
previous, then running the probe:

    before repair   live -> []            previous -> the old live; ARTIST-PARKED-OLD gone
    after repair    live -> unchanged     previous -> unchanged

This test pins the repair without needing Qt or hython: it asserts the redirection, which is
the thing that makes the probe safe.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "python", "synapse", "panel", "scripts", "probe_first_click.py")


def _load_probe():
    spec = importlib.util.spec_from_file_location("_probe_first_click_under_test", PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not os.path.isfile(PROBE), reason="probe not present on this tree")
def test_prepare_env_pins_the_conversation_store_off_the_real_one(monkeypatch):
    if os.path.join(ROOT, "python") not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, "python"))
    from synapse.server import session_store

    real = session_store._resolve_store_dir()
    monkeypatch.setattr(session_store, "_resolve_store_dir",
                        session_store._resolve_store_dir, raising=True)

    mod = _load_probe()
    mod._prepare_env()

    now = session_store._resolve_store_dir()
    assert now != real, (
        "the probe left the conversation store on the real path; constructing the panel "
        "will park and destroy the artist's previous session")
    assert "synapse_probe_store_" in now
    assert os.path.isdir(now)

    # and the two paths the parking code actually uses both follow the redirect
    assert now == os.path.dirname(session_store.conversation_path())
    assert now == os.path.dirname(session_store.previous_path())
