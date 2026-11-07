"""NR-SPARSE-RENDER contract: an explicit frame list renders exactly those frames.

The legacy surface only understood start_frame/end_frame/step, which cannot
express a sparse frame set (e.g. [1, 3] without 2). These tests pin the four
seams that make an explicit list authoritative end to end:

  * the MCP schema advertises ``frames`` and the payload builder keeps it;
  * the handler forwards ``frames`` to the farm without inventing a range;
  * the farm renders exactly the named frames (deduped + sorted, ints);
  * the contiguous fallback is untouched when ``frames`` is absent;
  * an empty list is refused instead of silently becoming a range.

Mock-based -- no Houdini required.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: ensure synapse package structure is importable
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parent.parent / "python"

# R307: plants each namespace package AND binds it on its parent, so
# sys.modules['synapse.x'] and the attribute synapse.x stay the same object.
import pkgbootstrap  # noqa: E402  (tests/ is on sys.path under pytest)

for mod_name, mod_path in [
    ("synapse", _root / "synapse"),
    ("synapse.core", _root / "synapse" / "core"),
    ("synapse.server", _root / "synapse" / "server"),
    ("synapse.memory", _root / "synapse" / "memory"),
    ("synapse.mcp", _root / "synapse" / "mcp"),
]:
    pkgbootstrap.ensure_package(mod_name, mod_path)

for mod_name, fpath in [
    ("synapse.core.determinism", _root / "synapse" / "core" / "determinism.py"),
    ("synapse.core.aliases", _root / "synapse" / "core" / "aliases.py"),
    ("synapse.memory.models", _root / "synapse" / "memory" / "models.py"),
    ("synapse.server.render_diagnostics", _root / "synapse" / "server" / "render_diagnostics.py"),
    ("synapse.server.render_notify", _root / "synapse" / "server" / "render_notify.py"),
    ("synapse.server.render_farm", _root / "synapse" / "server" / "render_farm.py"),
    ("synapse.server.handlers_usd", _root / "synapse" / "server" / "handlers_usd.py"),
    ("synapse.server.handlers_render", _root / "synapse" / "server" / "handlers_render.py"),
    ("synapse.mcp._tool_registry", _root / "synapse" / "mcp" / "_tool_registry.py"),
]:
    pkgbootstrap.load_module(mod_name, fpath)

render_handlers_mod = sys.modules["synapse.server.handlers_render"]
farm_mod = sys.modules["synapse.server.render_farm"]
registry_mod = sys.modules["synapse.mcp._tool_registry"]
notify_mod = sys.modules["synapse.server.render_notify"]

RenderHandlerMixin = render_handlers_mod.RenderHandlerMixin
RenderFarmOrchestrator = farm_mod.RenderFarmOrchestrator
RenderCallbacks = farm_mod.RenderCallbacks
BatchReport = notify_mod.BatchReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_callbacks(
    render_resp=None,
    validate_resp=None,
    settings_resp=None,
    stage_resp=None,
):
    """Create RenderCallbacks with mock handlers (mirrors test_render_farm.py)."""
    if render_resp is None:
        render_resp = {"image_path": "/tmp/frame.exr", "rop": "/stage/karma1"}
    if isinstance(render_resp, dict) and "output_file" not in render_resp:
        render_resp = {**render_resp, "output_file": render_resp.get("image_path", "")}
    if validate_resp is None:
        validate_resp = {"valid": True, "checks": {}}
    if settings_resp is None:
        settings_resp = {"settings": {"pathtracedsamples": 64}}

    return RenderCallbacks(
        render_frame=MagicMock(return_value=render_resp),
        validate_frame=MagicMock(return_value=validate_resp),
        get_render_settings=MagicMock(return_value=settings_resp),
        set_render_settings=MagicMock(return_value=settings_resp),
        get_stage_info=MagicMock(return_value=stage_resp or {"prims": []}),
        broadcast=MagicMock(),
    )


def _make_handler():
    """Create a RenderHandlerMixin instance with mocked dependencies."""
    handler = RenderHandlerMixin()
    handler._handle_render = MagicMock(return_value={
        "image_path": "/tmp/frame.0001.exr", "rop": "/stage/karma1",
    })
    handler._handle_validate_frame = MagicMock(return_value={
        "valid": True, "checks": {},
    })
    handler._handle_render_settings = MagicMock(return_value={
        "settings": {"pathtracedsamples": 64},
    })
    handler._handle_get_stage_info = MagicMock(return_value={"prims": []})
    handler._broadcast = MagicMock()
    handler._memory = None
    return handler


def _rendered_frames(callbacks):
    """Frames the render callback was actually asked to render, in order."""
    return [c.args[0]["frame"] for c in callbacks.render_frame.call_args_list]


def _rendered_frames_of(handler):
    """Frames the handler's render callback was actually asked to render."""
    return [c.args[0]["frame"] for c in handler._handle_render.call_args_list]


