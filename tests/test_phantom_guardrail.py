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
