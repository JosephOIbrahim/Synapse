"""Pins the P2 phantom guardrail's core AST logic (harness/verify/checks.py::
_hou_phantoms_in_source). The harness verify layer isn't a package, so load it by path.
Authority in production is scout's dir() symbol table; here we pass a tiny fake surface so
the matrix is hermetic (no hou, no scout, no git)."""
import importlib.util
import pathlib

_CHECKS = pathlib.Path(__file__).resolve().parents[1] / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

# A stand-in 'live surface': these hou.* exist; anything else (hou.lopNetworks, hou.pdg,
# hou.secure, hou.updateGraphTick) is absent ⇒ phantom.
TABLE = {"hou", "hou.node", "hou.LopNode", "hou.hipFile", "hou.pwd"}


def _syms(src):
    return [s for _, s in checks._hou_phantoms_in_source(src, TABLE)]


def test_flags_real_phantom_attribute():
    assert "hou.lopNetworks" in _syms("import hou\nx = hou.lopNetworks()\n")


def test_reports_line_number():
    hits = checks._hou_phantoms_in_source("import hou\n\nhou.secure.foo()\n", TABLE)
    assert (3, "hou.secure") in hits


def test_ignores_phantom_in_string_and_docstring():
    assert _syms('"""never call hou.lopNetworks()"""\nx = "hou.pdg"\n') == []


def test_ignores_phantom_in_comment():
    assert _syms("import hou\nn = hou.node('a')  # do not use hou.secure\n") == []


def test_resolves_import_alias():
    assert "hou.updateGraphTick" in _syms("import hou as h\nh.updateGraphTick()\n")


def test_real_symbol_not_flagged():
    assert _syms("import hou\nn = hou.node('/obj')\nc = hou.pwd()\n") == []


def test_depth2_member_not_flagged():
    # hou.LopNode is present (covered); .fakeMethod is depth-2, not table-complete → unknown != phantom.
    assert _syms("import hou\nhou.LopNode.fakeMethod()\n") == []


def test_attribute_named_hou_on_other_object_not_flagged():
    # self.hou.lopNetworks(): value of the outer Attribute is an Attribute, not Name('hou').
    assert _syms("self.hou.lopNetworks()\n") == []


def test_clean_file_is_empty():
    assert _syms("import hou\nfor i in range(3):\n    print(hou.node(str(i)))\n") == []


def test_gui_submodules_allowlisted():
    # hou.ui/qt/audio/desktop/viewportVisualizers are real but absent from a HEADLESS dir() table;
    # check_phantom_clean unions them in. Simulate that union and confirm they're not flagged.
    gui = checks._GUI_HOU_ABSENT_HEADLESS
    assert {"hou.ui", "hou.qt"} <= gui
    tbl = TABLE | gui
    assert checks._hou_phantoms_in_source("import hou\nhou.ui.displayMessage('x')\nx = hou.qt.mainWindow()\n", tbl) == []
    # a genuine phantom still trips even with the allowlist in place
    assert ("hou.lopNetworks" in [s for _, s in checks._hou_phantoms_in_source("hou.lopNetworks()\n", tbl)])


def test_check_phantom_clean_clean_path_returns_ok(monkeypatch, tmp_path):
    # Regression for the checks.py:451 NameError (`len(touched)` where the bound var
    # is `added`). check_phantom_clean runs as a guardrail on EVERY sprint; on the
    # clean path (added .py, zero phantom offenders) the summary line referenced an
    # unbound name and crashed the whole checks.py JSON emit — the happy path the
    # helper-level tests above never exercised, which is why the bug shipped. Stub the
    # three externals and prove the guardrail now returns ok:True instead of raising.
    import synapse.cognitive.tools.scout as scout
    monkeypatch.setattr(
        scout, "_load_symbol_table",
        lambda: ({"hou", "hou.node"}, {"houdini_version": "21.0.671"}),
    )
    monkeypatch.setattr(checks, "sh", lambda *a, **k: (0, "deadbeef\n", ""))
    # a real-looking added .py that isn't on disk → the AST loop skips it, so offenders
    # stays empty and execution reaches the (previously broken) clean-summary line.
    monkeypatch.setattr(
        checks, "_sprint_added_py",
        lambda wt, base: {"python/synapse/_nope.py": None},
    )
    result = checks.check_phantom_clean({"wt": str(tmp_path)})
    assert result["ok"] is True
    assert "clean" in result["detail"]
