"""
Synapse Viewport Capture — Live Integration Test

Must be run INSIDE a graphical Houdini session (not hython — needs a viewport).
Creates a temporary scene, captures the viewport via flipbook, verifies the
output, and cleans up.

Usage:
    # From Houdini Python Shell:
    import runpy; runpy.run_path("tests/test_live_capture.py")

    # Or paste into the Python Shell directly:
    exec(open("tests/test_live_capture.py").read())

Expected output:
    [1/5] PASS: Handler import
    [2/5] PASS: Scene setup (box at /obj/_synapse_test_cap/box1)
    [3/5] PASS: Viewport capture — 800x600 jpeg, 45KB, 312ms
    [4/5] PASS: PNG capture — 800x600 png, 128KB, 287ms
    [5/5] PASS: Cleanup
    ========================================
    All 5 tests passed.
"""

import os
import sys
import time

# ---------------------------------------------------------------------------
# Preflight — skip gracefully when run by pytest outside Houdini
# ---------------------------------------------------------------------------

try:
    import hou
    _HAS_HOU = True
except ImportError:
    _HAS_HOU = False

try:
    import hdefereval
    _HAS_DEFER = True
except ImportError:
    _HAS_DEFER = False

# When run via pytest, skip silently instead of sys.exit
try:
    import pytest
    pytest.importorskip("hou", reason="Requires graphical Houdini session")
except ImportError:
    # Running directly (not pytest) — hard fail is fine
    if not _HAS_HOU:
        print("FAIL: This test must run inside Houdini (hou module not available)")
        sys.exit(1)
    if not _HAS_DEFER:
        print("FAIL: hdefereval not available — are you in a graphical Houdini session?")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _report(num, total, ok, msg):
    global _passed, _failed
    status = "PASS" if ok else "FAIL"
    if ok:
        _passed += 1
    else:
        _failed += 1
    print(f"[{num}/{total}] {status}: {msg}")


TOTAL = 5

# -- Test 1: Import handler ------------------------------------------------

try:
    from synapse.server.handlers import SynapseHandler
    handler = SynapseHandler()
    _report(1, TOTAL, True, "Handler import")
except Exception as e:
    _report(1, TOTAL, False, f"Handler import — {e}")
    print("Cannot continue without handler. Aborting.")
    sys.exit(1)

# -- Test 2: Create a test scene -------------------------------------------

_TEST_GEO = "/obj/_synapse_test_cap"

try:
    # Clean up any previous failed run
    existing = hou.node(_TEST_GEO)
    if existing:
        existing.destroy()

    obj = hou.node("/obj")
    geo = obj.createNode("geo", "_synapse_test_cap")
    box = geo.createNode("box", "box1")

    # Add color so the capture isn't just grey
    color = geo.createNode("color", "orange")
    color.setInput(0, box)
    color.parm("colorr").set(1.0)
    color.parm("colorg").set(0.5)
    color.parm("colorb").set(0.0)
    color.setDisplayFlag(True)
    color.setRenderFlag(True)
    geo.layoutChildren()

    # Point the viewport at our test geo
    desktop = hou.ui.curDesktop()
    sv = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
    if sv is None:
        raise RuntimeError("No SceneViewer — is a viewport visible?")
    sv.setPwd(obj)

    # Frame the object on the main thread (viewport ops need main thread)
    def _frame():
        sv.curViewport().frameAll()
    hdefereval.executeInMainThreadWithResult(_frame)

    _report(2, TOTAL, True, f"Scene setup (box at {color.path()})")
except Exception as e:
    _report(2, TOTAL, False, f"Scene setup — {e}")

# -- Test 3: JPEG capture --------------------------------------------------

try:
    t0 = time.perf_counter()
    data = handler._handle_capture_viewport({"format": "jpeg", "width": 800, "height": 600})
    elapsed_ms = (time.perf_counter() - t0) * 1000

    path = data["image_path"]
    assert os.path.exists(path), f"File not found: {path}"
    size_kb = os.path.getsize(path) / 1024
    assert size_kb > 1, f"File too small ({size_kb:.0f}KB) — capture likely failed"
    assert data["format"] == "jpeg"

    _report(3, TOTAL, True,
            f"Viewport capture — {data['width']}x{data['height']} jpeg, "
            f"{size_kb:.0f}KB, {elapsed_ms:.0f}ms")

    # Clean up temp file
    os.remove(path)
except Exception as e:
    _report(3, TOTAL, False, f"Viewport capture — {e}")

# -- Test 4: PNG capture ----------------------------------------------------

try:
    t0 = time.perf_counter()
    data = handler._handle_capture_viewport({"format": "png", "width": 800, "height": 600})
    elapsed_ms = (time.perf_counter() - t0) * 1000

    path = data["image_path"]
    assert os.path.exists(path), f"File not found: {path}"
    size_kb = os.path.getsize(path) / 1024
    assert size_kb > 1, f"File too small ({size_kb:.0f}KB) — capture likely failed"
    assert data["format"] == "png"

    _report(4, TOTAL, True,
            f"PNG capture — {data['width']}x{data['height']} png, "
            f"{size_kb:.0f}KB, {elapsed_ms:.0f}ms")

    # Clean up temp file
    os.remove(path)
except Exception as e:
    _report(4, TOTAL, False, f"PNG capture — {e}")

# -- Test 5: Cleanup -------------------------------------------------------

try:
    test_node = hou.node(_TEST_GEO)
    if test_node:
        test_node.destroy()
    assert hou.node(_TEST_GEO) is None, "Test node still exists after destroy"
    _report(5, TOTAL, True, "Cleanup")
except Exception as e:
    _report(5, TOTAL, False, f"Cleanup — {e}")

# -- Summary ----------------------------------------------------------------

print("=" * 40)
if _failed == 0:
    print(f"All {_passed} tests passed.")
else:
    print(f"{_passed} passed, {_failed} failed.")
