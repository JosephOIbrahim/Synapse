"""Tests for the Solaris compose tools (solaris_compose_tools.py).

These tools are hou-orchestration -- the meaningful gate is the LIVE [REAL]
verification on H21.0.671 (recorded per-mile in the commit history). This is a
thin CI net: import + the department-order invariant + the no-hou guard.

A minimal hou stub is installed in sys.modules so the package import chain
doesn't ImportError under CI (no Houdini). Monkeypatch rebinds auto-restore.
"""

import sys
import types

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = types.ModuleType("hou")

from synapse.server import solaris_compose_tools as t  # noqa: E402
from synapse.server import solaris_compose as sc  # noqa: E402


def test_department_order_render_strongest_first():
    # Conceptual strongest-first; the sublayer LOP is filled weakest-first
    # (verified: sublayer LOP composes filepathN as strongest).
    assert t.DEPARTMENT_LAYERS_STRONGEST_FIRST == [
        "render", "fx", "lighting", "animation", "layout",
    ]


def test_build_requires_hou(monkeypatch):
    monkeypatch.setattr(t, "HOU_AVAILABLE", False, raising=False)
    with pytest.raises(sc.ComposeError):
        t.build_karma_xpu_shot(object(), shot="x")


def test_set_helper_skips_locked(monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setattr(t, "HOU_AVAILABLE", True, raising=False)
    node = MagicMock()
    locked = MagicMock()
    locked.isLocked.return_value = True
    node.parm.return_value = locked
    assert t._set(node, "resolution2", 1920) is False  # locked -> skipped
    locked.set.assert_not_called()


def test_set_helper_missing_parm():
    from unittest.mock import MagicMock
    node = MagicMock()
    node.parm.return_value = None
    assert t._set(node, "no_such_parm", 1) is False
