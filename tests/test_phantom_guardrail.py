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
        lambda: ({"hou", "hou.node", "pdg", "pxr"}, {"houdini_version": "21.0.671"}),
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


# --- CLEAR L5 G2: pdg/pxr coverage via _phantoms_in_source ----------------------------------
# Same depth discipline as hou depth-1: pdg judged at pdg.<attr>; pxr namespaces judged at
# pxr.N.<attr> (one level under each `from pxr import` name). A tiny fake surface keeps the
# matrix hermetic; the real h22 table is exercised separately below.

TABLE_EXT = TABLE | {
    "pdg", "pdg.EventType", "pdg.EventType.CookComplete", "pdg.workItemState",
    "pxr", "pxr.Usd", "pxr.Usd.Stage", "pxr.Sdf", "pxr.Sdf.Path",
}


def _psyms(src):
    return [s for _, s in checks._phantoms_in_source(src, TABLE_EXT)]


def test_hou_behavior_unchanged_through_unified_scanner():
    # The unified scanner must produce byte-identical hou verdicts.
    src = "import hou as h\nh.updateGraphTick()\nn = hou.node('/obj')\n"
    assert checks._phantoms_in_source(src, TABLE_EXT) == checks._hou_phantoms_in_source(src, TABLE_EXT)


def test_pdg_real_name_not_flagged():
    assert _psyms("import pdg\nx = pdg.EventType\n") == []


def test_pdg_alias_phantom_flagged_and_depth2_untouched():
    hits = checks._phantoms_in_source(
        "import pdg as _pdg\n_pdg.NotAName\n_pdg.EventType\n_pdg.EventType.CookComplete\n", TABLE_EXT)
    assert (2, "pdg.NotAName") in hits
    assert len(hits) == 1  # EventType clean; depth-2 member not table-judged


def test_pdg_camelname_miss_gets_actionable_hint():
    hits = checks._phantoms_in_source("import pdg\npdg.WorkItemState\n", TABLE_EXT)
    assert len(hits) == 1
    lineno, symbol = hits[0]
    assert lineno == 2
    assert "check camelCase: pdg.workItemState?" in symbol


def test_pdg_uppercase_phantom_no_real_match_no_hint():
    hits = checks._phantoms_in_source("import pdg\npdg.PDG_CONTEXT\n", TABLE_EXT)
    assert hits == [(2, "pdg.PDG_CONTEXT")]


def test_pxr_from_import_clean_and_flagged():
    src = "from pxr import Usd, Sdf\nUsd.Stage\nSdf.Path\nUsd.NotAClass\n"
    hits = checks._phantoms_in_source(src, TABLE_EXT)
    assert hits == [(4, "pxr.Usd.NotAClass")]


def test_pxr_alias_resolved_to_canonical_namespace():
    hits = checks._phantoms_in_source("from pxr import Usd as U\nU.NotAClass\nU.Stage\n", TABLE_EXT)
    assert hits == [(2, "pxr.Usd.NotAClass")]


def test_pxr_member_alias_flagged():
    # `from pxr.Usd import Stage` binds Stage locally; Stage.X would be judged pxr? — NOT
    # scanned (module != "pxr"), so no flag. Only module == "pxr" imports bind namespaces.
    assert _psyms("from pxr.Usd import Stage\nStage.NoSuch\n") == []


def test_pxr_relative_import_does_not_bind_pxrsurface():
    # Crucible F2: `from .pxr import Usd` (level=1) must NOT bind Usd to the pxr surface —
    # the package-local .pxr module is a different thing than the USD binding. level==0 gate.
    assert _psyms("from .pxr import Usd\nUsd.MadeUp\n") == []


def test_getattr_string_access_not_flagged():
    # getattr(Usd, "Prim", None): attr name is a Constant, not an Attribute — out of scope.
    assert _psyms("from pxr import Usd\nP = getattr(Usd, 'Prim', None)\nG = getattr(Usd, 'NotAName', None)\n") == []


def test_pdg_and_pxr_names_outside_imports_judged_anyway_when_bound():
    # A bare `pdg.` ref with no `import pdg` in file is still canonical ("pdg" is in the
    # default name set, mirroring hou depth-1 default {"hou"}).
    hits = checks._phantoms_in_source("pdg.NotAName\n", TABLE_EXT)
    assert hits == [(1, "pdg.NotAName")]


def test_real_h22_table_usdrender_stage_absent():
    # Exercises the REAL table (h22_symbol_table.json, 35903 syms, stamp 22.0.368):
    # UsdRender.Stage is made up — the true positive the scanner must produce.
    import json
    table_path = pathlib.Path(__file__).resolve().parents[1] / (
        "python/synapse/cognitive/tools/data/h22_symbol_table.json")
    if not table_path.is_file():
        import pytest
        pytest.skip("h22 symbol table not present on disk")
    real_syms = set(json.loads(table_path.read_text(encoding="utf-8"))["symbols"])
    hits = checks._phantoms_in_source("from pxr import UsdRender\nUsdRender.Stage\n", real_syms)
    assert hits == [(2, "pxr.UsdRender.Stage")]


def test_real_h22_table_production_pdgs_clean():
    # Real production idioms against the REAL table — zero false positives.
    import json
    table_path = pathlib.Path(__file__).resolve().parents[1] / (
        "python/synapse/cognitive/tools/data/h22_symbol_table.json")
    if not table_path.is_file():
        import pytest
        pytest.skip("h22 symbol table not present on disk")
    real_syms = set(json.loads(table_path.read_text(encoding="utf-8"))["symbols"])
    src = ("\nimport pdg as _pdg\n"
           "handler = gc.addEventHandler(fn, _pdg.EventType.CookComplete)\n"
           "state = _pdg.workItemState.Cooked\n"
           "x = _pdg.EventType.CookError\n")
    hits = checks._phantoms_in_source(src, real_syms)
    assert hits == []
