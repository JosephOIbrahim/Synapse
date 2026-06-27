"""
Thread-safety regression tests for the live metrics scene collector.

FINDING 1 (v5.17.0): MetricsAggregator._collect_scene ran hou.* directly on the
background daemon thread. hou is not thread-safe off Houdini's main thread and an
off-main call can segfault Houdini (a segfault is NOT caught by `except Exception`).
The fix marshals the hou-touching block onto the main thread via run_on_main with a
short timeout, so:
  - hou is touched ONLY inside the marshalled callable, never on the daemon thread;
  - a run_on_main timeout yields an empty SceneMetrics() instead of hanging.

No Houdini required — hou is stubbed before import.
"""

import os
import sys
import threading
import types
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: add python/ to path and stub 'hou' before importing live_metrics
# ---------------------------------------------------------------------------

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)

_original_hou = sys.modules.get("hou")

if "hou" not in sys.modules:
    # Minimal placeholder so the module imports; per-test stubs replace it.
    sys.modules["hou"] = types.ModuleType("hou")

from synapse.server.live_metrics import MetricsAggregator, SceneMetrics  # noqa: E402


def _make_recording_hou(touched):
    """Build a fake hou whose every access records the thread ident that touched it."""
    hou = types.ModuleType("hou")

    def record(name):
        touched.setdefault(name, []).append(threading.get_ident())

    class _HipFile:
        def path(self):
            record("hipFile.path")
            return "/tmp/scene.hip"

    hou.hipFile = _HipFile()
    hou.frame = lambda: (record("frame"), 1)[1]
    hou.fps = lambda: (record("fps"), 24.0)[1]

    node = MagicMock()
    node.type.return_value.category.return_value.name.return_value = "Sop"
    node.warnings.return_value = []
    node.errors.return_value = []

    root = MagicMock()
    root.allSubChildren.return_value = [node]
    hou.node = lambda _p: (record("node"), root)[1]
    return hou


def _install_hou(stub):
    saved = sys.modules.get("hou")
    sys.modules["hou"] = stub

    def restore():
        if saved is not None:
            sys.modules["hou"] = saved
        else:
            sys.modules.pop("hou", None)

    return restore


def test_collect_scene_marshals_hou_through_run_on_main():
    """hou is touched ONLY inside the run_on_main callable, never on the caller thread."""
    touched: dict = {}
    calling_thread = threading.get_ident()
    marshalled_thread: dict = {}

    seen_timeout: dict = {}

    def fake_run_on_main(fn, timeout=10.0):
        # Simulate the real marshaller: fn runs on a DIFFERENT ("main") thread,
        # never the daemon/caller thread. Bounded timeout is respected by join.
        seen_timeout["v"] = timeout
        result: dict = {}

        def runner():
            marshalled_thread["id"] = threading.get_ident()
            result["v"] = fn()

        t = threading.Thread(target=runner)
        t.start()
        t.join(timeout=timeout)
        return result["v"]

    restore = _install_hou(_make_recording_hou(touched))
    try:
        with patch("synapse.server.main_thread.run_on_main", fake_run_on_main):
            agg = MetricsAggregator()
            scene = agg._collect_scene()
    finally:
        restore()

    assert isinstance(scene, SceneMetrics)
    assert scene.hip_file == "/tmp/scene.hip"
    assert scene.total_nodes == 1

    # hou was actually touched, and the marshalled callable ran on a foreign thread.
    assert touched, "expected hou to be accessed at all"
    assert "id" in marshalled_thread
    assert marshalled_thread["id"] != calling_thread

    # _collect_scene must pass the documented 1-second marshal budget.
    assert seen_timeout.get("v") == 1.0, (
        f"expected the documented 1s marshal timeout, got {seen_timeout.get('v')}"
    )

    # EVERY hou access (not just the first per name) happened on the marshalled
    # (main) thread — none leaked onto the calling/daemon thread. Rule #3.
    for name, idents in touched.items():
        for ident in idents:
            assert ident == marshalled_thread["id"], (
                f"hou access {name!r} ran on the daemon thread ({ident}) "
                f"instead of the marshalled main thread ({marshalled_thread['id']})"
            )


def test_collect_scene_timeout_yields_empty_metrics():
    """A run_on_main timeout returns an empty SceneMetrics() rather than hanging."""

    def fake_run_on_main_timeout(fn, timeout=10.0):
        # Mirror the real run_on_main contract on a busy main thread: raise
        # RuntimeError. fn() is NEVER called (no off-main hou access).
        raise RuntimeError("Houdini's main thread didn't respond in time")

    restore = _install_hou(_make_recording_hou({}))
    try:
        with patch("synapse.server.main_thread.run_on_main", fake_run_on_main_timeout):
            agg = MetricsAggregator()
            scene = agg._collect_scene()
    finally:
        restore()

    assert scene == SceneMetrics()


def test_collect_scene_no_hou_returns_empty():
    """Standalone (no hou) still short-circuits via the ImportError guard."""
    saved = sys.modules.get("hou")
    sys.modules["hou"] = None  # type: ignore[assignment]
    try:
        agg = MetricsAggregator()
        scene = agg._collect_scene()
        assert scene == SceneMetrics()
    finally:
        if saved is not None:
            sys.modules["hou"] = saved
        else:
            sys.modules.pop("hou", None)


def test_collect_scene_callable_failure_yields_empty():
    """An exception inside the marshalled walk degrades to empty SceneMetrics()."""

    def fake_run_on_main_raises_fn(fn, timeout=10.0):
        # Run fn so its internal failure propagates exactly as the real path would.
        return fn()

    broken = types.ModuleType("hou")
    broken.hipFile = MagicMock()
    broken.hipFile.path = MagicMock(return_value="/x.hip")
    broken.frame = MagicMock(return_value=1)
    broken.fps = MagicMock(return_value=24.0)
    broken.node = MagicMock(side_effect=RuntimeError("boom"))

    restore = _install_hou(broken)
    try:
        with patch("synapse.server.main_thread.run_on_main", fake_run_on_main_raises_fn):
            agg = MetricsAggregator()
            scene = agg._collect_scene()
    finally:
        restore()

    assert scene == SceneMetrics()


def teardown_module():
    if _original_hou is not None:
        sys.modules["hou"] = _original_hou
    elif "hou" in sys.modules:
        del sys.modules["hou"]
