"""Mile 3a: synapse_inspect_node defaults to include_geometry=False.

Geometry is the expensive part of an inspect. The handler must NOT fetch it
unless the caller opts in, and must still honor an explicit request.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.server import handlers as handlers_mod  # noqa: E402
from synapse.server import introspection as introspection_mod  # noqa: E402
from synapse.server import main_thread as main_thread_mod  # noqa: E402


def _capture_include_geometry(monkeypatch, payload):
    captured = {}

    def fake_detail(node_path, include_code=True, include_geometry=True,
                    include_expressions=True):
        captured["include_geometry"] = include_geometry
        return {"ok": True}

    monkeypatch.setattr(handlers_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(introspection_mod, "inspect_node_detail", fake_detail)
    monkeypatch.setattr(main_thread_mod, "run_on_main", lambda fn: fn())

    handler = handlers_mod.SynapseHandler()
    handler._handle_inspect_node(payload)
    return captured["include_geometry"]


def test_inspect_node_omits_geometry_by_default(monkeypatch):
    assert _capture_include_geometry(monkeypatch, {"node": "/obj/geo1"}) is False


def test_inspect_node_honors_explicit_geometry(monkeypatch):
    assert _capture_include_geometry(
        monkeypatch, {"node": "/obj/geo1", "include_geometry": True}
    ) is True
