"""shot_render_ready: on an EMPTY /stage it now BUILDS a render-ready Karma-XPU
scene from scratch (was: a no-op assemble → an empty rendered frame). A populated
stage still just gets wired.

Branch-logic unit test with stubbed sub-handlers — no hou, no live stage. This is
the headless gate; the live end-to-end smoke (real XPU build + non-empty frame) is
owed separately on the bridge.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _handler(assemble_chain_result):
    from synapse.server.handlers_usd import UsdHandlerMixin
    calls = {"build": 0, "assemble": 0, "render": 0}

    class H(UsdHandlerMixin):
        def _handle_create_textured_material(self, p):
            return {"material_usd_path": "/materials/m"}

        def _handle_solaris_assemble_chain(self, p):
            calls["assemble"] += 1
            return dict(assemble_chain_result)

        def _handle_solaris_shotsetup_karma_xpu(self, p):
            calls["build"] += 1
            self.last_build_payload = p
            return {"engine": p.get("engine", "xpu"),
                    "nodes": ["/stage/a", "/stage/b"], "disk_writes": ["x.usd"]}

        def _handle_safe_render(self, p):
            calls["render"] += 1
            return {"passed": True}

    return H(), calls


def test_empty_stage_builds_from_scratch():
    h, calls = _handler({"chain": []})          # empty stage → assemble wires nothing
    res = h._handle_shot_render_ready({"skip_render": True})
    assert calls["assemble"] == 1
    assert calls["build"] == 1, "empty stage must build a render-ready scene"
    steps = [s["step"] for s in res["steps"]]
    assert "solaris_build_from_scratch" in steps
    assert "solaris_assemble_chain" not in steps


def test_populated_stage_wires_not_rebuilds():
    h, calls = _handler({"chain": ["/stage/geo", "/stage/cam"]})
    res = h._handle_shot_render_ready({"skip_render": True})
    assert calls["build"] == 0, "a populated stage must NOT rebuild from scratch"
    steps = [s["step"] for s in res["steps"]]
    assert "solaris_assemble_chain" in steps
    assert "solaris_build_from_scratch" not in steps


def test_build_payload_threads_params():
    h, _calls = _handler({"chain": []})
    h._handle_shot_render_ready({"skip_render": True, "shot": "hero",
                                 "engine": "cpu", "width": 1280, "height": 720})
    p = h.last_build_payload
    assert p["shot"] == "hero"
    assert p["engine"] == "cpu"
    assert p["resolution"] == [1280, 720]