# ---------------------------------------------------------------------------
# Seam 1 -- MCP schema exposes frames and does not filter it out
# ---------------------------------------------------------------------------

class TestRegistrySchema:
    def _entry(self):
        return next(
            entry for entry in registry_mod.TOOL_DEFS
            if entry[0] == "synapse_render_sequence"
        )

    def test_schema_exposes_frames(self):
        entry = self._entry()
        schema = entry[4]
        props = schema["properties"]
        assert "frames" in props, (
            "synapse_render_sequence schema must expose 'frames' so a caller "
            "can name an explicit frame list"
        )
        assert props["frames"]["type"] == "array"
        assert props["frames"]["items"] == {"type": "integer"}

    def test_schema_declares_frames_or_range_alternative(self):
        """Assert the alternative directly -- never infer it.

        A helper that returns True when ``anyOf`` is absent would stay green
        if the constraint were deleted, so the constraint itself is asserted:
        one branch must require ``frames`` and that branch must not also
        require start_frame/end_frame.
        """
        schema = self._entry()[4]
        assert "anyOf" in schema, (
            "synapse_render_sequence must declare that either an explicit "
            "frames list or the start/end pair is enough"
        )
        frames_branches = [
            branch for branch in schema["anyOf"]
            if "frames" in branch.get("required", [])
        ]
        assert frames_branches, (
            "at least one anyOf branch must require 'frames'"
        )
        assert any(
            set(branch.get("required", [])) <= {"frames"}
            for branch in frames_branches
        ), (
            "the frames branch must not also require start_frame/end_frame -- "
            "a named list is authoritative on its own"
        )

    def test_payload_builder_keeps_frames(self):
        entry = self._entry()
        builder = entry[2]
        payload = builder({"frames": [1, 3]})
        assert "frames" in payload, (
            "the render_sequence payload builder must carry 'frames' into the "
            "handler payload"
        )
        assert payload["frames"] == [1, 3]
        assert "start_frame" not in payload and "end_frame" not in payload, (
            "the builder must not invent a contiguous range for a sparse "
            "request"
        )


# ---------------------------------------------------------------------------
# Seam 2 -- handler forwards frames to the farm
# ---------------------------------------------------------------------------

class TestHandlerForwardsFrames:
    def test_frames_are_forwarded_without_a_range(self):
        handler = _make_handler()
        mock_report = BatchReport(start_frame=1, end_frame=3, total_frames=2)

        with patch.object(
            RenderFarmOrchestrator, "render_sequence", return_value=mock_report
        ) as mock_seq:
            handler._handle_render_sequence({"frames": [1, 3], "rop": "/stage/karma1"})

        mock_seq.assert_called_once()
        kwargs = mock_seq.call_args[1]
        assert kwargs["frames"] == [1, 3]

    def test_contiguous_call_is_unchanged(self):
        handler = _make_handler()
        mock_report = BatchReport(start_frame=1, end_frame=3, total_frames=3)

        with patch.object(
            RenderFarmOrchestrator, "render_sequence", return_value=mock_report
        ) as mock_seq:
            handler._handle_render_sequence({
                "start_frame": 1, "end_frame": 3, "rop": "/stage/karma1",
            })

        kwargs = mock_seq.call_args[1]
        assert kwargs["frame_range"] == (1, 3)
        assert kwargs["step"] == 1
        assert "frames" not in kwargs, (
            "the contiguous path must not gain a frames kwarg for a request "
            "that never named one"
        )


# ---------------------------------------------------------------------------
# Seam 2b -- handler and farm composed for real
# ---------------------------------------------------------------------------

