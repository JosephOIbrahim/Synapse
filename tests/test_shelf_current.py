"""
W5-SHELF acceptance tests for the Synapse shelf.

Targets:
  * houdini/toolbar/synapse.shelf            (six action tools: icon + tooltip)
  * houdini/scripts/python/synapse_shelf.py  (PySide6-first clipboard + installer msg)
  * houdini/config/Icons/SYNAPSE_*.png       (committed icon assets)

Pure stdlib so it runs on BOTH suite legs -- the stock-python gate leg and the
hython shipping leg. It never imports a real `hou` (a stub is injected only
while the module loads) and never imports Qt for real (fakes are injected per
call). This is the behavioral proof the machine gate `check_shelf_current`
defers to it (see checks.py check_shelf_current FIX_IS_REAL_PROBE): the gate
proves PRESENCE of the PySide6 path + installer literal; this proves the ORDER
(PySide6 first, PySide2 fallback kept) actually executes.
"""
import contextlib
import importlib.util
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SHELF_XML = REPO / "houdini" / "toolbar" / "synapse.shelf"
SHELF_PY = REPO / "houdini" / "scripts" / "python" / "synapse_shelf.py"
ICONS_DIR = REPO / "houdini" / "config" / "Icons"

# The six ACTION tools this leg owns. The panel-open tool ("synapse_panel") is a
# 7th shelf entry and is deliberately out of W5-SHELF scope.
SIX_TOOLS = (
    "synapse_project_setup",
    "synapse_inspect_selection",
    "synapse_inspect_scene",
    "synapse_last_result",
    "synapse_health_check",
    "synapse_generate_docs",
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _tools():
    """{name: <tool Element>} for every <tool> in the shelf document."""
    root = ET.parse(SHELF_XML).getroot()
    return {t.get("name"): t for t in root.findall("tool")}


# ---- acceptance 3: each of the six tools carries a one-sentence tooltip ------

@pytest.mark.parametrize("name", SIX_TOOLS)
def test_tool_has_one_sentence_tooltip(name):
    tool = _tools().get(name)
    assert tool is not None, f"{name}: tool missing from shelf"
    help_el = tool.find("helpText")
    assert help_el is not None, f"{name}: no <helpText> element"
    text = (help_el.text or "").strip()
    assert len(text) >= 15, f"{name}: tooltip too short to be a sentence: {text!r}"
    assert text.endswith("."), f"{name}: tooltip is not a sentence: {text!r}"


# ---- acceptance 2 (functional side): each tool's icon resolves to a real PNG -

@pytest.mark.parametrize("name", SIX_TOOLS)
def test_tool_icon_file_exists(name):
    tool = _tools()[name]
    icon = tool.get("icon")
    assert icon, f"{name}: no icon attribute"
    png = ICONS_DIR / f"{icon}.png"
    assert png.is_file(), f"{name}: icon file missing: {png}"
    assert png.read_bytes()[:8] == PNG_MAGIC, f"{name}: {png.name} is not a PNG"
    assert png.stat().st_size > 200, f"{name}: {png.name} suspiciously small"


def test_six_tools_have_distinct_icons():
    tools = _tools()
    icons = [tools[n].get("icon") for n in SIX_TOOLS]
    assert len(set(icons)) == len(icons), f"icons not distinct: {icons}"


# ---- acceptance 1 (behavioral proof): PySide6-first, PySide2 fallback kept ---

def _fake_qt(tag):
    """A fake PySide-like module whose clipboard records setText() into `calls`."""
    calls = []
    mod = types.ModuleType("PySideFake")

    class _Clip:
        def setText(self, t):
            calls.append((tag, t))

    class _App:
        @staticmethod
        def instance():
            return _App()

        def clipboard(self):
            return _Clip()

    mod.QtWidgets = types.SimpleNamespace(QApplication=_App)
    return mod, calls


@contextlib.contextmanager
def _modules(**mods):
    """Temporarily set sys.modules entries; value None forces ImportError."""
    sentinel = object()
    saved = {k: sys.modules.get(k, sentinel) for k in mods}
    try:
        for k, v in mods.items():
            sys.modules[k] = v
        yield
    finally:
        for k, old in saved.items():
            if old is sentinel:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = old


def _load_shelf():
    """Import synapse_shelf with a stub `hou`, then put the prior resident back
    BY OBJECT. `hou` is never evicted from sys.modules -- eviction (pop/del) is
    banned suite-wide by tests/test_hou_reimport_guard.py, because a later
    `import hou` would re-execute hou.py and half-build the SWIG type map. The
    prior object (the suite's canonical fake, or None) is restored verbatim."""
    prior = sys.modules.get("hou")
    stub = types.ModuleType("hou")
    stub.severityType = types.SimpleNamespace(Message=0, Warning=1, Error=2)
    sys.modules["hou"] = stub
    try:
        spec = importlib.util.spec_from_file_location("synapse_shelf_undertest", SHELF_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.modules["hou"] = prior
    return mod


def test_clipboard_prefers_pyside6():
    shelf = _load_shelf()
    fake6, calls6 = _fake_qt("six")
    fake2, calls2 = _fake_qt("two")
    with _modules(PySide6=fake6, PySide2=fake2):
        assert shelf._copy_to_clipboard("PAYLOAD") is True
    assert calls6 == [("six", "PAYLOAD")], "PySide6 must be used first"
    assert calls2 == [], "PySide2 must not be touched when PySide6 is present"


def test_clipboard_falls_back_to_pyside2():
    shelf = _load_shelf()
    fake2, calls2 = _fake_qt("two")
    # PySide6 absent (None -> ImportError); PySide2 present -> fallback fires.
    with _modules(PySide6=None, PySide2=fake2):
        assert shelf._copy_to_clipboard("PAYLOAD") is True
    assert calls2 == [("two", "PAYLOAD")], "PySide2 fallback is kept by spec"


def test_clipboard_false_when_no_qt():
    shelf = _load_shelf()
    with _modules(PySide6=None, PySide2=None):
        assert shelf._copy_to_clipboard("PAYLOAD") is False


# ---- acceptance 1 (source): installer message + surviving PySide2 literal ----

def test_installer_message_names_current_installer():
    src = SHELF_PY.read_text(encoding="utf-8")
    assert "scripts/install_synapse_package.py" in src, "must point at the documented installer"
    assert "python install.py" not in src, "legacy installer reference must be gone"


def test_pyside2_fallback_literal_survives():
    # Crucible criterion: PySide2 legitimately survives the fix -- the gate greens
    # on PySide6 PRESENCE, never on PySide2 absence. Guard against over-eager cleanup.
    src = SHELF_PY.read_text(encoding="utf-8")
    assert "from PySide6" in src, "PySide6 path must be present"
    assert "from PySide2" in src, "PySide2 fallback must be KEPT"
