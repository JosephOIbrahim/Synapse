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

# pdg/pxr surface for the unified scan (P5.1). Mirrors the real H22 table shape: pdg.EventType
# and pxr.Usd are present (the introspect self-check asserts both); pdg.PyEventHandler is a
# known phantom (no constructor on H21.0.671 / H22.0.368).
PDG_PXR_TABLE = TABLE | {"pdg", "pdg.EventType", "pdg.GraphContext", "pdg.Scheduler",
                         "pdg.WorkItem", "pxr", "pxr.Usd", "pxr.Sdf", "pxr.Tf"}


def _syms(src):
    return [s for _, s in checks._hou_phantoms_in_source(src, TABLE)]


def _unified_syms(src, table=None):
    return [s for _, s in checks._phantoms_in_source(src, table or PDG_PXR_TABLE)]


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


# ---------- P5.1: unified hou/pdg/pxr depth-1 phantom scan ----------

def test_unified_flags_pdg_phantom_when_absent():
    # pdg.PyEventHandler has no constructor on H21/H22 — absent from a fake table ⇒ phantom.
    tbl = PDG_PXR_TABLE - {"pdg.PyEventHandler"} if "pdg.PyEventHandler" in PDG_PXR_TABLE else PDG_PXR_TABLE
    assert "pdg.PyEventHandler" in _unified_syms("import pdg\nh = pdg.PyEventHandler(fn)\n", tbl)


def test_unified_flags_pdg_eventtype_phantom_when_absent():
    tbl = PDG_PXR_TABLE - {"pdg.EventType"}
    assert "pdg.EventType" in _unified_syms("import pdg\npdg.EventType.CookComplete\n", tbl)


def test_unified_does_not_flag_real_pdg_eventtype():
    # pdg.EventType IS in the table (self-check asserts it) → not flagged, even at depth-1.
    assert _unified_syms("import pdg\nev = pdg.EventType.CookComplete\n") == []


def test_unified_does_not_flag_real_pxr_usd():
    # pxr.Usd IS in the table → not flagged.
    assert _unified_syms("import pxr\ns = pxr.Usd.Stage.CreateNew('x')\n") == []


def test_unified_resolves_pdg_alias():
    # shared/bridge.py uses `import pdg as _pdg` then `_pdg.EventType.CookComplete`.
    tbl = PDG_PXR_TABLE - {"pdg.EventType"}
    assert "pdg.EventType" in _unified_syms("import pdg as _pdg\n_pdg.EventType.CookComplete\n", tbl)
    # and the real alias form is clean when EventType is present
    assert _unified_syms("import pdg as _pdg\n_pdg.EventType.CookComplete\n") == []


def test_unified_resolves_pxr_alias():
    tbl = PDG_PXR_TABLE - {"pxr.Usd"}
    assert "pxr.Usd" in _unified_syms("import pxr as _pxr\n_pxr.Usd.Stage\n", tbl)


def test_unified_ignores_pdg_in_string_and_comment():
    assert _unified_syms('x = "pdg.PyEventHandler"\n# pdg.EventType\n') == []
    assert _unified_syms('"""never call pdg.PyEventHandler()"""\n') == []


def test_unified_ignores_pxr_in_string_and_comment():
    assert _unified_syms('x = "pxr.Usd"\n# pxr.Sdf\n') == []


def test_unified_hou_still_flagged():
    # The unified scan still catches hou phantoms — hou logic is unchanged.
    tbl = PDG_PXR_TABLE - {"hou.node"} if "hou.node" in PDG_PXR_TABLE else PDG_PXR_TABLE
    assert "hou.lopNetworks" in _unified_syms("import hou\nhou.lopNetworks()\n")


def test_unified_depth2_pdg_member_not_flagged():
    # pdg.EventType.CookComplete: pdg.EventType is depth-1 (covered), .CookComplete is depth-2
    # → unknown != phantom (same boundary as hou.LopNode.fakeMethod).
    assert _unified_syms("import pdg\npdg.EventType.CookComplte\n") == []


def test_unified_from_import_pxr_not_flagged_as_pxr_attr():
    # `from pxr import Usd` makes `Usd` the Name, not `pxr` — `Usd.Attribute` is depth-1 on Usd,
    # not on pxr, so the pxr branch never fires. This is the production pattern (grep-verified).
    assert _unified_syms("from pxr import Usd\ns = Usd.Stage.CreateNew('x')\n") == []


def test_module_depth1_phantoms_helper_is_sound_for_pdg():
    # The generalized helper mirrors _hou_phantoms_in_source exactly for pdg.
    tbl = PDG_PXR_TABLE - {"pdg.GraphContext"}
    hits = checks._module_depth1_phantoms("import pdg\ngc = pdg.GraphContext()\n", tbl, "pdg")
    assert ("pdg.GraphContext" in [s for _, s in hits])


def test_unified_no_pdg_pxr_imports_is_clean():
    # A file with only hou usage produces no pdg/pxr hits.
    assert _unified_syms("import hou\nhou.node('/obj')\n") == []


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