class TestHandlerFarmComposition:
    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_handler_drives_a_real_farm_over_the_named_frames(self, mock_notify):
        """Neither the handler nor the farm is mocked -- only the render call.

        The forwarding test above patches RenderFarmOrchestrator.render_sequence,
        so it can only prove a kwarg was passed. This test builds the real
        orchestrator from the handler's own callbacks, so the whole composition
        is exercised: callback wiring, normalization, render order, and report
        accounting.
        """
        mock_notify.return_value = {}
        handler = _make_handler()

        def _render(payload):
            path = "/tmp/frame.%04d.exr" % payload["frame"]
            return {"image_path": path, "output_file": path, "rop": payload["node"]}

        handler._handle_render = MagicMock(side_effect=_render)

        # Keep the handler's memory injection from reaching a real store.
        with patch.dict(sys.modules, {"synapse.memory.store": None}):
            report = handler._handle_render_sequence({
                "frames": [7, 3, 3], "rop": "/stage/karma1",
            })

        assert _rendered_frames_of(handler) == [3, 7], (
            "the composed path must render exactly the named frames, deduped "
            "and sorted"
        )
        assert report["total_frames"] == 2
        assert report["successful_frames"] == 2
        assert sorted(fr["frame"] for fr in report["frame_results"]) == [3, 7]
        assert mock_notify.call_count == 1


# ---------------------------------------------------------------------------
# Seam 3 -- the farm renders exactly the named frames
# ---------------------------------------------------------------------------

class TestFarmRendersExactFrames:
    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_renders_only_named_frames(self, mock_notify, tmp_path):
        mock_notify.return_value = {}
        callbacks = _make_callbacks()
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))

        # Deliberately unsorted + duplicated: dedupe and sort are contract.
        report = farm.render_sequence(
            "/stage/karma1", (1, 3), frames=[3, 1, 3],
        )

        assert _rendered_frames(callbacks) == [1, 3]
        assert 2 not in _rendered_frames(callbacks), "frame 2 was never named"
        assert report.total_frames == 2
        assert sorted(r.frame for r in report.frame_results) == [1, 3]
        assert (report.start_frame, report.end_frame) == (1, 3)

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_explicit_list_beats_frame_range(self, mock_notify, tmp_path):
        mock_notify.return_value = {}
        callbacks = _make_callbacks()
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))

        report = farm.render_sequence(
            "/stage/karma1", (1, 10), step=2, frames=[7, 5],
        )

        assert _rendered_frames(callbacks) == [5, 7], (
            "the farm must not blend an explicit list with the range"
        )
        assert report.total_frames == 2

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_contiguous_fallback_is_unchanged(self, mock_notify, tmp_path):
        mock_notify.return_value = {}
        callbacks = _make_callbacks()
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))

        report = farm.render_sequence("/stage/karma1", (1, 5), step=2)

        assert _rendered_frames(callbacks) == [1, 3, 5]
        assert report.total_frames == 3
        assert (report.start_frame, report.end_frame) == (1, 5)


# ---------------------------------------------------------------------------
# Seam 4 -- an empty explicit list is refused
# ---------------------------------------------------------------------------

class TestEmptyFramesRefused:
    def test_empty_list_raises_and_renders_nothing(self, tmp_path):
        callbacks = _make_callbacks()
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))

        with pytest.raises(ValueError, match="empty"):
            farm.render_sequence("/stage/karma1", (1, 3), frames=[])

        callbacks.render_frame.assert_not_called()
        assert farm.get_status()["running"] is False, (
            "a refused request must not leave the farm marked as running"
        )


# ---------------------------------------------------------------------------
# Seam 5 -- every non-integer entry is the documented ValueError
# ---------------------------------------------------------------------------

class TestNonIntegerFramesRefused:
    @pytest.mark.parametrize("bad", [
        float("inf"),        # int(inf) raises OverflowError, not ValueError
        float("-inf"),
        float("nan"),        # int(nan) raises ValueError already
        True,                # int(True) == 1 -- silently becomes a real frame
        False,
    ])
    def test_non_integer_entry_raises_value_error(self, bad):
        with pytest.raises(ValueError):
            farm_mod._normalize_explicit_frames([bad])

    def test_bad_entry_leaves_the_farm_idle(self, tmp_path):
        """The refusal must land before the farm marks itself running."""
        callbacks = _make_callbacks()
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))

        with pytest.raises(ValueError):
            farm.render_sequence(
                "/stage/karma1", (1, 3), frames=[float("inf")],
            )

        callbacks.render_frame.assert_not_called()
        assert farm.get_status()["running"] is False
